# News scraper and processing pipeline

## Setup

Use Python 3.11 or later and install the runtime dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe manage.py migrate
```

Article processing requires the local Ollama service and the model configured
in `ai/config.py`. Start the service with `ollama serve` and ensure the configured
model is installed before processing. Deduplication downloads its sentence
embedding model on the first run.

## Run

The default is a one-article demo using `data/unique_news.csv`:

```powershell
.\.venv\Scripts\python.exe Main.py
```

Process a selected number of articles or the full input:

```powershell
.\.venv\Scripts\python.exe Main.py --limit 5
.\.venv\Scripts\python.exe Main.py --all
```

Run the complete collection flow, or deduplicate an existing scrape:

```powershell
.\.venv\Scripts\python.exe Main.py --scrape --all
.\.venv\Scripts\python.exe Main.py --deduplicate --limit 1
```

Flow: scrape the configured sources into `data/news_data.csv` and Django's
database, deduplicate into `data/unique_news.csv`, check required content,
extract facts, generate an article, verify it, and save results to
`data/processed_news.csv`. `--scrape` includes deduplication; `--deduplicate`
uses the existing raw CSV. Without either flag, processing uses the existing
unique CSV directly.

Use `--input PATH` and `--output PATH` for separate CSV files beneath `data/`. When
deduplication is requested, `--input` is its output destination. Each processing
run replaces its output CSV with the selected rows and their statuses, facts,
generated articles, and verification results. Request failures are recorded per
row and processing continues; the CLI exits with status 1 if any stage failed.
An editorial rejection is recorded as `ARTICLE_REJECTED`.

The 450–600-word article length is a generation prompt target, not a deterministic
guarantee. Review generated articles and their verification results before use.

## Check and test

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

Automated regression tests use mocked generation responses to exercise approval,
rejection, malformed responses, outages, CSV handling, CLI flow, and the HTTP API
without requiring the local generation service. The root `Test*.py` files are
manual live-service examples, rather than the automated test suite.

Start the Django development server with:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000/> for the source collection homepage. It supports
headline/content search, category and language filters, pagination, and attributed
excerpt pages linking to the original publisher. These pages display collected
source records; they do not publish generated drafts or imply editorial approval.

## HTTP API

All endpoints live under `/api/v1/` and return JSON. Successful responses use
`{"data": ...}`; errors use `{"error": {"code", "message", "details"?}}` with a
matching HTTP status (400 validation, 401 auth, 404 not found, 405 wrong method,
409 conflict, 415 wrong media type, 500 unexpected). List responses add
`meta` with `page`, `page_size`, `total`, `total_pages`, and `count`.

Set the `NEWS_API_KEY` environment variable to require an `X-API-Key` header on
every endpoint except `health/`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health/` | Database and local generation service status |
| GET | `/api/v1/stats/` | Article and processing counts by source/status |
| GET | `/api/v1/articles/` | Scraped articles; filters `source`, `category`, `language`, `q`, `page`, `page_size` |
| GET | `/api/v1/articles/{id}/` | One scraped article |
| GET | `/api/v1/processed/` | Processing results; filters `status`, `source`, `q`, `page`, `page_size` |
| GET | `/api/v1/processed/{row}/` | One processing result by CSV row |
| GET/POST | `/api/v1/pipeline/runs/` | List runs, or queue a new run |
| GET | `/api/v1/pipeline/runs/{id}/` | Run status, summary, and error |
| GET | `/api/v1/openapi.json` | Raw OpenAPI 3 document for the API |
| GET | `/api/v1/docs/` | Swagger UI for the API |

### Interactive documentation

Start the server and open <http://127.0.0.1:8000/api/v1/docs/> for Swagger UI
(loaded from the unpkg CDN, so the machine needs internet access the first time).
The underlying specification is always available as JSON at
`/api/v1/openapi.json`; both endpoints stay public even when `NEWS_API_KEY`
is configured, and Swagger UI's "Try it out" works against every endpoint.

The specification is generated from the same code that serves the API
(`news/api/openapi.py`), and tests assert that every route in the URLconf is
documented, every `$ref` resolves, and the documented enums and limits match
the server-side validation.

## Git workflow

Every change is committed and pushed immediately: run the checks, commit, and
push in one step. The repository enables `core.hooksPath = .githooks`, so the
tracked `post-commit` hook pushes each new commit to its branch on `origin`
automatically — you never need to run `git push` by hand. The hook also
fast-forwards `main` (when possible) so the GitHub homepage always shows the
latest code.

After cloning, activate the hook once:

```powershell
git config core.hooksPath .githooks
```

To go back to manual pushing:

```powershell
git config core.hooksPath .git/hooks
```

Queue a run:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/pipeline/runs/ `
  -H "Content-Type: application/json" `
  -d '{"limit": 1}'
```

Body fields: `limit` (positive integer or `"all"`, default `1`), `input`,
`output` (project-relative paths), `scrape`, `deduplicate` (booleans). The
response is `202 Accepted` with a `Location` header. Runs execute in the
background with states `queued` → `running` → `succeeded`/`failed`; only one
run may be active at a time (otherwise `409 job_conflict`). Input/output paths
must be CSV files beneath `data/` and can never overwrite the raw scrape
CSV. Poll `pipeline/runs/{id}/` for `summary` (`processed`, `approved`,
`rejected`, `failed`, `by_status`) or `error`.

Runs with any failed processing stage report `failed`; editorial rejections are
completed decisions. Summary counts for approved, rejected, and failed rows are
disjoint. Worker startup failures return `503 worker_unavailable` and free the slot.

The current runner is a **single-process development runner**: only the newest
20 jobs are kept in memory; restarting the server loses job history and interrupts
active daemon threads. Its lock does not coordinate multiple web workers or CLI
runs. CSV results survive restarts. Durable queueing and restart recovery are
tracked separately in TODO.md (Celery/Redis milestone).
