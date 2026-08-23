import pytest
import hmac
import hashlib
import json
from decimal import Decimal
from fastapi.testclient import TestClient
from src.pluto.api.routes.billing import billing_router
from src.pluto.services.polar_billing import PolarBillingManager, RATE_CARD
from src.pluto.core.config import get_settings
from fastapi import FastAPI

app = FastAPI()
app.include_router(billing_router)
client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_manager():
    # Reset singleton for testing
    PolarBillingManager._instance = None
    mgr = PolarBillingManager()
    mgr.webhook_secret = "test_secret"
    mgr.x402_secret = b"agent_secret"
    mgr.ledger = {}
    mgr.tier = {}
    mgr._processed_events = set()
    yield mgr
    PolarBillingManager._instance = None

def test_webhook_signature_validation(reset_manager):
    payload = b'{"type":"checkout.created","data":{"customer_id":"cust_123","credits":100}}'
    
    expected_sig = hmac.new(
        b"test_secret",
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    assert reset_manager.verify_webhook_signature(payload, expected_sig) == True
    assert reset_manager.verify_webhook_signature(payload, "invalid_sig") == False

def test_webhook_processing(reset_manager):
    payload = {"customer_id": "cust_123", "credits": 100}
    reset_manager.process_webhook("evt_1", "checkout.created", payload)
    
    assert reset_manager.ledger.get("cust_123") == Decimal("100")
    usage = reset_manager.get_usage_and_tier("cust_123")
    assert usage["credits_remaining"] == 100.0
    
    # Test idempotency
    reset_manager.process_webhook("evt_1", "checkout.created", payload)
    assert reset_manager.ledger.get("cust_123") == Decimal("100")

def test_usage_ledger_debiting(reset_manager):
    reset_manager.ledger["cust_123"] = Decimal("1.0") # 1 credit
    
    # LTX-2.5 is $0.005/sec
    # Debit for 10 seconds = 0.05
    success = reset_manager.debit_usage("cust_123", "ltx-2.5", 10.0)
    assert success == True
    assert reset_manager.ledger["cust_123"] == Decimal("0.95")
    
    # Try debiting more than available
    success = reset_manager.debit_usage("cust_123", "ltx-2.5", 1000.0) # costs 5.0
    assert success == False
    assert reset_manager.ledger["cust_123"] == Decimal("0.95")

def test_x402_signature_verification(reset_manager):
    payload = {"agent_id": "agent_007", "amount": 5.0}
    raw_payload = json.dumps(payload, sort_keys=True).encode('utf-8')
    
    expected_sig = hmac.new(
        b"agent_secret",
        msg=raw_payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    result = reset_manager.verify_x402_micropayment(expected_sig, raw_payload, payload)
    assert result["status"] == "success"
    assert result["amount_credited"] == 5.0
    assert reset_manager.ledger["agent_007"] == Decimal("5.0")
    
    invalid_result = reset_manager.verify_x402_micropayment("bad_sig", raw_payload, payload)
    assert invalid_result["status"] == "error"


# API Tests
def test_api_auth_rejection(reset_manager):
    # Missing auth token
    response = client.get("/api/billing/usage?customer_id=cust_123")
    assert response.status_code == 401

def test_api_usage_endpoint(reset_manager):
    reset_manager.ledger["cust_123"] = Decimal("50.0")
    settings = get_settings()
    
    response = client.get(
        "/api/billing/usage?customer_id=cust_123",
        headers={"X-Pluto-Token": settings.studio_token}
    )
    assert response.status_code == 200
    assert response.json()["credits_remaining"] == 50.0

def test_api_webhook_processing(reset_manager):
    payload = {"id": "evt_api", "type": "checkout.created", "data": {"customer_id": "cust_api", "credits": 200}}
    raw_payload = json.dumps(payload).encode('utf-8')
    
    sig = hmac.new(b"test_secret", msg=raw_payload, digestmod=hashlib.sha256).hexdigest()
    
    response = client.post(
        "/api/billing/polar/webhook",
        content=raw_payload,
        headers={"x-polar-signature": sig}
    )
    assert response.status_code == 200
    assert reset_manager.ledger["cust_api"] == Decimal("200")
    
    # Invalid sig
    response_invalid = client.post(
        "/api/billing/polar/webhook",
        content=raw_payload,
        headers={"x-polar-signature": "bad"}
    )
    assert response_invalid.status_code == 401

def test_api_x402_verification(reset_manager):
    payload = {"agent_id": "api_agent", "amount": 10.0}
    raw_payload = json.dumps(payload).encode('utf-8')
    
    sig = hmac.new(b"agent_secret", msg=raw_payload, digestmod=hashlib.sha256).hexdigest()
    
    response = client.post(
        "/api/billing/x402/verify",
        content=raw_payload,
        headers={"x-agent-signature": sig}
    )
    assert response.status_code == 200
    assert response.json()["amount_credited"] == 10.0
    assert reset_manager.ledger["api_agent"] == Decimal("10.0")
