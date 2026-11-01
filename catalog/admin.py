from django.contrib import admin

from .models import Category, Product, ProductImage, Promotion, PromotionItem, Review


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "category", "price", "stock", "is_available", "is_featured")
    list_filter = ("is_available", "is_featured", "is_best_seller", "is_new_arrival", "category")
    search_fields = ("name", "brand")
    inlines = [ProductImageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "position", "is_active")
    list_filter = ("is_active",)


class PromotionItemInline(admin.TabularInline):
    model = PromotionItem
    extra = 1


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("name", "discount_percent", "starts_at", "ends_at", "is_active", "applied")
    inlines = [PromotionItemInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_verified_purchase", "is_approved", "created_at")
    list_filter = ("is_approved", "rating")
