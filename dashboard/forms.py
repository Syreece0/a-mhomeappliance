from django import forms
from django.utils import timezone

from catalog.models import Category, Product, Promotion
from core.forms import MultipleImageField, StyledFormMixin
from core.models import Banner, BusinessSettings, PageSection, SitePage
from core.content import TOKEN_HELP
from core.richtext import MAX_BODY_CHARS, plain_text, sanitize_html
from marketing.models import Campaign
from orders.models import Order


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "parent", "description", "image", "position", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Category.objects.filter(parent__isnull=True)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = qs
        self.fields["parent"].required = False


class ProductForm(StyledFormMixin, forms.ModelForm):
    new_images = MultipleImageField(label="Upload images (you can select several)")

    class Meta:
        model = Product
        fields = [
            "name", "category", "brand", "price", "previous_price", "stock", "is_available", "warranty",
            "description", "specifications", "is_featured", "is_best_seller", "is_new_arrival",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "specifications": forms.Textarea(attrs={"rows": 5, "placeholder": "Capacity: 7kg\nPower: 1200W"}),
        }

    def clean(self):
        cleaned = super().clean()
        price, prev = cleaned.get("price"), cleaned.get("previous_price")
        if prev is not None and price is not None and prev <= price:
            cleaned["previous_price"] = None  # a "previous price" that is not higher is meaningless
        return cleaned


class StockForm(StyledFormMixin, forms.Form):
    mode = forms.ChoiceField(choices=[("add", "Add stock (+)"), ("remove", "Remove stock (-)"), ("set", "Set to exact count")])
    quantity = forms.IntegerField(min_value=0)
    note = forms.CharField(max_length=200, required=False)


class OrderStatusForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(choices=Order.STATUS_CHOICES)
    note = forms.CharField(max_length=200, required=False)
    carrier = forms.CharField(max_length=100, required=False)
    tracking_number = forms.CharField(max_length=100, required=False)
    delivery_estimate = forms.CharField(max_length=150, required=False)


class WalletAdjustForm(StyledFormMixin, forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, help_text="Positive adds credit, negative removes it.")
    reason = forms.CharField(max_length=200)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount == 0:
            raise forms.ValidationError("Amount cannot be zero.")
        return amount


class PromotionForm(StyledFormMixin, forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all().order_by("name"), required=False,
        widget=forms.SelectMultiple(attrs={"size": 10}),
    )

    class Meta:
        model = Promotion
        fields = ["name", "discount_percent", "starts_at", "ends_at", "is_active"]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("starts_at", "ends_at"):
            self.fields[f].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        if self.instance.pk:
            self.fields["products"].initial = list(self.instance.products.values_list("pk", flat=True))


class BannerForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Banner
        fields = ["kind", "title", "subtitle", "button_text", "link_url", "image", "position", "is_active", "starts_at", "ends_at"]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("starts_at", "ends_at"):
            self.fields[f].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]


class CampaignForm(StyledFormMixin, forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.filter(is_available=True).order_by("name"), required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )
    send_option = forms.ChoiceField(
        choices=[("draft", "Save as draft"), ("schedule", "Schedule for later"), ("now", "Send now")],
        initial="draft",
    )

    class Meta:
        model = Campaign
        fields = ["name", "subject", "message", "banner", "discount_info", "button_text", "audience", "scheduled_for"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 6}),
            "scheduled_for": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_for"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
        self.fields["scheduled_for"].required = False
        if self.instance.pk:
            self.fields["products"].initial = list(self.instance.products.values_list("pk", flat=True))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("send_option") == "schedule":
            when = cleaned.get("scheduled_for")
            if not when:
                self.add_error("scheduled_for", "Choose when to send.")
            elif when <= timezone.now():
                self.add_error("scheduled_for", "Pick a time in the future.")
        return cleaned


class SettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BusinessSettings
        exclude = []
        widgets = {"address": forms.Textarea(attrs={"rows": 2}), "delivery_info": forms.Textarea(attrs={"rows": 3})}


# --------------------------------------------------------------------------- website content
MAX_IMAGE_SIDE = 6000


class RichTextArea(forms.Textarea):
    """A textarea that static/js/richtext.js upgrades to a visual editor (it still works as plain HTML without JS)."""

    def __init__(self, attrs=None):
        import json

        base = {"data-richtext": "1", "rows": 14, "data-tokens": json.dumps(TOKEN_HELP)}
        base.update(attrs or {})
        super().__init__(attrs=base)


def _check_image_size(image):
    """Reject absurdly large images (pixels). File size and 'is really an image' are checked by the model field."""
    if image and hasattr(image, "image"):
        w, h = image.image.size
        if max(w, h) > MAX_IMAGE_SIDE:
            raise forms.ValidationError(f"Image is too large ({w}x{h}px). Please use one no larger than {MAX_IMAGE_SIDE}px.")
    return image


class PageDetailsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SitePage
        fields = ["title", "summary", "hero_image"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 3, "maxlength": 600})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].help_text = "You can use details such as {{business_name}} in titles."
        if self.instance.kind != SitePage.ABOUT:
            del self.fields["hero_image"]

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("A title is required.")
        return title

    def clean_hero_image(self):
        return _check_image_size(self.cleaned_data.get("hero_image"))


class SectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PageSection
        fields = ["title", "body", "image", "is_active"]
        widgets = {"body": RichTextArea()}

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("A section title is required.")
        return title

    def clean_body(self):
        body = sanitize_html(self.cleaned_data.get("body", ""))
        if len(body) > MAX_BODY_CHARS:
            raise forms.ValidationError(f"This section is too long ({len(body):,} characters). Please split it into two sections.")
        if not plain_text(body):
            raise forms.ValidationError("Please write some text for this section.")
        return body

    def clean_image(self):
        return _check_image_size(self.cleaned_data.get("image"))


class ContactInfoForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BusinessSettings
        fields = [
            "phone", "whatsapp_number", "email", "address", "opening_hours", "contact_instructions",
            "facebook_url", "instagram_url", "twitter_url", "tiktok_url", "youtube_url",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "opening_hours": forms.Textarea(attrs={"rows": 4, "placeholder": "Mon - Sat: 9am - 6pm\nSunday: Closed"}),
            "contact_instructions": forms.Textarea(attrs={"rows": 3}),
        }


class PolicyDetailsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BusinessSettings
        fields = ["delivery_estimate", "return_window"]
