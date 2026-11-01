import secrets

from django.db import models

from core.validators import validate_image_size


def _token():
    return secrets.token_urlsafe(24)


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    token = models.CharField(max_length=64, unique=True, default=_token, editable=False)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email


class UnsubscribedEmail(models.Model):
    """Global marketing suppression list (covers registered customers too). Transactional mail is unaffected."""

    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Campaign(models.Model):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (DRAFT, "Draft"), (SCHEDULED, "Scheduled"), (SENDING, "Sending"), (SENT, "Sent"), (CANCELLED, "Cancelled"),
    ]

    ALL_OPTED_IN = "opted_in"
    SUBSCRIBERS = "subscribers"
    CUSTOMERS = "customers"
    BUYERS = "buyers"
    AUDIENCE_CHOICES = [
        (ALL_OPTED_IN, "Everyone subscribed (newsletter + opted-in customers)"),
        (SUBSCRIBERS, "Newsletter subscribers only"),
        (CUSTOMERS, "Opted-in registered customers"),
        (BUYERS, "Opted-in customers who have bought before"),
    ]

    name = models.CharField(max_length=140, help_text="Internal name")
    subject = models.CharField(max_length=200)
    message = models.TextField()
    banner = models.ImageField(upload_to="campaigns/", blank=True, validators=[validate_image_size])
    products = models.ManyToManyField("catalog.Product", blank=True, related_name="campaigns")
    discount_info = models.CharField(max_length=200, blank=True, help_text="e.g. 'Up to 30% off until Sunday'")
    button_text = models.CharField(max_length=40, default="Shop Now")
    audience = models.CharField(max_length=15, choices=AUDIENCE_CHOICES, default=ALL_OPTED_IN)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipients_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
