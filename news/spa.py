"""Serve the built React single-page app from the Django server.

The app is served at the site root from ``frontend/dist`` (the output of
``npm run build``). Unknown extensionless paths return ``index.html`` so
client-side routes (``/article/1``) resolve; real files are served with a guessed
content type. Missing asset-style paths such as ``/favicon.ico`` return 404
instead of the app, and paths are resolved inside ``dist`` so traversal is
rejected.
"""

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET

DIST_DIR = Path(settings.BASE_DIR) / "frontend" / "dist"
INDEX_MISSING_MESSAGE = (
    "Frontend build not found. Run `npm install` and `npm run build` inside frontend/."
)

# Extensions that must never fall back to index.html: a missing asset should 404
# rather than return HTML with an image/script content type.
ASSET_EXTENSIONS = frozenset({
    ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".bmp",
    ".css", ".js", ".mjs", ".map", ".json", ".txt", ".xml",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".webm", ".mp3",
})


@require_GET
def spa(request, path=""):
    dist = DIST_DIR.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return HttpResponse(
            INDEX_MISSING_MESSAGE, status=503, content_type="text/plain; charset=utf-8"
        )

    if path:
        candidate = (dist / path).resolve()
        try:
            candidate.relative_to(dist)
        except ValueError:
            raise Http404("Invalid asset path") from None
        if candidate.is_file():
            content_type, _ = mimetypes.guess_type(str(candidate))
            return FileResponse(candidate.open("rb"), content_type=content_type)
        if Path(path).suffix.lower() in ASSET_EXTENSIONS:
            raise Http404("Asset not found")

    return FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
