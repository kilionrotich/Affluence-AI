from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
