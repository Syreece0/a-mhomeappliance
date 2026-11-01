import logging

from django.db import transaction

from catalog.models import Product

from .models import InventoryMovement

logger = logging.getLogger(__name__)


class InventoryError(Exception):
    pass


@transaction.atomic
def adjust_stock(product_id, delta, reason, note="", user=None, order=None, allow_clamp=False):
    """Change stock by `delta` under a row lock and record the movement.

    Returns (product, applied_delta). With allow_clamp, a deduction larger than the stock only
    removes what is available (stock never goes negative).
    """
    product = Product.objects.select_for_update().get(pk=product_id)
    new_stock = product.stock + delta
    if new_stock < 0:
        if not allow_clamp:
            raise InventoryError(f"Not enough stock for {product.name}.")
        delta = -product.stock
        new_stock = 0
    if delta == 0:
        return product, 0
    product.stock = new_stock
    product.save(update_fields=["stock", "updated_at"])
    InventoryMovement.objects.create(
        product=product, change=delta, balance_after=new_stock, reason=reason, note=note[:255], order=order,
        created_by=user,
    )
    return product, delta


@transaction.atomic
def set_stock(product_id, new_quantity, user=None, note="Stock count correction"):
    product = Product.objects.select_for_update().get(pk=product_id)
    return adjust_stock(product.pk, int(new_quantity) - product.stock, InventoryMovement.ADJUSTMENT, note, user)


@transaction.atomic
def deduct_for_order(order):
    """Reduce stock for a freshly paid order. Returns a list of shortage descriptions."""
    shortages = []
    if order.stock_deducted:
        return shortages
    for item in order.items.select_related("product"):
        if not item.product_id:
            continue
        _, applied = adjust_stock(
            item.product_id, -item.quantity, InventoryMovement.SALE, f"Order {order.number}", order=order,
            allow_clamp=True,
        )
        item.stock_applied = -applied
        item.save(update_fields=["stock_applied"])
        if item.stock_applied < item.quantity:
            shortages.append(f"{item.name}: ordered {item.quantity}, only {item.stock_applied} were in stock")
    order.stock_deducted = True
    order.save(update_fields=["stock_deducted"])
    return shortages


@transaction.atomic
def restore_for_order(order, reason=InventoryMovement.CANCELLATION):
    """Return the stock a paid order consumed (idempotent)."""
    if not order.stock_deducted or order.stock_restored:
        return
    for item in order.items.all():
        if item.product_id and item.stock_applied:
            adjust_stock(item.product_id, item.stock_applied, reason, f"Order {order.number}", order=order)
    order.stock_restored = True
    order.save(update_fields=["stock_restored"])
