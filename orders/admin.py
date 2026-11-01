from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "name", "unit_price", "quantity", "stock_applied")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "user", "status", "subtotal", "wallet_amount", "amount_payable", "paid_at", "needs_attention")
    list_filter = ("status", "needs_attention")
    search_fields = ("number", "email", "full_name", "phone")
    inlines = [OrderItemInline]
    # Status/payment changes must go through the services (stock, wallet, emails); keep the raw admin read-only.
    readonly_fields = [f.name for f in Order._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(OrderStatusHistory)
