"""Small SEO endpoints for the React frontend.

The SPA handles all client routes, so crawlers get a plain robots file and an
XML sitemap listing the home page, section pages, and every collected article.
The sitemap is cached; the cache key includes the article count and newest
scraped timestamp, so it refreshes automatically when the data changes.
"""

from xml.sax.saxutils import escape

from django.core.cache import cache
from django.db.models import Count, Max
from django.http import HttpResponse
from django.views.decorators.http import require_GET

SECTION_SLUGS = ("latest", "business", "opinion", "sports", "culture", "lifestyle", "world")
SITEMAP_CACHE_SECONDS = 3600


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

    origin = request.build_absolute_uri("/").rstrip("/")
    summary = News.objects.aggregate(total=Count("pk"), latest=Max("scraped_date"))
    latest = summary["latest"].isoformat() if summary["latest"] else "none"
    cache_key = f"sitemap:{origin}:{summary['total']}:{latest}"

    body = cache.get(cache_key)
    if body is None:
        sections = "".join(
            f"<url><loc>{escape(origin)}/section/{slug}</loc></url>" for slug in SECTION_SLUGS
        )
        entries = []
        rows = News.objects.order_by("pk").values_list("pk", "scraped_date").iterator()
        for pk, scraped_date in rows:
            lastmod = f"<lastmod>{scraped_date.date().isoformat()}</lastmod>" if scraped_date else ""
            entries.append(f"<url><loc>{escape(origin)}/article/{pk}</loc>{lastmod}</url>")
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{escape(origin)}/</loc></url>{sections}{''.join(entries)}</urlset>"
        )
        cache.set(cache_key, body, SITEMAP_CACHE_SECONDS)
    return HttpResponse(body, content_type="application/xml; charset=utf-8")
