from datetime import datetime
from pydantic import BaseModel, Field


class ScanResponse(BaseModel):
    inserted: int
    products: list[dict]


class PurchaseRequest(BaseModel):
    tracking_code: str
    amount: float | None = Field(default=None, gt=0)


class PurchaseResponse(BaseModel):
    purchase_id: int
    commission_id: int
    commission_amount: float


class ValidateResponse(BaseModel):
    confirmed: int


class PayoutRequest(BaseModel):
    method: str = Field(pattern="^(paypal|mpesa)$")


class PayoutResponse(BaseModel):
    payout_id: int
    amount: float
    method: str
    transaction_ref: str


class ReportResponse(BaseModel):
    daily_earnings: list[dict]
    weekly_earnings: list[dict]
    payouts: list[dict]
    pending_balance: float
    confirmed_balance: float


class CredentialPayload(BaseModel):
    provider: str
    api_key: str


class CommissionRow(BaseModel):
    id: int
    amount: float
    status: str
    eligible_at: datetime


# New Schemas for unimplemented features

class ClickCreate(BaseModel):
    tracking_code: str
    ip_address: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    country: str | None = None


class ClickResponse(BaseModel):
    id: int
    link_id: int
    ip_address: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    country: str | None = None
    clicked_at: datetime


class ContentDraftCreate(BaseModel):
    title: str
    content_type: str = Field(pattern="^(blog|social|newsletter)$")
    platform: str = Field(pattern="^(twitter|linkedin|wordpress|medium)$")
    body: str
    affiliate_link_id: int | None = None
    scheduled_at: datetime | None = None


class ContentDraftResponse(BaseModel):
    id: int
    title: str
    content_type: str
    platform: str
    body: str
    disclosure_added: bool
    compliance_passed: bool
    status: str
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    external_post_id: str | None = None
    error_message: str | None = None
    created_at: datetime


class ContentPublishRequest(BaseModel):
    content_id: int


class ComplianceCheckRequest(BaseModel):
    content_type: str
    platform: str
    content_text: str


class ComplianceCheckResponse(BaseModel):
    passed: bool
    checks: list[dict] = []


class ComplianceRuleCreate(BaseModel):
    platform: str
    rule_name: str
    rule_type: str = Field(pattern="^(disclosure|claim|spam|policy)$")
    pattern: str
    action: str = Field(pattern="^(block|warn|flag)$")
    description: str | None = None


class NotificationResponse(BaseModel):
    id: int
    notification_type: str
    title: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime


class ApprovedChannelCreate(BaseModel):
    platform: str
    channel_name: str
    api_endpoint: str | None = None


class LinkAnalyticsResponse(BaseModel):
    link_id: int
    url: str
    tracking_code: str
    total_clicks: int
    total_conversions: int
    conversion_rate: float
    disclosure_label: str | None = None


class AuditLogResponse(BaseModel):
    id: int
    action: str
    action_category: str | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    details: str | None = None
    ip_address: str | None = None
    user_role: str | None = None
    success: bool
    created_at: datetime


class LogCategoryCount(BaseModel):
    category: str
    count: int


class LogCategoriesResponse(BaseModel):
    categories: list[LogCategoryCount]


class LiveLogEvent(BaseModel):
    """Schema for SSE log stream events."""
    id: int
    action: str
    action_category: str | None = None
    details: str | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    success: bool
    created_at: str  # ISO format


class ScanAutomatedRequest(BaseModel):
    continuous: bool = False
    interval_minutes: int = 60


class LinkValidateRequest(BaseModel):
    link_id: int


class LinkValidateResponse(BaseModel):
    valid: bool
    expires_at: datetime | None = None
    message: str | None = None


class SummaryRequest(BaseModel):
    period: str = Field(default="daily", pattern="^(daily|weekly)$")


class SummaryResponse(BaseModel):
    period: str
    total_earnings: float
    total_commissions: int
    total_payouts: float
    clicks_count: int
    conversions_count: int
    compliance_alerts: int
    message: str


# ---------------------------------------------------------------------------
# Active Social Accounts Module Schemas
# ---------------------------------------------------------------------------

SOCIAL_PLATFORMS = r"^(twitter|facebook|linkedin|instagram|wordpress|mailchimp|tiktok|whatsapp|telegram|youtube|pinterest|reddit|medium|snapchat|discord|other)$"


class SocialAccountCreate(BaseModel):
    platform: str = Field(pattern=SOCIAL_PLATFORMS)
    account_name: str = Field(min_length=1, max_length=128)
    credentials: dict = Field(default_factory=dict, description="API keys, OAuth tokens etc.")
    oauth_token_expires_at: datetime | None = None


class SocialAccountUpdate(BaseModel):
    account_name: str | None = None
    credentials: dict | None = None
    oauth_token_expires_at: datetime | None = None
    is_active: bool | None = None


class SocialAccountResponse(BaseModel):
    id: int
    platform: str
    account_name: str
    connection_status: str
    oauth_token_expires_at: datetime | None = None
    last_verified_at: datetime | None = None
    is_active: bool
    created_at: datetime


class SocialAccountVerifyResponse(BaseModel):
    id: int
    platform: str
    account_name: str
    connection_status: str
    message: str


class PostingModeUpdate(BaseModel):
    mode: str = Field(pattern="^(auto|manual)$")


class PostingModeResponse(BaseModel):
    mode: str
    updated_at: datetime


class PostingQueueResponse(BaseModel):
    id: int
    content_draft_id: int
    social_account_id: int
    posting_mode: str
    status: str
    queued_at: datetime
    approved_at: datetime | None = None
    published_at: datetime | None = None
    content_title: str | None = None
    platform: str | None = None
    account_name: str | None = None


class PostingQueueAction(BaseModel):
    queue_id: int


class AccountAnalyticsResponse(BaseModel):
    account_id: int
    account_name: str
    platform: str
    connection_status: str
    total_posts: int
    total_clicks: int
    total_conversions: int
    total_earnings: float
    conversion_rate: float


class AccountComparativeResponse(BaseModel):
    accounts: list[AccountAnalyticsResponse]
    top_account: str | None = None
    total_earnings_all: float
    total_clicks_all: int
    total_conversions_all: int


# ---------------------------------------------------------------------------
# Morphism Layer Schemas
# ---------------------------------------------------------------------------

class RawFeedItem(BaseModel):
    """A single arbitrary raw feed item (loose key naming accepted)."""
    name: str | None = None
    title: str | None = None
    product_name: str | None = None
    productName: str | None = None
    network: str | None = None
    networkName: str | None = None
    provider: str | None = None
    product_id: str | None = None
    id: str | None = None
    sku: str | None = None
    productId: str | None = None
    price: float | None = None
    sale_price: float | None = None
    amount: float | None = None
    commission_rate: float | None = None
    commissionRate: float | None = None
    rate: float | None = None
    category: str | None = None
    cat: str | None = None
    image_url: str | None = None
    image: str | None = None
    imageUrl: str | None = None
    description: str | None = None
    desc: str | None = None
    url: str | None = None
    affiliate_url: str | None = None
    link: str | None = None
    affiliateUrl: str | None = None


class FeedMorphismRequest(BaseModel):
    """Request body for data morphism: raw feed items to standardize."""
    items: list[RawFeedItem | dict] = Field(default_factory=list)


class ContentMorphismRequest(BaseModel):
    """Request body for content morphism: source product & link."""
    link_id: int
    category: str = "default"


class WorkflowRouteRequest(BaseModel):
    """Request body for workflow morphism: route a validated action."""
    action: str
    validated: bool = True


class AnalyticsMorphismResponse(BaseModel):
    """Output of analytics morphism (actionable insights)."""
    summary: dict
    insights: list[dict]
    trending_products: list[dict]
    morphed_at: str
