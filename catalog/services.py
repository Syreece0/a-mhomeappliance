import logging
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import Promotion, PromotionItem

logger = logging.getLogger(__name__)
CENT = Decimal("0.01")


def promo_price(original, percent):
    return (Decimal(original) * (100 - percent) / 100).quantize(CENT, rounding=ROUND_HALF_UP)


def _is_live(promo, now):
    return promo.is_active and promo.starts_at <= now < promo.ends_at


def _apply_items(promo):
    for item in promo.items.select_related("product").select_for_update(of=("self",)):
        if item.original_price is not None:
            continue
        product = item.product
        clash = (
            PromotionItem.objects.filter(product=product, promotion__applied=True, original_price__isnull=False)
            .exclude(promotion=promo)
            .exists()
        )
        if clash:  # another live promotion already discounts this product; never stack
            continue
        item.original_price = product.price
        item.original_previous_price = product.previous_price
        product.previous_price = product.price
        product.price = promo_price(item.original_price, promo.discount_percent)
        product.save(update_fields=["price", "previous_price", "updated_at"])
        item.save(update_fields=["original_price", "original_previous_price"])


def _revert_items(promo):
    for item in promo.items.select_related("product").select_for_update(of=("self",)):
        if item.original_price is None:
            continue
        product = item.product
        # Only restore when the price is still the promotional one (admin may have changed it meanwhile).
        if product.price == promo_price(item.original_price, promo.discount_percent):
            product.price = item.original_price
            product.previous_price = item.original_previous_price
            product.save(update_fields=["price", "previous_price", "updated_at"])
        item.original_price = None
        item.original_previous_price = None
        item.save(update_fields=["original_price", "original_previous_price"])


@transaction.atomic
def revert_promotion(promo_id):
    promo = Promotion.objects.select_for_update().get(pk=promo_id)
    _revert_items(promo)
    promo.applied = False
    promo.save(update_fields=["applied"])


@transaction.atomic
def sync_promotions():
    """Apply promotions that have started and revert those that ended or were disabled."""
    now = timezone.now()
    changed = 0
    for promo in Promotion.objects.select_for_update():
        live = _is_live(promo, now)
        if live:
            _apply_items(promo)  # also picks up products added after activation
            if not promo.applied:
                promo.applied = True
                promo.save(update_fields=["applied"])
                changed += 1
        elif promo.applied:
            _revert_items(promo)
            promo.applied = False
            promo.save(update_fields=["applied"])
            changed += 1
    return changed
