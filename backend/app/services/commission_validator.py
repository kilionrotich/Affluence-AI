from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Commission


def validate_commissions(db: Session) -> int:
    pending = db.scalars(
        select(Commission).where(
            Commission.status == "pending",
            Commission.eligible_at <= datetime.utcnow(),
        )
    ).all()
    for commission in pending:
        commission.status = "confirmed"
        commission.confirmed_at = datetime.utcnow()
    db.commit()
    return len(pending)
