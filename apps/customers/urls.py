from django.urls import path

from apps.customers import views

urlpatterns = [
    path("", views.customer_list, name="customer_list"),
    path("new/", views.customer_create, name="customer_create"),
    path("sites/", views.site_list, name="site_list"),
    path("sites/new/", views.site_create, name="site_create"),
]
