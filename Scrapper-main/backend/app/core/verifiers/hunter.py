"""Hunter.io email verifier (async)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.verifiers.base import VerificationResult

HUNTER_VERIFY_URL = "https://api.hunter.io/v2/email-verifier"


def _map_hunter(data: dict[str, Any]) -> tuple[str, float | None]:
    """Map Hunter data block to our status + confidence."""
    score = data.get("score")
    conf = float(score) / 100.0 if score is not None else None
    result = (data.get("result") or data.get("status") or "").lower()
    if result in ("deliverable",):
        return "valid", conf
    if result in ("undeliverable",):
        return "invalid", conf
    if result in ("risky",):
        return "catch_all", conf
    return "unknown", conf


class HunterVerifier:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._own: httpx.AsyncClient | None = None

    async def _client_(self) -> httpx.AsyncClient:
        if self._client:
            return self._client
        if self._own is None:
            self._own = httpx.AsyncClient(timeout=30.0)
        return self._own

    async def verify(self, email: str) -> VerificationResult:
        t0 = time.perf_counter()
        client = await self._client_()
        try:
            r = await client.get(
                HUNTER_VERIFY_URL,
                params={"email": email, "api_key": self._api_key},
            )
            r.raise_for_status()
            body = r.json()
            data = body.get("data") or {}
            st, conf = _map_hunter(data if isinstance(data, dict) else {})
            ms = int((time.perf_counter() - t0) * 1000)
            return VerificationResult(
                email=email,
                status=st,  # type: ignore[arg-type]
                provider="hunter",
                confidence=conf,
                raw_response=body if isinstance(body, dict) else {"raw": body},
                latency_ms=ms,
            )
        except Exception as e:
            ms = int((time.perf_counter() - t0) * 1000)
            return VerificationResult(
                email=email,
                status="unknown",
                provider="hunter",
                confidence=None,
                raw_response={"error": str(e)},
                latency_ms=ms,
            )

    async def verify_batch(self, emails: list[str]) -> list[VerificationResult]:
        return [await self.verify(e) for e in emails]

    async def healthcheck(self) -> dict:
        return {"provider": "hunter", "configured": bool(self._api_key)}
