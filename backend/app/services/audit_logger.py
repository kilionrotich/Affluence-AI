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

