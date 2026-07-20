from django.urls import path

from apps.imports import views

urlpatterns = [
    path("", views.import_batch_list, name="import_batch_list"),
    path("new/", views.import_preview_create, name="import_preview_create"),
    path("<uuid:batch_id>/", views.import_batch_detail, name="import_batch_detail"),
    path("<uuid:batch_id>/confirm/", views.import_batch_confirm, name="import_batch_confirm"),
    path("<uuid:batch_id>/rollback/", views.import_batch_rollback, name="import_batch_rollback"),
]
