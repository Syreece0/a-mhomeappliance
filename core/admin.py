from django.contrib import admin

from .models import Banner, BusinessSettings

admin.site.register(BusinessSettings)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "position", "is_active", "starts_at", "ends_at")
    list_filter = ("kind", "is_active")
