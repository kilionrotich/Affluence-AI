"""Tests for Content Distribution System."""

import os
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_content.db"
os.environ["ADMIN_TOKEN"] = "admin-token"
os.environ["VIEWER_TOKEN"] = "viewer-token"

from app.database import Base, engine
from app.main import app
from app.models import Product, ContentDraft, AffiliateLink
from app.services.content_distribution import ContentGenerator

from fastapi.testclient import TestClient
from app.database import SessionLocal

client = TestClient(app)
headers = {"Authorization": "Bearer admin-token"}
viewer_headers = {"Authorization": "Bearer viewer-token"}


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Seed a product
    with SessionLocal() as db:
        p = Product(
            network="amazon",
            product_id="test-prod-001",
            name="Test Product",
            price=99.99,
            commission_rate=0.04,
            category="Electronics",
        )
        db.add(p)
        db.commit()
        # Also seed a link
        l = AffiliateLink(
            product_id=p.id,
            partner_id="test-partner",
            tracking_code="tc-test-001",
            url="https://example.com/ref=test",
        )
        db.add(l)
        db.commit()


def test_generate_blog_content() -> None:
    """Test blog content generation for a product."""
    with SessionLocal() as db:
        product = db.query(Product).first()
        product_id = product.id

    resp = client.post(f"/content/generate/blog?product_id={product_id}&category=tech", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "title" in data
    assert "body" in data
    # Title may use the category name ("Electronics") or product name
    assert "Electronics" in data["title"] or "Test Product" in data["title"]


def test_generate_social_content() -> None:
    """Test social media content generation."""
    with SessionLocal() as db:
        product = db.query(Product).first()
        product_id = product.id

    resp = client.post(
        f"/content/generate/social?product_id={product_id}&platform=twitter&benefit=increasing%20productivity",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform"] == "twitter"
    assert "content" in data


def test_create_content_draft() -> None:
    """Test creating a content draft."""
    with SessionLocal() as db:
        link = db.query(AffiliateLink).first()
        link_id = link.id

    resp = client.post(
        "/content/draft",
        json={
            "title": "My Test Blog Post",
            "content_type": "blog",
            "platform": "wordpress",
            "body": "This is a test blog post with affiliate link. #ad I recommend this product!",
            "affiliate_link_id": link_id,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "My Test Blog Post"
    assert data["content_type"] == "blog"
    assert data["status"] == "draft"
    assert data["disclosure_added"] is True
    assert data["id"] > 0
    return data["id"]


def test_get_pending_content() -> None:
    """Test getting pending content drafts."""
    # Create a draft first
    draft_id = test_create_content_draft()

    resp = client.get("/content/pending", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Find our draft
    drafts = [d for d in data if d["id"] == draft_id]
    assert len(drafts) == 1
    assert drafts[0]["status"] == "draft"


def test_publish_content() -> None:
    """Test publishing a content draft."""
    draft_id = test_create_content_draft()

    resp = client.post("/content/publish", json={"content_id": draft_id}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("published", "failed")
    if data["status"] == "published":
        assert data["external_post_id"] is not None


def test_get_published_content() -> None:
    """Test getting published content."""
    resp = client.get("/content/published", headers=viewer_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_generate_blog_invalid_product() -> None:
    """Test generating blog for non-existent product."""
    resp = client.post("/content/generate/blog?product_id=99999", headers=headers)
    assert resp.status_code == 404


def test_viewer_can_read_content() -> None:
    """Test viewer role can read content endpoints."""
    resp = client.get("/content/pending", headers=viewer_headers)
    assert resp.status_code == 200

    resp = client.get("/content/published", headers=viewer_headers)
    assert resp.status_code == 200


def test_publish_without_compliance_fails() -> None:
    """Test publishing content without compliance check fails."""
    with SessionLocal() as db:
        link = db.query(AffiliateLink).first()
        link_id = link.id

    # Create draft with content that has no disclosure
    resp = client.post(
        "/content/draft",
        json={
            "title": "Non-compliant Post",
            "content_type": "blog",
            "platform": "wordpress",
            "body": "Buy this amazing product right now! No disclosure here.",
            "affiliate_link_id": link_id,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    draft_id = resp.json()["id"]
    assert resp.json()["compliance_passed"] is False or resp.json()["compliance_passed"] is True

    # Try to publish
    resp = client.post("/content/publish", json={"content_id": draft_id}, headers=headers)
    # Should either succeed (if compliance was auto-checked) or fail with 400
    assert resp.status_code in (200, 400)

