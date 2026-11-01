import re

from django.db import connection
from django.db.models import F
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render

from catalog.models import Category, Product, Review
from core.content import POLICY_SLUGS, ensure_pages, get_page, render_snapshot
from core.models import Banner, BusinessSettings, SitePage

CODE_RE = re.compile(r"^[A-Za-z0-9]{3,20}$")


def home(request):
    products = (
        Product.objects.available().with_rating().select_related("category").prefetch_related("images")
    )
    ctx = {
        "hero_slides": list(Banner.objects.live().filter(kind=Banner.HERO)[:6]),
        "promo_banner": Banner.objects.live().filter(kind=Banner.PROMO).first(),
        "categories": Category.objects.filter(is_active=True, parent__isnull=True)[:8],
        "featured": products.filter(is_featured=True)[:8],
        "best_sellers": products.filter(is_best_seller=True)[:8],
        "new_arrivals": products.filter(is_new_arrival=True)[:8],
        "offers": products.filter(previous_price__gt=F("price"))[:8],
        "testimonials": Review.objects.filter(is_approved=True, rating__gte=4)
        .exclude(body="")
        .select_related("user", "product")[:6],
    }
    return render(request, "core/home.html", ctx)


def referral_landing(request, code):
    """Referral share link: remember the code, send the visitor to register."""
    if CODE_RE.match(code):
        request.session["referral_code"] = code.upper()
    if request.user.is_authenticated:
        return redirect("core:home")
    return redirect("accounts:register")


def healthz(request):
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


# --------------------------------------------------------------------------- About / policies / contact
def policy_nav():
    """Published policies (published title/summary only, never draft text) for navigation and the index page."""
    def fetch():
        return list(SitePage.objects.filter(kind=SitePage.POLICY, published_at__isnull=False).order_by("position", "id"))

    pages = fetch()
    if not pages:
        ensure_pages()
        pages = fetch()
    biz = BusinessSettings.cached()
    rows = []
    for p in pages:
        snap = render_snapshot(p.published_snapshot, biz)
        rows.append({"slug": p.slug, "title": snap["title"], "summary": snap["summary"], "url": p.get_absolute_url(),
                     "updated": p.published_at})
    return rows


def _published(slug):
    page = get_page(slug)
    if page is None or page.published_snapshot is None:
        raise Http404
    return page, render_snapshot(page.published_snapshot, BusinessSettings.cached())


def about(request):
    page, content = _published("about-us")
    return render(request, "core/about.html", {"page": page, "content": content, "updated": page.published_at})


def policies(request):
    items = policy_nav()
    return render(request, "core/policies.html", {"policies": items})


def policy(request, slug):
    if slug not in POLICY_SLUGS:
        raise Http404
    page, content = _published(slug)
    return render(request, "core/policy.html", {
        "page": page, "content": content, "updated": page.published_at, "policies": policy_nav(),
    })


def contact(request):
    return render(request, "core/contact.html", {})
