from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import Product

from .models import Cart, CartItem


class CartError(Exception):
    pass


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def touch(cart):
    """Cart changed: restart the abandoned-cart reminder cycle."""
    Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now(), reminders_sent=0, last_reminder_at=None)


@transaction.atomic
def add_item(user, product_id, quantity=1):
    if quantity < 1:
        raise CartError("Quantity must be at least 1.")
    try:
        product = Product.objects.available().get(pk=product_id)
    except Product.DoesNotExist:
        raise CartError("This product is not available.")
    if product.stock < 1:
        raise CartError(f"{product.name} is out of stock.")
    cart = get_cart(user)
    item = CartItem.objects.select_for_update().filter(cart=cart, product=product).first()
    if item is None:
        if quantity > product.stock:
            raise CartError(f"Only {product.stock} of {product.name} in stock.")
        try:
            with transaction.atomic():
                item = CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        except IntegrityError:  # a concurrent request created the line first: fall through and add to it
            item = CartItem.objects.select_for_update().get(cart=cart, product=product)
        else:
            touch(cart)
            return item
    new_qty = item.quantity + quantity
    if new_qty > product.stock:
        raise CartError(f"Only {product.stock} of {product.name} in stock.")
    item.quantity = new_qty
    item.save(update_fields=["quantity"])
    touch(cart)
    return item


@transaction.atomic
def set_quantity(user, product_id, quantity):
    cart = get_cart(user)
    item = CartItem.objects.select_for_update().filter(cart=cart, product_id=product_id).select_related("product").first()
    if item is None:
        raise CartError("That item is not in your cart.")
    if quantity <= 0:
        item.delete()
    else:
        if quantity > item.product.stock:
            raise CartError(f"Only {item.product.stock} of {item.product.name} in stock.")
        item.quantity = quantity
        item.save(update_fields=["quantity"])
    touch(cart)


@transaction.atomic
def remove_item(user, product_id):
    cart = get_cart(user)
    CartItem.objects.filter(cart=cart, product_id=product_id).delete()
    touch(cart)


def summarize(user):
    cart = get_cart(user)
    items = list(cart.items.select_related("product").prefetch_related("product__images").order_by("id"))
    subtotal = sum((i.line_total for i in items), Decimal("0"))
    warnings = []
    for i in items:
        if not i.product.is_available or i.product.stock < 1:
            warnings.append(f"{i.product.name} is currently out of stock.")
        elif i.quantity > i.product.stock:
            warnings.append(f"Only {i.product.stock} of {i.product.name} left; please reduce the quantity.")
    return {
        "cart": cart,
        "items": items,
        "subtotal": subtotal,
        "count": sum(i.quantity for i in items),
        "warnings": warnings,
    }


@transaction.atomic
def clear_purchased(order):
    """Remove exactly what the customer bought from their cart; keep everything else."""
    cart = Cart.objects.select_for_update().filter(user_id=order.user_id).first()
    if cart is None:
        return
    changed = False
    for oi in order.items.all():
        if not oi.product_id:
            continue
        ci = CartItem.objects.select_for_update().filter(cart=cart, product_id=oi.product_id).first()
        if ci is None:
            continue
        remaining = ci.quantity - oi.quantity
        if remaining <= 0:
            ci.delete()
        else:
            ci.quantity = remaining
            ci.save(update_fields=["quantity"])
        changed = True
    if changed:
        touch(cart)
