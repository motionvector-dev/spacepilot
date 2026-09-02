"""Billing routes — disabled on purpose.

Billing ships from the `platform` repo on Dodo plus credits. Nothing in this
repo meters, debits, or persists anything, so every route here refuses with
501 rather than pretending to take money. The implementations are kept below,
commented, so the shapes are still readable when the real thing is wired up.

Three defects are why they refuse rather than merely go unused:

  * `verify_x402_micropayment` credited `ledger[agent_id] += amount` where
    `amount` came from the same body the signature covered. Anyone holding the
    signing key could credit itself any figure.
  * `POLAR_WEBHOOK_SECRET` defaulted to the literal "test_secret", and an unset
    `X402_AGENT_SECRET` yielded an empty HMAC key that still produced valid
    signatures.
  * Neither POST route carried `require_token`, and the structural guard in
    tests/test_web_api.py could not see them (FastAPI stopped flattening
    included routers into `app.routes`, so the walk matched nothing at all).

The routes keep `require_token` even while disabled: re-enabling a body must
not also silently re-open the gate.
"""

from fastapi import APIRouter, Depends, HTTPException

from spacepilot.api.deps import require_token

billing_router = APIRouter(prefix="/api/billing", tags=["billing"])

_DISABLED_DETAIL = (
    "Billing is not implemented in SpacePilot. Credits and metering ship from "
    "the platform service; this endpoint accepts nothing and grants nothing."
)


def _refuse() -> None:
    raise HTTPException(status_code=501, detail=_DISABLED_DETAIL)


@billing_router.post("/polar/webhook")
async def polar_webhook(_: None = Depends(require_token)):
    _refuse()


@billing_router.get("/usage")
async def get_usage(customer_id: str, _: None = Depends(require_token)):
    _refuse()


@billing_router.post("/x402/verify")
async def verify_x402(_: None = Depends(require_token)):
    _refuse()


# --- Original implementations, disabled ------------------------------------
#
# class WebhookPayload(BaseModel):
#     id: str
#     type: str
#     data: Dict[str, Any]
#
# class X402Payload(BaseModel):
#     agent_id: str
#     amount: float
#
# def get_billing_manager():
#     return PolarBillingManager()
#
# @billing_router.post("/polar/webhook")
# async def polar_webhook(
#     request: Request,
#     x_polar_signature: str = Header(None),
#     manager: PolarBillingManager = Depends(get_billing_manager)
# ):
#     if not x_polar_signature:
#         raise HTTPException(status_code=400, detail="Missing signature header")
#     payload_bytes = await request.body()
#     if not manager.verify_webhook_signature(payload_bytes, x_polar_signature):
#         raise HTTPException(status_code=401, detail="Invalid signature")
#     try:
#         data_json = json.loads(payload_bytes.decode('utf-8'))
#         webhook_data = WebhookPayload(**data_json)
#     except Exception:
#         raise HTTPException(status_code=400, detail="Invalid JSON or payload")
#     manager.process_webhook(webhook_data.id, webhook_data.type, webhook_data.data)
#     return {"status": "ok"}
#
# @billing_router.get("/usage")
# async def get_usage(
#     customer_id: str,
#     manager: PolarBillingManager = Depends(get_billing_manager),
#     _: None = Depends(require_token)
# ):
#     if not customer_id:
#         raise HTTPException(status_code=400, detail="customer_id required")
#     return manager.get_usage_and_tier(customer_id)
#
# @billing_router.post("/x402/verify")
# async def verify_x402(
#     request: Request,
#     x_agent_signature: str = Header(None),
#     manager: PolarBillingManager = Depends(get_billing_manager)
# ):
#     if not x_agent_signature:
#         raise HTTPException(status_code=400, detail="Missing signature header")
#     raw_payload = await request.body()
#     try:
#         data_json = json.loads(raw_payload.decode('utf-8'))
#         x402_data = X402Payload(**data_json)
#     except Exception:
#         raise HTTPException(status_code=400, detail="Invalid JSON or payload")
#     result = manager.verify_x402_micropayment(
#         x_agent_signature, raw_payload, x402_data.model_dump()
#     )
#     if result.get("status") == "error":
#         raise HTTPException(status_code=402, detail=result.get("message"))
#     return result
