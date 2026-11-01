from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from cart import services as cart_services
from catalog.models import Product
from core.utils import parse_int

from .models import WishlistItem


@login_required
def wishlist_list(request):
    items = WishlistItem.objects.filter(user=request.user).select_related("product").prefetch_related("product__images")
    return render(request, "wishlist/wishlist.html", {"items": items})


@require_POST
def toggle(request):
    ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if not request.user.is_authenticated:
        login = f"{reverse('accounts:login')}?next={request.POST.get('next', '/')}"
        if ajax:
            return JsonResponse({"ok": False, "login_url": login, "message": "Please log in to use your wishlist."}, status=401)
        return redirect(login)
    pid = parse_int(request.POST.get("product_id"), minimum=1)
    product = get_object_or_404(Product, pk=pid) if pid else None
    if product is None:
        return JsonResponse({"ok": False}, status=400) if ajax else redirect("wishlist:list")
    item = WishlistItem.objects.filter(user=request.user, product=product).first()
    if item:
        item.delete()
        in_list = False
    else:
        WishlistItem.objects.get_or_create(user=request.user, product=product)
        in_list = True
    if ajax:
        return JsonResponse({"ok": True, "in_wishlist": in_list,
                             "message": "Added to wishlist." if in_list else "Removed from wishlist."})
    messages.success(request, "Added to wishlist." if in_list else "Removed from wishlist.")
    return redirect(request.POST.get("next") or "wishlist:list")


@login_required
@require_POST
def move_to_cart(request):
    pid = parse_int(request.POST.get("product_id"), minimum=1)
    item = WishlistItem.objects.filter(user=request.user, product_id=pid).select_related("product").first()
    if item is None:
        messages.error(request, "That item is not in your wishlist.")
        return redirect("wishlist:list")
    try:
        cart_services.add_item(request.user, item.product_id, 1)
    except cart_services.CartError as exc:
        messages.error(request, str(exc))
        return redirect("wishlist:list")
    item.delete()
    messages.success(request, f"{item.product.name} moved to your cart.")
    return redirect("wishlist:list")
