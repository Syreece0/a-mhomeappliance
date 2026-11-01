from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class ReferralCode(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_code")
    code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class Referral(models.Model):
    """Permanent link between a referring customer and the customer they brought in.

    `referred` is unique: a customer can only ever be attributed to one referrer, and the
    attribution can never be edited after creation. At most one reward exists per referral.
    """

    PENDING = "pending"
    QUALIFIED = "qualified"
    NOT_ELIGIBLE = "not_eligible"
    STATUS_CHOICES = [
        (PENDING, "Pending first purchase"),
        (QUALIFIED, "Rewarded"),
        (NOT_ELIGIBLE, "Not eligible"),
    ]

    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals_made")
    referred = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referred_by")
    code_used = models.CharField(max_length=20)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    qualified_order = models.ForeignKey(
        "orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reward_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qualified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(referrer=F("referred")), name="no_self_referral"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original = Referral.objects.filter(pk=self.pk).values("referrer_id", "referred_id").first()
            if original and (original["referrer_id"] != self.referrer_id or original["referred_id"] != self.referred_id):
                raise ValueError("Referral attribution is permanent and cannot be changed.")
        super().save(*args, **kwargs)


class Wallet(models.Model):
    """Store credit. Never withdrawable; balance can never go negative."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total_earned = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total_spent = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(balance__gte=0), name="wallet_balance_non_negative")]

    def __str__(self):
        return f"Wallet({self.user_id}: {self.balance})"


class WalletTransaction(models.Model):
    REFERRAL_REWARD = "referral_reward"
    ORDER_DEBIT = "order_debit"
    ORDER_REVERSAL = "order_reversal"
    ADMIN_CREDIT = "admin_credit"
    ADMIN_DEBIT = "admin_debit"
    KIND_CHOICES = [
        (REFERRAL_REWARD, "Referral reward"),
        (ORDER_DEBIT, "Used on order"),
        (ORDER_REVERSAL, "Returned from order"),
        (ADMIN_CREDIT, "Admin credit"),
        (ADMIN_DEBIT, "Admin debit"),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text="Positive = credit, negative = debit.")
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="wallet_entries")
    referral = models.ForeignKey(Referral, null=True, blank=True, on_delete=models.SET_NULL, related_name="wallet_entries")
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["wallet", "-created_at"])]
        constraints = [models.CheckConstraint(condition=~Q(amount=0), name="wallet_txn_non_zero")]
