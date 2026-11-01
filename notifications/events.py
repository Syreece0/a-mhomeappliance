"""Backend events -> in-site notification + HTML email.

Every function swallows its own errors: a broken email or notification must never interrupt a
payment, an order or a registration.
"""
import functools
import logging

from django.urls import reverse

from core.utils import abs_url

from .models import Notification
from .services import notify, render_and_queue

logger = logging.getLogger(__name__)


def safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception("Notification event %s failed", fn.__name__)
            return None

    return wrapper


def _order_link(order):
    return reverse("orders:detail", args=[order.number])


def _lines(order):
    return [
        {"name": i.name, "quantity": i.quantity, "unit_price": i.unit_price, "line_total": i.line_total,
         "image": abs_url(i.product.image_url) if i.product_id else ""}
        for i in order.items.select_related("product").prefetch_related("product__images")
    ]


@safe
def welcome(user):
    notify(user, "Welcome to A&M Home Appliances", "Your account is ready. Happy shopping!", Notification.ACCOUNT,
           reverse("catalog:list"))
    render_and_queue(
        to=user.email, subject="Welcome to A&M Home Appliances", template="emails/welcome.html",
        context={"user": user, "shop_url": abs_url(reverse("catalog:list"))}, kind="welcome", user=user,
    )


@safe
def order_received(order):
    notify(order.user, f"Order {order.number} received", "Complete your payment to confirm the order.",
           Notification.ORDER, _order_link(order))
    render_and_queue(
        to=order.email, subject=f"We received your order {order.number}", template="emails/order_received.html",
        context={"order": order, "lines": _lines(order), "pay_url": abs_url(_order_link(order))},
        kind="order_confirmation", user=order.user,
    )


@safe
def payment_success(order, txn=None):
    notify(order.user, "Payment confirmed", f"We received your payment for order {order.number}.",
           Notification.PAYMENT, _order_link(order))
    render_and_queue(
        to=order.email, subject=f"Payment confirmed - order {order.number}", template="emails/payment_success.html",
        context={
            "order": order, "lines": _lines(order), "txn": txn,
            "reference": txn.reference if txn else "Referral wallet credit",
            "paid_on": (txn.paid_at if txn and txn.paid_at else order.paid_at),
            "order_url": abs_url(_order_link(order)),
        },
        kind="payment_success", user=order.user,
    )


@safe
def payment_failed(txn):
    order = txn.order
    notify(order.user, "Payment unsuccessful", f"Your payment for order {order.number} did not go through.",
           Notification.PAYMENT, _order_link(order))
    render_and_queue(
        to=order.email, subject=f"Payment unsuccessful - order {order.number}", template="emails/payment_failed.html",
        context={"order": order, "txn": txn, "retry_url": abs_url(_order_link(order))},
        kind="payment_failed", user=order.user,
    )


STATUS_COPY = {
    "processing": ("We are processing your order", "Your order is being prepared."),
    "shipped": ("Your order has shipped", "Your order is on its way."),
    "delivered": ("Your order was delivered", "Your order has been delivered. Enjoy!"),
    "cancelled": ("Your order was cancelled", "Your order has been cancelled."),
    "refunded": ("Your refund is confirmed", "Your order has been refunded."),
}


@safe
def order_status(order):
    copy = STATUS_COPY.get(order.status)
    if not copy:
        return
    title, message = copy
    notify(order.user, f"{title} ({order.number})", message, Notification.ORDER, _order_link(order))
    render_and_queue(
        to=order.email, subject=f"{title} - {order.number}", template="emails/order_status.html",
        context={"order": order, "lines": _lines(order), "headline": title, "message": message,
                 "order_url": abs_url(_order_link(order))},
        kind=f"order_{order.status}", user=order.user,
    )


@safe
def referral_reward(referral):
    referrer = referral.referrer
    notify(referrer, "You earned a referral reward",
           f"{referral.referred.display_name} made a first purchase. ₦{referral.reward_amount:,.0f} was added to your wallet.",
           Notification.REFERRAL, reverse("referrals:wallet"))
    render_and_queue(
        to=referrer.email, subject="You earned a referral reward", template="emails/referral_reward.html",
        context={"user": referrer, "amount": referral.reward_amount, "friend": referral.referred.display_name,
                 "wallet_url": abs_url(reverse("referrals:wallet"))},
        kind="referral_reward", user=referrer,
    )


@safe
def abandoned_cart(user, items, reminder_number):
    render_and_queue(
        to=user.email, subject="You left something in your cart", template="emails/abandoned_cart.html",
        context={
            "user": user, "reminder_number": reminder_number, "cart_url": abs_url(reverse("cart:detail")),
            "lines": [
                {"name": i.product.name, "quantity": i.quantity, "unit_price": i.product.price,
                 "line_total": i.product.price * i.quantity, "image": abs_url(i.product.image_url)}
                for i in items
            ],
        },
        kind="abandoned_cart", user=user,
    )
