from django.urls import path

from apps.backups import views

urlpatterns = [
    path("", views.configuration_summary, name="backup_configuration_summary"),
    path("technologies/", views.technology_list, name="backup_technology_list"),
    path("technologies/new/", views.technology_create, name="backup_technology_create"),
    path("jobs/", views.job_list, name="backup_job_list"),
    path("jobs/new/", views.job_create, name="backup_job_create"),
    path("targets/", views.target_list, name="backup_target_list"),
    path("targets/new/", views.target_create, name="backup_target_create"),
    path("schedules/new/", views.schedule_create, name="backup_schedule_create"),
    path("destinations/new/", views.destination_create, name="backup_destination_create"),
    path("retention/new/", views.retention_create, name="backup_retention_create"),
]
