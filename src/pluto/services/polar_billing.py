import hmac
import hashlib
import json
import os
from typing import Dict, Any, Optional

RATE_CARD = {
    "ltx-2.5": 0.005,
    "wan2.1-1.3b": 0.003,
    "wan2.1-14b": 0.012,
    "hunyuanvideo": 0.015,
}

class PolarBillingManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PolarBillingManager, cls).__new__(cls)
            cls._instance.webhook_secret = os.getenv("POLAR_WEBHOOK_SECRET", "test_secret")
            cls._instance.agent_pub_keys = {} # mock store for agent public keys
            cls._instance.ledger = {} # mock ledger {customer_id: credits}
            cls._instance.tier = {} # mock tier {customer_id: tier_name}
        return cls._instance
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        expected_sig = hmac.new(
            self.webhook_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)
    
    def process_webhook(self, event_type: str, payload: dict):
        # mock implementation
        if event_type == "checkout.created":
            customer_id = payload.get("customer_id")
            self.ledger[customer_id] = self.ledger.get(customer_id, 0) + payload.get("credits", 0)
    
    def verify_x402_micropayment(self, signature: str, payload: dict) -> dict:
        # In a real implementation, this would verify an elliptic curve or ed25519 signature
        # from the agent using their public key.
        # For this exercise, we'll do a simple SHA256 HMAC mock for the agent proof
        
        agent_id = payload.get("agent_id")
        amount = payload.get("amount", 0)
        
        # mock verification
        expected_sig = hmac.new(
            b"agent_secret",
            msg=json.dumps(payload, sort_keys=True).encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(expected_sig, signature)
        
        if is_valid:
            # credit the agent's balance or process payment
            self.ledger[agent_id] = self.ledger.get(agent_id, 0) + amount
            return {"status": "success", "agent_id": agent_id, "amount_credited": amount}
        else:
            return {"status": "error", "message": "Invalid signature"}
    
    def get_usage_and_tier(self, customer_id: str) -> dict:
        return {
            "tier": self.tier.get(customer_id, "free"),
            "credits_remaining": self.ledger.get(customer_id, 0.0),
            "rate_card": RATE_CARD
        }

    def debit_usage(self, customer_id: str, engine: str, seconds: float) -> bool:
        rate = RATE_CARD.get(engine)
        if rate is None:
            return False
            
        cost = rate * seconds
        current_credits = self.ledger.get(customer_id, 0.0)
        
        if current_credits >= cost:
            self.ledger[customer_id] = current_credits - cost
            return True
        return False
