from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("checkout/", views.checkout, name="checkout"),
    path("buy-now/", views.buy_now, name="buy_now"),
    path("<str:number>/", views.order_detail, name="detail"),
    path("<str:number>/cancel/", views.cancel, name="cancel"),
]
