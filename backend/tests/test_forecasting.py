"""Tests for Commission Forecasting Service."""

import os
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_forecast.db"
os.environ["ADMIN_TOKEN"] = "admin-token"
os.environ["VIEWER_TOKEN"] = "viewer-token"

from app.database import Base, engine
from app.main import app
from app.models import Commission, Purchase, AffiliateLink, Product

from fastapi.testclient import TestClient
from app.database import SessionLocal

client = TestClient(app)
headers = {"Authorization": "Bearer admin-token"}
viewer_headers = {"Authorization": "Bearer viewer-token"}


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Seed historical commission data
    with SessionLocal() as db:
        p = Product(
            network="amazon",
            product_id="forecast-prod",
            name="Forecast Product",
            price=100.0,
            commission_rate=0.1,
        )
        db.add(p)
        db.flush()

        link = AffiliateLink(
            product_id=p.id,
            partner_id="forecast-partner",
            tracking_code="fc-tc",
            url="https://example.com/fc",
        )
        db.add(link)
        db.flush()

        for i in range(5):
            purchase = Purchase(
                link_id=link.id,
                item_name=f"Purchase {i}",
                amount=100.0,
            )
            db.add(purchase)
            db.flush()

            # Spread across 5 months to ensure unique strftime groupings
            days_ago = 150 - i * 30
            commission = Commission(
                purchase_id=purchase.id,
                amount=10.0 + i * 2,  # Increasing amounts for an upward trend
                status="confirmed",
                eligible_at=datetime.utcnow() - timedelta(days=days_ago),
                confirmed_at=datetime.utcnow() - timedelta(days=days_ago),
                created_at=datetime.utcnow() - timedelta(days=days_ago),
            )
            db.add(commission)
        db.commit()


def test_get_forecast() -> None:
    """Test commission forecast endpoint."""
    resp = client.get("/forecast?period=monthly&months=3", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "forecast" in data
    assert "trend_direction" in data
    assert "confidence" in data
    assert "historical_data_points" in data
    assert data["historical_data_points"] >= 5


def test_get_trends() -> None:
    """Test commission trends endpoint."""
    resp = client.get("/forecast/trends", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_earnings" in data
    assert "total_commissions" in data
    assert "trend" in data
    assert "conversion_rate" in data
    assert "average_commission_value" in data
    assert data["total_commissions"] >= 5


def test_get_forecast_summary() -> None:
    """Test forecast summary endpoint."""
    resp = client.get("/forecast/summary", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "current_month_earnings" in data
    assert "next_month_projection" in data
    assert "quarter_projection" in data
    assert "trend" in data
    assert "insights" in data
    assert len(data["insights"]) >= 1


def test_forecast_confidence_levels() -> None:
    """Test that confidence is calculated correctly."""
    resp = client.get("/forecast?period=monthly&months=2", headers=viewer_headers)
    data = resp.json()
    # With 5 data points, confidence should be at least 'medium'
    assert data["confidence"] in ("high", "medium")


def test_forecast_forecast_periods() -> None:
    """Test that correct number of forecast periods are returned."""
    resp = client.get("/forecast?period=monthly&months=3", headers=viewer_headers)
    data = resp.json()
    assert len(data["forecast"]) == 3
    assert data["forecast_periods"] == 3


def test_viewer_can_access_forecast() -> None:
    """Test viewer role can access forecast endpoints."""
    for path in ["/forecast", "/forecast/trends", "/forecast/summary"]:
        resp = client.get(path, headers=viewer_headers)
        assert resp.status_code == 200, f"Viewer failed on {path}"

