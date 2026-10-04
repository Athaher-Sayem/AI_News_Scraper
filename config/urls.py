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

from news.spa import spa

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("news.api.urls")),
    # Server-rendered source collection pages (kept alongside the SPA).
    path("collected/", include("news.urls")),
    # React single-page app served at the site root; must stay last so the
    # specific admin/api/collected routes above win.
    re_path(r"^(?P<path>.*)$", spa, name="spa"),
]
