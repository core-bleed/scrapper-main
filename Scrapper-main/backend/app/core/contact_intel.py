"""Find-email / find-and-verify orchestration (Week 3)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.patterns import learner
from app.core.patterns.generator import generate_candidates
from app.core.patterns.scorer import pattern_weights_from_db_rows, score_candidates
from app.core.ranking import contact_ranker as ranker
from app.core.resolvers import domain_resolver as dr
from app.core.verifiers.factory import get_verifier
from app.core.verifiers.service import apply_verification_to_candidate
from app.db import models as m
from app.db import queries as q
from app.db import repository as repo

VERIFY_TOP_N = 7


@dataclass
class ResolvePersonOutcome:
    person_id: uuid.UUID
    employment_id: uuid.UUID
    company_id: uuid.UUID
    domain: str | None
    confidence: float
    source: str
    needs_review: bool


async def resolve_person_workflow(
    session: AsyncSession,
    *,
    person_id: uuid.UUID,
    employment_id: uuid.UUID | None,
    persist: bool = True,
) -> ResolvePersonOutcome:
    person = await session.get(m.Person, person_id)
    if not person:
        raise ValueError("Person not found")
    if employment_id:
        emp = await q.get_employment_with_company(session, employment_id)
        if not emp or emp.person_id != person_id:
            raise ValueError("Employment not found for person")
    else:
        emp = await q.pick_current_employment_for_person(session, person_id)
        if not emp:
            raise ValueError("No employment for person")
    company = emp.company
    if company is None:
        raise ValueError("Company not loaded")
    resolution = await dr.resolve_for_company(session, company)
    if persist and resolution.domain:
        await dr.persist_resolution(session, company, resolution)
        await session.flush()
    return ResolvePersonOutcome(
        person_id=person_id,
        employment_id=emp.id,
        company_id=company.id,
        domain=resolution.domain,
        confidence=resolution.confidence,
        source=resolution.source,
        needs_review=resolution.needs_review,
    )


@dataclass
class CandidateRowOut:
    email: str
    pattern_code: str | None
    generation_rank: int
    pattern_confidence: float | None
    final_score: float | None
    verification_state: str | None
    candidate_id: uuid.UUID | None = None


@dataclass
class FindEmailOutcome:
    person_id: uuid.UUID
    employment_id: uuid.UUID
    company_id: uuid.UUID
    domain: str
    domain_confidence: float
    candidates: list[CandidateRowOut]


async def find_email_workflow(
    session: AsyncSession,
    *,
    person_id: uuid.UUID,
    employment_id: uuid.UUID | None,
    persist_domain: bool = True,
) -> FindEmailOutcome:
    ro = await resolve_person_workflow(
        session,
        person_id=person_id,
        employment_id=employment_id,
        persist=persist_domain,
    )
    if not ro.domain:
        raise ValueError("Could not resolve domain for company")

    person = await session.get(m.Person, person_id)
    emp = await q.get_employment_with_company(session, ro.employment_id)
    company = await q.get_company_with_relations(session, ro.company_id)
    if not person or not emp or not company:
        raise ValueError("Missing person, employment, or company")

    raw = generate_candidates(person.full_name, ro.domain)
    weights = pattern_weights_from_db_rows(
        [(p.pattern_code, float(p.confidence)) for p in company.email_patterns]
    )
    scored = score_candidates(raw, pattern_weights=weights, default_weight=0.35)

    rows: list[CandidateRowOut] = []
    for rank, (gen, pre_score) in enumerate(scored):
        cand = await repo.upsert_contact_candidate(
            session,
            person_id=person_id,
            company_id=company.id,
            email=gen.email,
            normalized_email=gen.email.strip().lower(),
            domain=gen.email.split("@", 1)[-1].lower(),
            local_part=gen.local_part,
            pattern_code=gen.pattern_code,
            generation_source="pattern_engine",
            generation_rank=rank,
            pattern_confidence=pre_score,
        )
        fs = ranker.candidate_rank_score(
            verification_state=cand.verification_state or "pending",
            verifier_confidence=None,
            pattern_confidence=pre_score,
            domain_confidence=ro.confidence,
            is_c_suite=emp.is_c_suite,
        )
        cand.final_score = Decimal(str(fs))
        rows.append(
            CandidateRowOut(
                email=gen.email,
                pattern_code=gen.pattern_code,
                generation_rank=rank,
                pattern_confidence=pre_score,
                final_score=fs,
                verification_state=cand.verification_state,
                candidate_id=cand.id,
            )
        )
    rows.sort(key=lambda x: (-(x.final_score or 0), x.generation_rank))
    await session.flush()
    return FindEmailOutcome(
        person_id=person_id,
        employment_id=ro.employment_id,
        company_id=company.id,
        domain=ro.domain,
        domain_confidence=ro.confidence,
        candidates=rows,
    )


@dataclass
class FindAndVerifyOutcome:
    person_id: uuid.UUID
    employment_id: uuid.UUID
    company_id: uuid.UUID
    domain: str
    verified: list[CandidateRowOut]
    best: CandidateRowOut | None


async def find_and_verify_workflow(
    session: AsyncSession,
    settings: Settings,
    *,
    person_id: uuid.UUID,
    employment_id: uuid.UUID | None,
    http_client: httpx.AsyncClient | None = None,
    persist_domain: bool = True,
) -> FindAndVerifyOutcome:
    fe = await find_email_workflow(
        session,
        person_id=person_id,
        employment_id=employment_id,
        persist_domain=persist_domain,
    )
    top = sorted(fe.candidates, key=lambda x: x.generation_rank)[:VERIFY_TOP_N]
    verifier = get_verifier(settings, client=http_client)

    for row in top:
        if not row.candidate_id:
            continue
        cand = await session.get(m.ContactCandidate, row.candidate_id)
        if not cand:
            continue
        res = await verifier.verify(row.email)
        await apply_verification_to_candidate(session, candidate=cand, result=res)
        if res.status == "valid" and cand.pattern_code:
            await learner.record_valid_pattern(
                session,
                company_id=fe.company_id,
                domain=fe.domain,
                pattern_code=cand.pattern_code,
            )

    emp = await q.get_employment_with_company(session, fe.employment_id)
    company = await session.get(m.Company, fe.company_id)
    dom_conf = (
        float(company.domain_confidence)
        if company and company.domain_confidence is not None
        else fe.domain_confidence
    )

    all_cands = await q.list_contact_candidates_for_pair(
        session,
        person_id=person_id,
        company_id=fe.company_id,
    )
    ids = [c.id for c in all_cands]
    vc_map = await q.latest_verifier_confidence_by_candidate(session, ids)

    for c in all_cands:
        fs = ranker.candidate_rank_score(
            verification_state=c.verification_state,
            verifier_confidence=vc_map.get(c.id),
            pattern_confidence=float(c.pattern_confidence) if c.pattern_confidence is not None else None,
            domain_confidence=dom_conf,
            is_c_suite=emp.is_c_suite if emp else False,
        )
        c.final_score = Decimal(str(fs))

    pick = ranker.pick_best(
        all_cands,
        domain_confidence=dom_conf,
        is_c_suite=emp.is_c_suite if emp else False,
        last_verifier_confidence=vc_map,
    )

    await repo.clear_best_flags_for_person_company(
        session,
        person_id=person_id,
        company_id=fe.company_id,
    )
    best_row: CandidateRowOut | None = None
    if pick:
        for c in all_cands:
            c.is_best_current = c.id == pick.candidate_id
        winner = next((c for c in all_cands if c.id == pick.candidate_id), None)
        if winner:
            best_row = CandidateRowOut(
                email=winner.email,
                pattern_code=winner.pattern_code,
                generation_rank=winner.generation_rank,
                pattern_confidence=float(winner.pattern_confidence)
                if winner.pattern_confidence is not None
                else None,
                final_score=float(winner.final_score) if winner.final_score is not None else None,
                verification_state=winner.verification_state,
                candidate_id=winner.id,
            )
            if emp:
                await repo.update_employment_best_candidate(
                    session,
                    emp,
                    best_candidate_id=winner.id,
                    best_status=winner.verification_state,
                    best_score=pick.score,
                )
    elif emp:
        await repo.update_employment_best_candidate(
            session,
            emp,
            best_candidate_id=None,
            best_status=None,
            best_score=None,
        )

    verified_out: list[CandidateRowOut] = []
    top_ids = {r.candidate_id for r in top if r.candidate_id}
    for c in all_cands:
        if c.id not in top_ids:
            continue
        verified_out.append(
            CandidateRowOut(
                email=c.email,
                pattern_code=c.pattern_code,
                generation_rank=c.generation_rank,
                pattern_confidence=float(c.pattern_confidence)
                if c.pattern_confidence is not None
                else None,
                final_score=float(c.final_score) if c.final_score is not None else None,
                verification_state=c.verification_state,
                candidate_id=c.id,
            )
        )
    verified_out.sort(key=lambda x: x.generation_rank)
    await session.flush()

    return FindAndVerifyOutcome(
        person_id=person_id,
        employment_id=fe.employment_id,
        company_id=fe.company_id,
        domain=fe.domain,
        verified=verified_out,
        best=best_row,
    )
