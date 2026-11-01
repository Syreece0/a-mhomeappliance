import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from orders.models import Order

from . import paystack, services
from .models import PaymentTransaction, WebhookEvent

logger = logging.getLogger(__name__)


@login_required
@require_POST
def pay(request, number):
    """Start (or retry) payment for one of the customer's own orders."""
    order = get_object_or_404(Order, number=number, user=request.user)
    try:
        url = services.start_payment(order, request.build_absolute_uri(reverse("payments:callback")))
    except services.PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("orders:detail", number=number)
    return redirect(url)


@login_required
@require_GET
def callback(request):
    """Customer returns from Paystack. The query string is never trusted: we verify server-side."""
    reference = request.GET.get("reference") or request.GET.get("trxref") or ""
    txn = get_object_or_404(PaymentTransaction.objects.select_related("order"), reference=reference,
                            order__user=request.user)
    try:
        txn = services.verify_and_process(reference)
    except paystack.PaystackError:
        messages.warning(request, "We could not confirm your payment yet. Use 'Check payment status' in a moment.")
        return redirect("orders:detail", number=txn.order.number)
    if txn.status == PaymentTransaction.SUCCESS:
        messages.success(request, "Payment confirmed. Thank you!")
    elif txn.status == PaymentTransaction.FAILED:
        messages.error(request, "Your payment was not successful. You can retry from this page.")
    elif txn.status == PaymentTransaction.ABANDONED:
        messages.warning(request, "The payment was not completed. You can retry whenever you are ready.")
    else:
        messages.info(request, "Your payment is still being confirmed.")
    return redirect("orders:detail", number=txn.order.number)


@login_required
@require_POST
def recheck(request, number):
    order = get_object_or_404(Order, number=number, user=request.user)
    services.verify_pending_for_order(order)
    order.refresh_from_db()
    if order.paid_at:
        messages.success(request, "Payment confirmed. Thank you!")
    else:
        messages.info(request, "No confirmed payment yet. If you were charged, it can take a few minutes to show.")
    return redirect("orders:detail", number=number)


@csrf_exempt
@require_POST
def webhook(request):
    """Paystack webhook. Authenticated by HMAC signature; payment state still comes from /verify."""
    raw = request.body
    if not paystack.verify_signature(raw, request.headers.get("x-paystack-signature", "")):
        return HttpResponseBadRequest("invalid signature")
    try:
        payload = json.loads(raw)
    except ValueError:
        return HttpResponseBadRequest("invalid payload")

    event = str(payload.get("event", ""))
    data = payload.get("data") or {}
    reference = str(data.get("reference", ""))
    key = f"{event}:{reference}:{data.get('id', '')}"[:160]
    record, created = WebhookEvent.objects.get_or_create(
        event_key=key, defaults={"event": event[:60], "reference": reference[:80], "payload": payload}
    )
    if not created and record.processed:
        return HttpResponse("already processed")

    if event == "charge.success" and reference:
        try:
            services.verify_and_process(reference)
        except PaymentTransaction.DoesNotExist:
            record.error = "Unknown reference"
        except paystack.PaystackError as exc:
            record.error = str(exc)
            record.save(update_fields=["error"])
            return HttpResponse("retry later", status=503)  # ask Paystack to redeliver
        except Exception:
            logger.exception("Webhook processing failed for %s", reference)
            record.error = "processing error"
            record.save(update_fields=["error"])
            return HttpResponse("error", status=500)
    record.processed = True
    record.save(update_fields=["processed", "error"])
    return HttpResponse("ok")
