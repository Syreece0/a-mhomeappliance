import logging

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.utils import abs_url
from notifications.models import EmailDelivery, Notification
from notifications.services import base_context, notify, queue_email

from .models import Campaign, NewsletterSubscriber, UnsubscribedEmail

logger = logging.getLogger(__name__)
SALT = "am-marketing-unsub"


# ------------------------------------------------------------------ preferences
def unsubscribe_token(email):
    return signing.dumps(email.lower(), salt=SALT)


def email_from_token(token):
    try:
        return signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None


def unsubscribe_url(email):
    return abs_url(reverse("marketing:unsubscribe", args=[unsubscribe_token(email)]))


def can_receive_marketing(email):
    """Final gate used at send time: the global suppression list always wins."""
    return not UnsubscribedEmail.objects.filter(email__iexact=email).exists()


@transaction.atomic
def unsubscribe(email):
    email = email.strip().lower()
    UnsubscribedEmail.objects.get_or_create(email=email)
    NewsletterSubscriber.objects.filter(email__iexact=email).update(is_active=False, unsubscribed_at=timezone.now())
    User.objects.filter(email__iexact=email).update(marketing_opt_in=False)


@transaction.atomic
def subscribe(email):
    """Explicit, user-initiated opt-in only. Returns (subscriber, created)."""
    email = email.strip().lower()
    UnsubscribedEmail.objects.filter(email__iexact=email).delete()
    sub, created = NewsletterSubscriber.objects.get_or_create(email=email)
    if not created and not sub.is_active:
        sub.is_active = True
        sub.unsubscribed_at = None
        sub.save(update_fields=["is_active", "unsubscribed_at"])
    return sub, created


# ------------------------------------------------------------------ audience
def audience_emails(campaign):
    suppressed = set(UnsubscribedEmail.objects.values_list("email", flat=True))
    subs = set(NewsletterSubscriber.objects.filter(is_active=True).values_list("email", flat=True))
    customers_qs = User.objects.filter(is_active=True, marketing_opt_in=True)
    if campaign.audience == Campaign.BUYERS:
        customers_qs = customers_qs.filter(orders__paid_at__isnull=False).distinct()
    customers = set(customers_qs.values_list("email", flat=True))

    if campaign.audience == Campaign.SUBSCRIBERS:
        pool = subs
    elif campaign.audience in (Campaign.CUSTOMERS, Campaign.BUYERS):
        pool = customers
    else:
        pool = subs | customers
    return sorted(e for e in pool if e.lower() not in {s.lower() for s in suppressed})


# ------------------------------------------------------------------ rendering / sending
def render_campaign(campaign, unsub_url="#", preview=False):
    products = list(campaign.products.prefetch_related("images")[:8])
    ctx = base_context(
        campaign=campaign,
        banner_url=abs_url(campaign.banner.url) if campaign.banner else "",
        products=[
            {"name": p.name, "price": p.price, "previous_price": p.previous_price if p.discount_percent else None,
             "discount": p.discount_percent, "image": abs_url(p.image_url), "url": abs_url(p.get_absolute_url())}
            for p in products
        ],
        shop_url=abs_url(reverse("catalog:list")),
        unsubscribe_url=unsub_url,
        preview=preview,
    )
    return render_to_string("emails/promotion.html", ctx)


def send_campaign(campaign_id):
    """Queue one email per eligible recipient. Safe against double dispatch (status claim)."""
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
        if campaign.status not in (Campaign.DRAFT, Campaign.SCHEDULED):
            return 0
        campaign.status = Campaign.SENDING
        campaign.save(update_fields=["status"])

    queued = 0
    try:
        for email in audience_emails(campaign):
            link = unsubscribe_url(email)
            html = render_campaign(campaign, unsub_url=link)
            queue_email(
                to=email, subject=campaign.subject, html=html, kind="promotion", marketing=True,
                campaign_id=campaign.pk,
                headers={"List-Unsubscribe": f"<{link}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            )
            queued += 1
        for user in User.objects.filter(email__in=audience_emails(campaign)):
            notify(user, campaign.subject, campaign.discount_info or campaign.message[:140], Notification.PROMO,
                   reverse("catalog:list"))
    except Exception:
        logger.exception("Campaign %s failed part-way", campaign_id)
    finally:
        Campaign.objects.filter(pk=campaign_id).update(
            status=Campaign.SENT, sent_at=timezone.now(), recipients_count=queued
        )
    return queued


def campaign_stats(campaign):
    rows = EmailDelivery.objects.filter(campaign_id=campaign.pk).aggregate(
        total=Count("id"),
        sent=Count("id", filter=Q(status=EmailDelivery.SENT)),
        failed=Count("id", filter=Q(status=EmailDelivery.FAILED)),
        skipped=Count("id", filter=Q(status=EmailDelivery.SKIPPED)),
        queued=Count("id", filter=Q(status=EmailDelivery.QUEUED)),
    )
    return rows
