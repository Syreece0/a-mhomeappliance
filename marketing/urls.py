from django.urls import path

from . import views

app_name = "marketing"

urlpatterns = [
    path("subscribe/", views.newsletter_subscribe, name="subscribe"),
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
