from app.core.config import DEFAULT_DEV_CORS_ALLOW_ORIGIN_REGEX, load_settings


def test_load_settings_prefers_publishable_key(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable-key")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")

    settings = load_settings()

    assert settings.supabase_client_key == "publishable-key"


def test_load_settings_falls_back_to_anon_key(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")

    settings = load_settings()

    assert settings.supabase_client_key == "anon-key"


def test_load_settings_parses_cors_allowed_origins(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        " http://localhost:3000/ , http://127.0.0.1:8081 , http://localhost:3000 ",
    )
    monkeypatch.delenv("CORS_ALLOW_ORIGIN_REGEX", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    settings = load_settings()

    assert settings.cors_allowed_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:8081",
    )
    assert settings.cors_allow_origin_regex is None


def test_load_settings_defaults_to_loopback_cors_regex_in_development(
    monkeypatch,
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("TENUE_ENV", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ORIGIN_REGEX", raising=False)

    settings = load_settings()

    assert settings.cors_allowed_origins == ()
    assert settings.cors_allow_origin_regex == DEFAULT_DEV_CORS_ALLOW_ORIGIN_REGEX
