from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from news.api import jobs, services
from news.api.http import ApiError, api_view, error_response
from news.api.openapi import DOCS_HTML, build_spec


@require_GET
def openapi_spec(request):
    """Raw OpenAPI document (not wrapped in the data envelope)."""
    return JsonResponse(build_spec())


@require_GET
def api_docs(request):
    return HttpResponse(DOCS_HTML, content_type="text/html; charset=utf-8")


@api_view(["GET"], public=True)
def health(request, body):
    return services.health()


@api_view(["GET"])
def articles(request, body):
    return services.list_articles(request.GET)


@api_view(["GET"])
def article_detail(request, body, pk):
    return services.get_article(pk)


@api_view(["GET"])
def processed(request, body):
    return services.list_processed(request.GET)


@api_view(["GET"])
def processed_detail(request, body, row):
    return services.get_processed(row)


@api_view(["GET"])
def stats(request, body):
    return services.stats()


@api_view(["GET", "POST"])
def runs(request, body):
    if request.method == "POST":
        payload = services.parse_run_payload(body)
        job = jobs.submit(payload)
        location = reverse("news_api:run-detail", args=[job.id])
        return job.to_dict(), 202, {"Location": location}
    items = [job.to_dict() for job in jobs.recent()]
    return {"items": items, "meta": {"count": len(items)}}


@api_view(["GET"])
def run_detail(request, body, run_id):
    job = jobs.get(run_id)
    if job is None:
        raise ApiError("not_found", "Pipeline run not found", 404)
    return job.to_dict()


@api_view(["GET"])
def categories(request, body):
    return services.list_categories()


@api_view(["GET"])
def sources(request, body):
    return services.list_sources()


@api_view(["GET"])
def article_related(request, body, pk):
    return services.related_articles(pk)


@api_view(["POST"], public=True)
def article_view_beacon(request, body, pk):
    # A public telemetry beacon used to rank trending stories. Views are
    # deduplicated and rate-limited per client; see services.record_view.
    return services.record_view(pk, request), 202


@api_view(["GET"])
def trending(request, body):
    return services.list_trending()


def api_not_found(request, *args, **kwargs):
    """Return the JSON error envelope for API paths the URLconf does not match.

    Without this, the SPA catch-all would answer unknown API routes with HTML.
    """
    return error_response("not_found", "API endpoint not found", 404)
