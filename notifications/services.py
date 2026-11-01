import logging
 
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
 
from core.models import BusinessSettings
from core.utils import abs_url
 
from .models import EmailDelivery, Notification
 
logger = logging.getLogger(__name__)
 
 
def html_to_text(html):
    """Readable plain-text alternative for an HTML email (decodes entities, keeps link URLs and line breaks)."""
    import re
    from html import unescape
 
    html = re.sub(r"(?is)<(head|style|script)\b.*?</\1>", "", html or "")
    html = re.sub(r'(?is)<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                  lambda m: f"{strip_tags(m.group(2)).strip()} ({m.group(1)})" if strip_tags(m.group(2)).strip()
                  and m.group(1) not in strip_tags(m.group(2)) else strip_tags(m.group(2)), html)
    html = re.sub(r"(?i)<br\s*/?>|</(p|h[1-6]|tr|li|div|table)>", "\n", html)
    text = unescape(strip_tags(html))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
 
 
def notify(user, title, message="", kind=Notification.ACCOUNT, link=""):
    return Notification.objects.create(user=user, kind=kind, title=title[:140], message=message, link=link)
 
 
def base_context(**extra):
    biz = BusinessSettings.cached()
    ctx = {
        "biz": biz,
        "site_url": settings.SITE_URL,
        "logo_url": abs_url(biz.logo.url) if biz.logo else "",
        "year": timezone.now().year,
    }
    ctx.update(extra)
    return ctx
 
 
def queue_email(*, to, subject, html, text="", kind=EmailDelivery.TRANSACTIONAL, user=None, campaign_id=None,
                marketing=False, headers=None):
    """Record an email and hand it to Celery once the surrounding transaction commits.
 
    A failure to enqueue never raises: the row stays queued and the periodic retry task picks it up.
    """
    delivery = EmailDelivery.objects.create(
        to_email=to, user=user, subject=subject[:255], html_body=html, text_body=text or html_to_text(html),
        kind=kind, is_marketing=marketing, campaign_id=campaign_id, headers=headers or {},
    )
    transaction.on_commit(lambda: enqueue(delivery.pk))
    return delivery
 
 
def render_and_queue(*, to, subject, template, context, **kwargs):
    html = render_to_string(template, base_context(**context))
    return queue_email(to=to, subject=subject, html=html, **kwargs)
 
 
def enqueue(delivery_id):
    from .tasks import send_email_delivery
 
    try:
        send_email_delivery.delay(delivery_id)
    except Exception:
        logger.exception("Could not enqueue email %s; it will be retried by the periodic task.", delivery_id)
 
 
def deliver(delivery):
    """Send one EmailDelivery now. Updates its status; raises on SMTP failure."""
    if delivery.status in (EmailDelivery.SENT, EmailDelivery.SKIPPED):
        return delivery
    if delivery.is_marketing:
        from marketing.services import can_receive_marketing
 
        if not can_receive_marketing(delivery.to_email):
            delivery.status = EmailDelivery.SKIPPED
            delivery.error = "Recipient is unsubscribed."
            delivery.save(update_fields=["status", "error"])
            return delivery
    msg = EmailMultiAlternatives(
        subject=delivery.subject,
        body=delivery.text_body or html_to_text(delivery.html_body),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[delivery.to_email],
        headers=delivery.headers or None,
    )
    if delivery.html_body:
        msg.attach_alternative(delivery.html_body, "text/html")
    delivery.attempts += 1
    try:
        msg.send(fail_silently=False)
    except Exception as exc:
        delivery.status = EmailDelivery.FAILED
        delivery.error = str(exc)[:1000]
        delivery.save(update_fields=["status", "error", "attempts"])
        raise
    delivery.status = EmailDelivery.SENT
    delivery.sent_at = timezone.now()
    delivery.error = ""
    delivery.save(update_fields=["status", "sent_at", "error", "attempts"])
    return delivery