from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django import template

register = template.Library()


@register.filter
def naira(value):
    try:
        v = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    s = f"{v:,.2f}"
    if s.endswith(".00"):
        s = s[:-3]
    return f"₦{s}"


@register.filter
def stars(value):
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = 0
    n = max(0, min(5, n))
    return "★" * n + "☆" * (5 - n)


@register.simple_tag
def whatsapp_url(number, text=""):
    if not number:
        return ""
    return f"https://wa.me/{number}?text={quote(text or '')}"


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Return the current query string with the given keys replaced (None removes)."""
    query = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v is None or v == "":
            query.pop(k, None)
        else:
            query[k] = v
    return query.urlencode()


@register.filter
def multiply(a, b):
    try:
        return Decimal(a) * Decimal(b)
    except (InvalidOperation, TypeError, ValueError):
        return ""
