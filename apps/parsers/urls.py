from django.urls import path

from apps.parsers import views

urlpatterns = [
    path("review/", views.review_queue, name="parser_review_queue"),
    path("parse/", views.parse_unprocessed, name="parse_unprocessed_messages"),
    path("review/<uuid:item_id>/", views.parsed_item_review, name="parsed_item_review"),
]
