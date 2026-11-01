from django.conf import settings
from django.db import models


class Notification(models.Model):
    ORDER = "order"
    PAYMENT = "payment"
    PROMO = "promo"
    ACCOUNT = "account"
    REFERRAL = "referral"
    ANNOUNCEMENT = "announcement"
    KIND_CHOICES = [
        (ORDER, "Order update"),
        (PAYMENT, "Payment"),
        (PROMO, "Promotion"),
        (ACCOUNT, "Account"),
        (REFERRAL, "Referral"),
        (ANNOUNCEMENT, "Announcement"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=15, choices=KIND_CHOICES, default=ACCOUNT)
    title = models.CharField(max_length=140)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]

    def __str__(self):
        return self.title


class EmailDelivery(models.Model):
    """One row per email we send: the audit trail, delivery stats and retry queue."""

    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    STATUS_CHOICES = [(QUEUED, "Queued"), (SENT, "Sent"), (FAILED, "Failed"), (SKIPPED, "Skipped")]

    TRANSACTIONAL = "transactional"
    MARKETING = "marketing"

    to_email = models.EmailField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject = models.CharField(max_length=255)
    html_body = models.TextField(blank=True)
    text_body = models.TextField(blank=True)
    kind = models.CharField(max_length=40, default=TRANSACTIONAL, db_index=True)
    is_marketing = models.BooleanField(default=False)
    campaign_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    headers = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "attempts", "created_at"])]

    def __str__(self):
        return f"{self.kind} -> {self.to_email} [{self.status}]"
