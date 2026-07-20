from django.urls import path

from apps.operations import views

urlpatterns = [
    path("expected-executions/", views.expected_execution_list, name="expected_execution_list"),
    path(
        "expected-executions/generate/",
        views.expected_execution_generate,
        name="expected_execution_generate",
    ),
    path(
        "expected-executions/mark-missing/",
        views.expected_execution_mark_missing,
        name="expected_execution_mark_missing",
    ),
    path("daily-control/", views.daily_control_list, name="daily_control_list"),
    path("daily-control/new/", views.daily_control_create, name="daily_control_create"),
    path("daily-control/export/", views.daily_control_export, name="daily_control_export"),
]
