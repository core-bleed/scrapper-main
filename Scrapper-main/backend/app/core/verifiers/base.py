"""Pluggable email verification interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

VerificationStatus = Literal["valid", "catch_all", "invalid", "unknown", "pending"]


@dataclass(frozen=True)
class VerificationResult:
    email: str
    status: VerificationStatus
    provider: str
    confidence: float | None = None
    raw_response: dict | None = None
    latency_ms: int | None = None


class VerifierProtocol(Protocol):
    async def verify(self, email: str) -> VerificationResult: ...

    async def verify_batch(self, emails: list[str]) -> list[VerificationResult]: ...

    async def healthcheck(self) -> dict: ...
