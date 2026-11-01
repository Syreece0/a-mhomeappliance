from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.utils import parse_int

from . import services
from .models import CartItem


def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _count(user):
    return CartItem.objects.filter(cart__user=user).aggregate(n=Sum("quantity"))["n"] or 0


def _respond(request, ok, message, fallback="cart:detail"):
    if _wants_json(request):
        payload = {"ok": ok, "message": message}
        if request.user.is_authenticated:
            payload["count"] = _count(request.user)
        return JsonResponse(payload, status=200 if ok else 400)
    (messages.success if ok else messages.error)(request, message)
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect(fallback)


@login_required
def cart_detail(request):
    from core.models import BusinessSettings

    summary = services.summarize(request.user)
    biz = BusinessSettings.cached()
    lines = [f"- {i.quantity} x {i.product.name}" for i in summary["items"]]
    wa_text = "Hello A&M, I would like to order:\n" + "\n".join(lines) if lines else ""
    return render(request, "cart/cart.html", {**summary, "wa_text": wa_text, "biz": biz})


@require_POST
def add_to_cart(request):
    if not request.user.is_authenticated:
        if _wants_json(request):
            return JsonResponse(
                {"ok": False, "login_url": f"{reverse('accounts:login')}?next={request.POST.get('next', '/')}",
                 "message": "Please log in to add items to your cart."},
                status=401,
            )
        messages.info(request, "Please log in to add items to your cart.")
        return redirect(f"{reverse('accounts:login')}?next={request.POST.get('next', '/')}")
    pid = parse_int(request.POST.get("product_id"), minimum=1)
    qty = parse_int(request.POST.get("quantity", 1), default=1, minimum=1)
    if pid is None:
        return _respond(request, False, "Invalid product.")
    try:
        item = services.add_item(request.user, pid, qty)
    except services.CartError as exc:
        return _respond(request, False, str(exc))
    return _respond(request, True, f"{item.product.name} added to your cart.")


@login_required
@require_POST
def update_cart(request):
    pid = parse_int(request.POST.get("product_id"), minimum=1)
    qty = parse_int(request.POST.get("quantity"), minimum=0)
    if pid is None or qty is None:
        return _respond(request, False, "Invalid quantity.")
    try:
        services.set_quantity(request.user, pid, qty)
    except services.CartError as exc:
        return _respond(request, False, str(exc))
    return _respond(request, True, "Cart updated.")


@login_required
@require_POST
def remove_from_cart(request):
    pid = parse_int(request.POST.get("product_id"), minimum=1)
    if pid is None:
        return _respond(request, False, "Invalid product.")
    services.remove_item(request.user, pid)
    return _respond(request, True, "Item removed.")
