"""Notification Service

Handles all system notifications including compliance alerts,
payout notifications, account warnings, and daily/weekly summaries.
"""
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import List

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    AuditLog,
    Click,
    Commission,
    ContentDraft,
    Notification,
    Payout,
    Purchase,
)
from ..config import get_settings


class NotificationService:
    """Manages all user-facing notifications and summaries."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def create_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "info",
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_unread_notifications(self) -> List[Notification]:
        """Get all unread notifications."""
        return list(
            self.db.scalars(
                select(Notification)
                .where(Notification.is_read == False)
                .order_by(Notification.created_at.desc())
            ).all()
        )

    def get_all_notifications(self, limit: int = 50) -> List[Notification]:
        """Get recent notifications."""
        return list(
            self.db.scalars(
                select(Notification)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            ).all()
        )

    def mark_as_read(self, notification_id: int) -> None:
        """Mark a notification as read."""
        notification = self.db.get(Notification, notification_id)
        if notification:
            notification.is_read = True
            self.db.commit()

    def mark_all_as_read(self) -> None:
        """Mark all notifications as read."""
        self.db.execute(
            Notification.__table__.update().values(is_read=True).where(
                Notification.is_read == False
            )
        )
        self.db.commit()

    def send_payout_notification(self, payout: Payout) -> None:
        """Send notification when a payout is processed."""
        self.create_notification(
            notification_type="payout",
            title=f"Payout Processed: ${payout.amount:.2f}",
            message=(
                f"A payout of ${payout.amount:.2f} has been processed via {payout.method.upper()}. "
                f"Transaction reference: {payout.transaction_ref}"
            ),
            severity="info",
        )

        # Send email alert if configured
        self._send_email(
            subject=f"Payout Processed - {payout.amount:.2f}",
            body=(
                f"Your payout of ${payout.amount:.2f} has been processed.\n\n"
                f"Method: {payout.method.upper()}\n"
                f"Transaction Reference: {payout.transaction_ref}\n"
                f"Date: {payout.created_at.isoformat()}\n\n"
                f"Please check your account for the funds."
            ),
        )

    def send_payout_received_notification(self, payout: Payout) -> None:
        """Send notification when a payout is received."""
        payout.received_at = datetime.utcnow()
        payout.status = "received"
        self.db.commit()

        self.create_notification(
            notification_type="payment_received",
            title=f"Payment Received: ${payout.amount:.2f}",
            message=(
                f"Payment of ${payout.amount:.2f} via {payout.method.upper()} has been received. "
                f"Transaction: {payout.transaction_ref}"
            ),
            severity="info",
        )

        self._send_email(
            subject=f"Payment Received - ${payout.amount:.2f}",
            body=(
                f"Great news! Your payment of ${payout.amount:.2f} has been received.\n\n"
                f"Method: {payout.method.upper()}\n"
                f"Transaction Reference: {payout.transaction_ref}\n"
                f"Date Received: {payout.received_at.isoformat()}\n\n"
                f"Keep up the great work!"
            ),
        )

    def send_compliance_alert(self, title: str, message: str, severity: str = "warning") -> None:
        """Send a compliance-related alert."""
        self.create_notification(
            notification_type="compliance_alert",
            title=title,
            message=message,
            severity=severity,
        )

        self._send_email(
            subject=f"[Compliance Alert] {title}",
            body=f"COMPLIANCE ALERT\n\n{title}\n\n{message}\n\nAction may be required.",
        )

    def send_account_warning(self, platform: str, warning_message: str) -> None:
        """Send notification about account warnings from platforms."""
        self.create_notification(
            notification_type="account_warning",
            title=f"Account Warning: {platform}",
            message=warning_message,
            severity="critical",
        )

        self._send_email(
            subject=f"⚠️ ACCOUNT WARNING: {platform}",
            body=(
                f"An account warning has been detected for {platform}.\n\n"
                f"Warning Details:\n{warning_message}\n\n"
                f"Please take immediate action to resolve this issue."
            ),
        )

    def send_daily_summary(self) -> dict:
        """Generate and send a daily summary of affiliate activity."""
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)

        # Calculate totals for today
        total_earnings = (
            self.db.scalar(
                select(func.coalesce(func.sum(Commission.amount), 0)).where(
                    Commission.created_at >= today,
                    Commission.created_at < tomorrow,
                )
            ) or 0
        )

        total_commissions = (
            self.db.scalar(
                select(func.count(Commission.id)).where(
                    Commission.created_at >= today,
                    Commission.created_at < tomorrow,
                )
            ) or 0
        )

        total_payouts = (
            self.db.scalar(
                select(func.coalesce(func.sum(Payout.amount), 0)).where(
                    Payout.created_at >= today,
                    Payout.created_at < tomorrow,
                )
            ) or 0
        )

        clicks_count = (
            self.db.scalar(
                select(func.count(Click.id)).where(
                    Click.clicked_at >= today,
                    Click.clicked_at < tomorrow,
                )
            ) or 0
        )

        conversions_count = (
            self.db.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.purchased_at >= today,
                    Purchase.purchased_at < tomorrow,
                )
            ) or 0
        )

        compliance_alerts = (
            self.db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.notification_type == "compliance_alert",
                    Notification.created_at >= today,
                    Notification.created_at < tomorrow,
                )
            ) or 0
        )

        summary = {
            "period": "daily",
            "date": today.isoformat(),
            "total_earnings": float(total_earnings),
            "total_commissions": total_commissions,
            "total_payouts": float(total_payouts),
            "clicks_count": clicks_count,
            "conversions_count": conversions_count,
            "compliance_alerts": compliance_alerts,
        }

        # Send email summary
        email_body = (
            f"📊 Daily Affiliate Summary - {today}\n\n"
            f"💰 Total Earnings: ${total_earnings:.2f}\n"
            f"📋 Commissions: {total_commissions}\n"
            f"💸 Payouts: ${total_payouts:.2f}\n"
            f"🖱️ Clicks: {clicks_count}\n"
            f"🛒 Conversions: {conversions_count}\n"
            f"⚠️ Compliance Alerts: {compliance_alerts}\n\n"
            f"Keep up the great work! Check your dashboard for more details."
        )

        self._send_email(subject=f"Daily Summary - {today}", body=email_body)

        # Create notification
        self.create_notification(
            notification_type="daily_summary",
            title=f"Daily Summary - {today}",
            message=email_body,
            severity="info",
        )

        return summary

    def send_weekly_summary(self) -> dict:
        """Generate and send a weekly summary."""
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)

        total_earnings = (
            self.db.scalar(
                select(func.coalesce(func.sum(Commission.amount), 0)).where(
                    Commission.created_at >= week_ago,
                )
            ) or 0
        )

        total_commissions = (
            self.db.scalar(
                select(func.count(Commission.id)).where(
                    Commission.created_at >= week_ago,
                )
            ) or 0
        )

        total_payouts = (
            self.db.scalar(
                select(func.coalesce(func.sum(Payout.amount), 0)).where(
                    Payout.created_at >= week_ago,
                )
            ) or 0
        )

        clicks_count = (
            self.db.scalar(
                select(func.count(Click.id)).where(
                    Click.clicked_at >= week_ago,
                )
            ) or 0
        )

        conversions_count = (
            self.db.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.purchased_at >= week_ago,
                )
            ) or 0
        )

        compliance_alerts = (
            self.db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.notification_type == "compliance_alert",
                    Notification.created_at >= week_ago,
                )
            ) or 0
        )

        summary = {
            "period": "weekly",
            "start_date": week_ago.isoformat(),
            "end_date": today.isoformat(),
            "total_earnings": float(total_earnings),
            "total_commissions": total_commissions,
            "total_payouts": float(total_payouts),
            "clicks_count": clicks_count,
            "conversions_count": conversions_count,
            "compliance_alerts": compliance_alerts,
        }

        email_body = (
            f"📊 Weekly Affiliate Summary ({week_ago} - {today})\n\n"
            f"💰 Total Earnings: ${total_earnings:.2f}\n"
            f"📋 Commissions: {total_commissions}\n"
            f"💸 Payouts: ${total_payouts:.2f}\n"
            f"🖱️ Clicks: {clicks_count}\n"
            f"🛒 Conversions: {conversions_count}\n"
            f"⚠️ Compliance Alerts: {compliance_alerts}\n\n"
            f"Great work this week! Check your dashboard for a detailed breakdown."
        )

        self._send_email(subject=f"Weekly Summary - {today}", body=email_body)

        self.create_notification(
            notification_type="weekly_summary",
            title=f"Weekly Summary ({week_ago} - {today})",
            message=email_body,
            severity="info",
        )

        return summary

    def _send_email(self, subject: str, body: str) -> None:
        """Send an email alert if SMTP is configured."""
        if (
            self.settings.smtp_host
            and self.settings.alert_email_to
            and self.settings.smtp_user
            and self.settings.smtp_password
        ):
            try:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = self.settings.smtp_user
                msg["To"] = self.settings.alert_email_to
                msg.set_content(body)
                with smtplib.SMTP(
                    self.settings.smtp_host, self.settings.smtp_port, timeout=5
                ) as server:
                    server.starttls()
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                    server.send_message(msg)
            except Exception as e:
                # Log email failure but don't crash
                print(f"Email send failed: {e}")

    def _send_sms(self, body: str) -> None:
        """Send an SMS alert if Twilio is configured."""
        if (
            self.settings.twilio_sid
            and self.settings.twilio_token
            and self.settings.twilio_from
            and self.settings.alert_sms_to
        ):
            try:
                requests.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{self.settings.twilio_sid}/Messages.json",
                    data={
                        "From": self.settings.twilio_from,
                        "To": self.settings.alert_sms_to,
                        "Body": body,
                    },
                    auth=(self.settings.twilio_sid, self.settings.twilio_token),
                    timeout=5,
                )
            except Exception as e:
                print(f"SMS send failed: {e}")

