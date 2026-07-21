from django.urls import path

from apps.imports import views

urlpatterns = [
    path("", views.import_batch_list, name="import_batch_list"),
    path("new/", views.import_preview_create, name="import_preview_create"),
    path("legacy/", views.legacy_import_summary, name="legacy_import_summary"),
    path(
        "legacy/configurations/",
        views.legacy_import_configuration_list,
        name="legacy_import_configuration_list",
    ),
    path(
        "legacy/configurations/<uuid:config_id>/",
        views.legacy_import_configuration_detail,
        name="legacy_import_configuration_detail",
    ),
    path(
        "legacy/records/",
        views.legacy_import_daily_record_list,
        name="legacy_import_daily_record_list",
    ),
    path("legacy/issues/", views.legacy_import_issue_list, name="legacy_import_issue_list"),
    path("<uuid:batch_id>/", views.import_batch_detail, name="import_batch_detail"),
    path("<uuid:batch_id>/confirm/", views.import_batch_confirm, name="import_batch_confirm"),
    path("<uuid:batch_id>/rollback/", views.import_batch_rollback, name="import_batch_rollback"),
]
