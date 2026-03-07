from control_api.config import Settings


def test_settings_accept_csv_env_for_list_fields(monkeypatch) -> None:
    monkeypatch.setenv(
        "QAONGDUR_CONTROL_API_CORS_ORIGINS",
        "http://localhost:5173, http://localhost:4173",
    )
    monkeypatch.setenv("QAONGDUR_KEYCLOAK_EXPECTED_ALGORITHMS", "RS256, ES256")

    settings = Settings(_env_file=None)

    assert settings.control_api_cors_origins == [
        "http://localhost:5173",
        "http://localhost:4173",
    ]
    assert settings.keycloak_expected_algorithms == ["RS256", "ES256"]


def test_settings_accept_json_env_for_list_fields(monkeypatch) -> None:
    monkeypatch.setenv(
        "QAONGDUR_CONTROL_API_CORS_ORIGINS",
        '["http://localhost:5173"]',
    )
    monkeypatch.setenv("QAONGDUR_KEYCLOAK_EXPECTED_ALGORITHMS", '["RS256"]')

    settings = Settings(_env_file=None)

    assert settings.control_api_cors_origins == ["http://localhost:5173"]
    assert settings.keycloak_expected_algorithms == ["RS256"]
