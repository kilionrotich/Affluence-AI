"""Tests for Social Account Manager."""

import os
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_social.db"
os.environ["ADMIN_TOKEN"] = "admin-token"
os.environ["VIEWER_TOKEN"] = "viewer-token"

from app.database import Base, engine
from app.main import app
from app.models import SocialAccount, Notification

from fastapi.testclient import TestClient
from app.database import SessionLocal

client = TestClient(app)
headers = {"Authorization": "Bearer admin-token"}
viewer_headers = {"Authorization": "Bearer viewer-token"}


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_create_social_account() -> None:
    """Test creating a social account."""
    resp = client.post(
        "/social-accounts",
        json={
            "platform": "twitter",
            "account_name": "My Twitter Bot",
            "credentials": {"api_key": "test-key", "api_secret": "test-secret"},
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_name"] == "My Twitter Bot"
    assert data["platform"] == "twitter"
    assert data["connection_status"] in ("active", "pending", "suspended")
    assert data["is_active"] is True
    assert data["id"] > 0
    return data["id"]


def test_list_social_accounts() -> None:
    """Test listing social accounts."""
    test_create_social_account()
    resp = client.get("/social-accounts", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_social_account() -> None:
    """Test getting a specific social account."""
    account_id = test_create_social_account()
    resp = client.get(f"/social-accounts/{account_id}", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == account_id


def test_update_social_account() -> None:
    """Test updating a social account."""
    account_id = test_create_social_account()
    resp = client.put(
        f"/social-accounts/{account_id}",
        json={"account_name": "Updated Bot Name", "is_active": False},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_name"] == "Updated Bot Name"
    assert data["is_active"] is False


def test_verify_social_account() -> None:
    """Test verifying a social account connection."""
    account_id = test_create_social_account()
    resp = client.post(f"/social-accounts/{account_id}/verify", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["connection_status"] in ("active", "expired", "suspended", "pending")
    assert "message" in data


def test_list_filter_by_platform() -> None:
    """Test filtering social accounts by platform."""
    # Create twitter and linkedin accounts
    client.post(
        "/social-accounts",
        json={"platform": "linkedin", "account_name": "LinkedIn Bot", "credentials": {"token": "abc"}},
        headers=headers,
    )

    resp = client.get("/social-accounts?platform=linkedin", headers=viewer_headers)
    data = resp.json()
    assert all(a["platform"] == "linkedin" for a in data)


def test_list_active_only() -> None:
    """Test filtering by active only."""
    resp = client.get("/social-accounts?active_only=true", headers=viewer_headers)
    data = resp.json()
    assert all(a["is_active"] is True for a in data)


def test_delete_social_account() -> None:
    """Test deleting a social account."""
    account_id = test_create_social_account()
    resp = client.delete(f"/social-accounts/{account_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify it's gone
    resp = client.get(f"/social-accounts/{account_id}", headers=viewer_headers)
    assert resp.status_code == 404


def test_get_nonexistent_account() -> None:
    """Test getting a non-existent account."""
    resp = client.get("/social-accounts/99999", headers=viewer_headers)
    assert resp.status_code == 404


def test_delete_nonexistent_account() -> None:
    """Test deleting a non-existent account."""
    resp = client.delete("/social-accounts/99999", headers=headers)
    assert resp.status_code == 404


def test_token_expiry_check() -> None:
    """Test token expiry detection."""
    # Create account with expired token
    expires = (datetime.utcnow() - timedelta(days=1)).isoformat()
    resp = client.post(
        "/social-accounts",
        json={
            "platform": "facebook",
            "account_name": "Expired Token Bot",
            "credentials": {"access_token": "old-token"},
            "oauth_token_expires_at": expires,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["connection_status"] == "expired"

    # Should have created a notification about re-auth
    with SessionLocal() as db:
        notifications = db.query(Notification).filter(
            Notification.notification_type.in_(["re_auth_required", "token_expired"])
        ).all()
        assert len(notifications) >= 1

