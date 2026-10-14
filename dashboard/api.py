"""JSON endpoints behind the operations dashboard.

These sit beside the documented ``/api/v1`` API and reuse its envelope,
``X-API-Key`` authentication, and pipeline job runner. They add what an operator
needs that the public API does not expose: live run progress and logs,
cancellation, per-publisher source selection, a data-file inventory, a
read-only configuration snapshot, and an overview that aggregates it all.
"""

import csv
import sys
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.http import FileResponse
from django.utils import timezone

from news.api import jobs, services
from news.api.http import ApiError, _authorized, api_view, error_response
from news.models import News
from pipeline import flow, progress

DATA_DIR = flow.BASE_DIR / "data"
MAX_FILES = 200
TIMELINE_DAYS = 14
_ROW_COUNT_CACHE = {}

try:  # Article bodies can exceed csv's default 128 KiB field limit.
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
except (OverflowError, ValueError):  # pragma: no cover - platform specific
    pass


def _count_rows(path):
    """Count CSV records, cached per (mtime, size) so polling stays cheap."""
    stat = path.stat()
    key = str(path)
    cached = _ROW_COUNT_CACHE.get(key)
    if cached and cached[0] == (stat.st_mtime_ns, stat.st_size):
        return cached[1]
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)  # header
            rows = sum(1 for _ in reader)
    except (OSError, csv.Error, UnicodeDecodeError):
        rows = None
    _ROW_COUNT_CACHE[key] = ((stat.st_mtime_ns, stat.st_size), rows)
    return rows


def _role(path):
    for role, known in (
        ("raw", flow.RAW_CSV_PATH),
        ("unique", flow.UNIQUE_CSV_PATH),
        ("processed", flow.PROCESSED_CSV_PATH),
    ):
        if path.resolve() == known.resolve():
            return role
    return "other"


def list_data_files():
    if not DATA_DIR.is_dir():
        return []
    items = []
    for path in sorted(DATA_DIR.rglob("*.csv"))[:MAX_FILES]:
        if not path.is_file():
            continue
        stat = path.stat()
        items.append({
            "name": path.relative_to(DATA_DIR).as_posix(),
            "role": _role(path),
            "rows": _count_rows(path),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.get_current_timezone()
            ).isoformat(),
        })
    return items


def _funnel(by_status, processed_total):
    """Survival counts after each processing stage."""
    get = lambda status: by_status.get(status, 0)  # noqa: E731
    content = processed_total - get("CONTENT_REJECTED")
    facts = content - get("FACT_EXTRACTION_FAILED")
    generated = facts - get("ARTICLE_GENERATION_FAILED")
    verified = generated - get("ARTICLE_VERIFICATION_FAILED")
    approved = get("APPROVED")
    return [
        {"key": "processed", "label": "Processed", "count": processed_total},
        {"key": "content_check", "label": "Passed content check", "count": content},
        {"key": "fact_extraction", "label": "Facts extracted", "count": facts},
        {"key": "article_generation", "label": "Article generated", "count": generated},
        {"key": "verification", "label": "Verification completed", "count": verified},
        {"key": "approved", "label": "Approved", "count": approved},
    ]


def _source_rows(processed_rows):
    db = {
        row["source"]: row
        for row in News.objects.exclude(source="")
        .values("source")
        .annotate(articles=Count("id"), latest=Max("scraped_date"), categories=Count("category", distinct=True))
    }
    processed = Counter()
    approved = Counter()
    for row in processed_rows:
        name = row.get("source", "")
        processed[name] += 1
        if row.get("status") == "APPROVED":
            approved[name] += 1
    extra = sorted((set(db) | set(processed)) - set(flow.SOURCE_NAMES) - {""})
    items = []
    for name in [*flow.SOURCE_NAMES, *extra]:
        row = db.get(name)
        items.append({
            "name": name,
            "configured": name in flow.SOURCE_NAMES,
            "articles": row["articles"] if row else 0,
            "categories": row["categories"] if row else 0,
            "latest_scraped": row["latest"].isoformat() if row and row["latest"] else None,
            "processed": processed.get(name, 0),
            "approved": approved.get(name, 0),
        })
    return items


def _timeline():
    since = timezone.now() - timedelta(days=TIMELINE_DAYS - 1)
    counts = {
        row["day"]: row["count"]
        for row in News.objects.filter(scraped_date__gte=since.replace(hour=0, minute=0, second=0, microsecond=0))
        .annotate(day=TruncDate("scraped_date"))
        .values("day")
        .annotate(count=Count("id"))
    }
    today = timezone.localdate()
    days = [today - timedelta(days=offset) for offset in range(TIMELINE_DAYS - 1, -1, -1)]
    return [{"date": day.isoformat(), "count": counts.get(day, 0)} for day in days]


def _config():
    from ai import config as ai_config

    return {
        "generation": {
            "url": ai_config.OLLAMA_URL,
            "model": ai_config.MODEL_NAME,
            "temperature": ai_config.TEMPERATURE,
            "max_tokens": ai_config.MAX_TOKENS,
        },
        "deduplication": {"threshold": flow.DEDUP_THRESHOLD},
        "paths": {
            "raw": str(flow.RAW_CSV_PATH.relative_to(flow.BASE_DIR).as_posix()),
            "unique": str(flow.UNIQUE_CSV_PATH.relative_to(flow.BASE_DIR).as_posix()),
            "processed": str(flow.PROCESSED_CSV_PATH.relative_to(flow.BASE_DIR).as_posix()),
        },
        "server": {
            "debug": bool(settings.DEBUG),
            "api_key_required": bool(getattr(settings, "NEWS_API_KEY", "")),
            "view_retention_days": settings.VIEW_RETENTION_DAYS,
            "database": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
        },
        "sources": list(flow.SOURCE_NAMES),
        "job_history_limit": jobs.MAX_JOBS,
    }


def serialize_run(job, after=0, include_log=False):
    data = job.to_dict()
    data["sources"] = job.request.get("sources")
    started = job.started_at or job.created_at
    ended = job.finished_at or timezone.now()
    data["duration_seconds"] = max(0.0, (ended - started).total_seconds())
    data["progress"] = job.tracker.snapshot(after=after, include_log=include_log)
    return data


@api_view(["GET"])
def overview(request, body):
    rows = services.read_processed_rows()
    by_status = Counter(row.get("status", "") for row in rows)
    files = list_data_files()
    by_role = {item["role"]: item for item in files}
    latest = News.objects.aggregate(latest=Max("scraped_date"))["latest"]
    active = next((job for job in jobs.recent() if job.status in jobs.ACTIVE_STATUSES), None)
    recent = jobs.recent(1)
    total_processed = len(rows)
    return {
        "generated_at": timezone.now().isoformat(),
        "totals": {
            "articles": News.objects.count(),
            "raw_rows": (by_role.get("raw") or {}).get("rows"),
            "unique_rows": (by_role.get("unique") or {}).get("rows"),
            "processed": total_processed,
            "approved": by_status.get("APPROVED", 0),
            "latest_scraped": latest.isoformat() if latest else None,
        },
        "by_status": dict(by_status),
        "funnel": _funnel(by_status, total_processed),
        "timeline": _timeline(),
        "sources": _source_rows(rows),
        "files": files,
        "config": _config(),
        "active_run": serialize_run(active) if active else None,
        "latest_run": serialize_run(recent[0]) if recent else None,
    }


@api_view(["GET", "POST"])
def runs(request, body):
    if request.method == "GET":
        items = [serialize_run(job) for job in jobs.recent()]
        return {"items": items, "meta": {"count": len(items), "limit": jobs.MAX_JOBS}}

    body = dict(body)
    raw_sources = body.pop("sources", None)
    payload = services.parse_run_payload(body)
    if raw_sources is not None:
        try:
            names = flow.validate_sources(raw_sources)
        except ValueError as error:
            raise ApiError("invalid_field", str(error), 400, {"field": "sources"}) from None
        if not payload["scrape"]:
            raise ApiError(
                "invalid_field", "sources can only be chosen when scrape is enabled", 400,
                {"field": "sources"},
            )
        if len(names) < len(flow.SOURCE_NAMES):
            payload["sources"] = names
    job = jobs.submit(payload)
    data = serialize_run(job)
    return data, 202, {"Location": f"/dashboard/api/runs/{job.id}/"}


def _after(request):
    raw = request.GET.get("after", "0")
    try:
        return max(0, int(raw))
    except ValueError:
        raise ApiError("invalid_query_parameter", "after must be an integer", 400,
                       {"parameter": "after"}) from None


@api_view(["GET"])
def run_detail(request, body, run_id):
    job = jobs.get(run_id)
    if job is None:
        raise ApiError("not_found", "Pipeline run not found", 404)
    return serialize_run(job, after=_after(request), include_log=True)


@api_view(["POST"])
def run_cancel(request, body, run_id):
    job = jobs.cancel(run_id)
    return serialize_run(job, include_log=True), 202


@api_view(["GET"])
def files(request, body):
    items = list_data_files()
    return {"items": items, "meta": {"count": len(items)}}


def file_download(request, name):
    """Stream one CSV from data/ as an attachment (API key via header)."""
    if request.method != "GET":
        return error_response("method_not_allowed", "Only GET is allowed", 405)
    if not _authorized(request):
        return error_response("unauthorized", "A valid X-API-Key header is required", 401)
    try:
        path = flow.resolve_project_path(DATA_DIR / name, "file")
    except ValueError:
        return error_response("not_found", "File not found", 404)
    if not path.is_file():
        return error_response("not_found", "File not found", 404)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name,
                        content_type="text/csv; charset=utf-8")
