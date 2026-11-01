import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_abandoned_cart_reminders():
    """Email customers whose carts have sat idle, honouring the admin-configured schedule."""
    from core.models import BusinessSettings
    from notifications import events

    from .models import Cart

    biz = BusinessSettings.load()
    if not biz.abandoned_cart_enabled or biz.abandoned_cart_max_reminders <= 0:
        return 0

    now = timezone.now()
    sent = 0
    carts = (
        Cart.objects.filter(items__isnull=False, reminders_sent__lt=biz.abandoned_cart_max_reminders)
        .select_related("user")
        .distinct()
    )
    for cart in carts:
        if not cart.user.is_active:
            continue
        if cart.reminders_sent == 0:
            due = cart.updated_at + timedelta(minutes=biz.abandoned_cart_wait_minutes)
        else:
            due = (cart.last_reminder_at or cart.updated_at) + timedelta(hours=biz.abandoned_cart_interval_hours)
        if now < due:
            continue
        # Claim this reminder atomically so overlapping runs never double-send.
        claimed = Cart.objects.filter(pk=cart.pk, reminders_sent=cart.reminders_sent).update(
            reminders_sent=F("reminders_sent") + 1, last_reminder_at=now
        )
        if not claimed:
            continue
        items = [i for i in cart.items.select_related("product").prefetch_related("product__images")
                 if i.product.is_in_stock]
        if not items:
            continue
        try:
            events.abandoned_cart(cart.user, items, cart.reminders_sent + 1)
            sent += 1
        except Exception:
            logger.exception("Abandoned cart reminder failed for cart %s", cart.pk)
    return sent
