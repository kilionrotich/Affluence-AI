import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_affiliate.db"
os.environ["ADMIN_TOKEN"] = "admin-token"
os.environ["VIEWER_TOKEN"] = "viewer-token"
os.environ["PAYOUT_THRESHOLD"] = "1"
os.environ["REFUND_PERIOD_DAYS"] = "0"

from app.database import Base, engine
from app.main import app
from app.models import Commission


client = TestClient(app)
headers = {"Authorization": "Bearer " + os.environ["ADMIN_TOKEN"]}


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_affiliate_flow_endpoints() -> None:
    scan = client.post("/scan", headers=headers)
    assert scan.status_code == 200
    product = scan.json()["products"][0]

    purchase = client.post(
        "/purchase",
        json={"tracking_code": product["tracking_code"], "amount": 120},
        headers=headers,
    )
    assert purchase.status_code == 200
    assert purchase.json()["commission_amount"] > 0

    # force commission eligible for validation
    from app.database import SessionLocal

    with SessionLocal() as db:
        c = db.query(Commission).first()
        c.eligible_at = datetime.utcnow() - timedelta(days=1)
        db.commit()

    validate = client.post("/validate", headers=headers)
    assert validate.status_code == 200
    assert validate.json()["confirmed"] >= 1

    payout = client.post("/payout", json={"method": "paypal"}, headers=headers)
    assert payout.status_code == 200

    viewer = client.get("/report", headers={"Authorization": "Bearer " + os.environ["VIEWER_TOKEN"]})
    assert viewer.status_code == 200
    body = viewer.json()
    assert "daily_earnings" in body
    assert "payouts" in body


def test_rbac_blocks_without_token() -> None:
    response = client.get("/report")
    assert response.status_code == 401
