import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Commission, Payout
from .payout_monitor import balances


def generate_report(db: Session) -> dict:
    commissions = db.scalars(select(Commission)).all()
    payouts = db.scalars(select(Payout).order_by(Payout.created_at.desc())).all()

    rows = [
        {
            "amount": c.amount,
            "status": c.status,
            "date": (c.confirmed_at or c.eligible_at).date().isoformat(),
        }
        for c in commissions
    ]
    daily = []
    weekly = []
    if rows:
        frame = pd.DataFrame(rows)
        daily = (
            frame.groupby("date")["amount"]
            .sum()
            .reset_index()
            .rename(columns={"amount": "earnings"})
            .to_dict(orient="records")
        )
        frame["date"] = pd.to_datetime(frame["date"])
        frame["week"] = frame["date"].dt.to_period("W").astype(str)
        weekly = (
            frame.groupby("week")["amount"]
            .sum()
            .reset_index()
            .rename(columns={"amount": "earnings"})
            .to_dict(orient="records")
        )

    pending_balance, confirmed_balance = balances(db)
    return {
        "daily_earnings": daily,
        "weekly_earnings": weekly,
        "payouts": [
            {
                "id": p.id,
                "method": p.method,
                "amount": p.amount,
                "status": p.status,
                "transaction_ref": p.transaction_ref,
                "created_at": p.created_at.isoformat(),
            }
            for p in payouts
        ],
        "pending_balance": pending_balance,
        "confirmed_balance": confirmed_balance,
    }
