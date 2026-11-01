from django import forms

from core.forms import StyledFormMixin

from .models import Review


class ReviewForm(StyledFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(5, "5 - Excellent"), (4, "4 - Good"), (3, "3 - Average"), (2, "2 - Poor"), (1, "1 - Terrible")],
        coerce=int,
    )

    class Meta:
        model = Review
        fields = ["rating", "title", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}
