from news.api.services import MAX_PAGE_SIZE, MAX_QUERY_LENGTH, STATUSES

DOCS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI News Scraper API</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <style>
    body { margin: 0; background: #fafafa; }
    .swagger-ui .topbar { display: none; }
  </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  window.onload = function () {
    window.ui = SwaggerUIBundle({
      url: "/api/v1/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      tryItOutEnabled: true,
      filter: true,
      docExpansion: "list"
    });
  };
</script>
</body>
</html>
"""

DESCRIPTION = """JSON API for scraping, deduplicating, verifying, and generating news articles.

**Response envelope.** Successful responses return `{"data": ...}`. Errors return
`{"error": {"code", "message", "details"?}}` with a matching HTTP status:
400 validation, 401 missing/invalid API key, 404 not found, 405 wrong method
(includes an `Allow` header), 409 conflict, 415 wrong content type, 500 unexpected.

**Authentication.** Set the `NEWS_API_KEY` environment variable on the server to
require an `X-API-Key` header on every endpoint except `health/`, `openapi.json`,
and `docs/`.

**Pipeline runs.** `POST /api/v1/pipeline/runs` queues a background run and
returns `202` with a `Location` header. Runs move through
`queued` → `running` → `succeeded` or `failed`. Only one run can be active at a
time; a second attempt returns `409 job_conflict`. Paths must stay inside the
project's `data/` directory, must use `.csv`, and can never overwrite the raw scrape CSV."""


def _ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def _param_ref(name):
    return {"$ref": f"#/components/parameters/{name}"}


def _envelope(schema):
    return {
        "type": "object",
        "properties": {"data": schema},
        "required": ["data"],
    }


def _error(description):
    return {
        "description": description,
        "content": {"application/json": {"schema": _ref("ErrorEnvelope")}},
    }


def _ok(description, schema):
    return {
        "description": description,
        "content": {"application/json": {"schema": _envelope(schema)}},
    }


def _error_for(status):
    """Build the documented error response for an HTTP status code."""
    messages = {
        400: ("invalid_request", "Validation failed; `error.code` identifies the field or parameter"),
        401: ("unauthorized", "Missing or invalid `X-API-Key` header"),
        404: ("not_found", "Resource not found"),
        405: ("method_not_allowed", "Wrong HTTP method; see the `Allow` header"),
        409: ("job_conflict", "A pipeline run is already in progress"),
        415: ("unsupported_media_type", "Body must be `application/json`"),
        500: ("internal_error", "Unexpected server error"),
    }
    code, description = messages[status]
    return _error(f"{description} (`{code}`)")


def build_spec():
    article_list = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": _ref("Article")},
            "meta": _ref("PaginationMeta"),
        },
        "required": ["items", "meta"],
    }
    processed_list = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": _ref("ProcessedRow")},
            "meta": _ref("ProcessedMeta"),
        },
        "required": ["items", "meta"],
    }
    run_list = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": _ref("Run")},
            "meta": {
                "type": "object",
                "properties": {"count": {"type": "integer"}},
                "required": ["count"],
            },
        },
        "required": ["items", "meta"],
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "AI News Scraper API",
            "version": "1.0.0",
            "description": DESCRIPTION,
        },
        "servers": [{"url": "/", "description": "Current host"}],
        "security": [{"apiKeyAuth": []}],
        "tags": [
            {"name": "Health", "description": "Service and dependency status"},
            {"name": "Stats", "description": "Aggregate counts across articles and processing results"},
            {"name": "Articles", "description": "Scraped articles stored in the database"},
            {"name": "Processed", "description": "Pipeline results read from the processed CSV"},
            {"name": "Pipeline", "description": "Background scrape/deduplicate/process runs"},
        ],
        "paths": {
            "/api/v1/health/": {
                "get": {
                    "tags": ["Health"],
                    "operationId": "getHealth",
                    "summary": "Service health",
                    "security": [],
                    "responses": {
                        "200": _ok(
                            "Service is healthy",
                            _ref("Health"),
                        ),
                        "503": {
                            "description": "Database unreachable (`degraded` status)",
                            "content": {"application/json": {"schema": _envelope(_ref("Health"))}},
                        },
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
            },
            "/api/v1/stats/": {
                "get": {
                    "tags": ["Stats"],
                    "operationId": "getStats",
                    "summary": "Aggregate statistics",
                    "responses": {
                        "200": _ok("Counts by source and status", _ref("Stats")),
                        "401": _error_for(401),
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
            },
            "/api/v1/articles/": {
                "get": {
                    "tags": ["Articles"],
                    "operationId": "listArticles",
                    "summary": "List scraped articles",
                    "parameters": [
                        _param_ref("SourceFilter"),
                        _param_ref("CategoryFilter"),
                        _param_ref("LanguageFilter"),
                        _param_ref("ArticleQ"),
                        _param_ref("Page"),
                        _param_ref("PageSize"),
                    ],
                    "responses": {
                        "200": _ok("Page of articles", article_list),
                        "400": _error_for(400),
                        "401": _error_for(401),
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
            },
            "/api/v1/articles/{id}/": {
                "get": {
                    "tags": ["Articles"],
                    "operationId": "getArticle",
                    "summary": "Fetch one article",
                    "parameters": [_param_ref("ArticleId")],
                    "responses": {
                        "200": _ok("Article found", _ref("Article")),
                        "400": _error_for(400),
                        "401": _error_for(401),
                        "404": _error_for(404),
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
            },
            "/api/v1/processed/": {
                "get": {
                    "tags": ["Processed"],
                    "operationId": "listProcessed",
                    "summary": "List processing results",
                    "parameters": [
                        _param_ref("StatusFilter"),
                        _param_ref("SourceFilter"),
                        _param_ref("ProcessedQ"),
                        _param_ref("Page"),
                        _param_ref("PageSize"),
                    ],
                    "responses": {
                        "200": _ok("Page of processing results", processed_list),
                        "400": _error_for(400),
                        "401": _error_for(401),
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
            },
            "/api/v1/processed/{row}/": {
                "get": {
                    "tags": ["Processed"],
                    "operationId": "getProcessedRow",
                    "summary": "Fetch one processing result by CSV row",
                    "parameters": [_param_ref("Row")],
                    "responses": {
                        "200": _ok("Row found", _ref("ProcessedRow")),
                        "400": _error_for(400),
                        "401": _error_for(401),
                        "404": _error_for(404),
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
            },
            "/api/v1/pipeline/runs/": {
                "get": {
                    "tags": ["Pipeline"],
                    "operationId": "listRuns",
                    "summary": "List recent pipeline runs",
                    "responses": {
                        "200": _ok("Recent runs, newest first", run_list),
                        "401": _error_for(401),
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
                "post": {
                    "tags": ["Pipeline"],
                    "operationId": "createRun",
                    "summary": "Queue a pipeline run",
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {"schema": _ref("RunRequest")}
                        },
                    },
                    "responses": {
                        "202": {
                            "description": "Run queued (`job_conflict` if another run is active)",
                            "headers": {
                                "Location": {
                                    "description": "URL of the queued run",
                                    "schema": {"type": "string"},
                                }
                            },
                            "content": {"application/json": {"schema": _envelope(_ref("Run"))}},
                        },
                        "400": _error_for(400),
                        "401": _error_for(401),
                        "405": _error_for(405),
                        "409": _error_for(409),
                        "415": _error_for(415),
                        "500": _error_for(500),
                    },
                },
            },
            "/api/v1/pipeline/runs/{run_id}/": {
                "get": {
                    "tags": ["Pipeline"],
                    "operationId": "getRun",
                    "summary": "Poll a pipeline run",
                    "parameters": [_param_ref("RunId")],
                    "responses": {
                        "200": _ok("Run status, summary, and error", _ref("Run")),
                        "400": _error_for(400),
                        "401": _error_for(401),
                        "404": _error_for(404),
                        "405": _error_for(405),
                        "500": _error_for(500),
                    },
                },
            },
        },
        "components": {
            "securitySchemes": {
                "apiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "Required only when the server sets NEWS_API_KEY",
                }
            },
            "parameters": {
                "Page": {
                    "name": "page",
                    "in": "query",
                    "description": "1-based page number",
                    "schema": {"type": "integer", "minimum": 1, "default": 1},
                },
                "PageSize": {
                    "name": "page_size",
                    "in": "query",
                    "description": f"Items per page (1-{MAX_PAGE_SIZE})",
                    "schema": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_PAGE_SIZE,
                        "default": 20,
                    },
                },
                "SourceFilter": {
                    "name": "source",
                    "in": "query",
                    "description": "Exact source name",
                    "schema": {"type": "string"},
                },
                "CategoryFilter": {
                    "name": "category",
                    "in": "query",
                    "description": "Exact category name",
                    "schema": {"type": "string"},
                },
                "LanguageFilter": {
                    "name": "language",
                    "in": "query",
                    "description": "Exact language name",
                    "schema": {"type": "string"},
                },
                "ArticleQ": {
                    "name": "q",
                    "in": "query",
                    "description": "Case-insensitive search over title and content",
                    "schema": {"type": "string", "maxLength": MAX_QUERY_LENGTH},
                },
                "ProcessedQ": {
                    "name": "q",
                    "in": "query",
                    "description": "Case-insensitive search over title",
                    "schema": {"type": "string", "maxLength": MAX_QUERY_LENGTH},
                },
                "StatusFilter": {
                    "name": "status",
                    "in": "query",
                    "description": "Pipeline status filter",
                    "schema": {"type": "string", "enum": sorted(STATUSES)},
                },
                "ArticleId": {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "description": "Database id of the article",
                    "schema": {"type": "integer", "minimum": 1},
                },
                "Row": {
                    "name": "row",
                    "in": "path",
                    "required": True,
                    "description": "0-based row number in the processed CSV",
                    "schema": {"type": "integer", "minimum": 0},
                },
                "RunId": {
                    "name": "run_id",
                    "in": "path",
                    "required": True,
                    "description": "Identifier returned when the run was queued",
                    "schema": {"type": "string"},
                },
            },
            "schemas": {
                "ErrorEnvelope": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                                "details": {
                                    "type": "object",
                                    "additionalProperties": True,
                                },
                            },
                            "required": ["code", "message"],
                        }
                    },
                    "required": ["error"],
                },
                "PaginationMeta": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                        "total": {"type": "integer"},
                        "total_pages": {"type": "integer"},
                        "count": {"type": "integer"},
                    },
                    "required": ["page", "page_size", "total", "total_pages", "count"],
                },
                "ProcessedMeta": {
                    "allOf": [
                        _ref("PaginationMeta"),
                        {
                            "type": "object",
                            "properties": {
                                "source_file": {
                                    "type": "string",
                                    "description": "CSV file backing these results",
                                }
                            },
                            "required": ["source_file"],
                        },
                    ]
                },
                "Article": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "source": {"type": "string"},
                        "category": {"type": "string"},
                        "title": {"type": "string"},
                        "url": {"type": "string", "format": "uri"},
                        "content": {"type": "string"},
                        "author": {"type": "string"},
                        "published_date": {"type": "string"},
                        "image_url": {"type": "string"},
                        "language": {"type": "string"},
                        "scraped_date": {
                            "type": "string",
                            "format": "date-time",
                            "nullable": True,
                        },
                    },
                    "required": [
                        "id", "source", "category", "title", "url",
                        "content", "author", "published_date", "image_url",
                        "language", "scraped_date",
                    ],
                },
                "ProcessedRow": {
                    "type": "object",
                    "properties": {
                        "row": {"type": "integer", "minimum": 0},
                        "source": {"type": "string"},
                        "category": {"type": "string"},
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "content": {"type": "string"},
                        "author": {"type": "string"},
                        "published_date": {"type": "string"},
                        "image_url": {"type": "string"},
                        "language": {"type": "string"},
                        "scraped_date": {"type": "string"},
                        "status": {"type": "string", "enum": sorted(STATUSES)},
                        "reason": {"type": "string"},
                        "generated_article": {"type": "string", "nullable": True},
                        "facts": {
                            "nullable": True,
                            "oneOf": [
                                {"type": "object", "additionalProperties": True},
                                {"type": "string"},
                            ],
                        },
                        "verification": {
                            "nullable": True,
                            "oneOf": [
                                {"type": "object", "additionalProperties": True},
                                {"type": "string"},
                            ],
                        },
                    },
                    "required": [
                        "row", "source", "category", "title", "url", "content",
                        "author", "published_date", "image_url", "language",
                        "scraped_date", "status", "reason",
                    ],
                },
                "Health": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["ok", "degraded"]},
                        "database": {
                            "type": "object",
                            "properties": {"available": {"type": "boolean"}},
                            "required": ["available"],
                        },
                        "generation": _ref("GenerationStatus"),
                    },
                    "required": ["status", "database", "generation"],
                },
                "GenerationStatus": {
                    "type": "object",
                    "properties": {
                        "available": {"type": "boolean"},
                        "model": {"type": "string"},
                        "model_installed": {"type": "boolean"},
                    },
                    "required": ["available", "model", "model_installed"],
                },
                "Stats": {
                    "type": "object",
                    "properties": {
                        "articles": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "integer"},
                                "by_source": {
                                    "type": "object",
                                    "additionalProperties": {"type": "integer"},
                                },
                                "latest_scraped_date": {
                                    "type": "string",
                                    "format": "date-time",
                                    "nullable": True,
                                },
                            },
                            "required": ["total", "by_source", "latest_scraped_date"],
                        },
                        "processed": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "integer"},
                                "by_status": {
                                    "type": "object",
                                    "additionalProperties": {"type": "integer"},
                                },
                                "available": {"type": "boolean"},
                            },
                            "required": ["total", "by_status", "available"],
                        },
                    },
                    "required": ["articles", "processed"],
                },
                "RunRequest": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "limit": {
                            "description": "Number of articles to process, or \"all\" for every input row",
                            "default": 1,
                            "oneOf": [
                                {"type": "integer", "minimum": 1},
                                {"type": "string", "enum": ["all"]},
                            ],
                        },
                        "input": {
                            "type": "string",
                            "description": "Input .csv path beneath the project's data/ directory",
                        },
                        "output": {
                            "type": "string",
                            "description": "Output .csv path beneath data/; must not overwrite the raw scrape CSV",
                        },
                        "scrape": {
                            "type": "boolean",
                            "default": False,
                            "description": "Collect all sources first (implies deduplication)",
                        },
                        "deduplicate": {
                            "type": "boolean",
                            "default": False,
                            "description": "Deduplicate data/news_data.csv into `input` before processing",
                        },
                    },
                },
                "RunSummary": {
                    "type": "object",
                    "properties": {
                        "processed": {"type": "integer"},
                        "approved": {"type": "integer"},
                        "rejected": {"type": "integer"},
                        "failed": {"type": "integer"},
                        "by_status": {
                            "type": "object",
                            "additionalProperties": {"type": "integer"},
                        },
                    },
                    "required": ["processed", "approved", "rejected", "failed", "by_status"],
                },
                "Run": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["queued", "running", "succeeded", "failed"],
                        },
                        "request": _ref("RunRequest"),
                        "summary": {"nullable": True, "allOf": [_ref("RunSummary")]},
                        "error": {"type": "string", "nullable": True},
                        "created_at": {"type": "string", "format": "date-time"},
                        "started_at": {"type": "string", "format": "date-time", "nullable": True},
                        "finished_at": {"type": "string", "format": "date-time", "nullable": True},
                    },
                    "required": [
                        "id", "status", "request", "summary", "error",
                        "created_at", "started_at", "finished_at",
                    ],
                },
            },
        },
    }
