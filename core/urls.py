from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("r/<str:code>/", views.referral_landing, name="referral_landing"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("policies/", views.policies, name="policies"),
    path("policies/<slug:slug>/", views.policy, name="policy"),
    path("healthz/", views.healthz, name="healthz"),
]
