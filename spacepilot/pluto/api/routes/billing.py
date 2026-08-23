from fastapi import APIRouter, Request, Header, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
import json
from spacepilot.pluto.services.polar_billing import PolarBillingManager
from spacepilot.pluto.api.deps import require_token

billing_router = APIRouter(prefix="/api/billing", tags=["billing"])

class WebhookPayload(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]

class X402Payload(BaseModel):
    agent_id: str
    amount: float

def get_billing_manager():
    return PolarBillingManager()

@billing_router.post("/polar/webhook")
async def polar_webhook(
    request: Request,
    x_polar_signature: str = Header(None),
    manager: PolarBillingManager = Depends(get_billing_manager)
):
    if not x_polar_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")
        
    payload_bytes = await request.body()
    
    if not manager.verify_webhook_signature(payload_bytes, x_polar_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    try:
        data_json = json.loads(payload_bytes.decode('utf-8'))
        webhook_data = WebhookPayload(**data_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON or payload")
    
    manager.process_webhook(webhook_data.id, webhook_data.type, webhook_data.data)
    return {"status": "ok"}

@billing_router.get("/usage")
async def get_usage(
    customer_id: str, 
    manager: PolarBillingManager = Depends(get_billing_manager),
    _: None = Depends(require_token)
):
    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id required")
        
    return manager.get_usage_and_tier(customer_id)

@billing_router.post("/x402/verify")
async def verify_x402(
    request: Request,
    x_agent_signature: str = Header(None),
    manager: PolarBillingManager = Depends(get_billing_manager)
):
    if not x_agent_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")
        
    raw_payload = await request.body()
    
    try:
        data_json = json.loads(raw_payload.decode('utf-8'))
        x402_data = X402Payload(**data_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON or payload")
        
    result = manager.verify_x402_micropayment(x_agent_signature, raw_payload, x402_data.model_dump())
    
    if result.get("status") == "error":
        raise HTTPException(status_code=402, detail=result.get("message"))
        
    return result
