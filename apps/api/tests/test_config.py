from app.core.config import load_settings


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
