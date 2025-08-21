# tests/test_whatsapp_router_validation.py
import json
import pytest
from unittest.mock import AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import FormData
from twilio.request_validator import RequestValidator

# Importa tu router ya configurado
from app.routers.whatsapp import router as whatsapp_router

@pytest.fixture
def app():
    """Crear aplicación FastAPI de test."""
    app = FastAPI()
    app.include_router(whatsapp_router)  # Sin prefix, usar rutas originales
    return app

@pytest.fixture
def client(app):
    """Cliente de test para la aplicación."""
    return TestClient(app)

@pytest.fixture
def mock_background_task(monkeypatch):
    """Mock del background task para evitar procesamiento real."""
    mock = AsyncMock()
    # Importa el módulo y patchea la función
    import app.routers.whatsapp as whatsapp_module
    monkeypatch.setattr(whatsapp_module, "_process_and_reply", mock)
    return mock

def test_form_signature_ok(client, twilio_token_env, mock_background_task):
    """Test webhook con firma válida."""
    url = "https://testserver/whatsapp"  # TestClient usa este host por defecto
    params = {
        "From": "whatsapp:+573001234567",
        "Body": "hola",
        "MessageSid": "SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX3",
    }
    validator = RequestValidator(twilio_token_env)
    sig = validator.compute_signature(url, params)

    res = client.post(
        "/whatsapp",
        data=params,
        headers={
            "X-Twilio-Signature": sig,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testserver",  # para que effective_url reconstruya igual al url firmado
        },
    )
    assert res.status_code == 200
    assert res.json() == {"status": "accepted"}
    
    # Verificar que el background task fue llamado
    mock_background_task.assert_called_once()

def test_form_signature_bad(client, twilio_token_env, mock_background_task):
    """Test webhook con firma inválida."""
    url = "https://testserver/whatsapp"
    params = {
        "From": "whatsapp:+573001234567",
        "Body": "hola",
        "MessageSid": "SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX4",
    }
    validator = RequestValidator(twilio_token_env)
    sig = validator.compute_signature(url, params)

    # Mutamos Body después de firmar → debe fallar
    params["Body"] = "HOLA"

    res = client.post(
        "/whatsapp",
        data=params,
        headers={
            "X-Twilio-Signature": sig,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testserver",
        },
    )
    assert res.status_code == 403
    
    # El background task no debe ser llamado
    mock_background_task.assert_not_called()

def test_form_no_signature(client, twilio_token_env, mock_background_task):
    """Test webhook sin firma."""
    params = {
        "From": "whatsapp:+573001234567",
        "Body": "hola",
        "MessageSid": "SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX5",
    }

    res = client.post(
        "/whatsapp",
        data=params,
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testserver",
        },
    )
    assert res.status_code == 403
    mock_background_task.assert_not_called()

def test_json_signature_ok(client, twilio_token_env, mock_background_task):
    """Test webhook JSON con firma válida."""
    url = "https://testserver/whatsapp/json"
    raw = b'{"From":"whatsapp:+573001234567","Body":"hola"}'

    # Genera firma al estilo JSON (url + raw bytes, SHA1)
    import hmac, hashlib, base64
    data = url.encode("utf-8") + raw
    sig = base64.b64encode(hmac.new(twilio_token_env.encode("utf-8"), data, hashlib.sha1).digest()).decode("utf-8")

    res = client.post(
        "/whatsapp/json",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Twilio-Signature": sig,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testserver",
        },
    )
    assert res.status_code == 200
    assert res.json() == {"status": "accepted"}
    mock_background_task.assert_called_once()

def test_json_signature_bad(client, twilio_token_env, mock_background_task):
    """Test webhook JSON con firma inválida."""
    url = "https://testserver/whatsapp/json"
    raw = b'{"From":"whatsapp:+573001234567","Body":"hola"}'

    # Firma válida para el body original
    import hmac, hashlib, base64
    data = url.encode("utf-8") + raw
    sig = base64.b64encode(hmac.new(twilio_token_env.encode("utf-8"), data, hashlib.sha1).digest()).decode("utf-8")

    # Enviamos otro body → debe fallar
    raw_bad = b'{"From":"whatsapp:+573001234567","Body":"HOLA"}'

    res = client.post(
        "/whatsapp/json",
        content=raw_bad,
        headers={
            "Content-Type": "application/json",
            "X-Twilio-Signature": sig,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testserver",
        },
    )
    assert res.status_code == 403
    mock_background_task.assert_not_called()

def test_form_invalid_phone_number(client, twilio_token_env, mock_background_task):
    """Test webhook con número de teléfono inválido."""
    url = "https://testserver/whatsapp"
    params = {
        "From": "",  # Número vacío
        "Body": "hola",
        "MessageSid": "SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX6",
    }
    validator = RequestValidator(twilio_token_env)
    sig = validator.compute_signature(url, params)

    res = client.post(
        "/whatsapp",
        data=params,
        headers={
            "X-Twilio-Signature": sig,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "testserver",
        },
    )
    assert res.status_code == 400
    mock_background_task.assert_not_called()
