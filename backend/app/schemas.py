from datetime import datetime
from pydantic import BaseModel, Field


class ScanResponse(BaseModel):
    inserted: int
    products: list[dict]


class PurchaseRequest(BaseModel):
    tracking_code: str
    amount: float | None = Field(default=None, gt=0)


class PurchaseResponse(BaseModel):
    purchase_id: int
    commission_id: int
    commission_amount: float


class ValidateResponse(BaseModel):
    confirmed: int


class PayoutRequest(BaseModel):
    method: str = Field(pattern="^(paypal|mpesa)$")


class PayoutResponse(BaseModel):
    payout_id: int
    amount: float
    method: str
    transaction_ref: str


class ReportResponse(BaseModel):
    daily_earnings: list[dict]
    weekly_earnings: list[dict]
    payouts: list[dict]
    pending_balance: float
    confirmed_balance: float


class CredentialPayload(BaseModel):
    provider: str
    api_key: str


class CommissionRow(BaseModel):
    id: int
    amount: float
    status: str
    eligible_at: datetime
