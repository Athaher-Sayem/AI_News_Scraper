import csv
import hashlib
from collections import Counter
from datetime import timedelta

import requests
from django.conf import settings
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone

from news.api.http import ApiError
from news.api.serializers import serialize_article, serialize_processed
from news.models import ArticleView, News
from pipeline import flow

TRENDING_WINDOW_DAYS = 7

ARTICLE_FILTERS = {"source", "category", "language", "q"}
PROCESSED_FILTERS = {"status", "source", "q"}
PAGE_PARAMS = {"page", "page_size"}
STATUSES = {
    "APPROVED",
    "CONTENT_REJECTED",
    "FACT_EXTRACTION_FAILED",
    "ARTICLE_GENERATION_FAILED",
    "ARTICLE_REJECTED",
    "ARTICLE_VERIFICATION_FAILED",
}
MAX_PAGE_SIZE = 100
MAX_QUERY_LENGTH = 200


def _reject_unknown(query, allowed):
    unknown = set(query.keys()) - allowed
    if unknown:
        raise ApiError(
            "unknown_query_parameter",
            "Unknown query parameters",
            400,
            {"parameters": sorted(unknown)},
        )


def _int_param(query, name, default, maximum=None):
    raw = query.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(
            "invalid_query_parameter",
            f"{name} must be an integer",
            400,
            {"parameter": name},
        ) from None
    if value < 1 or (maximum is not None and value > maximum):
        raise ApiError(
            "invalid_query_parameter",
            f"{name} must be between 1 and {maximum}" if maximum is not None else f"{name} must be positive",
            400,
            {"parameter": name, "maximum": maximum},
        )
    return value


def _search_term(query):
    value = query.get("q", "").strip()
    if len(value) > MAX_QUERY_LENGTH:
        raise ApiError(
            "invalid_query_parameter",
            f"q must be at most {MAX_QUERY_LENGTH} characters",
            400,
            {"parameter": "q"},
        )
    return value


def _generation_status():
    from ai.config import MODEL_NAME, OLLAMA_URL

    tags_url = OLLAMA_URL.rsplit("/", 1)[0] + "/tags"
    status = {"available": False, "model": MODEL_NAME, "model_installed": False}
    try:
        response = requests.get(tags_url, timeout=2)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            return status
        names = [model.get("name") for model in payload["models"] if isinstance(model, dict)]
        configured_name = MODEL_NAME if ":" in MODEL_NAME else MODEL_NAME + ":latest"
        status["available"] = True
        status["model_installed"] = configured_name in names
    except (requests.RequestException, ValueError):
        pass
    return status


def health():
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        database_ok = False
    data = {
        "status": "ok" if database_ok else "degraded",
        "database": {"available": database_ok},
        "generation": _generation_status(),
    }
    return data, 200 if database_ok else 503


def list_articles(query):
    _reject_unknown(query, ARTICLE_FILTERS | PAGE_PARAMS)
    queryset = News.objects.all()
    if query.get("source"):
        queryset = queryset.filter(source=query["source"])
    categories = [value for value in query.getlist("category") if value]
    if categories:
        queryset = queryset.filter(category__in=categories)
    if query.get("language"):
        queryset = queryset.filter(language=query["language"])
    term = _search_term(query)
    if term:
        queryset = queryset.filter(Q(title__icontains=term) | Q(content__icontains=term))
    queryset = queryset.order_by("-scraped_date", "-id")
    page = _int_param(query, "page", 1)
    page_size = _int_param(query, "page_size", 20, maximum=MAX_PAGE_SIZE)
    total = queryset.count()
    start = (page - 1) * page_size
    page_items = list(queryset[start : start + page_size]) if start < total else []
    return {
        "items": [serialize_article(item) for item in page_items],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "count": len(page_items),
        },
    }


def get_article(pk):
    try:
        item = News.objects.get(pk=pk)
    except News.DoesNotExist:
        raise ApiError("not_found", "Article not found", 404) from None
    return serialize_article(item)


def read_processed_rows():
    path = flow.PROCESSED_CSV_PATH
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def list_processed(query):
    _reject_unknown(query, PROCESSED_FILTERS | PAGE_PARAMS)
    status = query.get("status", "")
    if status and status not in STATUSES:
        raise ApiError(
            "invalid_query_parameter",
            "status must be a known pipeline status",
            400,
            {"parameter": "status", "allowed": sorted(STATUSES)},
        )
    rows = list(enumerate(read_processed_rows()))
    if status:
        rows = [(index, row) for index, row in rows if row.get("status", "") == status]
    if query.get("source"):
        rows = [(index, row) for index, row in rows if row.get("source", "") == query["source"]]
    term = _search_term(query)
    if term:
        rows = [(index, row) for index, row in rows if term.lower() in row.get("title", "").lower()]

    page = _int_param(query, "page", 1)
    page_size = _int_param(query, "page_size", 20, maximum=MAX_PAGE_SIZE)
    total = len(rows)
    start = (page - 1) * page_size
    window = rows[start : start + page_size]
    return {
        "items": [serialize_processed(row, index) for index, row in window],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
            "count": len(window),
            "source_file": str(flow.PROCESSED_CSV_PATH),
        },
    }


def get_processed(row):
    rows = read_processed_rows()
    if row >= len(rows):
        raise ApiError("not_found", "Processed row not found", 404)
    return serialize_processed(rows[row], row)


def stats():
    by_source = dict(
        News.objects.values("source")
        .annotate(count=Count("id"))
        .order_by("source")
        .values_list("source", "count")
    )
    latest = News.objects.order_by("-scraped_date").values_list("scraped_date", flat=True).first()
    rows = read_processed_rows()
    by_status = Counter(row.get("status", "") for row in rows)
    return {
        "articles": {
            "total": News.objects.count(),
            "by_source": by_source,
            "latest_scraped_date": latest.isoformat() if latest else None,
        },
        "processed": {
            "total": len(rows),
            "by_status": dict(by_status),
            "available": bool(rows) or flow.PROCESSED_CSV_PATH.exists(),
        },
    }


def list_categories():
    rows = (
        News.objects.exclude(category="")
        .values("category")
        .annotate(count=Count("id"))
        .order_by("-count", "category")
    )
    return {"items": [{"category": row["category"], "count": row["count"]} for row in rows]}


def list_sources():
    rows = (
        News.objects.exclude(source="")
        .values("source")
        .annotate(count=Count("id"))
        .order_by("-count", "source")
    )
    return {"items": [{"source": row["source"], "count": row["count"]} for row in rows]}


def related_articles(pk, limit=6):
    try:
        article = News.objects.get(pk=pk)
    except News.DoesNotExist:
        raise ApiError("not_found", "Article not found", 404) from None
    queryset = (
        News.objects.filter(category=article.category)
        .exclude(pk=pk)
        .order_by("-scraped_date", "-id")[:limit]
    )
    return {"items": [serialize_article(item) for item in queryset]}


def _client_key(request):
    """A privacy-preserving per-client key: a salted hash of address + agent.

    ``X-Forwarded-For`` is only consulted when ``VIEW_TRUST_PROXY`` is enabled,
    so clients cannot spoof the header to evade the dedupe/rate limits.
    """
    ip = request.META.get("REMOTE_ADDR", "")
    if settings.VIEW_TRUST_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
    agent = request.META.get("HTTP_USER_AGENT", "")
    material = f"{settings.SECRET_KEY}|{ip}|{agent}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:64]


def record_view(pk, request):
    """Record one article view, deduplicated and rate-limited per client."""
    try:
        article = News.objects.get(pk=pk)
    except News.DoesNotExist:
        raise ApiError("not_found", "Article not found", 404) from None

    client_key = _client_key(request)
    if client_key:
        now = timezone.now()
        rate_since = now - timedelta(seconds=settings.VIEW_RATE_WINDOW_SECONDS)
        recent = ArticleView.objects.filter(client_key=client_key, created_at__gte=rate_since).count()
        if recent >= settings.VIEW_RATE_MAX:
            raise ApiError("rate_limited", "Too many view requests", 429)

        dedupe_since = now - timedelta(seconds=settings.VIEW_DEDUP_SECONDS)
        already_recorded = ArticleView.objects.filter(
            article=article, client_key=client_key, created_at__gte=dedupe_since
        ).exists()
        if already_recorded:
            return {"recorded": False}

    ArticleView.objects.create(article=article, client_key=client_key)
    return {"recorded": True}


def list_trending(limit=10):
    since = timezone.now() - timedelta(days=TRENDING_WINDOW_DAYS)
    ranked = (
        ArticleView.objects.filter(created_at__gte=since)
        .values("article_id")
        .annotate(views=Count("id"))
        .order_by("-views")[:limit]
    )
    counts = {row["article_id"]: row["views"] for row in ranked}
    articles = {article.pk: article for article in News.objects.filter(pk__in=counts)}
    items = [
        {**serialize_article(articles[pk]), "views": counts[pk]}
        for pk in counts
        if pk in articles
    ]
    if not items:
        items = [
            serialize_article(article)
            for article in News.objects.order_by("-scraped_date", "-id")[:limit]
        ]
    return {"items": items}


def parse_run_payload(body):
    allowed = {"limit", "input", "output", "scrape", "deduplicate"}
    unknown = set(body.keys()) - allowed
    if unknown:
        raise ApiError(
            "unknown_field",
            "Unknown request fields",
            400,
            {"fields": sorted(unknown)},
        )

    limit = body.get("limit", 1)
    if limit == "all":
        limit = None
    elif isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ApiError(
            "invalid_limit",
            'limit must be a positive integer or the string "all"',
            400,
            {"field": "limit"},
        )

    for field in ("scrape", "deduplicate"):
        if not isinstance(body.get(field, False), bool):
            raise ApiError(
                "invalid_field",
                f"{field} must be a boolean",
                400,
                {"field": field},
            )

    input_csv = body.get("input", str(flow.UNIQUE_CSV_PATH))
    output_csv = body.get("output", str(flow.PROCESSED_CSV_PATH))
    if not isinstance(input_csv, str) or not isinstance(output_csv, str):
        raise ApiError(
            "invalid_field",
            "input and output must be path strings",
            400,
            {"fields": ["input", "output"]},
        )

    try:
        input_path, output_path = flow.validate_paths(
            input_csv,
            output_csv,
            scrape=body.get("scrape", False),
            deduplicate=body.get("deduplicate", False),
        )
        flow.validate_limit(limit)
    except ValueError as error:
        raise ApiError("invalid_path", str(error), 400) from None

    return {
        "input_csv": input_path,
        "output_csv": output_path,
        "limit": limit,
        "scrape": bool(body.get("scrape", False)),
        "deduplicate": bool(body.get("deduplicate", False)),
    }
