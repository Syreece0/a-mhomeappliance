from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from cart import services as cart_services
from core.models import BusinessSettings
from core.utils import parse_int

from . import services
from .forms import CheckoutForm
from .models import Order


def _initial_for(user):
    return {
        "full_name": user.get_full_name(),
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "state": user.state,
        "city": user.city,
    }


@login_required
def checkout(request):
    only = parse_int(request.POST.get("only_product") or request.GET.get("only"), minimum=1)
    summary = services.build_summary(request.user, only)
    if not summary["items"]:
        messages.info(request, "Your cart is empty.")
        return redirect("cart:detail")

    form = CheckoutForm(request.POST or None, initial={**_initial_for(request.user), "only_product": only or ""})
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        try:
            order = services.create_order_from_cart(
                request.user, cd, use_wallet=cd["use_wallet"], only_product_id=cd.get("only_product")
            )
        except services.CheckoutError as exc:
            messages.error(request, str(exc))
            return redirect("cart:detail")

        if order.amount_payable == 0:
            messages.success(request, f"Order {order.number} placed and paid with your referral wallet.")
            return redirect("orders:detail", number=order.number)

        from payments import services as payment_services

        callback = request.build_absolute_uri(reverse("payments:callback"))
        try:
            url = payment_services.start_payment(order, callback)
        except payment_services.PaymentError as exc:
            messages.error(
                request, f"Your order {order.number} was saved but we could not start the payment: {exc} "
                         "You can retry from the order page."
            )
            return redirect("orders:detail", number=order.number)
        return redirect(url)

    return render(
        request, "orders/checkout.html", {"form": form, "summary": summary, "only": only}
    )


@login_required
@require_POST
def buy_now(request):
    pid = parse_int(request.POST.get("product_id"), minimum=1)
    qty = parse_int(request.POST.get("quantity", 1), default=1, minimum=1)
    if pid is None:
        messages.error(request, "Invalid product.")
        return redirect("catalog:list")
    try:
        cart_services.add_item(request.user, pid, qty)
    except cart_services.CartError as exc:
        messages.error(request, str(exc))
        return redirect(request.META.get("HTTP_REFERER") or "catalog:list")
    return redirect(f"{reverse('orders:checkout')}?only={pid}")


@login_required
def order_list(request):
    page = Paginator(Order.objects.filter(user=request.user).prefetch_related("items"), 10).get_page(
        request.GET.get("page")
    )
    return render(request, "orders/order_list.html", {"page": page})


@login_required
def order_detail(request, number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product", "history", "transactions"), number=number, user=request.user
    )
    biz = BusinessSettings.cached()
    lines = [f"- {i.quantity} x {i.name}" for i in order.items.all()]
    wa_text = f"Hello A&M, I have a question about my order {order.number}:\n" + "\n".join(lines)
    return render(
        request,
        "orders/order_detail.html",
        {"order": order, "wa_text": wa_text, "biz": biz, "steps": [(s, dict(Order.STATUS_CHOICES)[s]) for s in Order.PROGRESS_STEPS]},
    )


@login_required
@require_POST
def cancel(request, number):
    order = get_object_or_404(Order, number=number, user=request.user)
    if not order.can_customer_cancel:
        messages.error(request, "This order can no longer be cancelled online. Please contact us.")
        return redirect("orders:detail", number=number)
    from payments.services import verify_pending_for_order

    verify_pending_for_order(order)  # never cancel an order the customer has actually paid for
    order.refresh_from_db()
    if not order.can_customer_cancel:
        messages.info(request, "Your payment was confirmed, so the order is now being processed.")
        return redirect("orders:detail", number=number)
    services.cancel_order(order.pk, by=request.user, note="Cancelled by customer")
    messages.success(request, f"Order {number} was cancelled. Any referral credit used has been returned.")
    return redirect("orders:detail", number=number)
