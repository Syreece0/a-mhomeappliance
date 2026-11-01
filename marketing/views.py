from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services


@require_POST
def newsletter_subscribe(request):
    email = request.POST.get("email", "").strip()
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Please enter a valid email address.")
        return redirect(request.META.get("HTTP_REFERER") or "core:home")
    _, created = services.subscribe(email)
    messages.success(
        request,
        "You are subscribed. Thanks for joining!" if created else "You are already on our list - thank you!",
    )
    return redirect(request.META.get("HTTP_REFERER") or "core:home")


@csrf_exempt  # one-click unsubscribe (RFC 8058) is POSTed by mail clients without a CSRF token
def unsubscribe(request, token):
    email = services.email_from_token(token)
    if email is None:
        return render(request, "marketing/unsubscribe.html", {"state": "invalid"}, status=400)
    if request.method == "POST":
        services.unsubscribe(email)
        return render(request, "marketing/unsubscribe.html", {"state": "done", "email": email})
    return render(request, "marketing/unsubscribe.html", {"state": "confirm", "email": email})
