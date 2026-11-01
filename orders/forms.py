from django import forms

from accounts.forms import clean_phone_value
from core.constants import STATE_CHOICES
from core.forms import StyledFormMixin


class CheckoutForm(StyledFormMixin, forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    address = forms.CharField(label="Delivery address", widget=forms.Textarea(attrs={"rows": 3}))
    state = forms.ChoiceField(choices=STATE_CHOICES)
    city = forms.CharField(max_length=80)
    notes = forms.CharField(
        label="Additional delivery instructions", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    use_wallet = forms.BooleanField(label="Use my referral wallet balance", required=False)
    only_product = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def clean_phone(self):
        value = clean_phone_value(self.cleaned_data.get("phone"))
        if not value:
            raise forms.ValidationError("Phone number is required.")
        return value

    def clean_state(self):
        state = self.cleaned_data["state"]
        if not state:
            raise forms.ValidationError("Select a state.")
        return state
