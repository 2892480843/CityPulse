import pytest
from pydantic import ValidationError

from citypulse.shared.config import Settings


def test_development_defaults_are_explicit() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.cookie_secure is False
    assert settings.app_version == "0.1.0"


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"debug": True}, "debug must be disabled"),
        ({"cookie_secure": False}, "secure cookies are required"),
        (
            {"session_secret": "local-development-only-change-me"},
            "replace the development session secret",
        ),
    ],
)
def test_production_rejects_unsafe_settings(
    overrides: dict[str, object], expected_fragment: str
) -> None:
    values: dict[str, object] = {
        "environment": "production",
        "debug": False,
        "cookie_secure": True,
        "session_secret": "production-secret-with-at-least-32-characters",
    }
    values.update(overrides)

    with pytest.raises(ValidationError, match=expected_fragment):
        Settings(**values, _env_file=None)
