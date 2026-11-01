from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("callback/", views.callback, name="callback"),
    path("webhook/", views.webhook, name="webhook"),
    path("pay/<str:number>/", views.pay, name="pay"),
    path("recheck/<str:number>/", views.recheck, name="recheck"),
]
