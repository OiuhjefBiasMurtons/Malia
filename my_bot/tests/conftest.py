# tests/conftest.py
import os
import pytest

@pytest.fixture(scope="session")
def twilio_token_env():
    """Fixture para obtener el token de Twilio del entorno."""
    return os.getenv("TWILIO_AUTH_TOKEN", "test_auth_token_123")

@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch, twilio_token_env):
    """Setup automático para cada test con variables de entorno."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", twilio_token_env)
    monkeypatch.setenv("DISABLE_WEBHOOK_VALIDATION", "False")
    monkeypatch.setenv("DEBUG", "True")
