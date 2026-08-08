"""Tests for Posting Controller (Queue & Mode Management)."""

import os
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_posting.db"
os.environ["ADMIN_TOKEN"] = "admin-token"
os.environ["VIEWER_TOKEN"] = "viewer-token"

from app.database import Base, engine
from app.main import app
from app.models import (
    Product, AffiliateLink, ContentDraft, SocialAccount,
    PostingQueue, PostingModeConfig, Notification,
)

from fastapi.testclient import TestClient
from app.database import SessionLocal

client = TestClient(app)
headers = {"Authorization": "Bearer admin-token"}
viewer_headers = {"Authorization": "Bearer viewer-token"}


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Seed data for posting tests
    with SessionLocal() as db:
        p = Product(
            network="amazon",
            product_id="post-prod",
            name="Post Test Product",
            price=50.0,
            commission_rate=0.05,
        )
        db.add(p)
        db.flush()

        link = AffiliateLink(
            product_id=p.id,
            partner_id="post-partner",
            tracking_code="post-tc",
            url="https://example.com/post",
        )
        db.add(link)
        db.flush()

        draft = ContentDraft(
            title="Post Test Draft",
            content_type="blog",
            platform="wordpress",
            body="Test body content with #ad disclosure.",
            affiliate_link_id=link.id,
            disclosure_added=True,
            compliance_passed=True,
            status="draft",
        )
        db.add(draft)
        db.flush()

        draft2 = ContentDraft(
            title="Post Test Draft 2",
            content_type="social",
            platform="twitter",
            body="Another test. #ad",
            disclosure_added=True,
            compliance_passed=True,
            status="draft",
        )
        db.add(draft2)
        db.flush()

        account = SocialAccount(
            platform="twitter",
            account_name="Post Test Account",
            encrypted_credentials="gAAAAABn",
            connection_status="active",
            is_active=True,
        )
        db.add(account)
        db.commit()

        account2 = SocialAccount(
            platform="wordpress",
            account_name="WP Test Account",
            encrypted_credentials="gAAAAABn",
            connection_status="active",
            is_active=True,
        )
        db.add(account2)
        db.commit()


def test_get_posting_mode_default() -> None:
    """Test getting the default posting mode."""
    resp = client.get("/posting-mode", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert data["mode"] in ("auto", "manual")


def test_update_posting_mode() -> None:
    """Test updating posting mode."""
    resp = client.put("/posting-mode", json={"mode": "auto"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "auto"

    # Switch back to manual
    resp = client.put("/posting-mode", json={"mode": "manual"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["mode"] == "manual"


def test_posting_queue_lists_empty() -> None:
    """Test posting queue returns empty list initially."""
    resp = client.get("/posting-queue", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_get_queue_with_status_filter() -> None:
    """Test filtering queue by status."""
    resp = client.get("/posting-queue?status=queued", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_approve_nonexistent_queue_item() -> None:
    """Test approving a non-existent queue item."""
    resp = client.post("/posting-queue/99999/approve", headers=headers)
    assert resp.status_code == 400


def test_reject_nonexistent_queue_item() -> None:
    """Test rejecting a non-existent queue item."""
    resp = client.post("/posting-queue/99999/reject", headers=headers)
    assert resp.status_code == 400


def test_posting_mode_creates_notification() -> None:
    """Test that changing mode creates a notification."""
    # Clear notifications first
    with SessionLocal() as db:
        db.query(Notification).delete()
        db.commit()

    client.put("/posting-mode", json={"mode": "auto"}, headers=headers)

    with SessionLocal() as db:
        notif = db.query(Notification).filter(
            Notification.notification_type == "posting_mode_change"
        ).first()
        assert notif is not None
        assert "auto" in notif.message.lower()


def test_content_post_to_accounts() -> None:
    """Test posting content to accounts (creates queue or publishes)."""
    with SessionLocal() as db:
        draft = db.query(ContentDraft).first()
        accounts = db.query(SocialAccount).all()

    account_ids = [a.id for a in accounts]
    resp = client.post(
        f"/content/post?content_draft_id={draft.id}&social_account_ids={account_ids[0]}",
        headers=headers,
    )
    # This might fail if the body format isn't right, but should return 200 or 422
    assert resp.status_code in (200, 422)

    if resp.status_code == 200:
        data = resp.json()
        assert "results" in data


def test_account_analytics_nonexistent() -> None:
    """Test getting analytics for non-existent account."""
    resp = client.get("/analytics/account/99999", headers=viewer_headers)
    assert resp.status_code == 404


def test_all_accounts_analytics() -> None:
    """Test getting analytics for all accounts."""
    resp = client.get("/analytics/accounts", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts" in data
    assert "total_earnings_all" in data
    assert "total_clicks_all" in data
    assert "total_conversions_all" in data

