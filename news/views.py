from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from urllib.parse import urlsplit

from .models import News


@require_GET
def home(request):
    articles = News.objects.order_by("-scraped_date", "-id")
    query = request.GET.get("q", "").strip()[:200]
    category = request.GET.get("category", "")
    language = request.GET.get("language", "")
    if query:
        articles = articles.filter(Q(title__icontains=query) | Q(content__icontains=query))
    if category:
        articles = articles.filter(category=category)
    if language:
        articles = articles.filter(language=language)
    page = Paginator(articles, 12).get_page(request.GET.get("page"))
    filters = request.GET.copy()
    filters.pop("page", None)
    return render(request, "news/home.html", {
        "page": page, "query": query, "category": category, "language": language,
        "filters": filters.urlencode(),
        "categories": News.objects.exclude(category="").order_by("category").values_list("category", flat=True).distinct(),
        "languages": News.objects.exclude(language="").order_by("language").values_list("language", flat=True).distinct(),
    })


@require_GET
def article_detail(request, pk):
    article = get_object_or_404(News, pk=pk)
    try:
        parsed = urlsplit(article.url)
        source_url = article.url if parsed.scheme in {"http", "https"} and parsed.hostname else None
    except ValueError:
        source_url = None
    return render(request, "news/detail.html", {"article": article, "source_url": source_url})
