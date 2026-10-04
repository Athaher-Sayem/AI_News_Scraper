"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path, re_path

from news import seo
from news.api import views as api_views
from news.spa import spa

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("news.api.urls")),
    # Unknown API paths must return the JSON error envelope, never SPA HTML.
    re_path(r"^api/", api_views.api_not_found, name="api-not-found"),
    path("robots.txt", seo.robots, name="robots"),
    path("sitemap.xml", seo.sitemap, name="sitemap"),
    # Server-rendered source collection pages (kept alongside the SPA).
    path("collected/", include("news.urls")),
    # React single-page app served at the root. The negative lookahead keeps
    # backend/static prefixes out of the SPA so their unknown paths 404 instead
    # of returning index.html.
    re_path(r"^(?!admin/|static/|api/)(?P<path>.*)$", spa, name="spa"),
]
