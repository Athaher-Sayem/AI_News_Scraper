from django.urls import path

from news.api import views

app_name = "news_api"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("stats/", views.stats, name="stats"),
    path("articles/", views.articles, name="article-list"),
    path("articles/<int:pk>/", views.article_detail, name="article-detail"),
    path("processed/", views.processed, name="processed-list"),
    path("processed/<int:row>/", views.processed_detail, name="processed-detail"),
    path("pipeline/runs/", views.runs, name="run-list"),
    path("pipeline/runs/<str:run_id>/", views.run_detail, name="run-detail"),
]
