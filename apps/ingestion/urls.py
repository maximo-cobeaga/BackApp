from django.urls import path

from apps.ingestion import views

urlpatterns = [
    path("connectors/", views.connector_list, name="mail_connector_list"),
    path("connectors/new/", views.connector_create, name="mail_connector_create"),
    path("connectors/<uuid:connector_id>/sync/", views.connector_sync, name="mail_connector_sync"),
    path("messages/", views.message_list, name="inbound_message_list"),
]
