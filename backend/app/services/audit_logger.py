"""Audit Logging Service

Logs all system actions for auditability and compliance tracking.
Supports categorized event logging for filtering by action type.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AuditLog


class AuditLogger:
    """Logs all significant actions in the system for audit trail."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        action_category: str | None = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_role: Optional[str] = None,
        success: bool = True,
        source: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> AuditLog:
        """Create an audit log entry with optional category for filtering."""
        log_entry = AuditLog(
            action=action,
            action_category=action_category,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_role=user_role,
            success=success,
            source=source,
            metadata_json=metadata,
        )
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        return log_entry

    def get_logs(
        self,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        action_category: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """Retrieve audit logs with optional filtering."""
        query = select(AuditLog).order_by(AuditLog.created_at.desc())

        if action:
            query = query.where(AuditLog.action == action)
        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)
        if action_category:
            query = query.where(AuditLog.action_category == action_category)

        return list(self.db.scalars(query.limit(limit)).all())

    def get_recent_actions(self, minutes: int = 60) -> list:
        """Get actions performed in the last N minutes."""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        return list(
            self.db.scalars(
                select(AuditLog)
                .where(AuditLog.created_at >= since)
                .order_by(AuditLog.created_at.desc())
            ).all()
        )

    def get_categories(self) -> list[dict]:
        """Get log counts grouped by action category."""
        rows = (
            self.db.execute(
                select(
                    AuditLog.action_category,
                    func.count(AuditLog.id).label("count"),
                )
                .where(AuditLog.action_category.isnot(None))
                .group_by(AuditLog.action_category)
                .order_by(AuditLog.action_category)
            )
            .all()
        )
        return [
            {"category": r.action_category, "count": r.count}
            for r in rows
        ]

    # ── Categorized Logging Methods ─────────────────────────────────

    def log_scan(self, products_count: int, user_role: str = "admin") -> AuditLog:
        """Log a market scan action."""
        return self.log(
            action="market_scan",
            action_category="scanning",
            entity_type="Product",
            details=f"Scanned and found {products_count} products",
            user_role=user_role,
        )

    def log_purchase(self, purchase_id: int, amount: float) -> AuditLog:
        """Log a purchase recording."""
        return self.log(
            action="purchase_recorded",
            action_category="payment",
            entity_type="Purchase",
            entity_id=purchase_id,
            details=f"Purchase recorded for ${amount:.2f}",
            user_role="admin",
        )

    def log_payout(self, payout_id: int, method: str, amount: float) -> AuditLog:
        """Log a payout trigger."""
        return self.log(
            action="payout_triggered",
            action_category="payment",
            entity_type="Payout",
            entity_id=payout_id,
            details=f"Payout of ${amount:.2f} triggered via {method}",
            user_role="admin",
        )

    def log_content_publish(self, content_id: int, platform: str, status: str) -> AuditLog:
        """Log content publishing."""
        return self.log(
            action="content_published",
            action_category="posting",
            entity_type="ContentDraft",
            entity_id=content_id,
            details=f"Content published to {platform} with status: {status}",
            user_role="admin",
        )

    def log_compliance_check(self, content_id: int, passed: bool, reason: Optional[str] = None) -> AuditLog:
        """Log a compliance check."""
        return self.log(
            action="compliance_check",
            action_category="compliance",
            entity_type="ContentDraft",
            entity_id=content_id,
            details=f"Compliance check {'passed' if passed else 'failed'}: {reason or 'All checks passed'}",
            user_role="system",
            success=passed,
        )

    def log_error(self, action: str, error_message: str, entity_type: Optional[str] = None) -> AuditLog:
        """Log an error (defaults to system category)."""
        return self.log(
            action=action,
            action_category="system",
            entity_type=entity_type,
            details=f"ERROR: {error_message}",
            success=False,
            user_role="system",
        )

    # ── AI / Operational Logging Methods ────────────────────────────

    def log_post_to_account(
        self, content_id: int, account_name: str, platform: str, success: bool = True
    ) -> AuditLog:
        """Log a post action to a specific social account."""
        return self.log(
            action="post_to_account",
            action_category="posting",
            entity_type="ContentDraft",
            entity_id=content_id,
            details=f"Posted to {platform} account '{account_name}'",
            user_role="system",
            success=success,
        )

    def log_content_queued(
        self, content_id: int, account_name: str, platform: str
    ) -> AuditLog:
        """Log content queued for manual approval."""
        return self.log(
            action="content_queued",
            action_category="posting",
            entity_type="ContentDraft",
            entity_id=content_id,
            details=f"Content queued for {platform} account '{account_name}'",
            user_role="system",
        )

    def log_link_validation(self, link_id: int, valid: bool, message: str = "") -> AuditLog:
        """Log an affiliate link validation check."""
        return self.log(
            action="link_validation",
            action_category="validation",
            entity_type="AffiliateLink",
            entity_id=link_id,
            details=f"Link validation {'passed' if valid else 'failed'}: {message}",
            user_role="system",
            success=valid,
        )

    def log_commission_validated(self, count: int) -> AuditLog:
        """Log commission validation."""
        return self.log(
            action="commission_validation",
            action_category="validation",
            entity_type="Commission",
            details=f"Validated {count} commissions",
            user_role="system",
        )

    def log_post_rejected(self, queue_id: int, content_title: str, reason: str) -> AuditLog:
        """Log rejection of a queued post."""
        return self.log(
            action="post_rejected",
            action_category="posting",
            entity_type="PostingQueue",
            entity_id=queue_id,
            details=f"Post '{content_title}' rejected: {reason}",
            user_role="admin",
            success=False,
        )

    def log_re_auth_alert(self, account_name: str, platform: str) -> AuditLog:
        """Log re-authentication alert for an account."""
        return self.log(
            action="re_auth_required",
            action_category="system",
            entity_type="SocialAccount",
            details=f"Re-authentication required for {platform} account '{account_name}'",
            user_role="system",
            success=False,
        )

    # ── Comprehensive User & AI Action Logging Methods ─────────────

    def log_user_action(
        self,
        action: str,
        details: Optional[str] = None,
        page: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> AuditLog:
        """Log a user interaction from the frontend (click, navigation, input)."""
        meta = dict(metadata or {})
        if page:
            meta["page"] = page
        return self.log(
            action=action,
            action_category="user_action",
            entity_type="User",
            details=details,
            ip_address=ip_address,
            user_role="user",
            source="user",
            metadata=meta,
        )

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        ip_address: Optional[str] = None,
        user_role: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> AuditLog:
        """Log an HTTP API request."""
        meta = dict(metadata or {})
        if duration_ms is not None:
            meta["duration_ms"] = round(duration_ms, 2)
        ok = status_code < 400
        return self.log(
            action=f"http_{method.lower()}",
            action_category="request",
            entity_type="HTTP",
            details=f"{method} {path} -> {status_code}",
            ip_address=ip_address,
            user_role=user_role or "system",
            success=ok,
            source="request",
            metadata=meta,
        )

    def log_ai_scan(self, network: str, products_count: int, new_count: int, updated_count: int) -> AuditLog:
        """Log an AI market scan for a specific network."""
        return self.log(
            action=f"ai_market_scan_{network}",
            action_category="ai_action",
            entity_type="Product",
            details=f"[AI] Scanned {network}: {products_count} products ({new_count} new, {updated_count} updated)",
            user_role="ai",
            source="ai",
            metadata={"network": network, "products_count": products_count, "new_count": new_count, "updated_count": updated_count},
        )

    def log_network_fetch(self, network: str, used_fallback: bool, count: int) -> AuditLog:
        """Log an AI network adapter fetch."""
        return self.log(
            action=f"network_fetch_{network}",
            action_category="ai_action",
            entity_type="Network",
            details=f"[AI] Fetched from {network} ({'fallback' if used_fallback else 'live API'}): {count} products",
            user_role="ai",
            source="ai",
            metadata={"network": network, "used_fallback": used_fallback, "count": count},
        )

    def log_link_generated(self, link_id: int, product_id: int, network: str, tracking_code: str, url: str) -> AuditLog:
        """Log an AI generating or retrieving an affiliate link."""
        return self.log(
            action="link_generated",
            action_category="link_generation",
            entity_type="AffiliateLink",
            entity_id=link_id,
            details=f"[AI] Generated affiliate link for product #{product_id} ({network}): {url}",
            user_role="ai",
            source="ai",
            metadata={"product_id": product_id, "network": network, "tracking_code": tracking_code},
        )

    def log_click_recorded(
        self,
        click_id: int,
        link_id: int,
        tracking_code: str,
        referrer: Optional[str] = None,
        country: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log a click recorded on an affiliate link (how links are obtained when clicked)."""
        return self.log(
            action="click_recorded",
            action_category="link_generation",
            entity_type="Click",
            entity_id=click_id,
            details=f"Click recorded on link #{link_id} (ref {tracking_code})"
                    f"{' from ' + referrer if referrer else ''}"
                    f"{' [' + country + ']' if country else ''}",
            ip_address=ip_address,
            user_role="user",
            source="user",
            metadata={"link_id": link_id, "tracking_code": tracking_code, "referrer": referrer, "country": country},
        )

    def log_content_generated(self, content_id: int, content_type: str, platform: str, title: str = "") -> AuditLog:
        """Log AI content generation."""
        return self.log(
            action="content_generated",
            action_category="content",
            entity_type="ContentDraft",
            entity_id=content_id,
            details=f"[AI] Generated {content_type} content for {platform}: {title}",
            user_role="ai",
            source="ai",
            metadata={"content_type": content_type, "platform": platform},
        )

    def log_new_product(self, product_id: int, network: str, name: str) -> AuditLog:
        """Log a new product discovered by the AI."""
        return self.log(
            action="product_discovered",
            action_category="scanning",
            entity_type="Product",
            entity_id=product_id,
            details=f"[AI] Discovered new product '{name}' on {network}",
            user_role="ai",
            source="ai",
            metadata={"network": network, "name": name},
        )

