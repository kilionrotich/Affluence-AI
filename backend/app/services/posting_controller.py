"""Posting Controller Service

Routes content distribution through auto-publish or manual-approval workflow
based on the global posting mode setting. Enforces compliance gates.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    ContentDraft,
    SocialAccount,
    PostingQueue,
    PostingModeConfig,
    Notification,
    Click,
    Purchase,
    AffiliateLink,
)
from ..config import get_settings
from ..security import EncryptionManager
from .compliance import ComplianceEngine
from .content_distribution import ContentGenerator
from .audit_logger import AuditLogger
from .notification_service import NotificationService


class PostingController:
    """Controls the posting workflow: auto vs manual approval."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.compliance = ComplianceEngine(db)
        self.generator = ContentGenerator(db)
        self.logger = AuditLogger(db)
        self.notifier = NotificationService(db)

    # ------------------------------------------------------------------ 
    # Posting Mode Management
    # ------------------------------------------------------------------

    def get_posting_mode(self) -> dict:
        """Get the current global posting mode."""
        config = self.db.scalar(select(PostingModeConfig).limit(1))
        if not config:
            # Create default config from env settings
            config = PostingModeConfig(mode=self.settings.posting_mode)
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        return {"mode": config.mode, "updated_at": config.updated_at}

    def set_posting_mode(self, mode: str) -> dict:
        """Set the global posting mode (auto/manual)."""
        config = self.db.scalar(select(PostingModeConfig).limit(1))
        if not config:
            config = PostingModeConfig(mode=mode)
            self.db.add(config)
        else:
            config.mode = mode
            config.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(config)

        # Audit log
        self.logger.log(
            action="posting_mode_changed",
            entity_type="PostingModeConfig",
            details=f"Posting mode changed to: {mode}",
        )

        # Notification
        self.notifier.create_notification(
            notification_type="posting_mode_change",
            title=f"Posting Mode: {mode.title()}",
            message=f"Global posting mode has been switched to {mode.upper()} mode.",
            severity="info",
        )

        return {"mode": config.mode, "updated_at": config.updated_at}

    # ------------------------------------------------------------------
    # Posting Workflow
    # ------------------------------------------------------------------

    def process_content_post(
        self,
        content_draft_id: int,
        social_account_ids: List[int],
    ) -> List[dict]:
        """Process content for posting to selected accounts.

        In auto mode: publish directly after compliance check.
        In manual mode: queue for approval.
        """
        draft = self.db.get(ContentDraft, content_draft_id)
        if not draft:
            raise ValueError(f"Content draft not found: {content_draft_id}")

        accounts = []
        for aid in social_account_ids:
            account = self.db.get(SocialAccount, aid)
            if not account:
                raise ValueError(f"Social account not found: {aid}")
            if account.connection_status != "active":
                raise ValueError(
                    f"Account '{account.account_name}' is not active (status: {account.connection_status}). "
                    f"Please verify connection first."
                )
            accounts.append(account)

        # Run compliance check
        passed, checks = self.compliance.check_content_compliance(
            draft.content_type, draft.platform, draft.body
        )
        if not passed and self.settings.compliance_strict_mode:
            raise ValueError(
                f"Content failed compliance checks. Cannot post. "
                f"Run compliance check for details."
            )

        mode = self.get_posting_mode()["mode"]
        results = []

        for account in accounts:
            if mode == "auto":
                result = self._auto_post(draft, account)
            else:
                result = self._queue_for_approval(draft, account)
            results.append(result)

        return results

    def _auto_post(self, draft: ContentDraft, account: SocialAccount) -> dict:
        """Auto-post: publish directly after compliance."""
        try:
            # Publish using the content generator
            published = self.generator.publish_content(draft)

            # Create queue entry as published
            queue_entry = PostingQueue(
                content_draft_id=draft.id,
                social_account_id=account.id,
                posting_mode="auto",
                status="published",
                queued_at=datetime.utcnow(),
                published_at=datetime.utcnow(),
            )
            self.db.add(queue_entry)
            self.db.commit()
            self.db.refresh(queue_entry)

            # Audit
            self.logger.log(
                action="auto_post",
                entity_type="ContentDraft",
                entity_id=draft.id,
                details=f"Auto-posted to {account.platform} account '{account.account_name}'",
            )

            # Notification
            self.notifier.create_notification(
                notification_type="auto_posted",
                title=f"Auto-Posted to {account.account_name}",
                message=f"Content '{draft.title}' was auto-posted to {account.platform} account '{account.account_name}'.",
                severity="info",
            )

            return {
                "queue_id": queue_entry.id,
                "account_name": account.account_name,
                "platform": account.platform,
                "status": "published",
                "mode": "auto",
                "message": f"Posted successfully to {account.account_name}.",
            }

        except Exception as e:
            # Log failure
            queue_entry = PostingQueue(
                content_draft_id=draft.id,
                social_account_id=account.id,
                posting_mode="auto",
                status="failed",
                queued_at=datetime.utcnow(),
            )
            self.db.add(queue_entry)
            self.db.commit()

            self.logger.log(
                action="auto_post_failed",
                entity_type="ContentDraft",
                entity_id=draft.id,
                details=f"Auto-post failed for {account.platform}/{account.account_name}: {e}",
                success=False,
            )

            return {
                "queue_id": queue_entry.id,
                "account_name": account.account_name,
                "platform": account.platform,
                "status": "failed",
                "mode": "auto",
                "message": f"Failed to post: {e}",
            }

    def _queue_for_approval(self, draft: ContentDraft, account: SocialAccount) -> dict:
        """Queue content for manual approval."""
        existing = self.db.scalar(
            select(PostingQueue).where(
                PostingQueue.content_draft_id == draft.id,
                PostingQueue.social_account_id == account.id,
                PostingQueue.status == "queued",
            )
        )
        if existing:
            return {
                "queue_id": existing.id,
                "account_name": account.account_name,
                "platform": account.platform,
                "status": "already_queued",
                "mode": "manual",
                "message": f"Already queued for {account.account_name}.",
            }

        queue_entry = PostingQueue(
            content_draft_id=draft.id,
            social_account_id=account.id,
            posting_mode="manual",
            status="queued",
            queued_at=datetime.utcnow(),
        )
        self.db.add(queue_entry)
        self.db.commit()
        self.db.refresh(queue_entry)

        # Audit
        self.logger.log(
            action="content_queued",
            entity_type="PostingQueue",
            entity_id=queue_entry.id,
            details=f"Content '{draft.title}' queued for {account.platform} account '{account.account_name}'",
        )

        # Notification
        self.notifier.create_notification(
            notification_type="content_queued",
            title=f"Content Queued: {draft.title}",
            message=f"Content '{draft.title}' is queued for posting to {account.account_name} on {account.platform}. "
                    f"Review and approve in the dashboard.",
            severity="info",
        )

        return {
            "queue_id": queue_entry.id,
            "account_name": account.account_name,
            "platform": account.platform,
            "status": "queued",
            "mode": "manual",
            "message": f"Queued for approval on {account.account_name}.",
        }

    # ------------------------------------------------------------------
    # Queue Management (Manual Approval)
    # ------------------------------------------------------------------

    def get_queued_items(self, status: Optional[str] = None) -> List[dict]:
        """Get posting queue items."""
        query = select(PostingQueue).order_by(PostingQueue.queued_at.desc())

        if status:
            query = query.where(PostingQueue.status == status)

        items = self.db.scalars(query).all()
        results = []
        for item in items:
            draft = self.db.get(ContentDraft, item.content_draft_id)
            account = self.db.get(SocialAccount, item.social_account_id)
            results.append({
                "id": item.id,
                "content_draft_id": item.content_draft_id,
                "social_account_id": item.social_account_id,
                "posting_mode": item.posting_mode,
                "status": item.status,
                "queued_at": item.queued_at,
                "approved_at": item.approved_at,
                "published_at": item.published_at,
                "content_title": draft.title if draft else None,
                "platform": account.platform if account else None,
                "account_name": account.account_name if account else None,
            })
        return results

    def approve_queued_item(self, queue_id: int) -> dict:
        """Approve a queued post for publishing."""
        queue_item = self.db.get(PostingQueue, queue_id)
        if not queue_item:
            raise ValueError(f"Queue item not found: {queue_id}")
        if queue_item.status != "queued":
            raise ValueError(f"Queue item is not in queued status (current: {queue_item.status})")

        draft = self.db.get(ContentDraft, queue_item.content_draft_id)
        account = self.db.get(SocialAccount, queue_item.social_account_id)
        if not draft or not account:
            raise ValueError("Associated draft or account not found")

        # Run final compliance check
        passed, checks = self.compliance.check_content_compliance(
            draft.content_type, draft.platform, draft.body
        )
        if not passed and self.settings.compliance_strict_mode:
            queue_item.status = "rejected"
            self.db.commit()
            raise ValueError(
                f"Content failed compliance checks on approval. "
                f"Post has been rejected."
            )

        # Publish
        try:
            published = self.generator.publish_content(draft)

            queue_item.status = "approved"
            queue_item.approved_at = datetime.utcnow()
            self.db.commit()

            # Then publish
            published = self.generator.publish_content(draft)
            queue_item.status = "published"
            queue_item.published_at = datetime.utcnow()
            self.db.commit()

            # Audit
            self.logger.log(
                action="content_approved_and_published",
                entity_type="PostingQueue",
                entity_id=queue_item.id,
                details=f"Approved and published '{draft.title}' to {account.account_name}",
            )

            # Notification
            self.notifier.create_notification(
                notification_type="content_published_approved",
                title=f"Published: {draft.title}",
                message=f"Content '{draft.title}' has been approved and published to {account.account_name}.",
                severity="info",
            )

            return {
                "queue_id": queue_item.id,
                "status": "published",
                "message": f"Content published to {account.account_name}.",
            }

        except Exception as e:
            queue_item.status = "failed"
            self.db.commit()

            self.logger.log(
                action="publish_failed_on_approval",
                entity_type="PostingQueue",
                entity_id=queue_item.id,
                details=f"Publish failed for '{draft.title}' to {account.account_name}: {e}",
                success=False,
            )

            return {
                "queue_id": queue_item.id,
                "status": "failed",
                "message": f"Publishing failed: {e}",
            }

    def reject_queued_item(self, queue_id: int) -> dict:
        """Reject a queued post."""
        queue_item = self.db.get(PostingQueue, queue_id)
        if not queue_item:
            raise ValueError(f"Queue item not found: {queue_id}")
        if queue_item.status != "queued":
            raise ValueError(f"Queue item is not in queued status (current: {queue_item.status})")

        queue_item.status = "rejected"
        self.db.commit()

        draft = self.db.get(ContentDraft, queue_item.content_draft_id)
        account = self.db.get(SocialAccount, queue_item.social_account_id)

        self.logger.log(
            action="content_rejected",
            entity_type="PostingQueue",
            entity_id=queue_item.id,
            details=f"Content '{draft.title if draft else 'Unknown'}' rejected for {account.account_name if account else 'Unknown'}",
        )

        return {
            "queue_id": queue_item.id,
            "status": "rejected",
            "message": "Post has been rejected.",
        }

    # ------------------------------------------------------------------
    # Per-Account Analytics
    # ------------------------------------------------------------------

    def get_account_analytics(self, account_id: int) -> dict:
        """Get analytics for a specific social account."""
        account = self.db.get(SocialAccount, account_id)
        if not account:
            raise ValueError(f"Social account not found: {account_id}")

        # Count posts made through this account
        total_posts = self.db.scalar(
            select(func.count(PostingQueue.id)).where(
                PostingQueue.social_account_id == account_id,
                PostingQueue.status == "published",
            )
        ) or 0

        # Get content drafts posted through this account
        posted_drafts = self.db.scalars(
            select(ContentDraft).where(
                ContentDraft.id.in_(
                    select(PostingQueue.content_draft_id).where(
                        PostingQueue.social_account_id == account_id,
                        PostingQueue.status == "published",
                    )
                )
            )
        ).all()

        # Aggregate clicks and conversions from affiliate links in these drafts
        total_clicks = 0
        total_conversions = 0
        total_earnings = 0.0

        for draft in posted_drafts:
            if draft.affiliate_link_id:
                link = self.db.get(AffiliateLink, draft.affiliate_link_id)
                if link:
                    total_clicks += link.click_count or 0
                    total_conversions += link.conversion_count or 0

                    # Sum commissions from purchases on this link
                    purchases = self.db.scalars(
                        select(Purchase).where(Purchase.link_id == link.id)
                    ).all()
                    for purchase in purchases:
                        from ..models import Commission
                        commission = self.db.scalar(
                            select(Commission).where(Commission.purchase_id == purchase.id)
                        )
                        if commission and commission.status == "confirmed":
                            total_earnings += commission.amount

        conversion_rate = round(
            (total_conversions / total_clicks * 100) if total_clicks > 0 else 0, 2
        )

        return {
            "account_id": account.id,
            "account_name": account.account_name,
            "platform": account.platform,
            "connection_status": account.connection_status,
            "total_posts": total_posts,
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_earnings": round(total_earnings, 2),
            "conversion_rate": conversion_rate,
        }

    def get_all_accounts_analytics(self) -> dict:
        """Get comparative analytics for all social accounts."""
        accounts = self.db.scalars(
            select(SocialAccount).order_by(SocialAccount.created_at.desc())
        ).all()

        account_analytics = []
        total_earnings_all = 0.0
        total_clicks_all = 0
        total_conversions_all = 0

        for account in accounts:
            analytics = self.get_account_analytics(account.id)
            account_analytics.append(analytics)
            total_earnings_all += analytics["total_earnings"]
            total_clicks_all += analytics["total_clicks"]
            total_conversions_all += analytics["total_conversions"]

        # Find top account by earnings
        top_account = None
        if account_analytics:
            top = max(account_analytics, key=lambda a: a["total_earnings"])
            if top["total_earnings"] > 0:
                top_account = top["account_name"]

        return {
            "accounts": account_analytics,
            "top_account": top_account,
            "total_earnings_all": round(total_earnings_all, 2),
            "total_clicks_all": total_clicks_all,
            "total_conversions_all": total_conversions_all,
        }

