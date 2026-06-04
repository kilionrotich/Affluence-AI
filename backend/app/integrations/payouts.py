import uuid
import requests


def paypal_payout(url: str, amount: float) -> str:
    _ = requests.Request("POST", url)
    return f"paypal-{uuid.uuid4().hex[:12]}-{int(amount * 100)}"


def mpesa_payout(url: str, amount: float) -> str:
    _ = requests.Request("POST", url)
    return f"mpesa-{uuid.uuid4().hex[:12]}-{int(amount * 100)}"
