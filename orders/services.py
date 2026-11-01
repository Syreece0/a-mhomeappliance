import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from cart import services as cart_services
from cart.models import Cart
from core.models import BusinessSettings
from inventory import services as inventory_services
from notifications import events
from referrals import services as referral_services
from referrals.models import Wallet, WalletTransaction

from .models import Order, OrderItem, OrderStatusHistory

logger = logging.getLogger(__name__)


class CheckoutError(Exception):
    pass


class OrderError(Exception):
    pass


TRANSITIONS = {
    Order.PENDING: {Order.CANCELLED},
    Order.PAYMENT_PENDING: {Order.CANCELLED},
    Order.PAID: {Order.PROCESSING, Order.CANCELLED, Order.REFUNDED},
    Order.PROCESSING: {Order.SHIPPED, Order.CANCELLED, Order.REFUNDED},
    Order.SHIPPED: {Order.DELIVERED, Order.REFUNDED},
    Order.DELIVERED: {Order.REFUNDED},
    Order.CANCELLED: {Order.REFUNDED},  # only if it had been paid (checked below)
    Order.REFUNDED: set(),
}


def _history(order, status, note="", by=None):
    OrderStatusHistory.objects.create(order=order, status=status, note=note[:255], created_by=by)


def _flag(order, note):
    order.needs_attention = True
    order.admin_note = f"{order.admin_note}\n{note}".strip()
    order.save(update_fields=["needs_attention", "admin_note", "updated_at"])


def _new_number():
    while True:
        number = f"AM{timezone.now():%y%m%d}{get_random_string(5, 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789')}"
        if not Order.objects.filter(number=number).exists():
            return number


# --------------------------------------------------------------------------- checkout
def build_summary(user, only_product_id=None):
    cart = Cart.objects.filter(user=user).first()
    items = []
    if cart:
        qs = cart.items.select_related("product").prefetch_related("product__images").order_by("id")
        if only_product_id:
            qs = qs.filter(product_id=only_product_id)
        items = list(qs)
    problems = []
    subtotal = Decimal("0")
    for it in items:
        p = it.product
        if not p.is_available or p.stock <= 0:
            problems.append(f"{p.name} is out of stock.")
        elif it.quantity > p.stock:
            problems.append(f"Only {p.stock} of {p.name} left in stock.")
        subtotal += p.price * it.quantity
    biz = BusinessSettings.load()
    delivery = biz.delivery_fee_for(subtotal) if items else Decimal("0")
    total = subtotal + delivery
    wallet = Wallet.objects.filter(user=user).first()
    balance = wallet.balance if wallet else Decimal("0")
    return {
        "items": items,
        "problems": problems,
        "subtotal": subtotal,
        "delivery_fee": delivery,
        "total": total,
        "wallet_balance": balance,
        "wallet_applicable": min(balance, total),
    }


@transaction.atomic
def create_order_from_cart(user, data, use_wallet=False, only_product_id=None):
    """Turn the cart (or one cart line) into an order.

    Wallet credit is debited immediately (a hold) so it cannot be spent twice; it is returned if
    the order is cancelled, expires or is refunded. The cart is NOT touched here - purchased
    items leave the cart only once payment is verified (see finalize_paid_order).
    """
    Cart.objects.select_for_update().filter(user=user).first()  # serialise concurrent checkouts per user
    s = build_summary(user, only_product_id)
    if not s["items"]:
        raise CheckoutError("Your cart is empty.")
    if s["problems"]:
        raise CheckoutError(" ".join(s["problems"]))

    total = s["total"]
    wallet_amount = Decimal("0")
    if use_wallet:
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        wallet_amount = min(wallet.balance, total)
    payable = total - wallet_amount

    order = Order.objects.create(
        number=_new_number(),
        user=user,
        status=Order.PAYMENT_PENDING if payable > 0 else Order.PENDING,
        full_name=data["full_name"],
        email=data["email"],
        phone=data["phone"],
        address=data["address"],
        state=data["state"],
        city=data["city"],
        notes=data.get("notes", ""),
        subtotal=s["subtotal"],
        delivery_fee=s["delivery_fee"],
        wallet_amount=wallet_amount,
        amount_payable=payable,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(order=order, product=i.product, name=i.product.name, unit_price=i.product.price,
                      quantity=i.quantity)
            for i in s["items"]
        ]
    )
    _history(order, order.status, "Order placed", user)

    if wallet_amount > 0:
        referral_services.apply_wallet_entry(
            user, -wallet_amount, WalletTransaction.ORDER_DEBIT, key=f"order-debit:{order.pk}", order=order,
            note=f"Used on order {order.number}",
        )
    if payable == 0:
        finalize_paid_order(order.pk)
        order.refresh_from_db()
    else:
        events.order_received(order)
    return order


# --------------------------------------------------------------------------- payment confirmed
@transaction.atomic
def finalize_paid_order(order_id, txn=None):
    """Everything that must happen exactly once when an order becomes paid.

    Callers must only invoke this after payment was verified with Paystack, or for an order fully
    covered by wallet credit. Idempotent: a second call is a no-op.
    Returns (order, newly_finalized).
    """
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.paid_at:
        return order, False
    if order.status in (Order.CANCELLED, Order.REFUNDED):
        _flag(order, f"Payment arrived after the order was {order.status}. Refund the customer via Paystack.")
        return order, False

    order.status = Order.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at", "updated_at"])
    _history(order, Order.PAID, "Payment confirmed")

    try:
        with transaction.atomic():
            shortages = inventory_services.deduct_for_order(order)
        if shortages:
            _flag(order, "Stock shortage at payment time: " + "; ".join(shortages))
    except Exception:
        logger.exception("Stock deduction failed for order %s", order.number)
        _flag(order, "Stock deduction failed - adjust inventory manually.")

    cart_services.clear_purchased(order)

    from django.db.models import F

    from catalog.models import Product

    for item in order.items.all():
        if item.product_id:
            Product.objects.filter(pk=item.product_id).update(sold_count=F("sold_count") + item.quantity)

    try:
        with transaction.atomic():
            referral_services.qualify_referral_for_order(order)
    except Exception:
        logger.exception("Referral qualification failed for order %s", order.number)
        _flag(order, "Referral qualification failed - review referral records.")

    events.payment_success(order, txn)
    return order, True


# --------------------------------------------------------------------------- cancel / refund / status
@transaction.atomic
def cancel_order(order_id, by=None, note="Order cancelled"):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status in (Order.CANCELLED, Order.REFUNDED):
        return order
    if order.status in (Order.SHIPPED, Order.DELIVERED):
        raise OrderError("A shipped order cannot be cancelled. Use a refund instead.")
    was_paid = order.paid_at is not None
    order.status = Order.CANCELLED
    if was_paid:
        inventory_services.restore_for_order(order)
        if order.amount_payable > 0:
            order.needs_attention = True
            order.admin_note = (
                f"{order.admin_note}\nCancelled after payment: refund {order.amount_payable} to the customer "
                f"through Paystack, then mark the order Refunded."
            ).strip()
    referral_services.reverse_order_wallet(order)
    order.save()
    _history(order, Order.CANCELLED, note, by)
    events.order_status(order)
    return order


@transaction.atomic
def refund_order(order_id, by=None, note="Order refunded"):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.REFUNDED:
        return order
    if order.paid_at is None:
        raise OrderError("Only paid orders can be refunded.")
    if order.status in (Order.PAID, Order.PROCESSING, Order.CANCELLED):
        # goods never left: put them back on the shelf (shipped/delivered stock is adjusted manually)
        inventory_services.restore_for_order(order, reason="return")
    referral_services.reverse_order_wallet(order)
    order.status = Order.REFUNDED
    order.needs_attention = False
    order.save()
    _history(order, Order.REFUNDED, note, by)
    events.order_status(order)
    return order


@transaction.atomic
def set_status(order_id, new_status, by=None, note="", carrier="", tracking_number="", delivery_estimate=""):
    order = Order.objects.select_for_update().get(pk=order_id)
    allowed = TRANSITIONS.get(order.status, set())
    if new_status not in allowed or (
        order.status == Order.CANCELLED and new_status == Order.REFUNDED and order.paid_at is None
    ):
        raise OrderError(f"Cannot change an order from {order.get_status_display()} to {new_status}.")
    if new_status == Order.CANCELLED:
        return cancel_order(order.pk, by, note or "Cancelled by staff")
    if new_status == Order.REFUNDED:
        return refund_order(order.pk, by, note or "Refunded by staff")

    order.status = new_status
    if new_status == Order.SHIPPED:
        order.shipped_at = timezone.now()
        order.carrier = carrier or order.carrier
        order.tracking_number = tracking_number or order.tracking_number
        order.delivery_estimate = delivery_estimate or order.delivery_estimate
    elif new_status == Order.DELIVERED:
        order.delivered_at = timezone.now()
    order.save()
    _history(order, new_status, note, by)
    events.order_status(order)
    return order


def expire_unpaid_orders():
    """Cancel orders whose payment window has passed, releasing held wallet credit."""
    from payments.services import verify_pending_for_order

    hours = BusinessSettings.load().payment_hold_hours
    cutoff = timezone.now() - timedelta(hours=hours)
    expired = 0
    for order in Order.objects.filter(status=Order.PAYMENT_PENDING, paid_at__isnull=True, created_at__lt=cutoff):
        verify_pending_for_order(order)  # the customer may have paid without returning to the site
        order.refresh_from_db()
        if order.status == Order.PAYMENT_PENDING:
            cancel_order(order.pk, note="Payment window expired")
            expired += 1
    return expired
