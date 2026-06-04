import smtplib
from email.message import EmailMessage
import requests

from ..config import get_settings


def send_threshold_alert(balance: float) -> None:
    settings = get_settings()
    text = f"Payout threshold reached. Confirmed balance: {balance:.2f}"

    if settings.smtp_host and settings.alert_email_to and settings.smtp_user and settings.smtp_password:
        msg = EmailMessage()
        msg["Subject"] = "Affiliate payout threshold reached"
        msg["From"] = settings.smtp_user
        msg["To"] = settings.alert_email_to
        msg.set_content(text)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

    if settings.twilio_sid and settings.twilio_token and settings.twilio_from and settings.alert_sms_to:
        requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_sid}/Messages.json",
            data={"From": settings.twilio_from, "To": settings.alert_sms_to, "Body": text},
            auth=(settings.twilio_sid, settings.twilio_token),
            timeout=5,
        )
