from django.conf import settings
from django.db import models


class InventoryMovement(models.Model):
    SALE = "sale"
    RESTOCK = "restock"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    CANCELLATION = "cancellation"
    REASON_CHOICES = [
        (SALE, "Sale"),
        (RESTOCK, "Restock"),
        (ADJUSTMENT, "Manual adjustment"),
        (RETURN, "Refund / return"),
        (CANCELLATION, "Order cancelled"),
    ]

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="movements")
    change = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="movements")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["product", "-created_at"])]

    def __str__(self):
        return f"{self.product_id}: {self.change:+d} ({self.reason})"
