"""Root URL configuration."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from apps.operations import views as operation_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", operation_views.dashboard, name="dashboard"),
    path("customers/", include("apps.customers.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("backups/", include("apps.backups.urls")),
    path("imports/", include("apps.imports.urls")),
    path("operations/", include("apps.operations.urls")),
]
