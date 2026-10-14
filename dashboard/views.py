"""Serve the dashboard's static web app (no build step, no third-party hosts)."""

import hashlib
from pathlib import Path

from django.http import FileResponse, Http404
from django.views.decorators.http import condition, require_GET

WEB_DIR = Path(__file__).resolve().parent / "web"

# Explicit types: the OS mimetype registry (notably on Windows) may map .js to
# text/plain, which browsers refuse for ES modules.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".json": "application/json",
}

# The page ships its own scripts, styles and fonts and talks only to this
# origin, so a strict policy costs nothing and blunts injected scraped content.
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none'"
)


def _resolve(path):
    root = WEB_DIR.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise Http404("Invalid asset path") from None
    if not candidate.is_file() or candidate.suffix.lower() not in CONTENT_TYPES:
        raise Http404("Asset not found")
    return candidate


def _etag(request, path="index.html"):
    try:
        stat = _resolve(path).stat()
    except Http404:
        return None
    return hashlib.md5(f"{stat.st_mtime_ns}-{stat.st_size}".encode()).hexdigest()


@require_GET
@condition(etag_func=_etag)
def asset(request, path="index.html"):
    file_path = _resolve(path)
    response = FileResponse(file_path.open("rb"), content_type=CONTENT_TYPES[file_path.suffix.lower()])
    response["Cache-Control"] = "no-cache"
    if file_path.suffix.lower() == ".html":
        response["Content-Security-Policy"] = CSP
        response["Referrer-Policy"] = "same-origin"
        response["X-Frame-Options"] = "DENY"
    return response
