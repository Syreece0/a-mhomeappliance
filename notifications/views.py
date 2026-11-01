from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    qs = Notification.objects.filter(user=request.user)
    if request.GET.get("filter") == "unread":
        qs = qs.filter(is_read=False)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "notifications/list.html", {"page": page, "filter": request.GET.get("filter", "")})


@login_required
def latest(request):
    """JSON feed for the navbar bell."""
    qs = Notification.objects.filter(user=request.user)
    items = [
        {"id": n.pk, "title": n.title, "message": n.message[:120], "is_read": n.is_read,
         "kind": n.kind, "when": n.created_at.strftime("%d %b, %H:%M"), "open_url": f"/notifications/{n.pk}/open/"}
        for n in qs[:6]
    ]
    return JsonResponse({"unread": qs.filter(is_read=False).count(), "items": items})


@login_required
def open_notification(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=["is_read"])
    target = n.link
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_read(request, pk):
    Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    return redirect(request.POST.get("next") or "notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("notifications:list")


@login_required
@require_POST
def delete(request, pk):
    Notification.objects.filter(pk=pk, user=request.user).delete()
    return redirect("notifications:list")
