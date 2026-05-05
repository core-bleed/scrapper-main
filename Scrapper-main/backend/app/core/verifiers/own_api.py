"""Stub verifier: wire OWN_VERIFIER_URL when ready."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.verifiers.base import VerificationResult


class OwnApiVerifier:
    def __init__(
        self,
        *,
        base_url: str | None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key
        self._client = client
        self._own_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client:
            return self._client
        if self._own_client is None:
            self._own_client = httpx.AsyncClient(timeout=30.0)
        return self._own_client

    async def verify(self, email: str) -> VerificationResult:
        if not self._base_url:
            return VerificationResult(
                email=email,
                status="unknown",
                provider="own_api",
                confidence=None,
                raw_response={"reason": "OWN_VERIFIER_URL not configured"},
            )
        t0 = time.perf_counter()
        client = await self._get_client()
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            r = await client.post(
                self._base_url,
                json={"email": email},
                headers=headers,
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json() if r.content else {}
            status = str(data.get("status") or data.get("result") or "unknown").lower()
            if status in ("deliverable", "valid", "ok"):
                st = "valid"
            elif status in ("catch_all", "catch-all", "risky"):
                st = "catch_all"
            elif status in ("invalid", "undeliverable"):
                st = "invalid"
            else:
                st = "unknown"
            conf = data.get("confidence")
            ms = int((time.perf_counter() - t0) * 1000)
            return VerificationResult(
                email=email,
                status=st,  # type: ignore[arg-type]
                provider="own_api",
                confidence=float(conf) if conf is not None else None,
                raw_response=data,
                latency_ms=ms,
            )
        except Exception as e:
            ms = int((time.perf_counter() - t0) * 1000)
            return VerificationResult(
                email=email,
                status="unknown",
                provider="own_api",
                confidence=None,
                raw_response={"error": str(e)},
                latency_ms=ms,
            )

    async def verify_batch(self, emails: list[str]) -> list[VerificationResult]:
        return [await self.verify(e) for e in emails]

    async def healthcheck(self) -> dict:
        return {"provider": "own_api", "configured": bool(self._base_url)}
