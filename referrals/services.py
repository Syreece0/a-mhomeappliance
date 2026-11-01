import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import BusinessSettings

from .models import Referral, ReferralCode, Wallet, WalletTransaction

logger = logging.getLogger(__name__)


class WalletError(Exception):
    pass


class InsufficientBalance(WalletError):
    pass


# --------------------------------------------------------------------------- wallet core
@transaction.atomic
def apply_wallet_entry(user, amount, kind, key=None, order=None, referral=None, note="", by=None):
    """Credit (amount > 0) or debit (amount < 0) a wallet under a row lock.

    * `key` makes the operation idempotent: repeating it returns the original entry.
    * The balance can never become negative (raises InsufficientBalance).
    Returns (transaction, created).
    """
    amount = Decimal(amount)
    if amount == 0:
        raise WalletError("Amount cannot be zero.")
    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
    if key:
        existing = WalletTransaction.objects.filter(idempotency_key=key).first()
        if existing:
            return existing, False
    new_balance = wallet.balance + amount
    if new_balance < 0:
        raise InsufficientBalance("Insufficient referral balance.")
    wallet.balance = new_balance
    if kind == WalletTransaction.REFERRAL_REWARD and amount > 0:
        wallet.total_earned += amount
    elif kind == WalletTransaction.ORDER_DEBIT:
        wallet.total_spent += -amount
    elif kind == WalletTransaction.ORDER_REVERSAL:
        wallet.total_spent = max(Decimal("0"), wallet.total_spent - amount)
    wallet.save()
    entry = WalletTransaction.objects.create(
        wallet=wallet, kind=kind, amount=amount, balance_after=new_balance, idempotency_key=key, order=order,
        referral=referral, note=note[:255], created_by=by,
    )
    return entry, True


def admin_adjust(user, amount, note, by):
    """Manual staff adjustment with an audit entry. Positive = credit, negative = debit."""
    if not note or not note.strip():
        raise WalletError("A reason is required for manual adjustments.")
    kind = WalletTransaction.ADMIN_CREDIT if Decimal(amount) > 0 else WalletTransaction.ADMIN_DEBIT
    return apply_wallet_entry(user, amount, kind, note=note.strip(), by=by)


def reverse_order_wallet(order):
    """Give back the wallet credit an order used (idempotent). Caller saves `order`."""
    if order.wallet_amount > 0 and not order.wallet_reversed:
        apply_wallet_entry(
            order.user, order.wallet_amount, WalletTransaction.ORDER_REVERSAL,
            key=f"order-reversal:{order.pk}", order=order, note=f"Returned from order {order.number}",
        )
        order.wallet_reversed = True


# --------------------------------------------------------------------------- referrals
def attribute_referral(new_user, code):
    """Permanently record who referred `new_user`. No reward is given here."""
    code = (code or "").strip().upper()
    if not code:
        return None
    rc = ReferralCode.objects.select_related("user").filter(code=code).first()
    if rc is None or rc.user_id == new_user.pk:
        return None
    referral, _ = Referral.objects.get_or_create(
        referred=new_user, defaults={"referrer": rc.user, "code_used": code}
    )
    return referral


@transaction.atomic
def qualify_referral_for_order(order):
    """Reward the referrer if `order` is the referred customer's first verified purchase.

    Must only be called after payment verification (or for a confirmed wallet-only order).
    Safe to call repeatedly and concurrently: the referral row is locked, the reward uses an
    idempotency key, and only a PENDING referral can ever be rewarded.
    """
    from orders.models import Order

    referral = Referral.objects.select_for_update().filter(referred_id=order.user_id).first()
    if referral is None or referral.status != Referral.PENDING:
        return None
    if referral.referrer_id == referral.referred_id:
        return None

    is_first = not (
        Order.objects.filter(user_id=order.user_id, paid_at__isnull=False).exclude(pk=order.pk).exists()
    )
    if not is_first:
        # A purchase already happened before this one: this referral can no longer qualify.
        referral.status = Referral.NOT_ELIGIBLE
        referral.note = "Not the referred customer's first purchase."
        referral.save(update_fields=["status", "note"])
        return None

    biz = BusinessSettings.load()
    reason = ""
    if not biz.referral_enabled:
        reason = "Referral programme was disabled at first purchase."
    elif biz.referral_reward_amount <= 0:
        reason = "Reward amount was zero at first purchase."
    elif order.total < biz.referral_min_order_amount:
        reason = "First order was below the minimum order amount."
    if reason:
        referral.status = Referral.NOT_ELIGIBLE
        referral.note = reason
        referral.save(update_fields=["status", "note"])
        return None

    amount = biz.referral_reward_amount
    entry, created = apply_wallet_entry(
        referral.referrer, amount, WalletTransaction.REFERRAL_REWARD, key=f"referral-reward:{referral.pk}",
        order=order, referral=referral, note=f"Referral reward: {referral.referred.display_name}'s first purchase",
    )
    referral.status = Referral.QUALIFIED
    referral.qualified_order = order
    referral.reward_amount = amount
    referral.qualified_at = timezone.now()
    referral.save(update_fields=["status", "qualified_order", "reward_amount", "qualified_at"])
    if created:
        from notifications import events

        events.referral_reward(referral)
    return entry
