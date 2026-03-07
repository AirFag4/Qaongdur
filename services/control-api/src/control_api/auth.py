from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Iterable, Literal

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from .config import Settings, get_settings

PlatformRole = Literal[
    "platform-admin",
    "site-admin",
    "operator",
    "reviewer",
    "viewer",
]

SUPPORTED_PLATFORM_ROLES: set[PlatformRole] = {
    "platform-admin",
    "site-admin",
    "operator",
    "reviewer",
    "viewer",
}

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class KeycloakPrincipal:
    subject: str
    username: str
    display_name: str
    email: str | None
    roles: set[PlatformRole]
    acr: str | None
    raw_token: str
    claims: dict[str, Any]


def extract_platform_roles(claims: dict[str, Any]) -> set[PlatformRole]:
    roles: set[PlatformRole] = set()

    realm_roles = claims.get("realm_access", {}).get("roles", [])
    for role in realm_roles:
        if role in SUPPORTED_PLATFORM_ROLES:
            roles.add(role)

    resource_access = claims.get("resource_access", {})
    for client_roles in resource_access.values():
        for role in client_roles.get("roles", []):
            if role in SUPPORTED_PLATFORM_ROLES:
                roles.add(role)

    return roles


def build_principal(claims: dict[str, Any], raw_token: str) -> KeycloakPrincipal:
    display_name = claims.get("name")
    if not display_name:
        given_name = claims.get("given_name")
        family_name = claims.get("family_name")
        display_name = " ".join(
            part for part in [given_name, family_name] if isinstance(part, str) and part
        ).strip()

    username = claims.get("preferred_username") or claims.get("email") or claims["sub"]

    return KeycloakPrincipal(
        subject=claims["sub"],
        username=username,
        display_name=display_name or username,
        email=claims.get("email"),
        roles=extract_platform_roles(claims),
        acr=claims.get("acr"),
        raw_token=raw_token,
        claims=claims,
    )


def has_required_acr(principal: KeycloakPrincipal, required_acr: str) -> bool:
    return bool(required_acr) and principal.acr == required_acr


class KeycloakTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._oidc_metadata: dict[str, Any] | None = None
        self._oidc_metadata_expires_at = datetime.min.replace(tzinfo=UTC)
        self._jwks: dict[str, Any] | None = None
        self._jwks_expires_at = datetime.min.replace(tzinfo=UTC)

    async def verify_access_token(self, token: str) -> KeycloakPrincipal:
        metadata = await self._get_oidc_metadata()
        jwks = await self._get_jwks(metadata["jwks_uri"])
        signing_key = self._resolve_signing_key(token, jwks)

        try:
            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=self.settings.keycloak_expected_algorithms,
                audience=self.settings.keycloak_audience,
                issuer=self.settings.keycloak_issuer_url,
                options={"require": ["exp", "iat", "iss", "sub"]},
            )
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return build_principal(claims, token)

    async def _get_oidc_metadata(self) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        if self._oidc_metadata and now < self._oidc_metadata_expires_at:
            return self._oidc_metadata

        discovery_url = (
            f"{self.settings.keycloak_issuer_url.rstrip('/')}"
            "/.well-known/openid-configuration"
        )
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            metadata = response.json()

        self._oidc_metadata = metadata
        self._oidc_metadata_expires_at = now + timedelta(
            seconds=self.settings.oidc_cache_ttl_seconds
        )
        return metadata

    async def _get_jwks(self, jwks_uri: str) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        if self._jwks and now < self._jwks_expires_at:
            return self._jwks

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(jwks_uri)
            response.raise_for_status()
            jwks = response.json()

        self._jwks = jwks
        self._jwks_expires_at = now + timedelta(
            seconds=self.settings.oidc_cache_ttl_seconds
        )
        return jwks

    def _resolve_signing_key(self, token: str, jwks: dict[str, Any]) -> Any:
        kid = jwt.get_unverified_header(token).get("kid")
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                return RSAAlgorithm.from_jwk(json.dumps(jwk))

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to resolve Keycloak signing key for token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@lru_cache(maxsize=1)
def get_token_verifier() -> KeycloakTokenVerifier:
    return KeycloakTokenVerifier(get_settings())


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: KeycloakTokenVerifier = Depends(get_token_verifier),
) -> KeycloakPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await verifier.verify_access_token(credentials.credentials)


def require_roles(*allowed_roles: PlatformRole):
    async def dependency(
        principal: KeycloakPrincipal = Depends(get_current_principal),
    ) -> KeycloakPrincipal:
        if not principal.roles.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "This action requires one of the following roles: "
                    + ", ".join(allowed_roles)
                ),
            )
        return principal

    return dependency
