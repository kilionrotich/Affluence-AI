import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_db
from .models import (
    AffiliateLink,
    ApiCredential,
    ApprovedChannel,
    Commission,
    ComplianceRule,
    ContentDraft,
    Notification,
    Product,
    Purchase,
    SocialAccount,
    PostingQueue,
    PostingModeConfig,
)
from .schemas import (
    ApprovedChannelCreate,
    ClickCreate,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceRuleCreate,
    ContentDraftCreate,
    ContentDraftResponse,
    ContentPublishRequest,
    CredentialPayload,
    LinkAnalyticsResponse,
    LinkValidateRequest,
    LinkValidateResponse,
    NotificationResponse,
    PayoutRequest,
    PayoutResponse,
    PurchaseRequest,
    PurchaseResponse,
    ReportResponse,
    ScanAutomatedRequest,
    ScanResponse,
    SummaryRequest,
    SummaryResponse,
    ValidateResponse,
    # Active Social Accounts schemas
    SocialAccountCreate,
    SocialAccountUpdate,
    SocialAccountResponse,
    SocialAccountVerifyResponse,
    PostingModeUpdate,
    PostingModeResponse,
    PostingQueueResponse,
    PostingQueueAction,
    AccountAnalyticsResponse,
    AccountComparativeResponse,
    # Log schemas
    AuditLogResponse,
    LogCategoryCount,
    LogCategoriesResponse,
    LiveLogEvent,
    # Morphism schemas
    FeedMorphismRequest,
    ContentMorphismRequest,
    WorkflowRouteRequest,
    AnalyticsMorphismResponse,
)
from .security import EncryptionManager, require_role
from .services import (
    commission_validator,
    link_generator,
    market_scanner,
    purchase_tracker,
    reporting,
    withdrawal_handler,
)
from .services.alerts import send_threshold_alert
from .services.audit_logger import AuditLogger
from .services.click_tracker import ClickTracker
from .services.compliance import ComplianceEngine
from .services.content_distribution import ContentGenerator
from .services.forecasting import CommissionForecaster
from .services.link_validator import LinkValidator
from .services.notification_service import NotificationService
from .services.payout_monitor import balances
from .services.social_account_manager import SocialAccountManager
from .services.posting_controller import PostingController
from .services.morphism import (
    DataMorphism,
    ContentMorphism,
    WorkflowMorphism,
    AnalyticsMorphism,
)
from .ratelimit import RateLimitMiddleware

scheduler = BackgroundScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Existing scheduled jobs
    scheduler.add_job(
        _scheduled_validate,
        "interval",
        minutes=30,
        id="validate",
        replace_existing=True,
    )
    scheduler.add_job(
        _scheduled_threshold_check,
        "interval",
        minutes=15,
        id="threshold_check",
        replace_existing=True,
    )
    # New: automated market scanning
    scheduler.add_job(
        _scheduled_auto_scan,
        "interval",
        minutes=60,
        id="auto_scan",
        replace_existing=True,
    )
    # New: daily summary notifications
    scheduler.add_job(
        _scheduled_daily_summary,
        "cron",
        hour=9,
        minute=0,
        id="daily_summary",
        replace_existing=True,
    )
    # New: weekly summary notifications
    scheduler.add_job(
        _scheduled_weekly_summary,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="weekly_summary",
        replace_existing=True,
    )
    # New: link validation checks
    scheduler.add_job(
        _scheduled_link_validation,
        "interval",
        hours=12,
        id="link_validation",
        replace_existing=True,
    )
    # New: social account token expiry check
    scheduler.add_job(
        _scheduled_token_expiry_check,
        "interval",
        hours=6,
        id="token_expiry_check",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Affluence-AI: Autonomous Affiliate Marketing System", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------------
# Scheduled background jobs
# ---------------------------------------------------------------------------

def _scheduled_validate() -> None:
    db = next(get_db())
    try:
        count = commission_validator.validate_commissions(db)
        if count > 0:
            logger = AuditLogger(db)
            logger.log(
                action="auto_validate",
                entity_type="Commission",
                details=f"Automatically validated {count} commissions",
            )
    finally:
        db.close()


def _scheduled_threshold_check() -> None:
    db = next(get_db())
    try:
        _, confirmed = balances(db)
        settings = get_settings()
        if confirmed >= settings.payout_threshold:
            send_threshold_alert(confirmed)
            notifier = NotificationService(db)
            notifier.create_notification(
                notification_type="threshold_alert",
                title="Payout Threshold Reached",
                message=f"Confirmed balance of ${confirmed:.2f} has reached the payout threshold.",
                severity="info",
            )
    finally:
        db.close()


def _scheduled_auto_scan() -> None:
    """Automated market scanning every hour."""
    db = next(get_db())
    try:
        products = market_scanner.scan_market(db)
        links = [link_generator.ensure_link(db, p.id) for p in products]
        logger = AuditLogger(db)
        logger.log_scan(len(products))
        notifier = NotificationService(db)
        if len(products) > 0:
            notifier.create_notification(
                notification_type="auto_scan",
                title=f"Auto-Scan Complete: {len(products)} Products Found",
                message=f"Affiliate market scan found {len(products)} new/updated products.",
                severity="info",
            )
    finally:
        db.close()


def _scheduled_daily_summary() -> None:
    """Send daily summary to user."""
    db = next(get_db())
    try:
        notifier = NotificationService(db)
        notifier.send_daily_summary()
    finally:
        db.close()


def _scheduled_weekly_summary() -> None:
    """Send weekly summary to user."""
    db = next(get_db())
    try:
        notifier = NotificationService(db)
        notifier.send_weekly_summary()
    finally:
        db.close()


def _scheduled_link_validation() -> None:
    """Check all affiliate links for expiration every 12 hours."""
    db = next(get_db())
    try:
        validator = LinkValidator(db)
        expired = validator.check_expired_links()
        if expired:
            logger = AuditLogger(db)
            logger.log(
                action="auto_link_validation",
                entity_type="AffiliateLink",
                details=f"Found {len(expired)} expired links requiring renewal",
                success=False,
            )
            notifier = NotificationService(db)
            notifier.create_notification(
                notification_type="link_expiry",
                title=f"{len(expired)} Affiliate Links Expired",
                message=f"The following links have expired: {', '.join(e['product_name'] or 'Unknown' for e in expired)}",
                severity="warning",
            )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def enforce_https(request: Request, call_next):
    if get_settings().require_https and request.url.scheme != "https":
        raise HTTPException(status_code=400, detail="HTTPS is required")
    return await call_next(request)


# ---------------------------------------------------------------------------
# Health check (used by Render healthCheckPath)
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Existing API Endpoints (Enhanced)
# ---------------------------------------------------------------------------

@app.post("/scan", response_model=ScanResponse)
def scan(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    products = market_scanner.scan_market(db)
    links = [link_generator.ensure_link(db, p.id) for p in products]

    # Audit logging
    logger = AuditLogger(db)
    logger.log_scan(len(products))

    return {
        "inserted": len(products),
        "products": [
            {
                "id": p.id,
                "network": p.network,
                "product_id": p.product_id,
                "name": p.name,
                "price": p.price,
                "commission_rate": p.commission_rate,
                "link": links[idx].url,
                "tracking_code": links[idx].tracking_code,
            }
            for idx, p in enumerate(products)
        ],
    }


@app.post("/purchase", response_model=PurchaseResponse)
def purchase(
    payload: PurchaseRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    settings = get_settings()
    try:
        purchase_row, commission = purchase_tracker.record_purchase(
            db,
            payload.tracking_code,
            payload.amount,
            settings.refund_period_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Audit logging
    logger = AuditLogger(db)
    logger.log_purchase(purchase_row.id, commission.amount)

    return {
        "purchase_id": purchase_row.id,
        "commission_id": commission.id,
        "commission_amount": commission.amount,
    }


@app.post("/validate", response_model=ValidateResponse)
def validate(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    count = commission_validator.validate_commissions(db)
    logger = AuditLogger(db)
    logger.log(
        action="commission_validation",
        entity_type="Commission",
        details=f"Validated {count} commissions",
    )
    return {"confirmed": count}


@app.post("/payout", response_model=PayoutResponse)
def payout(
    payload: PayoutRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    settings = get_settings()
    try:
        result = withdrawal_handler.trigger_payout(
            db, payload.method, settings.payout_threshold
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Audit logging
    logger = AuditLogger(db)
    logger.log_payout(result.id, payload.method, result.amount)

    # Notification
    notifier = NotificationService(db)
    notifier.send_payout_notification(result)

    return {
        "payout_id": result.id,
        "amount": result.amount,
        "method": result.method,
        "transaction_ref": result.transaction_ref,
    }


@app.get("/report", response_model=ReportResponse)
def report(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    base_report = reporting.generate_report(db)
    # Add notifications and compliance health to report
    notifier = NotificationService(db)
    compliance = ComplianceEngine(db)
    notifications = notifier.get_all_notifications(limit=20)
    health = compliance.get_compliance_health_score()

    base_report["notifications"] = [
        {
            "id": n.id,
            "notification_type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "severity": n.severity,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]
    base_report["compliance_health"] = health
    return base_report


@app.post("/credentials")
def save_credential(
    payload: CredentialPayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    enc = EncryptionManager()
    existing = (
        db.query(ApiCredential)
        .filter(ApiCredential.provider == payload.provider)
        .first()
    )
    if existing:
        existing.encrypted_key = enc.encrypt(payload.api_key)
    else:
        db.add(
            ApiCredential(
                provider=payload.provider,
                encrypted_key=enc.encrypt(payload.api_key),
            )
        )
    db.commit()
    return {"status": "stored"}


# ---------------------------------------------------------------------------
# NEW: Click Tracking Endpoints
# ---------------------------------------------------------------------------

@app.post("/click", response_model=dict)
def record_click(
    payload: ClickCreate,
    db: Session = Depends(get_db),
):
    """Record a click on an affiliate link (public endpoint - no auth required)."""
    tracker = ClickTracker(db)
    try:
        click = tracker.record_click(
            tracking_code=payload.tracking_code,
            ip_address=payload.ip_address,
            user_agent=payload.user_agent,
            referrer=payload.referrer,
            country=payload.country,
        )
        return {"id": click.id, "link_id": click.link_id, "clicked_at": click.clicked_at.isoformat()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/analytics/link/{link_id}", response_model=LinkAnalyticsResponse)
def get_link_analytics(
    link_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get analytics for a specific affiliate link."""
    tracker = ClickTracker(db)
    try:
        return tracker.get_link_analytics(link_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/analytics/overview")
def get_overall_analytics(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get overall analytics across all links."""
    tracker = ClickTracker(db)
    return tracker.get_overall_analytics()


@app.get("/analytics/top-links")
def get_top_links(
    limit: int = 10,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get top performing affiliate links."""
    tracker = ClickTracker(db)
    return tracker.get_top_performing_links(limit)


# ---------------------------------------------------------------------------
# NEW: Compliance Enforcement Endpoints
# ---------------------------------------------------------------------------

@app.post("/compliance/check", response_model=ComplianceCheckResponse)
def run_compliance_check(
    payload: ComplianceCheckRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Run compliance checks on content."""
    engine = ComplianceEngine(db)
    passed, checks = engine.check_content_compliance(
        payload.content_type, payload.platform, payload.content_text
    )
    return {"passed": passed, "checks": checks}


@app.post("/compliance/disclosure/auto-tag")
def auto_tag_disclosure(
    content: dict,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Auto-add FTC disclosure to content."""
    engine = ComplianceEngine(db)
    tagged = engine.auto_tag_disclosure(content.get("text", ""), content.get("platform", "blog"))
    return {"original_text": content.get("text"), "tagged_text": tagged}


@app.get("/compliance/health")
def get_compliance_health(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get compliance health score."""
    engine = ComplianceEngine(db)
    return engine.get_compliance_health_score()


@app.post("/compliance/rules")
def create_compliance_rule(
    payload: ComplianceRuleCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Add a custom compliance rule."""
    rule = ComplianceRule(
        platform=payload.platform,
        rule_name=payload.rule_name,
        rule_type=payload.rule_type,
        pattern=payload.pattern,
        action=payload.action,
        description=payload.description,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {
        "id": rule.id,
        "platform": rule.platform,
        "rule_name": rule.rule_name,
        "rule_type": rule.rule_type,
        "action": rule.action,
        "enabled": rule.enabled,
    }


@app.get("/compliance/rules")
def list_compliance_rules(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """List all compliance rules."""
    rules = db.scalars(select(ComplianceRule).order_by(ComplianceRule.created_at.desc())).all()
    return [
        {
            "id": r.id,
            "platform": r.platform,
            "rule_name": r.rule_name,
            "rule_type": r.rule_type,
            "pattern": r.pattern,
            "action": r.action,
            "enabled": r.enabled,
            "description": r.description,
        }
        for r in rules
    ]


@app.put("/compliance/rules/{rule_id}/toggle")
def toggle_compliance_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Enable or disable a compliance rule."""
    rule = db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.enabled = not rule.enabled
    db.commit()
    return {"id": rule.id, "enabled": rule.enabled}


# ---------------------------------------------------------------------------
# NEW: Link Validation Endpoints
# ---------------------------------------------------------------------------

@app.post("/links/validate/{link_id}", response_model=LinkValidateResponse)
def validate_link(
    link_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Validate a specific affiliate link."""
    validator = LinkValidator(db)
    result = validator.validate_link(link_id)
    return {
        "valid": result["valid"],
        "expires_at": result.get("expires_at"),
        "message": result.get("message"),
    }


@app.get("/links/validate/all")
def validate_all_links(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Validate all affiliate links."""
    validator = LinkValidator(db)
    results = validator.validate_all_links()
    valid_count = sum(1 for r in results if r["valid"])
    return {
        "total": len(results),
        "valid": valid_count,
        "invalid": len(results) - valid_count,
        "results": results,
    }


@app.get("/links/expired")
def get_expired_links(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get list of expired links."""
    validator = LinkValidator(db)
    return {"expired_links": validator.check_expired_links()}


@app.post("/links/{link_id}/disclosure")
def add_disclosure_label(
    link_id: int,
    label: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Add or update FTC disclosure label on a link."""
    link = db.get(AffiliateLink, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    validator = LinkValidator(db)
    updated = validator.add_disclosure_label(link, label)
    return {
        "link_id": updated.id,
        "url": updated.url,
        "disclosure_label": updated.disclosure_label,
    }


# ---------------------------------------------------------------------------
# NEW: Content Distribution Endpoints
# ---------------------------------------------------------------------------

@app.post("/content/generate/blog")
def generate_blog_content(
    product_id: int,
    category: str = "default",
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Generate a blog post for a product."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    generator = ContentGenerator(db)
    content = generator.generate_blog_post(product, category)
    return content


@app.post("/content/generate/social")
def generate_social_content(
    product_id: int,
    platform: str = "twitter",
    benefit: str = "improving productivity",
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Generate a social media post for a product."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    generator = ContentGenerator(db)
    post = generator.generate_social_post(product, platform, benefit)
    return {"platform": platform, "content": post}


@app.post("/content/draft", response_model=ContentDraftResponse)
def create_content_draft(
    payload: ContentDraftCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Create a content draft with optional scheduling."""
    generator = ContentGenerator(db)

    # Embed affiliate link if provided
    body = payload.body
    if payload.affiliate_link_id:
        link = db.get(AffiliateLink, payload.affiliate_link_id)
        if link:
            body = generator.embed_affiliate_link(body, link.url)

    # Auto-tag disclosure
    engine = ComplianceEngine(db)
    body = engine.auto_tag_disclosure(body, payload.platform)

    # Run compliance check
    compliance_engine = ComplianceEngine(db)
    passed, checks = compliance_engine.check_content_compliance(
        payload.content_type, payload.platform, body
    )

    draft = generator.create_content_draft(
        title=payload.title,
        content_type=payload.content_type,
        platform=payload.platform,
        body=body,
        affiliate_link_id=payload.affiliate_link_id,
        scheduled_at=payload.scheduled_at,
    )

    # Update compliance status
    draft.compliance_passed = passed
    draft.disclosure_added = True
    db.commit()
    db.refresh(draft)

    # Audit log
    logger = AuditLogger(db)
    logger.log_compliance_check(draft.id, passed, None if passed else str(checks))

    return {
        "id": draft.id,
        "title": draft.title,
        "content_type": draft.content_type,
        "platform": draft.platform,
        "body": draft.body,
        "disclosure_added": draft.disclosure_added,
        "compliance_passed": draft.compliance_passed,
        "status": draft.status,
        "scheduled_at": draft.scheduled_at,
        "published_at": draft.published_at,
        "external_post_id": draft.external_post_id,
        "error_message": draft.error_message,
        "created_at": draft.created_at,
    }


@app.post("/content/publish", response_model=ContentDraftResponse)
def publish_content(
    payload: ContentPublishRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Publish a content draft to its target platform."""
    draft = db.get(ContentDraft, payload.content_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Content draft not found")

    # Ensure compliance before publishing
    if not draft.compliance_passed:
        engine = ComplianceEngine(db)
        passed, checks = engine.check_content_compliance(
            draft.content_type, draft.platform, draft.body
        )
        if not passed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot publish: Content failed compliance checks. "
                f"Run compliance check first.",
            )
        draft.compliance_passed = True

    generator = ContentGenerator(db)
    published = generator.publish_content(draft)

    # Audit log
    logger = AuditLogger(db)
    logger.log_content_publish(published.id, published.platform, published.status)

    # Notification
    if published.status == "published":
        notifier = NotificationService(db)
        notifier.create_notification(
            notification_type="content_published",
            title=f"Content Published: {published.title}",
            message=f"'{published.title}' published to {published.platform}.",
            severity="info",
        )

    return {
        "id": published.id,
        "title": published.title,
        "content_type": published.content_type,
        "platform": published.platform,
        "body": published.body,
        "disclosure_added": published.disclosure_added,
        "compliance_passed": published.compliance_passed,
        "status": published.status,
        "scheduled_at": published.scheduled_at,
        "published_at": published.published_at,
        "external_post_id": published.external_post_id,
        "error_message": published.error_message,
        "created_at": published.created_at,
    }


@app.get("/content/pending")
def get_pending_content(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get all pending/scheduled content drafts."""
    generator = ContentGenerator(db)
    drafts = generator.get_pending_content()
    return [
        {
            "id": d.id,
            "title": d.title,
            "content_type": d.content_type,
            "platform": d.platform,
            "status": d.status,
            "compliance_passed": d.compliance_passed,
            "scheduled_at": d.scheduled_at,
            "created_at": d.created_at,
        }
        for d in drafts
    ]


@app.get("/content/published")
def get_published_content(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get all published content."""
    generator = ContentGenerator(db)
    drafts = generator.get_published_content()
    return [
        {
            "id": d.id,
            "title": d.title,
            "content_type": d.content_type,
            "platform": d.platform,
            "external_post_id": d.external_post_id,
            "published_at": d.published_at,
        }
        for d in drafts
    ]


# ---------------------------------------------------------------------------
# NEW: Notification Endpoints
# ---------------------------------------------------------------------------

@app.get("/notifications")
def get_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get notifications."""
    notifier = NotificationService(db)
    if unread_only:
        notifications = notifier.get_unread_notifications()
    else:
        notifications = notifier.get_all_notifications()
    return [
        {
            "id": n.id,
            "notification_type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "severity": n.severity,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


@app.put("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Mark a notification as read."""
    notifier = NotificationService(db)
    notifier.mark_as_read(notification_id)
    return {"status": "read"}


@app.put("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Mark all notifications as read."""
    notifier = NotificationService(db)
    notifier.mark_all_as_read()
    return {"status": "all_read"}


# ---------------------------------------------------------------------------
# NEW: Summary Endpoints
# ---------------------------------------------------------------------------

@app.post("/summary", response_model=SummaryResponse)
def generate_summary(
    payload: SummaryRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Generate a summary report."""
    notifier = NotificationService(db)

    if payload.period == "daily":
        summary = notifier.send_daily_summary()
    else:
        summary = notifier.send_weekly_summary()

    return {
        "period": summary["period"],
        "total_earnings": summary["total_earnings"],
        "total_commissions": summary["total_commissions"],
        "total_payouts": summary["total_payouts"],
        "clicks_count": summary["clicks_count"],
        "conversions_count": summary["conversions_count"],
        "compliance_alerts": summary["compliance_alerts"],
        "message": f"{payload.period.capitalize()} summary generated and sent.",
    }


# ---------------------------------------------------------------------------
# NEW: Approved Channels Endpoints
# ---------------------------------------------------------------------------

@app.post("/channels")
def add_approved_channel(
    payload: ApprovedChannelCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Add an approved distribution channel."""
    channel = ApprovedChannel(
        platform=payload.platform,
        channel_name=payload.channel_name,
        api_endpoint=payload.api_endpoint,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return {
        "id": channel.id,
        "platform": channel.platform,
        "channel_name": channel.channel_name,
        "is_active": channel.is_active,
    }


@app.get("/channels")
def list_approved_channels(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """List approved distribution channels."""
    channels = db.scalars(
        select(ApprovedChannel).order_by(ApprovedChannel.created_at.desc())
    ).all()
    return [
        {
            "id": c.id,
            "platform": c.platform,
            "channel_name": c.channel_name,
            "is_active": c.is_active,
            "api_endpoint": c.api_endpoint,
        }
        for c in channels
    ]


@app.put("/channels/{channel_id}/toggle")
def toggle_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Enable or disable an approved channel."""
    channel = db.get(ApprovedChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel.is_active = not channel.is_active
    db.commit()
    return {"id": channel.id, "is_active": channel.is_active}


# ---------------------------------------------------------------------------
# ENHANCED: Audit Log & System Logs Endpoints
# ---------------------------------------------------------------------------

@app.get("/audit-logs", response_model=list[AuditLogResponse])
def get_audit_logs(
    action: str | None = Query(None, description="Filter by action name"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    action_category: str | None = Query(None, description="Filter by category (scanning, validation, posting, payment, compliance, system)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Get audit logs with optional filtering by action, entity type, or action category."""
    logger = AuditLogger(db)
    logs = logger.get_logs(action=action, entity_type=entity_type, action_category=action_category, limit=limit)
    return [
        {
            "id": log.id,
            "action": log.action,
            "action_category": log.action_category,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "user_role": log.user_role,
            "success": log.success,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@app.get("/audit-logs/recent", response_model=list[AuditLogResponse])
def get_recent_audit_logs(
    minutes: int = Query(60, description="Lookback window in minutes"),
    action_category: str | None = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Get recent audit logs with optional category filter."""
    logger = AuditLogger(db)
    if action_category:
        logs = logger.get_logs(action_category=action_category, limit=500)
    else:
        logs = logger.get_recent_actions(minutes=minutes)
    return [
        {
            "id": log.id,
            "action": log.action,
            "action_category": log.action_category,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "user_role": log.user_role,
            "success": log.success,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@app.get("/logs/categories", response_model=LogCategoriesResponse)
def get_log_categories(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get log counts grouped by action category."""
    logger = AuditLogger(db)
    categories = logger.get_categories()
    # Always return all categories even if count is 0
    all_cats = {c: 0 for c in AuditLog.ACTION_CATEGORIES}
    for c in categories:
        all_cats[c["category"]] = c["count"]
    return {
        "categories": [
            {"category": cat, "count": count}
            for cat, count in all_cats.items()
        ]
    }


# ── SSE Real-Time Log Stream ──────────────────────────────────────────

@app.get("/logs/stream")
async def stream_system_logs(
    request: Request,
    action_category: str | None = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Server-Sent Events endpoint for real-time log streaming.

    Clients connect to this endpoint and receive log events as they occur.
    Supports optional filtering by action_category.
    """
    last_id = db.scalar(select(func.max(AuditLog.id))) or 0

    async def event_generator():
        nonlocal last_id
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                # Poll for new log entries
                query = select(AuditLog).where(AuditLog.id > last_id).order_by(AuditLog.id.asc())
                if action_category:
                    query = query.where(AuditLog.action_category == action_category)

                new_logs = list(db.scalars(query.limit(50)).all())

                for log_entry in new_logs:
                    event_data = {
                        "id": log_entry.id,
                        "action": log_entry.action,
                        "action_category": log_entry.action_category,
                        "details": log_entry.details,
                        "entity_type": log_entry.entity_type,
                        "entity_id": log_entry.entity_id,
                        "success": log_entry.success,
                        "created_at": log_entry.created_at.isoformat(),
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_id = log_entry.id

                # Send keepalive comment every 3 seconds
                yield f": keepalive\n\n"
                await asyncio.sleep(3)

            except Exception:
                yield f"event: error\ndata: {json.dumps({'error': 'Internal stream error'})}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# NEW: Commission Forecasting Endpoints
# ---------------------------------------------------------------------------

@app.get("/forecast")
def get_commission_forecast(
    period: str = "monthly",
    months: int = 3,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get commission forecast for the specified period."""
    forecaster = CommissionForecaster(db)
    forecast = forecaster.forecast_commissions(period=period, months=months)
    return forecast


@app.get("/forecast/trends")
def get_commission_trends(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get commission trends and insights."""
    forecaster = CommissionForecaster(db)
    trends = forecaster.get_trends()
    return trends


@app.get("/forecast/summary")
def get_forecast_summary(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get a summary of forecast insights."""
    forecaster = CommissionForecaster(db)
    return forecaster.get_summary()


# ---------------------------------------------------------------------------
# NEW: Multi-Network Dashboard Endpoints (Phase 7)
# ---------------------------------------------------------------------------

@app.get("/earnings/by-network")
def get_earnings_by_network(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get earnings breakdown by affiliate network."""
    results = (
        db.execute(
            select(
                Product.network,
                func.count(Commission.id).label("commission_count"),
                func.coalesce(func.sum(Commission.amount), 0).label("total_amount"),
                func.count(Purchase.id).label("purchase_count"),
            )
            .select_from(Commission)
            .join(Purchase, Commission.purchase_id == Purchase.id)
            .join(AffiliateLink, Purchase.link_id == AffiliateLink.id)
            .join(Product, AffiliateLink.product_id == Product.id)
            .group_by(Product.network)
        )
        .all()
    )

    return [
        {
            "network": r.network,
            "total_earnings": float(r.total_amount),
            "commission_count": r.commission_count,
            "purchase_count": r.purchase_count,
            "average_commission": float(r.total_amount) / r.commission_count if r.commission_count > 0 else 0,
        }
        for r in results
    ]


@app.get("/earnings/timeline")
def get_earnings_timeline(
    days: int = 30,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get earnings timeline for charting."""
    since = datetime.utcnow() - timedelta(days=days)

    results = (
        db.execute(
            select(
                func.date(Commission.confirmed_at).label("date"),
                func.coalesce(func.sum(Commission.amount), 0).label("earnings"),
                func.count(Commission.id).label("commissions"),
            )
            .where(Commission.confirmed_at >= since)
            .group_by(func.date(Commission.confirmed_at))
            .order_by(func.date(Commission.confirmed_at))
        )
        .all()
    )

    return [
        {"date": str(r.date), "earnings": float(r.earnings), "commissions": r.commissions}
        for r in results
    ]


@app.get("/earnings/by-channel")
def get_earnings_by_channel(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get earnings breakdown by content platform/channel."""
    results = (
        db.execute(
            select(
                ContentDraft.platform,
                func.count(Click.id).label("clicks"),
                func.count(Purchase.id).label("conversions"),
            )
            .select_from(ContentDraft)
            .outerjoin(AffiliateLink, ContentDraft.affiliate_link_id == AffiliateLink.id)
            .outerjoin(Click, Click.link_id == AffiliateLink.id)
            .outerjoin(Purchase, Purchase.link_id == AffiliateLink.id)
            .group_by(ContentDraft.platform)
        )
        .all()
    )

    return [
        {
            "platform": r.platform,
            "clicks": r.clicks,
            "conversions": r.conversions,
            "conversion_rate": round((r.conversions / r.clicks * 100) if r.clicks > 0 else 0, 2),
        }
        for r in results
    ]


@app.post("/auto/execute")
def execute_autonomous_workflow(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Execute the full autonomous affiliate workflow:
    1. Scan markets for new products
    2. Generate content for new products
    3. Check compliance
    4. Publish content (if compliance passes)
    5. Generate summary
    """
    logger = AuditLogger(db)
    notifier = NotificationService(db)
    results = {
        "scan": None,
        "content_generated": 0,
        "content_published": 0,
        "compliance_failures": 0,
        "errors": [],
    }

    # Step 1: Scan markets
    try:
        products = market_scanner.scan_market(db)
        links = [link_generator.ensure_link(db, p.id) for p in products]
        results["scan"] = {
            "products_found": len(products),
            "products": [
                {"id": p.id, "name": p.name, "network": p.network} for p in products
            ],
        }
        logger.log_scan(len(products))
    except Exception as e:
        results["errors"].append(f"Scan failed: {e}")
        logger.log_error("auto_scan", str(e))

    # Step 2 & 3: Generate content and check compliance
    if results["scan"] and results["scan"]["products_found"] > 0:
        generator = ContentGenerator(db)
        compliance_engine = ComplianceEngine(db)

        for product in products:
            try:
                # Generate blog post
                content = generator.generate_blog_post(product)
                link = links[products.index(product)]

                # Embed link and add disclosure
                body = generator.embed_affiliate_link(content["body"], link.url)
                body = compliance_engine.auto_tag_disclosure(body, "blog")

                # Check compliance
                passed, checks = compliance_engine.check_content_compliance(
                    "blog", "wordpress", body
                )

                # Create draft
                draft = generator.create_content_draft(
                    title=content["title"],
                    content_type="blog",
                    platform="wordpress",
                    body=body,
                    affiliate_link_id=link.id,
                )
                draft.compliance_passed = passed
                draft.disclosure_added = True
                db.commit()

                if not passed:
                    results["compliance_failures"] += 1
                    logger.log_compliance_check(draft.id, False, str(checks))
                else:
                    # Step 4: Publish (mock)
                    published = generator.publish_content(draft)
                    if published.status == "published":
                        results["content_published"] += 1
                        logger.log_content_publish(published.id, "wordpress", "published")

                results["content_generated"] += 1

            except Exception as e:
                results["errors"].append(f"Content generation failed for {product.name}: {e}")

    # Step 5: Generate summary
    try:
        summary = notifier.send_daily_summary()
        results["summary"] = summary
    except Exception as e:
        results["errors"].append(f"Summary generation failed: {e}")

# Final audit log
    logger.log(
        action="auto_workflow_executed",
        details=f"Generated {results['content_generated']} content pieces, "
        f"published {results['content_published']}, "
        f"{results['compliance_failures']} compliance failures, "
        f"{len(results['errors'])} errors",
    )

    return results


# ---------------------------------------------------------------------------
# Scheduled job: Social Account Token Expiry Check
# ---------------------------------------------------------------------------

def _scheduled_token_expiry_check() -> None:
    """Check all social accounts for expired OAuth tokens every 6 hours."""
    db = next(get_db())
    try:
        manager = SocialAccountManager(db)
        expired = manager.check_expired_tokens()
        if expired:
            logger = AuditLogger(db)
            logger.log(
                action="token_expiry_check",
                entity_type="SocialAccount",
                details=f"Found {len(expired)} accounts with expired tokens",
                success=False,
            )
    finally:
        db.close()


# ===========================================================================
# ACTIVE SOCIAL ACCOUNTS MODULE - API ENDPOINTS
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. Social Account CRUD
# ---------------------------------------------------------------------------

@app.post("/social-accounts", response_model=SocialAccountResponse)
def create_social_account(
    payload: SocialAccountCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Add a new social media account with encrypted credentials."""
    manager = SocialAccountManager(db)
    account = manager.create_account(
        platform=payload.platform,
        account_name=payload.account_name,
        credentials=payload.credentials,
        oauth_token_expires_at=payload.oauth_token_expires_at,
    )

    # Audit log
    logger = AuditLogger(db)
    logger.log(
        action="social_account_created",
        entity_type="SocialAccount",
        entity_id=account.id,
        details=f"Added {payload.platform} account '{payload.account_name}'",
    )

    return {
        "id": account.id,
        "platform": account.platform,
        "account_name": account.account_name,
        "connection_status": account.connection_status,
        "oauth_token_expires_at": account.oauth_token_expires_at,
        "last_verified_at": account.last_verified_at,
        "is_active": account.is_active,
        "created_at": account.created_at,
    }


@app.get("/social-accounts", response_model=list[SocialAccountResponse])
def list_social_accounts(
    platform: str | None = Query(None, description="Filter by platform"),
    active_only: bool = Query(False, description="Show only active accounts"),
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """List all social accounts with filtering options."""
    manager = SocialAccountManager(db)
    accounts = manager.list_accounts(platform=platform, active_only=active_only)
    return [
        {
            "id": a.id,
            "platform": a.platform,
            "account_name": a.account_name,
            "connection_status": a.connection_status,
            "oauth_token_expires_at": a.oauth_token_expires_at,
            "last_verified_at": a.last_verified_at,
            "is_active": a.is_active,
            "created_at": a.created_at,
        }
        for a in accounts
    ]


@app.get("/social-accounts/{account_id}", response_model=SocialAccountResponse)
def get_social_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get details of a specific social account."""
    manager = SocialAccountManager(db)
    account = manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")
    return {
        "id": account.id,
        "platform": account.platform,
        "account_name": account.account_name,
        "connection_status": account.connection_status,
        "oauth_token_expires_at": account.oauth_token_expires_at,
        "last_verified_at": account.last_verified_at,
        "is_active": account.is_active,
        "created_at": account.created_at,
    }


@app.put("/social-accounts/{account_id}", response_model=SocialAccountResponse)
def update_social_account(
    account_id: int,
    payload: SocialAccountUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Update a social account's configuration."""
    manager = SocialAccountManager(db)
    try:
        account = manager.update_account(
            account_id=account_id,
            account_name=payload.account_name,
            credentials=payload.credentials,
            oauth_token_expires_at=payload.oauth_token_expires_at,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Audit log
    logger = AuditLogger(db)
    logger.log(
        action="social_account_updated",
        entity_type="SocialAccount",
        entity_id=account.id,
        details=f"Updated {account.platform} account '{account.account_name}'",
    )

    return {
        "id": account.id,
        "platform": account.platform,
        "account_name": account.account_name,
        "connection_status": account.connection_status,
        "oauth_token_expires_at": account.oauth_token_expires_at,
        "last_verified_at": account.last_verified_at,
        "is_active": account.is_active,
        "created_at": account.created_at,
    }


@app.delete("/social-accounts/{account_id}")
def delete_social_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Remove a social account."""
    manager = SocialAccountManager(db)
    account = manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    platform = account.platform
    name = account.account_name
    manager.remove_account(account_id)

    # Audit log
    logger = AuditLogger(db)
    logger.log(
        action="social_account_deleted",
        entity_type="SocialAccount",
        entity_id=account_id,
        details=f"Removed {platform} account '{name}'",
    )

    return {"status": "deleted", "message": f"{platform} account '{name}' removed."}


# ---------------------------------------------------------------------------
# 2. Connection Verification
# ---------------------------------------------------------------------------

@app.post("/social-accounts/{account_id}/verify", response_model=SocialAccountVerifyResponse)
def verify_social_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Verify connection status for a social account."""
    manager = SocialAccountManager(db)
    try:
        result = manager.verify_connection(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Audit log
    logger = AuditLogger(db)
    logger.log(
        action="social_account_verified",
        entity_type="SocialAccount",
        entity_id=account_id,
        details=f"Verification result: {result['connection_status']}",
    )

    return result


# ---------------------------------------------------------------------------
# 3. Posting Mode Management
# ---------------------------------------------------------------------------

@app.get("/posting-mode", response_model=PostingModeResponse)
def get_posting_mode(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get the current global posting mode (auto/manual)."""
    controller = PostingController(db)
    return controller.get_posting_mode()


@app.put("/posting-mode", response_model=PostingModeResponse)
def update_posting_mode(
    payload: PostingModeUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Set the global posting mode (auto/manual)."""
    controller = PostingController(db)
    return controller.set_posting_mode(payload.mode)


# ---------------------------------------------------------------------------
# 4. Posting Queue Management
# ---------------------------------------------------------------------------

@app.get("/posting-queue", response_model=list[PostingQueueResponse])
def get_posting_queue(
    status: str | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get the posting queue with optional status filter."""
    controller = PostingController(db)
    items = controller.get_queued_items(status=status)
    return items


@app.post("/posting-queue/{queue_id}/approve")
def approve_posting_queue_item(
    queue_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Approve a queued post for publishing."""
    controller = PostingController(db)
    try:
        result = controller.approve_queued_item(queue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.post("/posting-queue/{queue_id}/reject")
def reject_posting_queue_item(
    queue_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Reject a queued post."""
    controller = PostingController(db)
    try:
        result = controller.reject_queued_item(queue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.post("/content/post")
def post_content_to_accounts(
    content_draft_id: int,
    social_account_ids: list[int],
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Post content to selected social accounts (auto or queue based on mode)."""
    controller = PostingController(db)
    try:
        results = controller.process_content_post(content_draft_id, social_account_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"results": results}


# ---------------------------------------------------------------------------
# 5. Account Analytics
# ---------------------------------------------------------------------------

@app.get("/analytics/account/{account_id}", response_model=AccountAnalyticsResponse)
def get_account_analytics(
    account_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get analytics for a specific social account."""
    controller = PostingController(db)
    try:
        return controller.get_account_analytics(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/analytics/accounts", response_model=AccountComparativeResponse)
def get_all_accounts_analytics(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get comparative analytics for all social accounts."""
    controller = PostingController(db)
    return controller.get_all_accounts_analytics()


# ===========================================================================
# MORPHISM LAYER MODULE - API ENDPOINTS
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. Data Morphism: raw feed -> standardized products
# ---------------------------------------------------------------------------

@app.post("/morph/feed")
def morph_feed(
    payload: FeedMorphismRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Transform raw affiliate feed items into standardized product objects."""
    morph = DataMorphism(db)
    result = morph.transform_feed([item.model_dump() if hasattr(item, "model_dump") else item for item in payload.items])
    # Audit into scanning category
    logger = AuditLogger(db)
    logger.log(
        action="data_morphism",
        action_category="scanning",
        entity_type="Product",
        details=f"Data morphism transformed {result['morphed_count']} raw feed items",
        user_role="admin",
    )
    return result


# ---------------------------------------------------------------------------
# 2. Content Morphism: validated link -> multi-format content
# ---------------------------------------------------------------------------

@app.post("/morph/content")
def morph_content(
    payload: ContentMorphismRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Transform a validated affiliate link into multiple content formats."""
    link = db.get(AffiliateLink, payload.link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Affiliate link not found")
    product = link.product
    if not product:
        raise HTTPException(status_code=404, detail="Associated product not found")

    morph = ContentMorphism(db)
    result = morph.transform_content(product, link, payload.category)
    return result


# ---------------------------------------------------------------------------
# 3. Workflow Morphism: validated actions -> execution paths
# ---------------------------------------------------------------------------

@app.get("/morph/workflow")
def get_morph_workflow_map(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Get the current workflow routing map (auto vs manual execution paths)."""
    morph = WorkflowMorphism(db)
    return morph.get_workflow_map()


@app.post("/morph/workflow/route")
def route_morph_workflow_action(
    payload: WorkflowRouteRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin"})),
):
    """Route a validated action to the appropriate execution path."""
    morph = WorkflowMorphism(db)
    return morph.route_action(payload.action, payload.validated)


# ---------------------------------------------------------------------------
# 4. Analytics Morphism: raw data -> actionable insights
# ---------------------------------------------------------------------------

@app.get("/morph/analytics", response_model=AnalyticsMorphismResponse)
def get_morph_analytics(
    db: Session = Depends(get_db),
    _: str = Depends(require_role({"admin", "viewer"})),
):
    """Transform raw click/conversion data into actionable insights (CTR, ROI, trending)."""
    morph = AnalyticsMorphism(db)
    return morph.transform_analytics()


# ===========================================================================
# Static frontend serving (single-service deploy)
# ---------------------------------------------------------------------------
# NOTE: This MUST be registered LAST so it does not shadow the API routes above.
# The SPA catch-all below only handles paths that don't match any API endpoint.
# ===========================================================================

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.isdir(STATIC_DIR):
    # Mount hashed assets (JS/CSS/images) under /assets
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(STATIC_DIR, "assets")),
        name="assets",
    )

    # SPA catch-all: serve index.html for any non-API route.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend not built. Run build.sh first.")
