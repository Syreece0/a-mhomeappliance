from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse

from .models import Referral, ReferralCode, Wallet


@login_required
def wallet_page(request):
    user = request.user
    code_obj, _ = ReferralCode.objects.get_or_create(user=user, defaults={"code": f"AM{user.pk:05d}"})
    wallet, _ = Wallet.objects.get_or_create(user=user)
    stats = Referral.objects.filter(referrer=user).aggregate(
        total=Count("id"),
        successful=Count("id", filter=Q(status=Referral.QUALIFIED)),
        pending=Count("id", filter=Q(status=Referral.PENDING)),
    )
    link = request.build_absolute_uri(reverse("core:referral_landing", args=[code_obj.code]))
    msg = f"Shop quality home appliances at A&M Home Appliances. Join with my link: {link}"
    page = Paginator(wallet.transactions.select_related("order"), 15).get_page(request.GET.get("page"))
    referred = Referral.objects.filter(referrer=user).select_related("referred")[:20]
    share = {
        "whatsapp": f"https://wa.me/?text={quote(msg)}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={quote(link)}",
        "twitter": f"https://twitter.com/intent/tweet?text={quote(msg)}",
        "telegram": f"https://t.me/share/url?url={quote(link)}&text={quote('Shop with A&M Home Appliances')}",
        "email": f"mailto:?subject={quote('Shop with A&M Home Appliances')}&body={quote(msg)}",
    }
    return render(
        request,
        "referrals/wallet.html",
        {"code": code_obj.code, "link": link, "wallet": wallet, "stats": stats, "page": page, "share": share,
         "referred": referred},
    )
