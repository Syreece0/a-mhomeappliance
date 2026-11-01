from django.conf import settings
from django.db.models import Prefetch, Sum


def site(request):
    from catalog.models import Category
    from core.models import BusinessSettings

    ctx = {
        "biz": BusinessSettings.cached(),
        "SITE_URL": settings.SITE_URL,
        "nav_categories": Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related(
            Prefetch("children", queryset=Category.objects.filter(is_active=True), to_attr="active_children")
        )[:10],
        "cart_count": 0,
        "unread_count": 0,
        "wishlist_ids": set(),
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from cart.models import CartItem
        from notifications.models import Notification
        from wishlist.models import WishlistItem

        ctx["cart_count"] = CartItem.objects.filter(cart__user=user).aggregate(n=Sum("quantity"))["n"] or 0
        ctx["unread_count"] = Notification.objects.filter(user=user, is_read=False).count()
        ctx["wishlist_ids"] = set(WishlistItem.objects.filter(user=user).values_list("product_id", flat=True))
    return ctx
