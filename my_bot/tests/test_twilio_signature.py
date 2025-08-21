# tests/test_twilio_signature.py
import hmac
import hashlib
import base64
import pytest
from starlette.datastructures import FormData
from twilio.request_validator import RequestValidator

from app.services.whatsapp_service import WhatsAppService

def compute_twilio_json_signature(url: str, raw_body: bytes, auth_token: str, algo: str = "SHA1") -> str:
    """Simula la firma JSON de Twilio: base64(hmac(algo, auth_token, url + raw_body))."""
    data = url.encode("utf-8") + raw_body
    if algo.upper() == "SHA256":
        digest = hmac.new(auth_token.encode("utf-8"), data, hashlib.sha256).digest()
    else:
        digest = hmac.new(auth_token.encode("utf-8"), data, hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")

def test_validate_webhook_form_valid(twilio_token_env):
    """Test validación de webhook con FormData válida usando RequestValidator oficial."""
    url = "https://example.com/whatsapp"
    params = {
        "From": "whatsapp:+573001234567",
        "Body": "hola",
        "MessageSid": "SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX1",
    }

    # Usa el validador oficial para generar una firma correcta (igual que Twilio)
    validator = RequestValidator(twilio_token_env)
    signature = validator.compute_signature(url, params)

    # Pasa FormData crudo como hace el router
    formdata = FormData(params.items())

    assert WhatsAppService.validate_webhook(url, formdata, signature) is True

def test_validate_webhook_form_invalid(twilio_token_env):
    """Test validación de webhook con FormData inválida."""
    url = "https://example.com/whatsapp"
    params = {
        "From": "whatsapp:+573001234567",
        "Body": "hola",
        "MessageSid": "SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX2",
    }

    validator = RequestValidator(twilio_token_env)
    good_sig = validator.compute_signature(url, params)

    # Cambiamos el body → la firma ya no coincide
    params_bad = dict(params)
    params_bad["Body"] = "hola!!"

    formdata = FormData(params_bad.items())
    assert WhatsAppService.validate_webhook(url, formdata, good_sig) is False

def test_validate_webhook_form_missing_data(twilio_token_env):
    """Test validación con datos faltantes."""
    url = "https://example.com/whatsapp"
    params = {"From": "whatsapp:+573001234567"}
    
    formdata = FormData(params.items())
    
    # Sin firma
    assert WhatsAppService.validate_webhook(url, formdata, "") is False
    
    # Sin URL
    assert WhatsAppService.validate_webhook("", formdata, "some_signature") is False

def test_validate_webhook_json_valid(twilio_token_env):
    """Test validación JSON con firma válida."""
    url = "https://example.com/whatsapp/json"
    raw_body = b'{"From":"+573001234567","Body":"hola"}'

    sig = compute_twilio_json_signature(url, raw_body, twilio_token_env, algo="SHA1")
    assert WhatsAppService.validate_webhook_json(url, raw_body, sig, signature_algo="SHA1") is True

def test_validate_webhook_json_invalid(twilio_token_env):
    """Test validación JSON con firma inválida."""
    url = "https://example.com/whatsapp/json"
    raw_body = b'{"From":"+573001234567","Body":"hola"}'

    sig = compute_twilio_json_signature(url, raw_body, twilio_token_env, algo="SHA1")
    # Cambiamos el body → debe fallar
    raw_body_bad = b'{"From":"+573001234567","Body":"HOLA"}'
    assert WhatsAppService.validate_webhook_json(url, raw_body_bad, sig, signature_algo="SHA1") is False

def test_validate_webhook_json_sha256(twilio_token_env):
    """Test validación JSON con algoritmo SHA256."""
    url = "https://example.com/whatsapp/json"
    raw_body = b'{"From":"+573001234567","Body":"hola"}'
    sig = compute_twilio_json_signature(url, raw_body, twilio_token_env, algo="SHA256")
    assert WhatsAppService.validate_webhook_json(url, raw_body, sig, signature_algo="SHA256") is True

def test_validate_webhook_json_string_body(twilio_token_env):
    """Test validación JSON con body como string."""
    url = "https://example.com/whatsapp/json"
    raw_body = '{"From":"+573001234567","Body":"hola"}'
    
    sig = compute_twilio_json_signature(url, raw_body.encode("utf-8"), twilio_token_env, algo="SHA1")
    assert WhatsAppService.validate_webhook_json(url, raw_body, sig, signature_algo="SHA1") is True
