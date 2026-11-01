"""Helpers for the admin-editable pages: live business-detail tokens, public rendering, first-run seeding."""
import re
from decimal import Decimal
from html import escape

TOKEN_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")

TOKEN_HELP = [
    ("business_name", "Business name"), ("phone", "Business phone"), ("whatsapp", "WhatsApp number"),
    ("email", "Business email"), ("address", "Business address"), ("opening_hours", "Opening hours"),
    ("delivery_charges_summary", "Delivery fee sentence built from your settings"),
    ("delivery_estimate", "Estimated delivery period"), ("return_window", "Return request period"),
    ("referral_reward", "Referral reward amount"), ("referral_min_order_sentence", "Minimum first-order sentence"),
    ("referral_status", "'active' or 'currently paused'"), ("payment_hold_hours", "Hours before unpaid orders cancel"),
]


def naira(value):
    d = Decimal(value or 0)
    text = f"{d:,.2f}"
    return "₦" + (text[:-3] if text.endswith(".00") else text)


def token_values(biz):
    """Plain-text values for every token, taken from the live BusinessSettings."""
    fee, threshold = Decimal(biz.default_delivery_fee or 0), Decimal(biz.free_delivery_threshold or 0)
    if fee > 0:
        delivery = f"A standard delivery fee of {naira(fee)} applies to orders."
    else:
        delivery = "Any delivery charge is shown at checkout before you pay."
    if threshold > 0:
        delivery += f" Orders of {naira(threshold)} or more qualify for free delivery."
    minimum = Decimal(biz.referral_min_order_amount or 0)
    return {
        "business_name": biz.business_name,
        "phone": biz.phone or "the phone number on our Contact Us page",
        "whatsapp": biz.whatsapp_number or "the WhatsApp contact on our Contact Us page",
        "email": biz.email or "the email address on our Contact Us page",
        "address": biz.address or "our business address on the Contact Us page",
        "opening_hours": (biz.opening_hours or "").replace("\n", ", ") or "the hours shown on our Contact Us page",
        "delivery_charges_summary": delivery,
        "delivery_estimate": biz.delivery_estimate
        or "confirmed by our team when your order is processed, because it depends on your location and the product",
        "return_window": biz.return_window or "the period stated on your order confirmation or given by our team at purchase",
        "referral_reward": naira(biz.referral_reward_amount),
        "referral_min_order_sentence": (
            f"The referred customer's first order must total at least {naira(minimum)}." if minimum > 0
            else "There is currently no minimum order amount for the referred customer's first order."
        ),
        "referral_status": "active" if biz.referral_enabled else "currently paused",
        "payment_hold_hours": str(biz.payment_hold_hours),
    }


def render_tokens(html, values):
    """Replace {{token}} markers with escaped values. Unknown tokens are left visible so the admin can spot typos."""
    return TOKEN_RE.sub(lambda m: escape(values[m.group(1)]) if m.group(1) in values else m.group(0), html or "")


def render_snapshot(snapshot, biz):
    """Return a copy of a page snapshot with tokens filled in, ready for the public templates."""
    values = token_values(biz)
    out = dict(snapshot)
    for key in ("title", "summary"):
        out[key] = TOKEN_RE.sub(lambda m: values.get(m.group(1), m.group(0)), snapshot.get(key, ""))
    out["sections"] = [
        {**s, "title": TOKEN_RE.sub(lambda m: values.get(m.group(1), m.group(0)), s["title"]),
         "body": render_tokens(s["body"], values), "anchor": f"s{i + 1}"}
        for i, s in enumerate(snapshot.get("sections", []))
    ]
    return out


POLICY_SLUGS = [
    "privacy-policy", "delivery-policy", "returns-and-refunds", "payment-policy", "referral-policy",
    "terms-and-conditions",
]


def ensure_pages(only=None):
    """Create any missing default page (published straight away so the site works out of the box).

    Existing pages are never touched, so admin edits are never overwritten.
    """
    from .content_defaults import DEFAULT_PAGES
    from .models import PageSection, SitePage

    created = []
    for pos, (slug, data) in enumerate(DEFAULT_PAGES.items()):
        if only and slug != only:
            continue
        if SitePage.objects.filter(slug=slug).exists():
            continue
        page = SitePage.objects.create(
            slug=slug, kind=data["kind"], title=data["title"], summary=data["summary"], position=pos
        )
        for i, (title, body) in enumerate(data["sections"]):
            PageSection.objects.create(page=page, title=title, body=body, position=i)
        page.publish()
        created.append(slug)
    return created


def get_page(slug):
    from .models import SitePage

    page = SitePage.objects.filter(slug=slug).first()
    if page is None:
        ensure_pages(only=slug)
        page = SitePage.objects.filter(slug=slug).first()
    return page
