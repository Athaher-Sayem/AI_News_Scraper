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

Configuration loads from the ignored `.env` file, with environment variables
taking precedence. See `.env.example` for names. Do not replace an existing
`.env` containing your settings. `DJANGO_SECRET_KEY` and `NEWS_API_KEY` must be
set when `DJANGO_DEBUG=false`; configure `DJANGO_ALLOWED_HOSTS` for that server.
Without a local secret, development uses a new random key each start, so admin
sessions expire on restart. Set your own persistent local key to retain sessions.
The default database remains SQLite; PostgreSQL integration is still a roadmap item.

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

Run the entire offline check sequence with
`.\.venv\Scripts\python.exe tools/check.py`. GitHub Actions invokes the same
command on pushes to `main`/`Demo-v1` and on pull requests. The sequence stops at
the first failure. Live publisher, browser/CDN, embedding-download, and generation
checks are separate from this offline suite.

Automated regression tests use mocked generation responses to exercise approval,
rejection, malformed responses, outages, CSV handling, CLI flow, and the HTTP API
without requiring the local generation service. The root `Test*.py` files are
manual live-service examples, rather than the automated test suite.

Start the Django development server with:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000/> for the React frontend (see below). The
server-rendered source collection pages live at <http://127.0.0.1:8000/collected/>;
they support headline/content search, category and language filters, pagination,
and attributed excerpt pages linking to the original publisher. These pages
display collected source records; they do not publish generated drafts or imply
editorial approval.

## React frontend

A React (Vite) single-page app provides the newspaper-style homepage built from
the collected stories. Django serves it at the site root from the same origin as
the JSON API, so no CORS setup is required. Build it once:

```powershell
cd frontend
npm install
npm run build   # writes frontend/dist
```

Then open <http://127.0.0.1:8000/>. The home page has a lead story, a
"Top News" list, per-category section blocks, and an "In Case You Missed It" grid.
Section (`/section/<name>`) and search (`/search?q=...`) pages paginate, and
article pages (`/article/<id>`) show the full text, a source-attribution link, and
related stories.

For live development with hot reload:

```powershell
cd frontend
npm run dev     # http://localhost:5173/, /api proxied to Django on :8000
```

Django returns a helpful `503` at the root until `frontend/dist` exists.
`frontend/node_modules/` is ignored; the built `frontend/dist/` is committed so the
app also works without a local Node build.

## HTTP API

All endpoints live under `/api/v1/` and return JSON. Successful responses use
`{"data": ...}`; errors use `{"error": {"code", "message", "details"?}}` with a
matching HTTP status (400 validation, 401 auth, 404 not found, 405 wrong method,
409 conflict, 415 wrong media type, 500 unexpected). List responses add
`meta` with `page`, `page_size`, `total`, `total_pages`, and `count`.

Set the `NEWS_API_KEY` environment variable to require an `X-API-Key` header on
every data endpoint except `health/`. Swagger and its raw specification stay public.

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

The specification is defined in `news/api/openapi.py`; it is not automatically
inferred from handler implementations. Tests check route coverage, `$ref`s,
document validity, selected serialized response contracts, and shared enums/limits.

### Queue and inspect a run

Queue a run:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/pipeline/runs/ `
  -Method Post -ContentType 'application/json' -Body '{"limit": 1}'
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

## Git workflow

For each focused change, test the affected behavior and then run:

```powershell
git status
git add .
git commit -m "Describe the verified change"
git push
git status --short --branch
git ls-remote --heads origin Demo-v1 main
```

Inspect the diff before staging; `.env` must remain ignored. The installed
`post-commit` hook attempts to push the current branch and fast-forward `main`.
It does **not** run tests or create commits, and a failed network push does not
undo a successful local commit. Check its output and verify the remote tip;
retry `git push` (and the intended main fast-forward) when necessary.

Hook setup is local to a clone. To enable the tracked hook after cloning, run
`git config core.hooksPath .githooks`. To return to normal manual pushing, run
`git config core.hooksPath .git/hooks`.
