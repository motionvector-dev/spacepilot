from fastapi import APIRouter, Request, Header, HTTPException, Depends
from typing import Dict, Any, Optional
from src.pluto.services.polar_billing import PolarBillingManager

billing_router = APIRouter(prefix="/api/billing", tags=["billing"])

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
        
    payload = await request.body()
    
    if not manager.verify_webhook_signature(payload, x_polar_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    data = await request.json()
    event_type = data.get("type")
    
    manager.process_webhook(event_type, data.get("data", {}))
    return {"status": "ok"}

@billing_router.get("/usage")
async def get_usage(customer_id: str, manager: PolarBillingManager = Depends(get_billing_manager)):
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
        
    data = await request.json()
    result = manager.verify_x402_micropayment(x_agent_signature, data)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=402, detail=result.get("message"))
        
    return result
