import re
from decimal import Decimal

from django.core.cache import cache
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .validators import validate_image_size

CACHE_KEY = "am_business_settings_v1"


class BusinessSettings(models.Model):
    """Singleton row holding every admin-editable business setting."""

    business_name = models.CharField(max_length=120, default="A&M Home Appliances")
    logo = models.ImageField(upload_to="branding/", blank=True, validators=[validate_image_size])
    email = models.EmailField(blank=True)
    phone = models.CharField("business phone", max_length=30, blank=True)
    whatsapp_number = models.CharField(
        max_length=30, blank=True, help_text="International format, e.g. 2348012345678 (a leading 0 is treated as Nigeria +234)."
    )
    address = models.TextField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField("X / Twitter URL", blank=True)
    tiktok_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    delivery_info = models.TextField(blank=True)
    opening_hours = models.TextField(
        blank=True, help_text="Shown on the Contact Us page and footer, one line per entry, e.g. 'Mon-Sat: 9am - 6pm'."
    )
    contact_instructions = models.TextField(
        blank=True, help_text="Short note on the Contact Us page, e.g. 'Please quote your order number when you write to us.'"
    )
    delivery_estimate = models.CharField(
        max_length=200, blank=True,
        help_text="Shown in the Delivery Policy, e.g. '2-5 working days within Lagos'. Leave empty if you do not want to state one.",
    )
    return_window = models.CharField(
        max_length=200, blank=True,
        help_text="Shown in the Returns Policy, e.g. '7 days of delivery'. Leave empty to say the period is confirmed at purchase.",
    )
    announcement = models.CharField(
        max_length=255, blank=True, help_text="Shown in a bar at the top of every page. Leave empty to hide."
    )
    default_delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    free_delivery_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"), help_text="Orders at or above this subtotal ship free. 0 disables."
    )
    low_stock_threshold = models.PositiveIntegerField(default=5)
    payment_hold_hours = models.PositiveIntegerField(
        default=24, help_text="Unpaid orders are cancelled (and wallet credit released) after this many hours."
    )

    # referral programme
    referral_enabled = models.BooleanField(default=True)
    referral_reward_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1000"))
    referral_min_order_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"),
        help_text="Referred customer's first order total must be at least this to qualify. 0 = no minimum.",
    )

    # abandoned carts
    abandoned_cart_enabled = models.BooleanField(default=True)
    abandoned_cart_wait_minutes = models.PositiveIntegerField(default=60, help_text="Wait before the first reminder.")
    abandoned_cart_max_reminders = models.PositiveSmallIntegerField(default=2)
    abandoned_cart_interval_hours = models.PositiveIntegerField(default=24, help_text="Gap between reminders.")

    # promotions
    promo_emails_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "business settings"
        verbose_name_plural = "business settings"

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(CACHE_KEY)

    def delete(self, *args, **kwargs):  # singleton: never deleted
        return 0, {}

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def cached(cls):
        obj = cache.get(CACHE_KEY)
        if obj is None:
            obj = cls.load()
            cache.set(CACHE_KEY, obj, 300)
        return obj

    @property
    def whatsapp_digits(self):
        digits = re.sub(r"\D", "", self.whatsapp_number or "")
        if digits.startswith("0") and len(digits) == 11:
            digits = "234" + digits[1:]
        return digits

    def delivery_fee_for(self, subtotal):
        subtotal = Decimal(subtotal)
        if self.free_delivery_threshold and subtotal >= self.free_delivery_threshold:
            return Decimal("0")
        return self.default_delivery_fee


class BannerQuerySet(models.QuerySet):
    def live(self):
        now = timezone.now()
        return (
            self.filter(is_active=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        )


class Banner(models.Model):
    HERO = "hero"
    PROMO = "promo"
    KIND_CHOICES = [(HERO, "Hero slider"), (PROMO, "Promotional banner")]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=HERO)
    title = models.CharField(max_length=140)
    subtitle = models.CharField(max_length=255, blank=True)
    button_text = models.CharField(max_length=40, blank=True)
    link_url = models.CharField(max_length=300, blank=True, help_text="Site path (/shop/) or full URL.")
    image = models.ImageField(upload_to="banners/", blank=True, validators=[validate_image_size])
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BannerQuerySet.as_manager()

    class Meta:
        ordering = ["kind", "position", "-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"


# --------------------------------------------------------------------------- admin-editable pages
class SitePage(models.Model):
    """About Us and the policy pages.

    The admin edits the *working copy* (this row + its PageSection rows). "Publish" freezes a snapshot of it into
    `published_snapshot`; the public site only ever renders that snapshot, so saving a draft can never change what
    visitors see, and the last published version is always preserved.
    """

    ABOUT = "about"
    POLICY = "policy"
    KIND_CHOICES = [(ABOUT, "About page"), (POLICY, "Policy")]

    slug = models.SlugField(max_length=60, unique=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=POLICY)
    title = models.CharField(max_length=140)
    summary = models.TextField(blank=True, max_length=600, help_text="Short description shown under the title.")
    hero_image = models.ImageField(
        upload_to="pages/", blank=True, validators=[validate_image_size], help_text="Optional banner image."
    )
    position = models.PositiveIntegerField(default=0)
    published_snapshot = models.JSONField(null=True, blank=True, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    draft_updated_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False
    )

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.title

    # -- state
    @property
    def is_published(self):
        return self.published_snapshot is not None

    @property
    def has_unpublished_changes(self):
        return self.published_at is None or self.draft_updated_at > self.published_at

    @property
    def status_label(self):
        if not self.is_published:
            return "Draft (never published)"
        return "Published, with unpublished changes" if self.has_unpublished_changes else "Published"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("core:about") if self.slug == "about-us" else reverse("core:policy", args=[self.slug])

    def touch(self, user=None, note=""):
        """Record that the working copy changed (without publishing it)."""
        self.draft_updated_at = timezone.now()
        if user is not None and getattr(user, "pk", None):
            self.updated_by = user
        self.save(update_fields=["draft_updated_at", "updated_by"])
        if note:
            PageRevision.objects.create(page=self, action=PageRevision.DRAFT, note=note[:255], user=self.updated_by)

    # -- snapshots
    def build_snapshot(self):
        sections = []
        for s in self.sections.filter(is_active=True).order_by("position", "id"):
            sections.append({
                "id": s.pk, "title": s.title, "body": s.body,
                "image_url": s.image.url if s.image else "", "image_name": s.image.name if s.image else "",
            })
        return {
            "title": self.title,
            "summary": self.summary,
            "hero_url": self.hero_image.url if self.hero_image else "",
            "hero_name": self.hero_image.name if self.hero_image else "",
            "sections": sections,
        }

    def publish(self, user=None):
        from django.db import transaction

        with transaction.atomic():
            snap = self.build_snapshot()
            self.published_snapshot = snap
            self.published_at = timezone.now()
            self.draft_updated_at = self.published_at
            if user is not None and getattr(user, "pk", None):
                self.updated_by = user
            self.save(update_fields=["published_snapshot", "published_at", "draft_updated_at", "updated_by"])
            PageRevision.objects.create(
                page=self, action=PageRevision.PUBLISHED, note="Published", snapshot=snap, user=self.updated_by
            )

    def discard_draft(self, user=None):
        """Throw away unpublished edits and go back to the last published version."""
        from django.db import transaction

        snap = self.published_snapshot
        if snap is None:
            return False
        with transaction.atomic():
            self.title = snap.get("title", self.title)
            self.summary = snap.get("summary", "")
            self.hero_image.name = snap.get("hero_name", "") or ""
            self.sections.all().delete()
            for pos, s in enumerate(snap.get("sections", [])):
                sec = PageSection(page=self, title=s.get("title", ""), body=s.get("body", ""), position=pos)
                sec.image.name = s.get("image_name", "") or ""
                sec.save()
            self.save(update_fields=["title", "summary", "hero_image"])
            self.touch(user)
            self.draft_updated_at = self.published_at
            self.save(update_fields=["draft_updated_at"])
            PageRevision.objects.create(page=self, action=PageRevision.RESTORED, note="Draft discarded", user=user)
        return True


class PageSection(models.Model):
    page = models.ForeignKey(SitePage, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=140)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to="pages/", blank=True, validators=[validate_image_size])
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Untick to hide this section without deleting it.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.page.title}: {self.title}"


class PageRevision(models.Model):
    """Audit trail of content changes. Published revisions keep a full snapshot."""

    DRAFT, PUBLISHED, RESTORED = "draft", "published", "restored"
    ACTION_CHOICES = [(DRAFT, "Draft saved"), (PUBLISHED, "Published"), (RESTORED, "Draft discarded")]

    page = models.ForeignKey(SitePage, on_delete=models.CASCADE, related_name="revisions")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    snapshot = models.JSONField(null=True, blank=True)
    user = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
