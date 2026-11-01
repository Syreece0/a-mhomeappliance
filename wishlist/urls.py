from django.urls import path

from . import views

app_name = "wishlist"

urlpatterns = [
    path("", views.wishlist_list, name="list"),
    path("toggle/", views.toggle, name="toggle"),
    path("move-to-cart/", views.move_to_cart, name="move_to_cart"),
]
