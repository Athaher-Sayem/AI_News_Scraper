"""Small SEO endpoints for the React frontend.

The SPA handles all client routes, so crawlers get a plain robots file and an
XML sitemap listing the home page, section pages, and every collected article.
"""

from django.http import HttpResponse
from django.views.decorators.http import require_GET

SECTION_SLUGS = ("latest", "business", "opinion", "sports", "culture", "lifestyle", "world")


@require_GET
def robots(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@require_GET
def sitemap(request):
    from news.models import News

    locations = [request.build_absolute_uri("/")]
    locations += [request.build_absolute_uri(f"/section/{slug}") for slug in SECTION_SLUGS]
    locations += [
        request.build_absolute_uri(f"/article/{pk}")
        for pk in News.objects.values_list("pk", flat=True).iterator()
    ]
    entries = "".join(f"<url><loc>{location}</loc></url>" for location in locations)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )
    return HttpResponse(body, content_type="application/xml; charset=utf-8")
