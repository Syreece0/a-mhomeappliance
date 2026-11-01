from decimal import Decimal, InvalidOperation

from django.utils.text import slugify


def unique_slug(model, base, instance=None, max_length=190):
    base = slugify(base)[: max_length - 8] or "item"
    slug, n = base, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def parse_decimal(value, default=None):
    try:
        d = Decimal(str(value).replace(",", "").strip())
        return d if d >= 0 else default
    except (InvalidOperation, ValueError, TypeError):
        return default


def parse_int(value, default=None, minimum=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and n < minimum:
        return default
    return n


def abs_url(path_or_url):
    """Return an absolute URL for a site path or a storage URL."""
    from django.conf import settings

    if not path_or_url:
        return ""
    if str(path_or_url).startswith(("http://", "https://")):
        return str(path_or_url)
    return settings.SITE_URL.rstrip("/") + "/" + str(path_or_url).lstrip("/")
