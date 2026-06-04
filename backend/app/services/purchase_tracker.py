from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AffiliateLink, Commission, Purchase


def record_purchase(db: Session, tracking_code: str, amount: float | None, refund_period_days: int) -> tuple[Purchase, Commission]:
    link = db.scalar(select(AffiliateLink).where(AffiliateLink.tracking_code == tracking_code))
    if not link:
        raise ValueError("Tracking code not found")

    purchase_amount = amount if amount is not None else link.product.price
    purchase = Purchase(
        link_id=link.id,
        item_name=link.product.name,
        amount=purchase_amount,
    )
    db.add(purchase)
    db.flush()

    commission = Commission(
        purchase_id=purchase.id,
        amount=round(purchase_amount * link.product.commission_rate, 2),
        status="pending",
        eligible_at=datetime.utcnow() + timedelta(days=refund_period_days),
    )
    db.add(commission)
    db.commit()
    db.refresh(purchase)
    db.refresh(commission)
    return purchase, commission
