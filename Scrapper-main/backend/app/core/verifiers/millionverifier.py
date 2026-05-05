"""MillionVerifier API v3 (async)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.verifiers.base import VerificationResult

MV_URL = "https://api.millionverifier.com/api/v3/"


def _map_mv(data: dict[str, Any]) -> tuple[str, float | None]:
    """
    MillionVerifier uses resultcode (int) and/or result string.
    See provider docs; map conservatively to our statuses.
    """
    code = data.get("resultcode")
    text = str(data.get("result") or data.get("quality") or "").lower()
    conf_raw = data.get("confidence")
    conf = float(conf_raw) if conf_raw is not None else None

    if code == 1 or text in ("ok", "good", "deliverable", "valid"):
        return "valid", conf
    if code == 2 or text in ("bad", "invalid", "undeliverable"):
        return "invalid", conf
    if code == 3 or "catch" in text or text in ("risky", "catch_all", "catch-all"):
        return "catch_all", conf
    if code == 4 or text in ("unknown",):
        return "unknown", conf
    if isinstance(code, int):
        if code in (5, 6, 7):
            return "unknown", conf
    return "unknown", conf


class MillionVerifierVerifier:
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
                MV_URL,
                params={"api": self._api_key, "email": email},
            )
            r.raise_for_status()
            body = r.json()
            data = body if isinstance(body, dict) else {}
            st, conf = _map_mv(data)
            ms = int((time.perf_counter() - t0) * 1000)
            return VerificationResult(
                email=email,
                status=st,  # type: ignore[arg-type]
                provider="millionverifier",
                confidence=conf,
                raw_response=data,
                latency_ms=ms,
            )
        except Exception as e:
            ms = int((time.perf_counter() - t0) * 1000)
            return VerificationResult(
                email=email,
                status="unknown",
                provider="millionverifier",
                confidence=None,
                raw_response={"error": str(e)},
                latency_ms=ms,
            )

    async def verify_batch(self, emails: list[str]) -> list[VerificationResult]:
        return [await self.verify(e) for e in emails]

    async def healthcheck(self) -> dict:
        return {"provider": "millionverifier", "configured": bool(self._api_key)}
