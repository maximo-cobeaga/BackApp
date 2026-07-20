from django.urls import path

from apps.operations import views

urlpatterns = [
    path("daily-control/", views.daily_control_list, name="daily_control_list"),
    path("daily-control/new/", views.daily_control_create, name="daily_control_create"),
    path("daily-control/export/", views.daily_control_export, name="daily_control_export"),
]
