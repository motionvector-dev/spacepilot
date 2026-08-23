import hmac
import hashlib
import json
import os
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

RATE_CARD = {
    "ltx-2.5": Decimal("0.005"),
    "wan2.1-1.3b": Decimal("0.003"),
    "wan2.1-14b": Decimal("0.012"),
    "hunyuanvideo": Decimal("0.015"),
}

class PolarBillingManager:
    """Manager for Polar billing and x402 micropayments."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PolarBillingManager, cls).__new__(cls)
            cls._instance.webhook_secret = os.getenv("POLAR_WEBHOOK_SECRET", "test_secret")
            cls._instance.agent_pub_keys = {} # mock store for agent public keys
            cls._instance.ledger: dict[str, Decimal] = {} # mock ledger {customer_id: credits}
            cls._instance.tier: dict[str, str] = {} # mock tier {customer_id: tier_name}
            cls._instance._processed_events = set()
            
            x402_secret_str = os.environ.get("X402_AGENT_SECRET", "")
            if not x402_secret_str:
                logger.warning("X402_AGENT_SECRET environment variable is not set")
            cls._instance.x402_secret = x402_secret_str.encode('utf-8')
        return cls._instance
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verifies the Polar webhook signature against the payload."""
        expected_sig = hmac.new(
            self.webhook_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)
    
    def process_webhook(self, event_id: str, event_type: str, payload: dict):
        """Processes a Polar webhook event idempotently."""
        if event_id in self._processed_events:
            return
            
        # mock implementation
        if event_type == "checkout.created":
            customer_id = payload.get("customer_id")
            credits = Decimal(str(payload.get("credits", 0)))
            self.ledger[customer_id] = self.ledger.get(customer_id, Decimal("0.0")) + credits
            
        self._processed_events.add(event_id)
    
    def verify_x402_micropayment(self, signature: str, raw_payload: bytes, payload_dict: dict) -> dict:
        """Verifies and processes an x402 micropayment using the raw request payload."""
        agent_id = payload_dict.get("agent_id")
        amount = Decimal(str(payload_dict.get("amount", 0)))
        
        expected_sig = hmac.new(
            self.x402_secret,
            msg=raw_payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(expected_sig, signature)
        
        if is_valid:
            # credit the agent's balance or process payment
            self.ledger[agent_id] = self.ledger.get(agent_id, Decimal("0.0")) + amount
            return {"status": "success", "agent_id": agent_id, "amount_credited": float(amount)}
        else:
            return {"status": "error", "message": "Invalid signature"}
    
    def get_usage_and_tier(self, customer_id: str) -> dict:
        """Gets the usage and tier for a customer."""
        return {
            "tier": self.tier.get(customer_id, "free"),
            "credits_remaining": float(self.ledger.get(customer_id, Decimal("0.0"))),
            "rate_card": {k: float(v) for k, v in RATE_CARD.items()}
        }

    def debit_usage(self, customer_id: str, engine: str, seconds: float) -> bool:
        """Debits usage from a customer's ledger."""
        rate = RATE_CARD.get(engine)
        if rate is None:
            return False
            
        cost = rate * Decimal(str(seconds))
        current_credits = self.ledger.get(customer_id, Decimal("0.0"))
        
        if current_credits >= cost:
            self.ledger[customer_id] = current_credits - cost
            return True
        return False
