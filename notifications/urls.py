from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("latest/", views.latest, name="latest"),
    path("mark-all-read/", views.mark_all_read, name="mark_all"),
    path("<int:pk>/open/", views.open_notification, name="open"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
    path("<int:pk>/delete/", views.delete, name="delete"),
]
