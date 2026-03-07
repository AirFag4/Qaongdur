from control_api.auth import (
    KeycloakPrincipal,
    build_principal,
    extract_platform_roles,
    has_required_acr,
)


def test_extract_platform_roles_reads_realm_and_client_roles() -> None:
    claims = {
        "sub": "user-123",
        "realm_access": {"roles": ["viewer", "reviewer"]},
        "resource_access": {
            "qaongdur-web": {"roles": ["operator", "not-a-platform-role"]},
            "account": {"roles": ["manage-account"]},
        },
    }

    assert extract_platform_roles(claims) == {"viewer", "reviewer", "operator"}


def test_build_principal_prefers_name_and_username() -> None:
    principal = build_principal(
        {
            "sub": "user-123",
            "name": "Pat Admin",
            "preferred_username": "pat.admin",
            "email": "pat.admin@example.com",
            "realm_access": {"roles": ["platform-admin"]},
            "acr": "urn:qaongdur:loa:2",
        },
        raw_token="token",
    )

    assert principal.display_name == "Pat Admin"
    assert principal.username == "pat.admin"
    assert principal.roles == {"platform-admin"}


def test_has_required_acr_is_exact_match() -> None:
    principal = KeycloakPrincipal(
        subject="user-123",
        username="pat.admin",
        display_name="Pat Admin",
        email=None,
        roles={"platform-admin"},
        acr="urn:qaongdur:loa:2",
        raw_token="token",
        claims={},
    )

    assert has_required_acr(principal, "urn:qaongdur:loa:2") is True
    assert has_required_acr(principal, "urn:qaongdur:loa:3") is False
