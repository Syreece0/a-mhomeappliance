import logging

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from notifications import events
from orders.models import Order
from orders.services import finalize_paid_order

from . import paystack
from .models import PaymentTransaction

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


def new_reference(order):
    return f"AMP-{order.number}-{get_random_string(8, 'abcdefghijklmnopqrstuvwxyz0123456789')}"


def start_payment(order, callback_url):
    """Create a Paystack transaction for the order's unpaid balance; returns the checkout URL."""
    order.refresh_from_db()
    if order.paid_at:
        raise PaymentError("This order has already been paid.")
    if order.status != Order.PAYMENT_PENDING or order.amount_payable <= 0:
        raise PaymentError("This order is not awaiting payment.")

    # An earlier attempt may have succeeded without the customer returning; settle that first.
    verify_pending_for_order(order)
    order.refresh_from_db()
    if order.paid_at:
        raise PaymentError("Your earlier payment was confirmed - this order is already paid.")

    txn = PaymentTransaction.objects.create(
        order=order, reference=new_reference(order), amount=order.amount_payable
    )
    try:
        data = paystack.initialize_transaction(
            email=order.email,
            amount=txn.amount,
            reference=txn.reference,
            callback_url=callback_url,
            metadata={"order_number": order.number, "order_id": order.pk},
        )
    except paystack.PaystackError as exc:
        txn.status = PaymentTransaction.FAILED
        txn.gateway_response = str(exc)[:255]
        txn.save(update_fields=["status", "gateway_response", "updated_at"])
        raise PaymentError(str(exc)) from exc
    txn.authorization_url = data.get("authorization_url", "")
    txn.access_code = data.get("access_code", "")
    txn.status = PaymentTransaction.PENDING
    txn.save(update_fields=["authorization_url", "access_code", "status", "updated_at"])
    return txn.authorization_url


def verify_and_process(reference):
    """Ask Paystack for the truth about `reference` and apply it. Returns the transaction."""
    data = paystack.verify_transaction(reference)  # raises PaystackError on network trouble
    return apply_verification(reference, data)


def verify_pending_for_order(order):
    qs = order.transactions.filter(
        status__in=[PaymentTransaction.INITIALIZED, PaymentTransaction.PENDING, PaymentTransaction.ABANDONED]
    ).exclude(authorization_url="")
    for txn in qs:
        try:
            verify_and_process(txn.reference)
        except paystack.PaystackError:
            logger.info("Could not verify %s right now", txn.reference)


@transaction.atomic
def apply_verification(reference, data):
    """Apply a Paystack verification payload. Idempotent and safe under concurrent callbacks/webhooks."""
    txn = PaymentTransaction.objects.select_for_update().select_related("order").get(reference=reference)
    if txn.status == PaymentTransaction.SUCCESS:
        return txn

    gateway_status = data.get("status")
    txn.raw_response = data
    txn.gateway_response = str(data.get("gateway_response", ""))[:255]
    txn.channel = str(data.get("channel", ""))[:30]
    if data.get("id"):
        txn.paystack_id = data["id"]

    if gateway_status == "success":
        amount_ok = data.get("amount") == txn.amount_kobo and (data.get("currency") or "NGN") == txn.currency
        if not amount_ok:
            logger.error("Amount/currency mismatch for %s: paystack=%s expected=%s", reference, data.get("amount"),
                         txn.amount_kobo)
            txn.status = PaymentTransaction.FAILED
            txn.gateway_response = "Amount mismatch - payment not accepted"
            txn.save()
            order = txn.order
            order.needs_attention = True
            order.admin_note = f"{order.admin_note}\nPaystack reported a different amount for {reference}.".strip()
            order.save(update_fields=["needs_attention", "admin_note", "updated_at"])
            return txn
        txn.status = PaymentTransaction.SUCCESS
        txn.paid_at = timezone.now()
        txn.save()
        order, newly_paid = finalize_paid_order(txn.order_id, txn)
        if not newly_paid and order.paid_at and txn.paid_at:
            # A different successful transaction already paid this order: a duplicate payment.
            order.needs_attention = True
            order.admin_note = (
                f"{order.admin_note}\nDuplicate payment {reference} received - refund it via Paystack."
            ).strip()
            order.save(update_fields=["needs_attention", "admin_note", "updated_at"])
        return txn

    previous = txn.status
    if gateway_status in ("failed", "reversed"):
        txn.status = PaymentTransaction.FAILED
        txn.save()
        if previous != PaymentTransaction.FAILED:
            events.payment_failed(txn)
    elif gateway_status == "abandoned":
        txn.status = PaymentTransaction.ABANDONED
        txn.save()
    elif gateway_status == "not_found":
        txn.save(update_fields=["raw_response", "updated_at"])
    else:  # ongoing / pending / processing / queued
        txn.status = PaymentTransaction.PENDING
        txn.save()
    return txn
