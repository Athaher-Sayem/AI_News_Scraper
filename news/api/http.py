import json
import logging
import secrets
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, code, message, status=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def error_response(code, message, status=400, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JsonResponse({"error": error}, status=status)


def _authorized(request):
    expected = getattr(settings, "NEWS_API_KEY", "")
    if not expected:
        return True
    provided = request.headers.get("X-API-Key", "")
    return bool(provided) and secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _parse_body(request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return {}
    raw = request.body
    if not raw.strip():
        return {}
    if request.content_type.lower() != "application/json":
        raise ApiError("unsupported_media_type", "Request body must be application/json", 415)
    try:
        parsed = json.loads(raw)
    except UnicodeDecodeError:
        raise ApiError("invalid_json", "Request body has invalid JSON encoding", 400) from None
    except json.JSONDecodeError as error:
        raise ApiError(
            "invalid_json",
            f"Invalid JSON body: {error.msg}",
            400,
            {"position": error.pos},
        ) from None
    if not isinstance(parsed, dict):
        raise ApiError("invalid_json", "JSON body must be an object", 400)
    return parsed


def api_view(methods, public=False):
    """Uniform JSON view: envelope, auth, method, body, and error handling."""
    methods = tuple(methods)

    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                response = error_response(
                    "method_not_allowed",
                    f"{request.method} is not allowed for this endpoint",
                    405,
                )
                response["Allow"] = ", ".join(methods)
                return response
            if not public and not _authorized(request):
                return error_response(
                    "unauthorized",
                    "A valid X-API-Key header is required",
                    401,
                )
            try:
                body = _parse_body(request)
                result = view(request, body, *args, **kwargs)
                if isinstance(result, tuple):
                    data = result[0]
                    status = result[1] if len(result) > 1 else 200
                    headers = result[2] if len(result) > 2 else {}
                else:
                    data, status, headers = result, 200, {}
                response = JsonResponse({"data": data}, status=status)
                for name, value in headers.items():
                    response[name] = value
                return response
            except ApiError as error:
                return error_response(error.code, error.message, error.status, error.details)
            except Exception:
                logger.exception("Unhandled API error on %s", request.path)
                return error_response("internal_error", "An unexpected error occurred", 500)

        return wrapper

    return decorator
