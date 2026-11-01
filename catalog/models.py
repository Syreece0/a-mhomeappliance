from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, Q
from django.templatetags.static import static
from django.urls import reverse

from core.utils import unique_slug
from core.validators import validate_image_size


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=190, unique=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    description = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, validators=[validate_image_size])
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return f"{self.parent.name} / {self.name}" if self.parent_id else self.name

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError("A category cannot be its own parent.")
        if self.parent_id and self.parent.parent_id:
            raise ValidationError("Only two category levels are supported.")

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.parent.name}-{self.name}" if self.parent_id else self.name
            self.slug = unique_slug(Category, base, self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{reverse('catalog:list')}?category={self.slug}"

    def family_ids(self):
        return [self.pk] + list(self.children.values_list("pk", flat=True))


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_available=True)

    def with_rating(self):
        approved = Q(reviews__is_approved=True)
        return self.annotate(
            avg_rating=Avg("reviews__rating", filter=approved),
            review_count=Count("reviews", filter=approved, distinct=True),
        )


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    brand = models.CharField(max_length=100, blank=True, db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    previous_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))]
    )
    stock = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True, help_text="Untick to hide the product from the shop.")
    warranty = models.CharField(max_length=150, blank=True)
    specifications = models.TextField(blank=True, help_text="One per line, as 'Label: value'.")
    is_featured = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    sold_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_available", "-created_at"]),
            models.Index(fields=["-sold_count"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="product_price_non_negative"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Product, self.name, self, max_length=215)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:detail", args=[self.slug])

    @property
    def is_in_stock(self):
        return self.is_available and self.stock > 0

    @property
    def discount_percent(self):
        if self.previous_price and self.previous_price > self.price:
            return int(((self.previous_price - self.price) / self.previous_price * 100).quantize(Decimal("1")))
        return 0

    @property
    def primary_image(self):
        images = list(self.images.all())
        if not images:
            return None
        for img in images:
            if img.is_primary:
                return img
        return images[0]

    @property
    def image_url(self):
        img = self.primary_image
        if img and img.image:
            return img.image.url
        return static("img/placeholder.svg")

    @property
    def spec_list(self):
        rows = []
        for line in self.specifications.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                label, _, value = line.partition(":")
                rows.append((label.strip(), value.strip()))
            else:
                rows.append(("", line))
        return rows


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/", validators=[validate_image_size])
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-is_primary", "position", "id"]

    def __str__(self):
        return f"Image for {self.product_id}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False, help_text="Reviews are published after admin approval.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="one_review_per_user_per_product"),
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"),
        ]

    def __str__(self):
        return f"{self.product} - {self.rating}/5 by {self.user_id}"


class Promotion(models.Model):
    """Percentage discount over a set of products during a time window.

    Prices are applied/reverted by catalog.services.sync_promotions (run every minute by Celery beat
    and immediately when an admin saves a promotion).
    """

    name = models.CharField(max_length=140)
    discount_percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(90)]
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    products = models.ManyToManyField(Product, through="PromotionItem", blank=True, related_name="promotions")
    applied = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{self.name} ({self.discount_percent}% off)"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError("End time must be after the start time.")


class PromotionItem(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="promotion_items")
    original_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False)
    original_previous_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["promotion", "product"], name="unique_product_per_promotion")]
