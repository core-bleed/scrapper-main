"""Build verifier from settings."""

from __future__ import annotations

import httpx

from app.config import Settings
from app.core.verifiers.base import VerifierProtocol
from app.core.verifiers.hunter import HunterVerifier
from app.core.verifiers.millionverifier import MillionVerifierVerifier
from app.core.verifiers.own_api import OwnApiVerifier


def get_verifier(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> VerifierProtocol:
    p = (settings.verifier_provider or "own_api").strip().lower()
    if p == "hunter":
        key = settings.hunter_api_key or ""
        if not key:
            return OwnApiVerifier(base_url=None, client=client)
        return HunterVerifier(key, client=client)
    if p in ("millionverifier", "million_verifier", "mv"):
        key = settings.millionverifier_api_key or ""
        if not key:
            return OwnApiVerifier(base_url=None, client=client)
        return MillionVerifierVerifier(key, client=client)
    return OwnApiVerifier(
        base_url=settings.own_verifier_url,
        api_key=settings.own_verifier_api_key,
        client=client,
    )
