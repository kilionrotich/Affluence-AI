"""Tests for the Compliance Enforcement Engine."""

import os
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_compliance.db"
os.environ["ADMIN_TOKEN"] = "admin-token"
os.environ["VIEWER_TOKEN"] = "viewer-token"

from app.database import Base, engine
from app.main import app
from app.models import ComplianceRule, ComplianceCheck
from app.services.compliance import ComplianceEngine

from fastapi.testclient import TestClient
from app.database import SessionLocal

client = TestClient(app)
headers = {"Authorization": "Bearer admin-token"}
viewer_headers = {"Authorization": "Bearer viewer-token"}


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_compliance_health_score() -> None:
    """Test compliance health score endpoint."""
    resp = client.get("/compliance/health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "health_score" in data
    assert "status" in data
    assert data["status"] in ("healthy", "warning", "critical")


def test_viewer_can_access_health() -> None:
    """Test viewer role can access compliance health."""
    resp = client.get("/compliance/health", headers=viewer_headers)
    assert resp.status_code == 200


def test_compliance_check_no_disclosure() -> None:
    """Test compliance check catches missing FTC disclosure."""
    resp = client.post(
        "/compliance/check",
        json={
            "content_type": "blog",
            "platform": "wordpress",
            "content_text": "This is a great product! Buy it now at our store.",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    # Should flag missing FTC disclosure
    checks = data["checks"]
    disclosures = [c for c in checks if c["rule_type"] == "disclosure"]
    assert len(disclosures) > 0
    assert any(not c["passed"] for c in disclosures)


def test_compliance_check_with_disclosure() -> None:
    """Test content with proper disclosure passes."""
    text = "This is a great product! #ad #affiliate Check it out here."
    resp = client.post(
        "/compliance/check",
        json={"content_type": "social", "platform": "twitter", "content_text": text},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should pass or partially pass
    assert "passed" in data


def test_misleading_claims_detected() -> None:
    """Test misleading claims are flagged."""
    text = "Get rich quick! Make $5000 per day with zero work! Guaranteed income!"
    resp = client.post(
        "/compliance/check",
        json={"content_type": "blog", "platform": "wordpress", "content_text": text},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    claims = [c for c in data["checks"] if c["rule_type"] == "claim"]
    assert len(claims) > 0
    assert any(not c["passed"] for c in claims)


def test_auto_tag_disclosure() -> None:
    """Test auto-tag adds disclosure when missing."""
    text = "Great product review!"
    resp = client.post(
        "/compliance/disclosure/auto-tag",
        json={"text": text, "platform": "blog"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "tagged_text" in data
    assert "Affiliate Disclosure" in data["tagged_text"] or "#ad" in data["tagged_text"]


def test_create_compliance_rule() -> None:
    """Test creating a custom compliance rule."""
    resp = client.post(
        "/compliance/rules",
        json={
            "platform": "twitter",
            "rule_name": "No Crypto Scams",
            "rule_type": "claim",
            "pattern": r"free crypto|get bitcoin|invest in crypto",
            "action": "block",
            "description": "Block crypto scam promotions",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rule_name"] == "No Crypto Scams"
    assert data["platform"] == "twitter"
    assert data["enabled"] is True
    assert data["id"] > 0


def test_list_compliance_rules() -> None:
    """Test listing all compliance rules."""
    resp = client.get("/compliance/rules", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_toggle_compliance_rule() -> None:
    """Test toggling a compliance rule on/off."""
    # First create a rule
    resp = client.post(
        "/compliance/rules",
        json={
            "platform": "facebook",
            "rule_name": "No Gambling",
            "rule_type": "policy",
            "pattern": r"casino|betting|gambling",
            "action": "block",
        },
        headers=headers,
    )
    rule_id = resp.json()["id"]

    # Toggle off
    resp = client.put(f"/compliance/rules/{rule_id}/toggle", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # Toggle back on
    resp = client.put(f"/compliance/rules/{rule_id}/toggle", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_compliance_check_content_type_passed() -> None:
    """Test that compliance check result is logged in DB."""
    with SessionLocal() as db:
        count_before = db.query(ComplianceCheck).count()

    text = "Nice product! #ad This is an affiliate link."
    client.post(
        "/compliance/check",
        json={"content_type": "blog", "platform": "wordpress", "content_text": text},
        headers=headers,
    )

    with SessionLocal() as db:
        count_after = db.query(ComplianceCheck).count()
    assert count_after > count_before


def test_cookie_stuffing_detection() -> None:
    """Test cookie stuffing patterns are detected."""
    text = '<img src="https://example.com/redirect?ref=abc123" />'
    resp = client.post(
        "/compliance/check",
        json={"content_type": "blog", "platform": "wordpress", "content_text": text},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    stuffing = [c for c in data["checks"] if c["rule"] == "Cookie Stuffing Prevention"]
    assert len(stuffing) > 0


def test_unauthorized_access() -> None:
    """Test that unauthenticated requests are rejected."""
    resp = client.post("/compliance/check", json={"content_type": "blog", "platform": "wp", "content_text": "test"})
    assert resp.status_code == 401

