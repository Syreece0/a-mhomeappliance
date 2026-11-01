from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


class Order(models.Model):
    PENDING = "pending"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (PAYMENT_PENDING, "Payment Pending"),
        (PAID, "Paid"),
        (PROCESSING, "Processing"),
        (SHIPPED, "Shipped"),
        (DELIVERED, "Delivered"),
        (CANCELLED, "Cancelled"),
        (REFUNDED, "Refunded"),
    ]

    number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    state = models.CharField(max_length=60)
    city = models.CharField(max_length=80)
    notes = models.TextField(blank=True, verbose_name="delivery instructions")

    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    wallet_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    amount_payable = models.DecimalField(
        max_digits=14, decimal_places=2, help_text="Charged through Paystack (total minus wallet credit)."
    )
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # idempotency / bookkeeping flags
    wallet_reversed = models.BooleanField(default=False)
    stock_deducted = models.BooleanField(default=False)
    stock_restored = models.BooleanField(default=False)
    needs_attention = models.BooleanField(default=False, db_index=True)
    admin_note = models.TextField(blank=True)

    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    delivery_estimate = models.CharField(max_length=150, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(wallet_amount__gte=0), name="order_wallet_non_negative"),
            models.CheckConstraint(condition=Q(amount_payable__gte=0), name="order_payable_non_negative"),
        ]

    def __str__(self):
        return self.number

    @property
    def total(self):
        return self.subtotal + self.delivery_fee

    @property
    def is_paid(self):
        return self.paid_at is not None

    @property
    def can_customer_cancel(self):
        return self.paid_at is None and self.status in (self.PENDING, self.PAYMENT_PENDING)

    @property
    def awaiting_payment(self):
        return self.status == self.PAYMENT_PENDING and self.amount_payable > 0

    PROGRESS_STEPS = [PAID, PROCESSING, SHIPPED, DELIVERED]

    @property
    def progress_index(self):
        """0..3 position in the paid -> delivered journey (-1 if not started)."""
        try:
            return self.PROGRESS_STEPS.index(self.status)
        except ValueError:
            return -1


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", null=True, on_delete=models.SET_NULL, related_name="order_items")
    name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    stock_applied = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=1), name="order_item_quantity_positive")]

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name_plural = "order status history"
