from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.utils import parse_decimal

from .forms import ReviewForm
from .models import Category, Product, Review

PER_PAGE = 12

SORTS = {
    "newest": "-created_at",
    "oldest": "created_at",
    "popular": "-sold_count",
    "price_asc": "price",
    "price_desc": "-price",
    "rating": "-avg_rating",
}


def product_list(request):
    qs = Product.objects.available().with_rating().select_related("category").prefetch_related("images")
    get = request.GET

    q = get.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(brand__icontains=q) | Q(category__name__icontains=q) | Q(description__icontains=q)
        )

    category = None
    slug = get.get("category", "").strip()
    if slug:
        category = Category.objects.filter(slug=slug, is_active=True).first()
        if category:
            qs = qs.filter(category_id__in=category.family_ids())
        else:
            qs = qs.none()

    brand = get.get("brand", "").strip()
    if brand:
        qs = qs.filter(brand__iexact=brand)

    min_price = parse_decimal(get.get("min_price"))
    max_price = parse_decimal(get.get("max_price"))
    if min_price is not None:
        qs = qs.filter(price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(price__lte=max_price)

    availability = get.get("availability", "")
    if availability == "in_stock":
        qs = qs.filter(stock__gt=0)
    elif availability == "out_of_stock":
        qs = qs.filter(stock__lte=0)
    else:
        availability = ""
    if get.get("discounted") == "1":
        qs = qs.filter(previous_price__gt=F("price"))

    sort = get.get("sort", "newest")
    if sort not in SORTS:
        sort = "newest"
    qs = qs.order_by(SORTS[sort], "-id") if sort != "rating" else qs.order_by(F("avg_rating").desc(nulls_last=True), "-id")

    page = Paginator(qs, PER_PAGE).get_page(get.get("page"))
    brand_qs = Product.objects.available().exclude(brand="")
    if category:  # only offer brands that actually exist in the category being viewed
        brand_qs = brand_qs.filter(category_id__in=category.family_ids())
    brands = brand_qs.order_by("brand").values_list("brand", flat=True).distinct()

    # sub-categories of the current top-level category, shown as a slim chip row (not a big category box)
    subcategories = []
    if category:
        top = category.parent if category.parent_id else category
        subcategories = [c for c in top.children.all() if c.is_active]
    filters_active = any([brand, min_price is not None, max_price is not None, availability, get.get("discounted") == "1"])
    ctx = {
        "page": page,
        "products": page.object_list,
        "q": q,
        "active_category": category,
        "subcategories": subcategories,
        "parent_category": (category.parent if category and category.parent_id else category),
        "filters_active": filters_active,
        "brands": brands,
        "sort": sort,
        "filters": {
            "brand": brand,
            "min_price": get.get("min_price", ""),
            "max_price": get.get("max_price", ""),
            "availability": availability,
            "discounted": "1" if get.get("discounted") == "1" else "",
        },
        "sort_choices": [
            ("newest", "Newest"),
            ("oldest", "Oldest"),
            ("popular", "Popularity"),
            ("price_asc", "Price: low to high"),
            ("price_desc", "Price: high to low"),
            ("rating", "Top rated"),
        ],
    }
    return render(request, "catalog/shop.html", ctx)


def _purchased(user, product):
    Order = apps.get_model("orders", "Order")
    return (
        Order.objects.filter(user=user, paid_at__isnull=False, items__product=product)
        .exclude(status__in=[Order.CANCELLED, Order.REFUNDED])
        .exists()
    )


def product_detail(request, slug):
    base = Product.objects.available().with_rating().select_related("category").prefetch_related("images")
    product = get_object_or_404(base, slug=slug)
    related = (
        Product.objects.available().with_rating().prefetch_related("images")
        .filter(category=product.category).exclude(pk=product.pk)[:4]
        if product.category_id
        else []
    )
    reviews = product.reviews.filter(is_approved=True).select_related("user")[:20]
    can_review, my_review = False, None
    if request.user.is_authenticated:
        my_review = Review.objects.filter(product=product, user=request.user).first()
        can_review = _purchased(request.user, product)
    wa_text = (
        f"Hello A&M, I am interested in {product.name} (₦{product.price:,.0f}). "
        f"{request.build_absolute_uri(product.get_absolute_url())}"
    )
    ctx = {
        "product": product,
        "wa_text": wa_text,
        "related": related,
        "reviews": reviews,
        "can_review": can_review,
        "my_review": my_review,
        "review_form": ReviewForm(instance=my_review),
    }
    return render(request, "catalog/product_detail.html", ctx)


def quick_view(request, slug):
    product = get_object_or_404(
        Product.objects.available().with_rating().prefetch_related("images"), slug=slug
    )
    return render(request, "catalog/_quick_view.html", {"product": product})


@login_required
@require_POST
def submit_review(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if not _purchased(request.user, product):
        messages.error(request, "Only customers who bought this product can review it.")
        return redirect(product)
    existing = Review.objects.filter(product=product, user=request.user).first()
    form = ReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.is_verified_purchase = True
        review.is_approved = False  # re-moderated on every edit
        review.save()
        messages.success(request, "Thanks! Your review will appear once it has been approved.")
    else:
        messages.error(request, "Please correct your review and try again.")
    return redirect(product)
