from django.urls import path

from news.api import views

app_name = "news_api"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("stats/", views.stats, name="stats"),
    path("categories/", views.categories, name="category-list"),
    path("sources/", views.sources, name="source-list"),
    path("articles/", views.articles, name="article-list"),
    path("articles/<int:pk>/", views.article_detail, name="article-detail"),
    path("articles/<int:pk>/related/", views.article_related, name="article-related"),
    path("processed/", views.processed, name="processed-list"),
    path("processed/<int:row>/", views.processed_detail, name="processed-detail"),
    path("pipeline/runs/", views.runs, name="run-list"),
    path("pipeline/runs/<str:run_id>/", views.run_detail, name="run-detail"),
    path("openapi.json", views.openapi_spec, name="openapi"),
    path("docs/", views.api_docs, name="docs"),
]
