from decimal import Decimal

from django.db import models


class PaymentTransaction(models.Model):
    INITIALIZED = "initialized"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"
    STATUS_CHOICES = [
        (INITIALIZED, "Initialized"),
        (PENDING, "Pending"),
        (SUCCESS, "Successful"),
        (FAILED, "Failed"),
        (ABANDONED, "Abandoned"),
    ]

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="transactions")
    reference = models.CharField(max_length=80, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=INITIALIZED, db_index=True)
    gateway_response = models.CharField(max_length=255, blank=True)
    channel = models.CharField(max_length=30, blank=True)
    paystack_id = models.BigIntegerField(null=True, blank=True)
    authorization_url = models.URLField(max_length=500, blank=True)
    access_code = models.CharField(max_length=60, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["order", "-created_at"])]

    def __str__(self):
        return f"{self.reference} ({self.status})"

    @property
    def amount_kobo(self):
        return int((self.amount * Decimal("100")).quantize(Decimal("1")))


class WebhookEvent(models.Model):
    """Every verified Paystack webhook delivery, used to deduplicate retries."""

    event_key = models.CharField(max_length=160, unique=True)
    event = models.CharField(max_length=60)
    reference = models.CharField(max_length=80, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
