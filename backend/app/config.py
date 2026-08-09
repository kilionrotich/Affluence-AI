from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Do NOT auto-read a .env file (Render can inject stray values) and ignore
    # any unknown environment variables that aren't declared above.
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_name: str = "Affiliate Commission Agent"
    database_url: str = "sqlite:///./affiliate.db"
    admin_token: str = "admin-token"
    viewer_token: str = "viewer-token"
    encryption_key: str | None = None
    refund_period_days: int = 7
    payout_threshold: float = 50.0
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    alert_email_to: str | None = None
    twilio_sid: str | None = None
    twilio_token: str | None = None
    twilio_from: str | None = None
    alert_sms_to: str | None = None
    paypal_payout_url: str = "https://api-m.sandbox.paypal.com/v1/payments/payouts"
    mpesa_payout_url: str = "https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
    require_https: bool = False
    scan_interval_minutes: int = 60
    content_approval_required: bool = True
    compliance_strict_mode: bool = True
    posting_mode: str = "manual"
    twitter_api_key: str | None = None
    twitter_api_secret: str | None = None
    twitter_access_token: str | None = None
    twitter_access_secret: str | None = None
    linkedin_access_token: str | None = None
    wordpress_url: str | None = None
    wordpress_username: str | None = None
    wordpress_password: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    amazon_paapi_access_key: str | None = None
    amazon_paapi_secret_key: str | None = None
    amazon_paapi_partner_tag: str | None = None
    clickbank_api_key: str | None = None
    sharesale_api_key: str | None = None
    cj_affiliate_api_key: str | None = None
    jumia_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
