from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..integrations.payouts import mpesa_payout, paypal_payout
from ..models import Commission, Payout


def trigger_payout(db: Session, method: str, threshold: float) -> Payout:
    confirmed = db.scalars(select(Commission).where(Commission.status == "confirmed")).all()
    total = round(sum(c.amount for c in confirmed), 2)
    if total < threshold:
        raise ValueError("Threshold not reached")

    settings = get_settings()
    if method == "paypal":
        transaction_ref = paypal_payout(settings.paypal_payout_url, total)
    else:
        transaction_ref = mpesa_payout(settings.mpesa_payout_url, total)

    payout = Payout(method=method, amount=total, transaction_ref=transaction_ref, status="processed")
    db.add(payout)
    for commission in confirmed:
        commission.status = "paid"
    db.commit()
    db.refresh(payout)
    return payout
