import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from catalog.models import Category, Product, ProductImage, Promotion, PromotionItem, Review
from catalog.services import revert_promotion, sync_promotions
from core.content import TOKEN_HELP, ensure_pages, render_snapshot
from core.models import Banner, BusinessSettings, PageSection, SitePage
from core.utils import parse_int
from inventory import services as inventory_services
from inventory.models import InventoryMovement
from marketing import services as marketing_services
from marketing.models import Campaign, NewsletterSubscriber
from notifications.models import EmailDelivery
from orders import services as order_services
from orders.models import Order
from payments.models import PaymentTransaction
from referrals import services as referral_services
from referrals.models import Referral, Wallet, WalletTransaction

from .decorators import content_manager_required, staff_required
from .forms import (BannerForm, CampaignForm, CategoryForm, ContactInfoForm, OrderStatusForm, PageDetailsForm,
                    PolicyDetailsForm, ProductForm, PromotionForm, SectionForm, SettingsForm, StockForm,
                    WalletAdjustForm)

ORDER_TOTAL = ExpressionWrapper(F("subtotal") + F("delivery_fee"), output_field=DecimalField(max_digits=14, decimal_places=2))
REVENUE_STATUSES = [Order.PAID, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]


def _page(request, qs, per=20):
    return Paginator(qs, per).get_page(request.GET.get("page"))


# ------------------------------------------------------------------ overview
@staff_required
def overview(request):
    biz = BusinessSettings.load()
    now = timezone.now()
    paid = Order.objects.filter(status__in=REVENUE_STATUSES)
    revenue = paid.aggregate(t=Sum(ORDER_TOTAL))["t"] or Decimal("0")

    start = (now - timedelta(days=13)).date()
    by_day = {
        r["d"]: r
        for r in paid.filter(paid_at__date__gte=start)
        .annotate(d=TruncDate("paid_at")).values("d").annotate(total=Sum(ORDER_TOTAL), n=Count("id"))
    }
    chart = []
    for i in range(14):
        d = start + timedelta(days=i)
        row = by_day.get(d)
        chart.append({"label": d.strftime("%d %b"), "total": float(row["total"]) if row else 0, "orders": row["n"] if row else 0})
    peak = max((c["total"] for c in chart), default=0) or 1
    for c in chart:
        c["pct"] = round(c["total"] / peak * 100)

    emails = EmailDelivery.objects.aggregate(
        total=Count("id"), sent=Count("id", filter=Q(status="sent")), failed=Count("id", filter=Q(status="failed")),
        queued=Count("id", filter=Q(status="queued")),
    )
    ctx = {
        "customers": User.objects.filter(is_staff=False).count(),
        "products": Product.objects.count(),
        "orders": Order.objects.count(),
        "revenue": revenue,
        "pending_orders": Order.objects.filter(status__in=[Order.PENDING, Order.PAYMENT_PENDING]).count(),
        "completed_orders": Order.objects.filter(status=Order.DELIVERED).count(),
        "cancelled_orders": Order.objects.filter(status=Order.CANCELLED).count(),
        "inventory_units": Product.objects.aggregate(n=Sum("stock"))["n"] or 0,
        "low_stock": Product.objects.filter(stock__lte=biz.low_stock_threshold, is_available=True).order_by("stock")[:8],
        "low_stock_count": Product.objects.filter(stock__lte=biz.low_stock_threshold, is_available=True).count(),
        "ok_txns": PaymentTransaction.objects.filter(status=PaymentTransaction.SUCCESS).count(),
        "failed_txns": PaymentTransaction.objects.filter(status=PaymentTransaction.FAILED).count(),
        "rewards_issued": WalletTransaction.objects.filter(kind=WalletTransaction.REFERRAL_REWARD).aggregate(t=Sum("amount"))["t"] or 0,
        "wallet_liability": Wallet.objects.aggregate(t=Sum("balance"))["t"] or 0,
        "emails": emails,
        "campaigns_sent": Campaign.objects.filter(status=Campaign.SENT).count(),
        "attention": Order.objects.filter(needs_attention=True).count(),
        "chart": chart,
        "recent_orders": Order.objects.select_related("user")[:8],
    }
    return render(request, "dashboard/overview.html", ctx)


# ------------------------------------------------------------------ products
@staff_required
def product_list(request):
    qs = Product.objects.select_related("category").prefetch_related("images")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q))
    if request.GET.get("low") == "1":
        qs = qs.filter(stock__lte=BusinessSettings.load().low_stock_threshold)
    return render(request, "dashboard/product_list.html", {"page": _page(request, qs), "q": q})


def _save_product_images(product, files):
    has_primary = product.images.filter(is_primary=True).exists()
    for idx, f in enumerate(files):
        ProductImage.objects.create(
            product=product, image=f, alt_text=product.name, is_primary=(not has_primary and idx == 0),
            position=product.images.count(),
        )


@staff_required
@transaction.atomic
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    old_stock = product.stock if product else 0
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        _save_product_images(saved, form.cleaned_data.get("new_images") or [])
        if saved.stock != old_stock:
            # keep the inventory ledger honest for stock typed directly into the product form
            InventoryMovement.objects.create(
                product=saved, change=saved.stock - old_stock, balance_after=saved.stock,
                reason=InventoryMovement.RESTOCK if not product else InventoryMovement.ADJUSTMENT,
                note="Set from product form", created_by=request.user,
            )
        messages.success(request, "Product saved.")
        return redirect("dashboard:product_edit", pk=saved.pk)
    return render(request, "dashboard/product_form.html", {"form": form, "product": product,
                                                           "stock_form": StockForm()})


@staff_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.order_items.exists():
        product.is_available = False
        product.save(update_fields=["is_available"])
        messages.warning(request, "This product appears in past orders, so it was hidden instead of deleted.")
    else:
        product.delete()
        messages.success(request, "Product deleted.")
    return redirect("dashboard:product_list")


@staff_required
@require_POST
def product_image_action(request, pk, image_id):
    product = get_object_or_404(Product, pk=pk)
    image = get_object_or_404(ProductImage, pk=image_id, product=product)
    action = request.POST.get("action")
    if action == "delete":
        was_primary = image.is_primary
        image.delete()
        if was_primary:
            nxt = product.images.first()
            if nxt:
                nxt.is_primary = True
                nxt.save(update_fields=["is_primary"])
    elif action == "primary":
        product.images.update(is_primary=False)
        image.is_primary = True
        image.save(update_fields=["is_primary"])
    return redirect("dashboard:product_edit", pk=pk)


@staff_required
@require_POST
def product_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = StockForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        try:
            if cd["mode"] == "set":
                inventory_services.set_stock(product.pk, cd["quantity"], request.user, cd["note"] or "Stock count")
            else:
                delta = cd["quantity"] if cd["mode"] == "add" else -cd["quantity"]
                inventory_services.adjust_stock(
                    product.pk, delta, InventoryMovement.RESTOCK if delta > 0 else InventoryMovement.ADJUSTMENT,
                    cd["note"], request.user,
                )
            messages.success(request, "Stock updated.")
        except inventory_services.InventoryError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Enter a valid quantity.")
    return redirect("dashboard:product_edit", pk=pk)


@staff_required
def inventory_log(request):
    qs = InventoryMovement.objects.select_related("product", "order", "created_by")
    pid = parse_int(request.GET.get("product"), minimum=1)
    if pid:
        qs = qs.filter(product_id=pid)
    return render(request, "dashboard/inventory_log.html", {"page": _page(request, qs, 30)})


# ------------------------------------------------------------------ categories
@staff_required
def category_list(request):
    cats = Category.objects.filter(parent__isnull=True).prefetch_related("children")
    return render(request, "dashboard/category_list.html", {"categories": cats})


@staff_required
def category_edit(request, pk=None):
    cat = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, request.FILES or None, instance=cat)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category saved.")
        return redirect("dashboard:category_list")
    return render(request, "dashboard/category_form.html", {"form": form, "category": cat})


@staff_required
@require_POST
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk)
    cat.delete()  # products keep existing (category set null); subcategories are removed with it
    messages.success(request, "Category deleted.")
    return redirect("dashboard:category_list")


@staff_required
@require_POST
def category_move(request, pk):
    """Reorder: swap position with the neighbouring sibling."""
    cat = get_object_or_404(Category, pk=pk)
    siblings = list(Category.objects.filter(parent=cat.parent).order_by("position", "name"))
    for i, s in enumerate(siblings):  # normalise positions first so swaps are unambiguous
        if s.position != i:
            Category.objects.filter(pk=s.pk).update(position=i)
            s.position = i
    idx = next(i for i, s in enumerate(siblings) if s.pk == cat.pk)
    j = idx - 1 if request.POST.get("direction") == "up" else idx + 1
    if 0 <= j < len(siblings):
        a, b = siblings[idx], siblings[j]
        Category.objects.filter(pk=a.pk).update(position=b.position)
        Category.objects.filter(pk=b.pk).update(position=a.position)
    return redirect("dashboard:category_list")


# ------------------------------------------------------------------ orders
@staff_required
def order_list(request):
    qs = Order.objects.select_related("user")
    status = request.GET.get("status", "")
    if status in dict(Order.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if request.GET.get("attention") == "1":
        qs = qs.filter(needs_attention=True)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(email__icontains=q) | Q(full_name__icontains=q) | Q(phone__icontains=q))
    return render(request, "dashboard/order_list.html", {"page": _page(request, qs), "q": q, "status": status,
                                                         "statuses": Order.STATUS_CHOICES})


@staff_required
def order_detail(request, number):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("items", "history", "transactions", "wallet_entries"), number=number)
    form = OrderStatusForm(initial={"status": order.status, "carrier": order.carrier,
                                    "tracking_number": order.tracking_number, "delivery_estimate": order.delivery_estimate})
    return render(request, "dashboard/order_detail.html", {"order": order, "form": form,
                                                           "allowed": order_services.TRANSITIONS.get(order.status, set())})


@staff_required
@require_POST
def order_status(request, number):
    order = get_object_or_404(Order, number=number)
    form = OrderStatusForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        try:
            order_services.set_status(
                order.pk, cd["status"], by=request.user, note=cd["note"], carrier=cd["carrier"],
                tracking_number=cd["tracking_number"], delivery_estimate=cd["delivery_estimate"],
            )
            messages.success(request, "Order updated and the customer was notified.")
        except order_services.OrderError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Invalid status update.")
    return redirect("dashboard:order_detail", number=number)


@staff_required
@require_POST
def order_clear_flag(request, number):
    Order.objects.filter(number=number).update(needs_attention=False)
    return redirect("dashboard:order_detail", number=number)


@staff_required
def transactions(request):
    qs = PaymentTransaction.objects.select_related("order")
    status = request.GET.get("status", "")
    if status in dict(PaymentTransaction.STATUS_CHOICES):
        qs = qs.filter(status=status)
    return render(request, "dashboard/transactions.html", {"page": _page(request, qs, 30), "status": status,
                                                           "statuses": PaymentTransaction.STATUS_CHOICES})


# ------------------------------------------------------------------ customers
@staff_required
def customer_list(request):
    qs = User.objects.filter(is_staff=False).select_related("wallet").annotate(order_count=Count("orders", distinct=True))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q))
    return render(request, "dashboard/customer_list.html", {"page": _page(request, qs.order_by("-date_joined")), "q": q})


@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(User.objects.select_related("wallet", "referral_code"), pk=pk, is_staff=False)
    ctx = {
        "customer": customer,
        "orders": customer.orders.all()[:20],
        "referrals": Referral.objects.filter(referrer=customer).select_related("referred"),
        "referred_by": Referral.objects.filter(referred=customer).select_related("referrer").first(),
        "wallet_txns": customer.wallet.transactions.all()[:20],
        "adjust_form": WalletAdjustForm(),
    }
    return render(request, "dashboard/customer_detail.html", ctx)


@staff_required
@require_POST
def customer_toggle_active(request, pk):
    customer = get_object_or_404(User, pk=pk, is_staff=False)
    customer.is_active = not customer.is_active
    customer.save(update_fields=["is_active"])
    messages.success(request, f"Account {'activated' if customer.is_active else 'suspended'}.")
    return redirect("dashboard:customer_detail", pk=pk)


@staff_required
@require_POST
def wallet_adjust(request, pk):
    customer = get_object_or_404(User, pk=pk, is_staff=False)
    form = WalletAdjustForm(request.POST)
    if form.is_valid():
        try:
            referral_services.admin_adjust(customer, form.cleaned_data["amount"], form.cleaned_data["reason"], request.user)
            messages.success(request, "Wallet adjusted and recorded in the audit trail.")
        except referral_services.WalletError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("dashboard:customer_detail", pk=pk)


# ------------------------------------------------------------------ referrals
@staff_required
def referral_admin(request):
    biz = BusinessSettings.load()
    if request.method == "POST":
        amount = request.POST.get("referral_reward_amount", "")
        minimum = request.POST.get("referral_min_order_amount", "0") or "0"
        try:
            amount, minimum = Decimal(amount), Decimal(minimum)
            if amount < 0 or minimum < 0:
                raise ValueError
        except Exception:
            messages.error(request, "Enter valid amounts.")
            return redirect("dashboard:referrals")
        biz.referral_enabled = request.POST.get("referral_enabled") == "on"
        biz.referral_reward_amount = amount
        biz.referral_min_order_amount = minimum
        biz.save()
        messages.success(request, "Referral settings saved. They apply to future first purchases.")
        return redirect("dashboard:referrals")

    status = request.GET.get("status", "")
    qs = Referral.objects.select_related("referrer", "referred", "qualified_order")
    if status in dict(Referral.STATUS_CHOICES):
        qs = qs.filter(status=status)
    stats = Referral.objects.aggregate(
        total=Count("id"), rewarded=Count("id", filter=Q(status=Referral.QUALIFIED)),
        pending=Count("id", filter=Q(status=Referral.PENDING)), paid_out=Sum("reward_amount"),
    )
    from referrals.models import ReferralCode

    return render(request, "dashboard/referrals.html", {
        "biz": biz, "page": _page(request, qs), "stats": stats, "status": status, "statuses": Referral.STATUS_CHOICES,
        "codes": ReferralCode.objects.select_related("user").order_by("-created_at")[:30],
        "liability": Wallet.objects.aggregate(t=Sum("balance"))["t"] or 0,
    })


# ------------------------------------------------------------------ promotions & banners
@staff_required
def promotion_list(request):
    return render(request, "dashboard/promotion_list.html", {"promotions": Promotion.objects.prefetch_related("items")})


@staff_required
@transaction.atomic
def promotion_edit(request, pk=None):
    promo = get_object_or_404(Promotion, pk=pk) if pk else None
    form = PromotionForm(request.POST or None, instance=promo)
    if request.method == "POST" and form.is_valid():
        if promo and promo.applied:
            revert_promotion(promo.pk)  # restore original prices before changing discount or product list
        promo = form.save()
        chosen = set(form.cleaned_data["products"].values_list("pk", flat=True))
        promo.items.exclude(product_id__in=chosen).delete()
        for pid in chosen:
            PromotionItem.objects.get_or_create(promotion=promo, product_id=pid)
        sync_promotions()
        messages.success(request, "Promotion saved.")
        return redirect("dashboard:promotion_list")
    return render(request, "dashboard/promotion_form.html", {"form": form, "promo": promo})


@staff_required
@require_POST
def promotion_delete(request, pk):
    promo = get_object_or_404(Promotion, pk=pk)
    if promo.applied:
        revert_promotion(promo.pk)
    promo.delete()
    messages.success(request, "Promotion deleted and prices restored.")
    return redirect("dashboard:promotion_list")


@staff_required
def banner_list(request):
    return render(request, "dashboard/banner_list.html", {"banners": Banner.objects.all()})


@staff_required
def banner_edit(request, pk=None):
    banner = get_object_or_404(Banner, pk=pk) if pk else None
    form = BannerForm(request.POST or None, request.FILES or None, instance=banner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Banner saved.")
        return redirect("dashboard:banner_list")
    return render(request, "dashboard/banner_form.html", {"form": form, "banner": banner})


@staff_required
@require_POST
def banner_delete(request, pk):
    get_object_or_404(Banner, pk=pk).delete()
    messages.success(request, "Banner deleted.")
    return redirect("dashboard:banner_list")


# ------------------------------------------------------------------ reviews
@staff_required
def review_list(request):
    qs = Review.objects.select_related("product", "user")
    if request.GET.get("filter") != "all":
        qs = qs.filter(is_approved=False)
    return render(request, "dashboard/review_list.html", {"page": _page(request, qs), "filter": request.GET.get("filter", "")})


@staff_required
@require_POST
def review_action(request, pk):
    review = get_object_or_404(Review, pk=pk)
    action = request.POST.get("action")
    if action == "approve":
        review.is_approved = True
        review.save(update_fields=["is_approved"])
    elif action == "reject":
        review.delete()
    return redirect(request.POST.get("next") or "dashboard:review_list")


# ------------------------------------------------------------------ email campaigns
@staff_required
def campaign_list(request):
    campaigns = list(Campaign.objects.all()[:50])
    for c in campaigns:
        c.stats = marketing_services.campaign_stats(c)
    failed = EmailDelivery.objects.filter(status=EmailDelivery.FAILED)
    return render(request, "dashboard/campaign_list.html", {
        "campaigns": campaigns, "failed": failed[:15], "failed_count": failed.count(),
        "subscribers": NewsletterSubscriber.objects.filter(is_active=True).count(),
        "opted_in": User.objects.filter(is_active=True, marketing_opt_in=True).count(),
    })


@staff_required
@transaction.atomic
def campaign_edit(request, pk=None):
    campaign = get_object_or_404(Campaign, pk=pk) if pk else None
    if campaign and campaign.status in (Campaign.SENDING, Campaign.SENT):
        messages.info(request, "Sent campaigns can't be edited.")
        return redirect("dashboard:campaign_list")
    form = CampaignForm(request.POST or None, request.FILES or None, instance=campaign)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        option = form.cleaned_data["send_option"]
        c.status = Campaign.SCHEDULED if option == "schedule" else Campaign.DRAFT
        if option != "schedule":
            c.scheduled_for = None
        c.save()
        c.products.set(form.cleaned_data["products"])
        if option == "now":
            transaction.on_commit(lambda: _send_now(c.pk))
            messages.success(request, "Campaign is being sent to eligible recipients.")
        elif option == "schedule":
            messages.success(request, "Campaign scheduled.")
        else:
            messages.success(request, "Draft saved.")
        return redirect("dashboard:campaign_list")
    return render(request, "dashboard/campaign_form.html", {"form": form, "campaign": campaign})


def _send_now(campaign_id):
    marketing_services.send_campaign(campaign_id)


@staff_required
def campaign_preview(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    html = marketing_services.render_campaign(campaign, unsub_url="#", preview=True)
    return HttpResponse(html)


@staff_required
@require_POST
def campaign_action(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    action = request.POST.get("action")
    if action == "cancel" and campaign.status in (Campaign.DRAFT, Campaign.SCHEDULED):
        campaign.status = Campaign.CANCELLED
        campaign.save(update_fields=["status"])
        messages.success(request, "Campaign cancelled.")
    elif action == "send" and campaign.status in (Campaign.DRAFT, Campaign.SCHEDULED):
        marketing_services.send_campaign(campaign.pk)
        messages.success(request, "Campaign sent.")
    elif action == "test":
        from notifications.services import queue_email

        queue_email(to=request.user.email, subject=f"[TEST] {campaign.subject}",
                    html=marketing_services.render_campaign(campaign, unsub_url="#", preview=True), kind="promotion_test")
        messages.success(request, f"Test email sent to {request.user.email}.")
    return redirect("dashboard:campaign_list")


@staff_required
def email_history(request):
    qs = EmailDelivery.objects.all()
    status = request.GET.get("status", "")
    if status in dict(EmailDelivery.STATUS_CHOICES):
        qs = qs.filter(status=status)
    return render(request, "dashboard/email_history.html", {"page": _page(request, qs, 30), "status": status,
                                                            "statuses": EmailDelivery.STATUS_CHOICES})


@staff_required
@require_POST
def email_retry(request, pk):
    from notifications.services import enqueue

    d = get_object_or_404(EmailDelivery, pk=pk)
    if d.status == EmailDelivery.FAILED:
        d.attempts = 0
        d.save(update_fields=["attempts"])
        enqueue(d.pk)
        messages.success(request, "Email re-queued.")
    return redirect(request.POST.get("next") or "dashboard:email_history")


@staff_required
def abandoned_cart_settings(request):
    biz = BusinessSettings.load()
    if request.method == "POST":
        try:
            biz.abandoned_cart_enabled = request.POST.get("abandoned_cart_enabled") == "on"
            biz.abandoned_cart_wait_minutes = int(request.POST["abandoned_cart_wait_minutes"])
            biz.abandoned_cart_max_reminders = int(request.POST["abandoned_cart_max_reminders"])
            biz.abandoned_cart_interval_hours = int(request.POST["abandoned_cart_interval_hours"])
            biz.promo_emails_enabled = request.POST.get("promo_emails_enabled") == "on"
            if min(biz.abandoned_cart_wait_minutes, biz.abandoned_cart_max_reminders, biz.abandoned_cart_interval_hours) < 0:
                raise ValueError
        except (KeyError, ValueError):
            messages.error(request, "Enter valid whole numbers (0 or more).")
            return redirect("dashboard:abandoned_cart")
        biz.save()
        messages.success(request, "Email automation settings saved.")
        return redirect("dashboard:abandoned_cart")
    return render(request, "dashboard/abandoned_cart.html", {"biz": biz})


# ------------------------------------------------------------------ settings
@staff_required
def business_settings(request):
    biz = BusinessSettings.load()
    form = SettingsForm(request.POST or None, request.FILES or None, instance=biz)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings saved.")
        return redirect("dashboard:settings")
    return render(request, "dashboard/settings.html", {"form": form})


# ------------------------------------------------------------------ website content (About, policies, contact)
def _content_page(slug):
    ensure_pages(only=slug)
    return get_object_or_404(SitePage, slug=slug)


@content_manager_required
def content_home(request):
    ensure_pages()
    biz = BusinessSettings.load()
    details = PolicyDetailsForm(request.POST or None, instance=biz)
    if request.method == "POST" and details.is_valid():
        details.save()
        messages.success(request, "Policy details saved. They now appear in the Delivery and Returns policies.")
        return redirect("dashboard:content_home")
    pages = SitePage.objects.select_related("updated_by").order_by("position", "id")
    return render(request, "dashboard/content_home.html", {
        "about": next((p for p in pages if p.kind == SitePage.ABOUT), None),
        "policies": [p for p in pages if p.kind == SitePage.POLICY],
        "details": details,
        "biz": biz,
    })


@content_manager_required
def content_page(request, slug):
    page = _content_page(slug)
    form = PageDetailsForm(request.POST or None, request.FILES or None, instance=page)
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "discard":
            if page.discard_draft(request.user):
                messages.success(request, "Unpublished changes discarded. The editor now matches the live page.")
            else:
                messages.error(request, "This page has never been published, so there is nothing to go back to.")
            return redirect("dashboard:content_page", slug=slug)
        if form.is_valid():
            form.save()
            page.touch(request.user, "Page details saved")
            if action == "publish":
                page.publish(request.user)
                messages.success(request, "Published. The changes are now live on the website.")
            else:
                messages.success(request, "Draft saved. Visitors still see the last published version.")
            return redirect("dashboard:content_page", slug=slug)
    page.refresh_from_db()
    return render(request, "dashboard/content_page.html", {
        "page": page, "form": form, "sections": page.sections.order_by("position", "id"),
        "revisions": page.revisions.select_related("user")[:10], "tokens": TOKEN_HELP,
    })


@content_manager_required
def content_preview(request, slug):
    from django.urls import reverse

    from core.views import policy_nav

    page = _content_page(slug)
    content = render_snapshot(page.build_snapshot(), BusinessSettings.cached())
    ctx = {
        "page": page, "content": content, "preview": True, "updated": page.published_at,
        "back_url": reverse("dashboard:content_page", args=[slug]),
    }
    if page.kind == SitePage.ABOUT:
        return render(request, "core/about.html", ctx)
    ctx["policies"] = policy_nav()
    return render(request, "core/policy.html", ctx)


@content_manager_required
def content_section_edit(request, slug, pk=None):
    page = _content_page(slug)
    section = get_object_or_404(PageSection, pk=pk, page=page) if pk else None
    form = SectionForm(request.POST or None, request.FILES or None, instance=section)
    if request.method == "POST" and form.is_valid():
        sec = form.save(commit=False)
        sec.page = page
        if section is None:
            sec.position = (page.sections.aggregate(m=Max("position"))["m"] or 0) + 1
        sec.save()
        page.touch(request.user, f"Section saved: {sec.title}"[:255])
        messages.success(request, "Section saved to the draft. Publish the page to make it live.")
        return redirect("dashboard:content_page", slug=slug)
    return render(request, "dashboard/content_section_form.html", {
        "page": page, "section": section, "form": form, "tokens": TOKEN_HELP,
    })


@content_manager_required
@require_POST
def content_section_delete(request, slug, pk):
    page = _content_page(slug)
    section = get_object_or_404(PageSection, pk=pk, page=page)
    title = section.title
    section.delete()
    page.touch(request.user, f"Section removed: {title}"[:255])
    messages.success(request, "Section removed from the draft. It stays on the live page until you publish.")
    return redirect("dashboard:content_page", slug=slug)


@content_manager_required
@require_POST
def content_section_move(request, slug, pk):
    page = _content_page(slug)
    ordered = list(page.sections.order_by("position", "id"))
    ids = [s.pk for s in ordered]
    if pk not in ids:
        return redirect("dashboard:content_page", slug=slug)
    i = ids.index(pk)
    j = i - 1 if request.POST.get("direction") == "up" else i + 1
    if 0 <= j < len(ordered):
        ordered[i], ordered[j] = ordered[j], ordered[i]
        for pos, sec in enumerate(ordered):
            if sec.position != pos:
                PageSection.objects.filter(pk=sec.pk).update(position=pos)
        page.touch(request.user, "Sections reordered")
    return redirect("dashboard:content_page", slug=slug)


@content_manager_required
def content_contact(request):
    biz = BusinessSettings.load()
    form = ContactInfoForm(request.POST or None, instance=biz)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contact information saved. It is live on the Contact Us page, footer and emails.")
        return redirect("dashboard:content_contact")
    return render(request, "dashboard/content_contact.html", {"form": form})
