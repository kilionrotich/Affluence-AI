from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Commission


def balances(db: Session) -> tuple[float, float]:
    pending = db.scalar(select(func.coalesce(func.sum(Commission.amount), 0.0)).where(Commission.status == "pending"))
    confirmed = db.scalar(select(func.coalesce(func.sum(Commission.amount), 0.0)).where(Commission.status == "confirmed"))
    return float(pending or 0.0), float(confirmed or 0.0)
