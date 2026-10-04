"""Serve the built React single-page app from the Django server.

The app lives under ``/app/`` and is served from ``frontend/dist`` (the output
of ``npm run build``). Unknown paths return ``index.html`` so client-side routes
(``/app/article/1``) resolve; real files are served with a guessed content type.
Paths are resolved inside ``dist`` so directory traversal is rejected.
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

    return FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
