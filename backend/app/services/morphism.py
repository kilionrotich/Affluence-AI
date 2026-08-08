"""Morphism Layer Service

Transforms raw data across the Affluence-AI pipeline into standardized,
actionable formats. Four transformation engines provide consistent data
handling from feed ingestion through content distribution and analytics.

Engines:
- DataMorphism:     Raw affiliate feed -> standardized product objects
- ContentMorphism:  Validated affiliate links -> multi-format content
- WorkflowMorphism: Validated actions -> execution paths (auto vs manual)
- AnalyticsMorphism: Raw click/conversion data -> actionable insights
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AffiliateLink,
    Click,
    Commission,
    ContentDraft,
    PostingModeConfig,
    PostingQueue,
    Product,
    Purchase,
    SocialAccount,
)
from ..config import get_settings
from .compliance import ComplianceEngine
from .content_distribution import ContentGenerator
from .audit_logger import AuditLogger


# ─────────────────────────────────────────────────────────────
# Helper: network display normalization
# ─────────────────────────────────────────────────────────────
NETWORK_LABELS = {
    "amazon": "Amazon Associates",
    "clickbank": "ClickBank",
    "cj": "CJ Affiliate",
    "sharesale": "ShareASale",
    "jumia": "Jumia Partners",
}


def _recognize_network(value: str) -> str:
    """Normalize a variety of network spellings to a known key."""
    v = (value or "").strip().lower()
    mappings = {
        "amazon": "amazon",
        "amazon associates": "amazon",
        "paapi": "amazon",
        "clickbank": "clickbank",
        "click bank": "clickbank",
        "cb": "clickbank",
        "cj": "cj",
        "cj affiliate": "cj",
        "commission junction": "cj",
        "shareasale": "sharesale",
        "share a sale": "sharesale",
        "jumia": "jumia",
        "jumia partners": "jumia",
    }
    return mappings.get(v, "other")


class DataMorphism:
    """Transform raw affiliate feed items into standardized product objects.

    Input: list of dicts (raw feed) with arbitrary/loose key names.
    Output: list of normalized dicts with predictable schema.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def transform_feed(self, raw_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert raw, heterogenous feed items into standardized products."""
        standardized = []
        skipped = 0

        for raw in raw_items:
            if not isinstance(raw, dict):
                skipped += 1
                continue

            # Extract fields tolerantly across common naming variants
            name = (
                raw.get("name")
                or raw.get("title")
                or raw.get("product_name")
                or raw.get("productName")
                or "Unnamed Product"
            )
            network_key = _recognize_network(
                raw.get("network") or raw.get("networkName") or raw.get("provider") or "other"
            )
            product_id = (
                raw.get("product_id")
                or raw.get("id")
                or raw.get("sku")
                or raw.get("productId")
                or f"{network_key}-{abs(hash(name)) % 100000}"
            )
            price = self._to_float(raw.get("price") or raw.get("sale_price") or raw.get("amount") or 0)
            commission_rate = self._to_float(raw.get("commission_rate") or raw.get("commissionRate") or raw.get("rate") or 0)
            category = raw.get("category") or raw.get("cat") or "General"
            image_url = raw.get("image_url") or raw.get("image") or raw.get("imageUrl")
            description = raw.get("description") or raw.get("desc") or ""
            url = raw.get("url") or raw.get("affiliate_url") or raw.get("link") or raw.get("affiliateUrl")

            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

            standardized.append({
                "network": network_key,
                "network_label": NETWORK_LABELS.get(network_key, network_key.title()),
                "product_id": str(product_id),
                "name": name,
                "slug": slug,
                "price": price,
                "commission_rate": commission_rate,
                "commission_pct": round(commission_rate * 100, 2),
                "estimated_commission": round(price * commission_rate, 2),
                "category": category,
                "image_url": image_url,
                "description": description,
                "affiliate_url": url,
                "morphed_at": datetime.utcnow().isoformat(),
            })

        return {
            "source_count": len(raw_items),
            "skipped": skipped,
            "morphed_count": len(standardized),
            "products": standardized,
        }

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


class ContentMorphism:
    """Transform validated affiliate links into multiple content formats.

    Generates blog posts, social media posts, and newsletter snippets from
    a single validated product/link source.
    """

    def __init__(self, db: Session):
        self.db = db
        self.generator = ContentGenerator(db)
        self.compliance = ComplianceEngine(db)
        self.logger = AuditLogger(db)

    def transform_content(self, product: Product, link: AffiliateLink, category: str = "default") -> Dict[str, Any]:
        """Generate content in multiple formats for a validated link/product."""
        formats = {}

        # Blog post
        blog = self.generator.generate_blog_post(product, category)
        blog_body = self.generator.embed_affiliate_link(blog["body"], link.url)
        blog_body = self.compliance.auto_tag_disclosure(blog_body, "wordpress")
        formats["blog"] = {
            "title": blog["title"],
            "platform": "wordpress",
            "content": blog_body,
            "length_chars": len(blog_body),
        }

        # Social (twitter/X)
        social = self.generator.generate_social_post(product, "twitter")
        social_body = self.generator.embed_affiliate_link(social, link.url)
        social_body = self.compliance.auto_tag_disclosure(social_body, "twitter")
        formats["social"] = {
            "title": None,
            "platform": "twitter",
            "content": social_body,
            "length_chars": len(social_body),
        }

        # Newsletter
        newsletter_body = (
            f"Product Spotlight: {product.name}\n\n"
            f"We're highlighting {product.name} this week. Priced at just ${product.price:.2f}, "
            f"it's a standout pick for your shortlist.\n\n"
            f"{link.url}\n\n"
            f"*Affiliate Disclosure: Some links in this newsletter are affiliate links. "
            f"I may earn a commission at no extra cost to you.*"
        )
        formats["newsletter"] = {
            "title": f"Spotlight: {product.name}",
            "platform": "newsletter",
            "content": newsletter_body,
            "length_chars": len(newsletter_body),
        }

        # Audit
        self.logger.log(
            action="content_morphism",
            action_category="posting",
            entity_type="AffiliateLink",
            entity_id=link.id,
            details=f"Generated content formats (blog/social/newsletter) for '{product.name}'",
            user_role="system",
        )

        return {
            "source": {
                "product_id": product.id,
                "name": product.name,
                "network": product.network,
                "link_id": link.id,
                "tracking_code": link.tracking_code,
            },
            "formats": formats,
            "format_count": len(formats),
            "morphed_at": datetime.utcnow().isoformat(),
        }


class WorkflowMorphism:
    """Map validated actions to execution paths (Auto-Post vs Manual Approval)."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.logger = AuditLogger(db)

    def get_workflow_map(self) -> Dict[str, Any]:
        """Return the current workflow routing configuration."""
        # Read global posting mode
        config = self.db.scalar(select(PostingModeConfig).limit(1))
        mode = config.mode if config else self.settings.posting_mode

        # Count active accounts
        active_accounts = self.db.scalar(
            select(PostingQueue.id).limit(1)
        )  # fallback; real count below
        active_count = self.db.scalar(
            select(PostingQueue.id).where(PostingQueue.status == "queued")
        )

        paths = self._build_paths(mode)

        return {
            "posting_mode": mode,
            "primary_execution_path": "auto-post" if mode == "auto" else "manual-approval",
            "routing": {
                "scan": {
                    "path": "market_scan",
                    "next": "link_validation",
                    "gated": False,
                },
                "link_validation": {
                    "path": "data_morphism",
                    "next": "content_morphism",
                    "gated": True,  # must pass before content
                },
                "content_morphism": {
                    "path": "content_generation",
                    "next": "compliance_gate",
                    "gated": False,
                },
                "compliance_gate": {
                    "path": "workflow_morphism",
                    "next": "distribution",
                    "gated": True,  # blocks non-compliant content
                },
                "distribution": paths,
            },
            "mode": mode,
        }

    def route_action(self, action: str, validated: bool = True) -> Dict[str, Any]:
        """Route a validated action to the appropriate execution path."""
        config = self.db.scalar(select(PostingModeConfig).limit(1))
        mode = config.mode if config else self.settings.posting_mode

        if action == "post_content":
            if not validated:
                return {
                    "action": action,
                    "status": "blocked",
                    "reason": "validation_failed",
                    "execution_path": None,
                }
            if mode == "auto":
                path = "auto_publish"
                status = "executing"
                detail = "Publishing directly to selected accounts after compliance."
            else:
                path = "queue_for_approval"
                status = "queued"
                detail = "Drafted and queued for operator approval."
        elif action == "scan":
            path = "market_scan"
            status = "validated" if validated else "blocked"
            detail = "Scanning confirmed affiliate networks for products."
        elif action == "generate_content":
            path = "content_morphism"
            status = "validated" if validated else "blocked"
            detail = "Transforming validated links into multi-format content."
        else:
            path = "unknown"
            status = "blocked"
            detail = f"Unrecognized action: {action}"

        self.logger.log(
            action=f"workflow_routed:{action}",
            action_category="system",
            details=f"Routed '{action}' -> {path} ({status})",
            user_role="system",
            success=(status != "blocked"),
        )

        return {
            "action": action,
            "validated": validated,
            "status": status,
            "execution_path": path,
            "detail": detail,
            "mode": mode,
        }

    def _build_paths(self, mode: str) -> Dict[str, Any]:
        if mode == "auto":
            return {
                "auto_post": {
                    "target": "distribute",
                    "gate": "compliance_passed",
                    "action_on_fail": "block",
                    "description": "Compliant content is posted to all selected accounts automatically.",
                }
            }
        return {
            "manual_approval": {
                "target": "queue",
                "gate": "operator_approval",
                "action_on_fail": "reject",
                "description": "AI drafts & queues content, then waits for operator approval before posting.",
            }
        }


class AnalyticsMorphism:
    """Transform raw click/conversion data into actionable insights (CTR, ROI, trending)."""

    def __init__(self, db: Session):
        self.db = db
        self.logger = AuditLogger(db)

    def transform_analytics(self) -> Dict[str, Any]:
        """Compute actionable insights from raw click & conversion data."""
        # Aggregate per-link data
        links = self.db.scalars(select(AffiliateLink)).all()

        insights_per_link = []
        total_clicks = 0
        total_conversions = 0
        total_earnings = 0.0

        for link in links:
            click_total = self.db.query(Click).filter(Click.link_id == link.id).count()

            # Conversions and earnings
            purchases = self.db.scalars(
                select(Purchase).where(Purchase.link_id == link.id)
            ).all()
            conversion_total = sum(
                1 for p in purchases if p.click_id is not None
            )

            earnings = 0.0
            for purchase in purchases:
                commission = self.db.scalar(
                    select(Commission).where(Commission.purchase_id == purchase.id)
                )
                if commission and commission.status == "confirmed":
                    earnings += commission.amount

            total_clicks += click_total
            total_conversions += conversion_total
            total_earnings += earnings

            product = link.product
            insights_per_link.append({
                "link_id": link.id,
                "product_id": product.id if product else None,
                "product_name": product.name if product else "Unknown",
                "network": product.network if product else "unknown",
                "clicks": click_total,
                "conversions": conversion_total,
                "performance": self._performance_label(click_total, conversion_total),
                "earnings": round(earnings, 2),
                "conversion_rate": round(
                    (conversion_total / click_total * 100) if click_total > 0 else 0, 2
                ),
            })

        overall_ctr = round((total_conversions / total_clicks * 100) if total_clicks > 0 else 0, 2)
        roi = round(total_earnings, 2)

        # Trending products (by conversions, then earnings)
        trending = sorted(
            insights_per_link,
            key=lambda x: (x["conversions"], x["earnings"]),
            reverse=True,
        )[:5]

        self.logger.log(
            action="analytics_morphism",
            action_category="validation",
            details=f"Generated insights from {total_clicks} clicks / {total_conversions} conversions / ${total_earnings:.2f}",
            user_role="system",
        )

        return {
            "summary": {
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "overall_conversion_rate": overall_ctr,
                "total_earnings": round(total_earnings, 2),
                "estimated_roi": roi,
                "active_links": len(insights_per_link),
            },
            "insights": insights_per_link,
            "trending_products": trending,
            "morphed_at": datetime.utcnow().isoformat(),
        }

    def _performance_label(self, clicks: int, conversions: int) -> str:
        """Classify link performance into actionable buckets."""
        if conversions == 0:
            return "needs_attention"
        rate = conversions / clicks if clicks > 0 else 0
        if rate >= 0.05:
            return "high_performing"
        if rate >= 0.02:
            return "promising"
        return "moderate"

