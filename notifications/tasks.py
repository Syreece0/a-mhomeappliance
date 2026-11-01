import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import EmailDelivery
from .services import deliver, enqueue

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


@shared_task(bind=True, max_retries=3)
def send_email_delivery(self, delivery_id):
    delivery = EmailDelivery.objects.filter(pk=delivery_id).first()
    if delivery is None or delivery.status in (EmailDelivery.SENT, EmailDelivery.SKIPPED):
        return
    try:
        deliver(delivery)
    except Exception as exc:
        logger.warning("Email %s failed (attempt %s): %s", delivery_id, delivery.attempts, exc)
        # Eager/dev mode: don't recurse; the periodic task retries later. Real workers back off.
        if self.request.is_eager or self.request.called_directly:
            return
        if delivery.attempts >= MAX_ATTEMPTS:
            return
        raise self.retry(exc=exc, countdown=60 * 2 ** delivery.attempts)


@shared_task
def retry_failed_emails():
    """Re-queue emails that are stuck (queued too long) or failed, up to MAX_ATTEMPTS."""
    cutoff = timezone.now() - timedelta(minutes=5)
    stuck = EmailDelivery.objects.filter(
        status__in=[EmailDelivery.QUEUED, EmailDelivery.FAILED], attempts__lt=MAX_ATTEMPTS, created_at__lt=cutoff
    ).values_list("pk", flat=True)[:200]
    count = 0
    for pk in stuck:
        enqueue(pk)
        count += 1
    return count
