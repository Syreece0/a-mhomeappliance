from django.contrib import admin

from .models import EmailDelivery, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ("to_email", "subject", "kind", "status", "attempts", "created_at")
    list_filter = ("status", "kind", "is_marketing")
    search_fields = ("to_email", "subject")
