"""Thin Paystack API client. All amounts are exchanged in kobo."""
import hashlib
import hmac
import logging
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.paystack.co"
TIMEOUT = 20


class PaystackError(Exception):
    pass


def to_kobo(amount):
    return int((Decimal(amount) * Decimal("100")).quantize(Decimal("1")))


def _headers():
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError("Paystack secret key is not configured.")
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}


def _request(method, path, **kwargs):
    try:
        resp = requests.request(method, f"{API_BASE}{path}", headers=_headers(), timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        logger.warning("Paystack request failed: %s", exc)
        raise PaystackError("Could not reach Paystack. Please try again.") from exc
    try:
        body = resp.json()
    except ValueError:
        raise PaystackError(f"Unexpected response from Paystack (HTTP {resp.status_code}).")
    return resp.status_code, body


def initialize_transaction(*, email, amount, reference, callback_url, metadata=None):
    status, body = _request(
        "POST",
        "/transaction/initialize",
        json={
            "email": email,
            "amount": to_kobo(amount),
            "currency": "NGN",
            "reference": reference,
            "callback_url": callback_url,
            "metadata": metadata or {},
        },
    )
    if status != 200 or not body.get("status"):
        raise PaystackError(body.get("message") or "Paystack could not initialize the payment.")
    return body["data"]


def verify_transaction(reference):
    """Return Paystack's transaction data, or {'status': 'not_found'} for unknown references."""
    status, body = _request("GET", f"/transaction/verify/{reference}")
    if status == 404 or (not body.get("status") and "not found" in str(body.get("message", "")).lower()):
        return {"status": "not_found"}
    if status != 200 or not body.get("status"):
        raise PaystackError(body.get("message") or "Paystack verification failed.")
    return body["data"]


def verify_signature(raw_body: bytes, signature: str) -> bool:
    """Paystack signs webhooks with HMAC-SHA512 of the raw body using the secret key."""
    if not signature or not settings.PAYSTACK_SECRET_KEY:
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
