from pydantic import BaseModel
from typing import Optional, Dict, Any

class AsaasPayment(BaseModel):
    id: str
    customer: str
    value: float
    netValue: float
    billingType: str
    status: str
    # Adicione outros campos conforme necessário

class AsaasWebhookPayload(BaseModel):
    event: str  # Ex: PAYMENT_RECEIVED, PAYMENT_OVERDUE
    payment: AsaasPayment


class AsaasPayload(BaseModel):
    event: str
    payment: AsaasPayment