"""Social Account Manager Service

Manages multiple social media accounts with encrypted credential storage,
connection verification, and re-authentication alerts.
"""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SocialAccount, Notification
from ..security import EncryptionManager
from ..config import get_settings


class SocialAccountManager:
    """Manages social media account configurations securely."""

    # Platform-specific verification hints for the UI
    PLATFORM_DETAILS = {
        "twitter": {
            "label": "Twitter / X",
            "icon": "🐦",
            "credential_fields": ["api_key", "api_secret", "access_token", "access_secret"],
            "doc_url": "https://developer.twitter.com/en/docs/authentication",
        },
        "facebook": {
            "label": "Facebook",
            "icon": "📘",
            "credential_fields": ["page_id", "access_token"],
            "doc_url": "https://developers.facebook.com/docs/facebook-login",
        },
        "linkedin": {
            "label": "LinkedIn",
            "icon": "💼",
            "credential_fields": ["access_token", "organization_id"],
            "doc_url": "https://docs.microsoft.com/en-us/linkedin/",
        },
        "instagram": {
            "label": "Instagram",
            "icon": "📸",
            "credential_fields": ["business_account_id", "access_token"],
            "doc_url": "https://developers.facebook.com/docs/instagram-api",
        },
        "wordpress": {
            "label": "WordPress",
            "icon": "📝",
            "credential_fields": ["site_url", "username", "password"],
            "doc_url": "https://developer.wordpress.org/",
        },
        "mailchimp": {
            "label": "Mailchimp",
            "icon": "📧",
            "credential_fields": ["api_key", "list_id"],
            "doc_url": "https://mailchimp.com/developer/",
        },
        "tiktok": {
            "label": "TikTok",
            "icon": "🎵",
            "credential_fields": ["access_token", "advertiser_id"],
            "doc_url": "https://developers.tiktok.com/",
        },
        "whatsapp": {
            "label": "WhatsApp",
            "icon": "💬",
            "credential_fields": ["phone_number_id", "access_token", "business_account_id"],
            "doc_url": "https://developers.facebook.com/docs/whatsapp",
        },
        "telegram": {
            "label": "Telegram",
            "icon": "✈️",
            "credential_fields": ["bot_token", "chat_id"],
            "doc_url": "https://core.telegram.org/bots/api",
        },
        "youtube": {
            "label": "YouTube",
            "icon": "▶️",
            "credential_fields": ["api_key", "channel_id", "oauth_token"],
            "doc_url": "https://developers.google.com/youtube",
        },
        "pinterest": {
            "label": "Pinterest",
            "icon": "📌",
            "credential_fields": ["access_token", "board_id"],
            "doc_url": "https://developers.pinterest.com/",
        },
        "reddit": {
            "label": "Reddit",
            "icon": "🤖",
            "credential_fields": ["client_id", "client_secret", "refresh_token"],
            "doc_url": "https://www.reddit.com/dev/api/",
        },
        "medium": {
            "label": "Medium",
            "icon": "✍️",
            "credential_fields": ["integration_token"],
            "doc_url": "https://medium.com/developers",
        },
        "snapchat": {
            "label": "Snapchat",
            "icon": "👻",
            "credential_fields": ["oauth_token", "ad_account_id"],
            "doc_url": "https://developers.snap.com/",
        },
        "discord": {
            "label": "Discord",
            "icon": "💎",
            "credential_fields": ["webhook_url", "bot_token", "channel_id"],
            "doc_url": "https://discord.com/developers/docs",
        },
        "other": {
            "label": "Other Platform",
            "icon": "🔗",
            "credential_fields": ["api_key", "api_secret"],
            "doc_url": None,
        },
    }

    def __init__(self, db: Session):
        self.db = db
        self.encryption = EncryptionManager()
        self.settings = get_settings()

    def create_account(
        self,
        platform: str,
        account_name: str,
        credentials: dict,
        oauth_token_expires_at: Optional[datetime] = None,
    ) -> SocialAccount:
        """Create a new social account with encrypted credentials."""
        encrypted = self.encryption.encrypt(json.dumps(credentials))

        account = SocialAccount(
            platform=platform,
            account_name=account_name,
            encrypted_credentials=encrypted,
            connection_status="pending",
            oauth_token_expires_at=oauth_token_expires_at,
            is_active=True,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)

        # Initial verification attempt
        self.verify_connection(account.id)

        return account

    def update_account(
        self,
        account_id: int,
        account_name: Optional[str] = None,
        credentials: Optional[dict] = None,
        oauth_token_expires_at: Optional[datetime] = None,
        is_active: Optional[bool] = None,
    ) -> SocialAccount:
        """Update an existing social account."""
        account = self.db.get(SocialAccount, account_id)
        if not account:
            raise ValueError(f"Social account not found: {account_id}")

        if account_name is not None:
            account.account_name = account_name
        if credentials is not None:
            account.encrypted_credentials = self.encryption.encrypt(json.dumps(credentials))
        if oauth_token_expires_at is not None:
            account.oauth_token_expires_at = oauth_token_expires_at
        if is_active is not None:
            account.is_active = is_active

        account.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(account)
        return account

    def remove_account(self, account_id: int) -> None:
        """Remove a social account."""
        account = self.db.get(SocialAccount, account_id)
        if not account:
            raise ValueError(f"Social account not found: {account_id}")
        self.db.delete(account)
        self.db.commit()

    def get_account(self, account_id: int) -> Optional[SocialAccount]:
        """Get a single social account."""
        return self.db.get(SocialAccount, account_id)

    def get_decrypted_credentials(self, account: SocialAccount) -> dict:
        """Decrypt and return the credentials for an account."""
        try:
            return json.loads(self.encryption.decrypt(account.encrypted_credentials))
        except Exception:
            return {}

    def list_accounts(self, platform: Optional[str] = None, active_only: bool = False) -> List[SocialAccount]:
        """List all social accounts, optionally filtered."""
        query = select(SocialAccount).order_by(SocialAccount.created_at.desc())

        if platform:
            query = query.where(SocialAccount.platform == platform)
        if active_only:
            query = query.where(SocialAccount.is_active == True)

        return list(self.db.scalars(query).all())

    def verify_connection(self, account_id: int) -> dict:
        """Verify the connection status for a social account.

        In production, this would make actual API calls to each platform
        to validate OAuth tokens / API keys. Here we simulate the check.
        """
        account = self.db.get(SocialAccount, account_id)
        if not account:
            raise ValueError(f"Social account not found: {account_id}")

        creds = self.get_decrypted_credentials(account)
        previous_status = account.connection_status

        # Simulate connection verification based on platform
        # In production, replace with real API calls
        is_valid = self._simulate_verify(account.platform, creds)

        if is_valid:
            account.connection_status = "active"
            account.last_verified_at = datetime.utcnow()
            message = f"{account.platform.title()} account '{account.account_name}' is connected and active."
        else:
            account.connection_status = "suspended"
            message = f"{account.platform.title()} account '{account.account_name}' failed verification. Check credentials."

        # Check for OAuth token expiry
        if account.oauth_token_expires_at and datetime.utcnow() > account.oauth_token_expires_at:
            account.connection_status = "expired"
            message = f"OAuth token for '{account.account_name}' has expired. Re-authentication required."

            # Send re-auth notification
            notification = Notification(
                notification_type="re_auth_required",
                title=f"Re-authentication Required: {account.account_name}",
                message=f"The OAuth token for your {account.platform} account '{account.account_name}' has expired. "
                        f"Please re-authenticate to continue posting.",
                severity="critical",
            )
            self.db.add(notification)

        # Alert if status changed to suspended/expired
        if previous_status == "active" and account.connection_status != "active":
            notification = Notification(
                notification_type="account_status_change",
                title=f"Account Issue: {account.account_name}",
                message=f"Your {account.platform} account '{account.account_name}' status changed from "
                        f"'{previous_status}' to '{account.connection_status}'. {message}",
                severity="warning",
            )
            self.db.add(notification)

        account.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(account)

        return {
            "id": account.id,
            "platform": account.platform,
            "account_name": account.account_name,
            "connection_status": account.connection_status,
            "message": message,
        }

    def verify_all_accounts(self) -> List[dict]:
        """Verify connection for all active accounts."""
        results = []
        accounts = self.list_accounts(active_only=True)
        for account in accounts:
            result = self.verify_connection(account.id)
            results.append(result)
        return results

    def check_expired_tokens(self) -> List[dict]:
        """Check all accounts for expired OAuth tokens and alert."""
        expired_accounts = []
        now = datetime.utcnow()

        accounts = self.db.scalars(
            select(SocialAccount).where(
                SocialAccount.oauth_token_expires_at.isnot(None),
                SocialAccount.oauth_token_expires_at <= now,
                SocialAccount.is_active == True,
            )
        ).all()

        for account in accounts:
            account.connection_status = "expired"
            expired_accounts.append({
                "id": account.id,
                "platform": account.platform,
                "account_name": account.account_name,
                "expired_at": account.oauth_token_expires_at.isoformat() if account.oauth_token_expires_at else None,
            })

            # Create notification
            notification = Notification(
                notification_type="token_expired",
                title=f"Token Expired: {account.account_name}",
                message=f"The OAuth token for {account.platform} account '{account.account_name}' has expired. "
                        f"Please re-authenticate to continue posting.",
                severity="critical",
            )
            self.db.add(notification)

        self.db.commit()
        return expired_accounts

    def get_platform_details(self, platform: str) -> dict:
        """Get platform-specific UI hints."""
        return self.PLATFORM_DETAILS.get(platform, self.PLATFORM_DETAILS["other"])

    def _simulate_verify(self, platform: str, credentials: dict) -> bool:
        """Simulate API verification (placeholder for real API calls).

        In production, this should be replaced with actual platform API calls:
        - Twitter: tweepy API v2
        - Facebook: Graph API
        - LinkedIn: LinkedIn API
        - Instagram: Instagram Basic Display API
        - WordPress: XML-RPC
        - Mailchimp: Mailchimp API
        - TikTok: TikTok Business API
        - WhatsApp: WhatsApp Business API
        - Telegram: Bot API
        - YouTube: YouTube Data API
        - Pinterest: Pinterest API
        - Reddit: Reddit API
        - Medium: Medium API
        - Snapchat: Snapchat API
        - Discord: Discord API
        """
        # Check if required fields are present
        required_fields = self.PLATFORM_DETAILS.get(platform, {}).get("credential_fields", ["api_key"])
        has_all_fields = all(field in credentials and credentials[field] for field in required_fields)

        # In production, return the result of actual API verification
        return has_all_fields

