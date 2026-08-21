import pytest
import hmac
import hashlib
import json
from src.pluto.services.polar_billing import PolarBillingManager, RATE_CARD
from src.pluto_mcp_server import pluto_get_billing_usage, pluto_verify_agent_payment

@pytest.fixture
def manager():
    mgr = PolarBillingManager()
    mgr.webhook_secret = "test_secret"
    mgr.ledger = {}
    mgr.tier = {}
    return mgr

def test_webhook_signature_validation(manager):
    payload = b'{"type":"checkout.created","data":{"customer_id":"cust_123","credits":100}}'
    
    expected_sig = hmac.new(
        b"test_secret",
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    assert manager.verify_webhook_signature(payload, expected_sig) == True
    assert manager.verify_webhook_signature(payload, "invalid_sig") == False

def test_webhook_processing(manager):
    payload = {"customer_id": "cust_123", "credits": 100}
    manager.process_webhook("checkout.created", payload)
    
    assert manager.ledger.get("cust_123") == 100
    usage = manager.get_usage_and_tier("cust_123")
    assert usage["credits_remaining"] == 100

def test_usage_ledger_debiting(manager):
    manager.ledger["cust_123"] = 1.0 # 1 credit
    
    # LTX-2.5 is $0.005/sec
    # Debit for 10 seconds = 0.05
    success = manager.debit_usage("cust_123", "ltx-2.5", 10.0)
    assert success == True
    assert manager.ledger["cust_123"] == 0.95
    
    # Try debiting more than available
    success = manager.debit_usage("cust_123", "ltx-2.5", 1000.0) # costs 5.0
    assert success == False
    assert manager.ledger["cust_123"] == 0.95

def test_x402_signature_verification(manager):
    payload = {"agent_id": "agent_007", "amount": 5.0}
    
    expected_sig = hmac.new(
        b"agent_secret",
        msg=json.dumps(payload, sort_keys=True).encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    result = manager.verify_x402_micropayment(expected_sig, payload)
    assert result["status"] == "success"
    assert result["amount_credited"] == 5.0
    assert manager.ledger["agent_007"] == 5.0
    
    invalid_result = manager.verify_x402_micropayment("bad_sig", payload)
    assert invalid_result["status"] == "error"

def test_fastmcp_tools(manager):
    manager.ledger["cust_mcp"] = 25.0
    
    usage = pluto_get_billing_usage("cust_mcp")
    assert usage["credits_remaining"] == 25.0
    assert "rate_card" in usage
    
    payload = {"agent_id": "agent_mcp", "amount": 10.0}
    expected_sig = hmac.new(
        b"agent_secret",
        msg=json.dumps(payload, sort_keys=True).encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    verify_result = pluto_verify_agent_payment(expected_sig, payload)
    assert verify_result["status"] == "success"
    assert verify_result["amount_credited"] == 10.0
