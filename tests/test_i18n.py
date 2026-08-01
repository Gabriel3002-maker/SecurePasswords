import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web-app" / "backend" / "app"
sys.path.insert(0, str(ROOT))

from core.i18n import normalize_locale, get_text, get_translation_map


def test_normalize_locale_accepts_supported_values():
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("es_MX") == "es"
    assert normalize_locale("pt-BR") == "pt"


def test_normalize_locale_falls_back_for_unknown():
    assert normalize_locale("fr") == "es"
    assert normalize_locale(None) == "es"
    assert normalize_locale("") == "es"


def test_get_text_returns_translation_for_requested_locale():
    assert get_text("en", "nav.dashboard") == "Dashboard"
    assert get_text("es", "nav.dashboard") == "Panel"
    assert get_text("pt", "nav.dashboard") == "Painel"


def test_get_text_supports_placeholders():
    assert get_text("es", "dashboard.welcome", name="Ana") == "Bienvenido, Ana"
    assert get_text("en", "dashboard.passwords_weak", count=3) == "3 weak password(s)"


def test_get_text_missing_key_returns_key():
    assert get_text("es", "nonexistent.key") == "nonexistent.key"


def test_get_text_unknown_locale_falls_back_to_default():
    assert get_text("fr", "nav.passwords") == "Contraseñas"


def test_get_translation_map_all_locales_have_same_keys():
    base = set(get_translation_map("es").keys())
    for locale in ("en", "pt"):
        assert set(get_translation_map(locale).keys()) == base, f"claves incompletas en {locale}"
