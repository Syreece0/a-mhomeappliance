import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.core.exceptions import ValidationError
from django.template import loader

from core.constants import STATE_CHOICES
from core.forms import StyledFormMixin

from .models import User

PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")


def clean_phone_value(value):
    value = (value or "").strip()
    if value and not PHONE_RE.match(value):
        raise ValidationError("Enter a valid phone number.")
    return value


class RegisterForm(StyledFormMixin, forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(
        label="Confirm password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    referral_code = forms.CharField(label="Referral code (optional)", required=False, max_length=20)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "marketing_opt_in"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["phone"].required = True
        self.fields["marketing_opt_in"].label = "Send me offers and promotions by email (optional)"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"))

    def clean_referral_code(self):
        from referrals.models import ReferralCode

        code = (self.cleaned_data.get("referral_code") or "").strip().upper()
        if code and not ReferralCode.objects.filter(code=code).exists():
            raise ValidationError("That referral code is not valid.")
        return code

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "The two passwords do not match.")
            else:
                candidate = User(email=cleaned.get("email", ""), first_name=cleaned.get("first_name", ""))
                try:
                    password_validation.validate_password(p1, candidate)
                except ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class ProfileForm(StyledFormMixin, forms.ModelForm):
    state = forms.ChoiceField(choices=STATE_CHOICES, required=False)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "address", "state", "city", "marketing_opt_in"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["marketing_opt_in"].label = "Send me offers and promotions by email"

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"))


class AMPasswordResetForm(StyledFormMixin, PasswordResetForm):
    """Routes the reset email through the same queued, logged, branded email pipeline."""

    email = forms.EmailField(label="Email", max_length=254)

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        from django.urls import reverse

        from notifications.services import base_context, queue_email

        reset_path = reverse("accounts:password_reset_confirm", kwargs={"uidb64": context["uid"], "token": context["token"]})
        context = {**base_context(), **context, "reset_url": f"{context['protocol']}://{context['domain']}{reset_path}"}
        subject = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        text = loader.render_to_string(email_template_name, context)
        html = loader.render_to_string(html_email_template_name, context) if html_email_template_name else ""
        queue_email(to=to_email, subject=subject, html=html or text, text=text, kind="password_reset",
                    user=context.get("user"))
