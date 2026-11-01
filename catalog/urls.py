from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("p/<slug:slug>/", views.product_detail, name="detail"),
    path("p/<slug:slug>/quick/", views.quick_view, name="quick_view"),
    path("p/<slug:slug>/review/", views.submit_review, name="review"),
]
