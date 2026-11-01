from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, ProfileForm, RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    initial = {"referral_code": request.session.get("referral_code", "")}
    form = RegisterForm(request.POST or None, initial=initial)
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if request.method == "POST" and form.is_valid():
        from referrals.services import attribute_referral

        with transaction.atomic():
            user = form.save()
            attribute_referral(user, form.cleaned_data.get("referral_code"))
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.pop("referral_code", None)
        messages.success(request, f"Welcome to A&M, {user.display_name}! Your account is ready.")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("catalog:list")
    return render(request, "accounts/register.html", {"form": form, "next": next_url})


class AMLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AMPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "Your password was changed.")
        return super().form_valid(form)


@login_required
def dashboard(request):
    from orders.models import Order
    from referrals.models import Wallet

    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    wallet = Wallet.objects.filter(user=request.user).first()
    return render(
        request,
        "accounts/dashboard.html",
        {"recent_orders": orders[:5], "order_total": orders.count(), "wallet": wallet},
    )


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
