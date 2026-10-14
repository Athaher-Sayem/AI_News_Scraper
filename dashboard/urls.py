from django.urls import path, re_path

from dashboard import api, views

app_name = "dashboard"

urlpatterns = [
    path("api/overview/", api.overview, name="overview"),
    path("api/runs/", api.runs, name="runs"),
    path("api/runs/<str:run_id>/", api.run_detail, name="run-detail"),
    path("api/runs/<str:run_id>/cancel/", api.run_cancel, name="run-cancel"),
    path("api/files/", api.files, name="files"),
    re_path(r"^api/files/(?P<name>.+)/download/$", api.file_download, name="file-download"),
    re_path(r"^assets/(?P<path>.+)$", views.asset, name="asset"),
    path("", views.asset, name="index"),
]
