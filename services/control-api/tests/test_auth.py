from control_api.auth import KeycloakTokenVerifier
from control_api.config import Settings


def _build_settings(**overrides: str) -> Settings:
    defaults = {
        "keycloak_issuer_url": "http://localhost:8080/realms/qaongdur-dev",
        "keycloak_discovery_url": "http://keycloak:8080/realms/qaongdur-dev",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def test_normalize_metadata_url_uses_discovery_host_for_issuer_relative_endpoints() -> None:
    verifier = KeycloakTokenVerifier(_build_settings())

    normalized = verifier._normalize_metadata_url(
        "http://localhost:8080/realms/qaongdur-dev/protocol/openid-connect/certs"
    )

    assert (
        normalized
        == "http://keycloak:8080/realms/qaongdur-dev/protocol/openid-connect/certs"
    )


def test_normalize_metadata_url_leaves_external_endpoints_unchanged() -> None:
    verifier = KeycloakTokenVerifier(_build_settings())

    normalized = verifier._normalize_metadata_url(
        "https://login.example.com/realms/qaongdur-dev/protocol/openid-connect/certs"
    )

    assert (
        normalized
        == "https://login.example.com/realms/qaongdur-dev/protocol/openid-connect/certs"
    )


def test_normalize_metadata_url_is_noop_without_discovery_url() -> None:
    verifier = KeycloakTokenVerifier(
        _build_settings(keycloak_discovery_url=None)
    )

    normalized = verifier._normalize_metadata_url(
        "http://localhost:8080/realms/qaongdur-dev/protocol/openid-connect/certs"
    )

    assert (
        normalized
        == "http://localhost:8080/realms/qaongdur-dev/protocol/openid-connect/certs"
    )
