from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("objects/", views.protected_object_list, name="protected_object_list"),
    path("objects/new/", views.protected_object_create, name="protected_object_create"),
    path("relations/", views.object_relation_list, name="object_relation_list"),
    path("relations/new/", views.object_relation_create, name="object_relation_create"),
]
