"""Billing is disabled. These tests prove it refuses rather than half-works.

What used to live here asserted that a webhook and an x402 call granted credit.
That behaviour is gone on purpose: `verify_x402_micropayment` credited the
amount taken from the caller's own request body, so anyone holding the signing
key could mint credit for itself. See the module docstrings in
spacepilot/services/polar_billing.py and
spacepilot/api/routes/billing.py.

The tests that survive cover the parts that grant nothing — signature
verification and `debit_usage` — plus the refusal itself.
"""

import hmac
import hashlib
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spacepilot.api.routes.billing import billing_router
from spacepilot.services.polar_billing import PolarBillingManager, RATE_CARD
from spacepilot.core.config import get_settings

app = FastAPI()
app.include_router(billing_router)
client = TestClient(app)

MONEY_ROUTES = ["/api/billing/polar/webhook", "/api/billing/x402/verify"]


@pytest.fixture(autouse=True)
def reset_manager():
    PolarBillingManager._instance = None
    mgr = PolarBillingManager()
    mgr.webhook_secret = "test_secret"
    mgr.x402_secret = b"agent_secret"
    mgr.ledger = {}
    mgr.tier = {}
    mgr._processed_events = set()
    yield mgr
    PolarBillingManager._instance = None


def _auth():
    return {"X-Pluto-Token": get_settings().studio_token}


def test_money_routes_refuse_with_501(reset_manager):
    """A disabled route must say so, not accept the request and do nothing."""
    for path in MONEY_ROUTES:
        response = client.post(path, json={}, headers=_auth())
        assert response.status_code == 501, f"{path} returned {response.status_code}"
        assert "not implemented" in response.json()["detail"].lower()


def test_usage_route_refuses_with_501(reset_manager):
    response = client.get(
        "/api/billing/usage?customer_id=cust_123", headers=_auth()
    )
    assert response.status_code == 501


def test_disabled_routes_still_require_the_token(reset_manager):
    """Re-enabling a body must not also silently re-open the gate."""
    assert client.post(MONEY_ROUTES[0], json={}).status_code == 401
    assert client.post(MONEY_ROUTES[1], json={}).status_code == 401
    assert client.get("/api/billing/usage?customer_id=x").status_code == 401


def test_credit_granting_is_gone_from_the_service(reset_manager):
    """Not just unrouted — unreachable, so a new caller cannot resurrect it."""
    with pytest.raises(NotImplementedError):
        reset_manager.process_webhook(
            "evt_1", "checkout.created", {"customer_id": "c", "credits": 100}
        )
    with pytest.raises(NotImplementedError):
        reset_manager.verify_x402_micropayment(
            "sig", b"{}", {"agent_id": "a", "amount": 5.0}
        )
    assert reset_manager.ledger == {}


def test_webhook_signature_validation(reset_manager):
    payload = b'{"type":"checkout.created","data":{"customer_id":"cust_123","credits":100}}'
    expected_sig = hmac.new(
        b"test_secret", msg=payload, digestmod=hashlib.sha256
    ).hexdigest()

    assert reset_manager.verify_webhook_signature(payload, expected_sig) is True
    assert reset_manager.verify_webhook_signature(payload, "invalid_sig") is False


def test_empty_webhook_secret_verifies_nothing(reset_manager):
    """An unset POLAR_WEBHOOK_SECRET must reject, not sign with an empty key."""
    reset_manager.webhook_secret = ""
    payload = b'{"type":"checkout.created"}'
    forged = hmac.new(b"", msg=payload, digestmod=hashlib.sha256).hexdigest()

    assert reset_manager.verify_webhook_signature(payload, forged) is False


def test_usage_ledger_debiting(reset_manager):
    reset_manager.ledger["cust_123"] = Decimal("1.0")

    assert reset_manager.debit_usage("cust_123", "ltx-2.5", 10.0) is True
    assert reset_manager.ledger["cust_123"] == Decimal("0.95")

    assert reset_manager.debit_usage("cust_123", "ltx-2.5", 1000.0) is False
    assert reset_manager.ledger["cust_123"] == Decimal("0.95")


def test_rate_card_is_intact():
    assert RATE_CARD["ltx-2.5"] == Decimal("0.005")
