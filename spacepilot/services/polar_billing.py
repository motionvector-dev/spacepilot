"""Polar / x402 billing manager — the credit-granting half is disabled.

Billing ships from the `platform` repo on Dodo plus credits. Nothing here is
wired to a store: the ledger is a process-local dict that dies on restart, and
`debit_usage` is called by no endpoint, so no credit is ever actually spent.

`process_webhook` and `verify_x402_micropayment` are the two methods that
*granted* credit, and both now refuse. `verify_x402_micropayment` was the
serious one: it verified an HMAC over the request body and then credited the
amount taken from that same body, so a holder of the signing key could credit
itself any figure it liked. The original bodies are kept below, commented, for
whoever wires the real thing up.

Signature verification and `debit_usage` stay live. They are pure computation,
they grant nothing, and the tests that cover them are worth keeping.
"""

import hmac
import hashlib
import os
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

RATE_CARD = {
    "ltx-2.5": Decimal("0.005"),
    "wan2.1-1.3b": Decimal("0.003"),
    "wan2.1-14b": Decimal("0.012"),
    "hunyuanvideo": Decimal("0.015"),
}

_DISABLED = (
    "Billing is disabled in SpacePilot. Credits are granted by the platform "
    "service, not here."
)


class PolarBillingManager:
    """Manager for Polar billing and x402 micropayments."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PolarBillingManager, cls).__new__(cls)
            # No default. An unset secret must fail loudly, not silently accept
            # signatures made with a string that is public in this file's history.
            secret = os.getenv("POLAR_WEBHOOK_SECRET")
            if not secret:
                logger.warning("POLAR_WEBHOOK_SECRET is not set")
            cls._instance.webhook_secret = secret or ""
            cls._instance.agent_pub_keys = {}
            cls._instance.ledger: dict[str, Decimal] = {}
            cls._instance.tier: dict[str, str] = {}
            cls._instance._processed_events = set()

            x402_secret_str = os.environ.get("X402_AGENT_SECRET", "")
            if not x402_secret_str:
                logger.warning("X402_AGENT_SECRET environment variable is not set")
            cls._instance.x402_secret = x402_secret_str.encode('utf-8')
        return cls._instance

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verifies the Polar webhook signature against the payload.

        An empty secret verifies nothing: without this an unset
        POLAR_WEBHOOK_SECRET still produces HMACs an attacker can reproduce.
        """
        if not self.webhook_secret:
            return False
        expected_sig = hmac.new(
            self.webhook_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    def process_webhook(self, event_id: str, event_type: str, payload: dict):
        """Disabled: granted credit from an unpersisted in-process ledger."""
        raise NotImplementedError(_DISABLED)

        # if event_id in self._processed_events:
        #     return
        # if event_type == "checkout.created":
        #     customer_id = payload.get("customer_id")
        #     credits = Decimal(str(payload.get("credits", 0)))
        #     self.ledger[customer_id] = self.ledger.get(customer_id, Decimal("0.0")) + credits
        # self._processed_events.add(event_id)

    def verify_x402_micropayment(self, signature: str, raw_payload: bytes, payload_dict: dict) -> dict:
        """Disabled: credited the caller's own `amount` after verifying it.

        The signature proved the body was authentic, never that the amount was
        owed — so any holder of X402_AGENT_SECRET could mint credit.
        """
        raise NotImplementedError(_DISABLED)

        # agent_id = payload_dict.get("agent_id")
        # amount = Decimal(str(payload_dict.get("amount", 0)))
        # expected_sig = hmac.new(
        #     self.x402_secret, msg=raw_payload, digestmod=hashlib.sha256
        # ).hexdigest()
        # if hmac.compare_digest(expected_sig, signature):
        #     self.ledger[agent_id] = self.ledger.get(agent_id, Decimal("0.0")) + amount
        #     return {"status": "success", "agent_id": agent_id, "amount_credited": float(amount)}
        # return {"status": "error", "message": "Invalid signature"}

    def get_usage_and_tier(self, customer_id: str) -> dict:
        """Gets the usage and tier for a customer."""
        return {
            "tier": self.tier.get(customer_id, "free"),
            "credits_remaining": float(self.ledger.get(customer_id, Decimal("0.0"))),
            "rate_card": {k: float(v) for k, v in RATE_CARD.items()}
        }

    def debit_usage(self, customer_id: str, engine: str, seconds: float) -> bool:
        """Debits usage from a customer's ledger. Called by no endpoint today."""
        rate = RATE_CARD.get(engine)
        if rate is None:
            return False

        cost = rate * Decimal(str(seconds))
        current_credits = self.ledger.get(customer_id, Decimal("0.0"))

        if current_credits >= cost:
            self.ledger[customer_id] = current_credits - cost
            return True
        return False
