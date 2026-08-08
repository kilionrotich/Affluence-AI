import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..integrations.payouts import mpesa_payout, paypal_payout
from ..models import Commission, Payout

logger = logging.getLogger(__name__)


def trigger_payout(db: Session, method: str, threshold: float) -> Payout:
    confirmed = db.scalars(select(Commission).where(Commission.status == "confirmed")).all()
    if not confirmed:
        raise ValueError("No confirmed commissions available for payout")

    total = round(sum(c.amount for c in confirmed), 2)
    if total < threshold:
        raise ValueError(
            f"Total confirmed balance (${total:.2f}) is below the payout threshold (${threshold:.2f})"
        )

    settings = get_settings()
    try:
        if method == "paypal":
            transaction_ref = paypal_payout(settings.paypal_payout_url, total)
        elif method == "mpesa":
            transaction_ref = mpesa_payout(settings.mpesa_payout_url, total)
        else:
            raise ValueError(f"Unsupported payout method: {method}")
    except Exception as e:
        logger.error(f"Payout failed for method {method}, amount ${total:.2f}: {e}")
        raise ValueError(f"Payout processing failed: {e}") from e

    payout = Payout(method=method, amount=total, transaction_ref=transaction_ref, status="processed")
    db.add(payout)
    for commission in confirmed:
        commission.status = "paid"
    try:
        db.commit()
        db.refresh(payout)
        logger.info(f"Payout processed: {payout.id}, method={method}, amount=${total:.2f}, ref={transaction_ref}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during payout recording: {e}")
        raise ValueError(f"Failed to record payout: {e}") from e

    return payout
