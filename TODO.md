# Review and delivery checklist

This checklist follows the supplied **AI-Powered Automated Newspaper Platform**
roadmap. An unchecked box is unfinished work, not an implemented feature.
The active review stabilizes the current aggregator, CLI, HTTP API, and Swagger
documentation. Later milestones are deliberately sequenced after the first
version, as requested by the roadmap; they are not implied by an empty module.

## Completion rule for every change

1. Read the implementation and its callers; reproduce the issue when possible.
2. Make one focused change, preserving unrelated behavior and user data.
3. Test the change, failure cases, related features, and the affected workflow.
4. Record actual results below. Never mark an unavailable live service as tested.
5. Run `git status`, `git add .`, `git commit -m "clear descriptive commit message"`,
   and `git push`. Inspect the diff/log before committing and verify the remote
   tip afterward. The installed post-commit hook also pushes to the current
   branch and fast-forwards `main`; verify both rather than assuming success.
6. Only then start the next item. If blocked, record the blocker explicitly.

## Active review (execute in order)

- [x] R01: Inventory Git changes, repository guidance, dependencies, migrations,
  existing tests, running services, and default workflow. Commit this checklist.
- [x] R02: Validate pipeline paths before work begins: reject overwriting code,
  credentials, the database, or raw input; preserve valid CSV/CLI usage.
- [x] R03: Verify processed-result filtering and pagination return stable row
  identifiers that resolve to the same detail resource.
- [x] R04: Verify request validation/authentication and error envelopes: malformed
  JSON/encoding, wrong content types, query bounds, method handling, and failures.
- [x] R05: Verify Swagger schemas against actual success, failure, empty, and
  nullable responses; check route coverage and browser rendering.
- [x] R06: Verify job lifecycle, failure summaries, concurrent submissions,
  thread startup errors, shutdown behavior, and documented persistence limits.
- [x] R07: Verify AI transport/JSON parsing, missing/malformed responses, content
  validation, strict approval, rejection, and continued processing after errors.
- [x] R08: Verify result persistence: empty inputs, stale output, failed writes,
  source preservation, Unicode, and concurrent API reads while saving.
- [x] R09: Verify scraper extraction/cleaning, HTTP failures, source configuration,
  URL deduplication, and database/CSV consistency with controlled fixtures.
- [x] R10: Verify semantic deduplication boundaries, invalid titles, small inputs,
  identical/non-English titles, and reproducible output on the available dataset.
- [ ] R11: Review first-version foundation gaps; deliver the smallest coherent
  increment with integration tests rather than implement all roadmap stages.
- [ ] R12: Review settings/secrets, dependencies, operator documentation, Git
  workflow claims, and repeatable local/CI checks; fix confirmed issues separately.
- [ ] R13: Final diff/repository review, full tests, Django/migration/dependency
  checks, complete fixture-based scrape-to-result workflow, available live-service
  smoke tests, localhost checks, and remote/working-tree verification.

## Full roadmap coverage and acceptance criteria

### Foundation and first version

- [ ] 01 Architecture: document boundaries, state transitions, ownership of raw
  versus generated data, failure/retry behavior, and CLI/API parity.
- [ ] 02 Backend foundation: assess current Django app structure; add new apps
  only when required; validate authentication, API pagination, and filtering.
- [ ] 03 Database: design/migrate Source, SourceArticle, ArticleCluster,
  NewsArticle, Category, Topic, Entity, Fact, AIAnalysis, SensitivityAnalysis,
  Translation, Media, Review, Publication, ScrapingJob, AIJob, ErrorLog; verify
  constraints, indexes, transactions, migrations, and rollback/data preservation.
- [ ] 04 Scraping: verify 3–5 configured sites, rate limits, bounded retries,
  timeouts, 403/429/layout changes, missing fields/images, duplicate URLs, and
  source/date/author attribution. Live sites and fixtures are separate checks.
- [ ] 05 Sources: persisted enabled flag, parser version, method, RSS/base URL,
  rate limit, last attempt/success, and errors; verify enable/disable behavior.
- [ ] 06 Cleaning: remove boilerplate and normalize whitespace, Unicode,
  Bangla, quotes, dates, and numbers without altering source facts.
- [ ] 07 Deduplication: exact/normalized URL/title checks plus semantic clusters;
  retain every cluster member and its attribution; validate threshold behavior.
- [ ] 08 Categorization: structured category/subcategory/confidence with
  validated outputs, failure handling, persistence, admin filters, and tests.
- [ ] First-version integration gate: sources → clean articles → deduplication →
  categories → PostgreSQL → Django admin → simple newspaper homepage. Verify
  PostgreSQL on an actual configured server before claiming that backend works.

### AI news engine (after the foundation gate)

- [ ] 09 Sensitivity: structured flags/risk/score and mandatory review routing;
  test sensitive, normal, uncertain, and failed analysis paths.
- [ ] 10 Facts: structured entities, dates, numbers, quotes, claims, evidence;
  validate schemas and preserve original source references.
- [ ] 11 Conflicts: compare facts across cluster members, retain disagreements,
  and route unresolved conflicts to review rather than inventing a resolution.
- [ ] 12 Generation: structured headline/subheadline/lead/body/facts/tags/SEO,
  attributed evidence, factual consistency, and validated output/length policy.
- [ ] 13 Bilingual: English and Bangla from shared facts, language detection,
  field validation, persistence, and factual-equivalence checks in both languages.
- [ ] 14 Images: provider abstraction, image prompt/metadata, storage, selected
  source images versus labeled generated illustrations, retries/failures.

### Editorial automation

- [ ] 15 Workers: durable Celery/Redis queue, persisted jobs, restart recovery,
  retry limits, priorities, idempotency, concurrency tests, and worker smoke test.
- [ ] 16 Scheduling: periodic scrape/process tasks and scheduled publication;
  verify timezone behavior, overdue jobs, retries, and no duplicate publications.
- [ ] 17 Dashboard: review queues, conflicts, drafts, media, failures, approved,
  scheduled/published content; test every authorized editor action and audit trail.
- [ ] 18 Search: indexed PostgreSQL search with the roadmap's filters and tests;
  consider external search only after measuring the baseline.
- [ ] 19 Vectors: embeddings/model versioning, pgvector indexes, related stories,
  migration/reindex behavior, and semantic-search quality/performance evaluation.
- [ ] 20 Recommendations: tested related-story similarity first; personalization
  only with explicit user preferences and measured relevance.
- [ ] 21 Publication: enforced SCRAPED/ANALYZING/DRAFT/REVIEW/APPROVED/SCHEDULED/
  PUBLISHED/REJECTED/FAILED transitions, revisions, publish/unpublish, and timing.
- [ ] 22 Roles: admin/editor/reviewer/author/reader permissions with both allowed
  and denied action tests; validate session/token behavior and CSRF requirements.
- [ ] 23 API expansion: sources/categories/search/related/trending/auth/reviews/
  publication endpoints, documented contracts, permissions, throttling, tests.
- [ ] 24 Website: home/category/detail/search/Bangla/English/latest/trending/
  related/about/contact; browser tests, pagination, escaping, and responsive UI.
- [ ] 25 Analytics: views/visitors/search/reading time/traffic and operational
  success rates; test deduplication, aggregation, and permissions.

### Production readiness

- [ ] 26 Observability: structured logs with job/source/stage identifiers, error
  retention, metrics, and tested notifications without leaking credentials.
- [ ] 27 Security: externalized credentials, appropriate auth/CSRF/XSS controls,
  validated file access/uploads, rate limits, and deployment settings checks.
- [ ] 28 Attribution/editorial: preserve source URL/name/date and evidence,
  distinguish drafts from publishable content, enforce sensitive review routing.
- [ ] 29 Deployment: Docker/Compose, PostgreSQL/Redis/workers, Nginx/Gunicorn,
  HTTPS/configuration, migrations, health checks, backup/restore, deployment test.
- [ ] 30 CI/CD: automated tests/checks on each push, reproducible environments,
  container build and deployment checks once deployment targets exist.
- [ ] 31 Testing: maintain unit/integration/API/auth/browser/end-to-end coverage
  for implemented stages; label mocks, fixtures, live tests, and untested services.
- [ ] 32 Advanced features: entity linking, topics, misinformation-risk signals,
  personalized recommendations, trends, breaking-news and headline optimization
  only after core correctness and performance are verified.

## Verification log

- R10: dedup CSV loading preserves strings, handles numeric titles and missing
  headers, retains Bangla Unicode letters/marks during normalization, protects
  hardlink aliases, and uses atomic output. 41 relevant tests passed. Two real
  embedding runs on all 1,136 rows produced the same 673 representatives and
  groups, round-tripped through CSV, with every retained URL belonging to the
  source dataset. Multilingual semantic model quality is not claimed by this check.
- R09c: complete category/extraction failure or failed database saves now fail
  collection explicitly instead of reporting a successful empty scrape. Successful
  and existing-article runs remain valid. Simulated 429 and DB outage plus the
  collection/CLI/API regression suite passed (54 tests). Configured-source live
  availability, persistent source management, and rate-limit retries remain
  separately unchecked roadmap work.
- R09b: fresh raw exports now include the required header. Export reconciles
  missing database rows atomically, preserving existing raw records. A disk-full
  simulation followed by another collection repaired the CSV without refetching
  the already stored article; repeat-run and archive-preservation tests passed
  alongside related pipeline/API tests (53 total).
- R09a: parser cleaning no longer destroys author/date metadata. HTTP error and
  contentless pages are rejected; ISO time attributes and absolute image URLs are
  retained. External/non-HTTP links are ignored and fragments do not create URL
  duplicates. Tested all four configured selector sets, Bangla, missing images,
  403/404/429/503, collection → real test DB → CSV, and repeat runs (51 tests).
  These are controlled fixtures, not claims about current publisher layouts.
- R08: result CSVs are flushed to a same-directory temporary file and atomically
  replaced. A simulated partial write/disk failure preserves the prior file and
  removes temporary output; a reader sees the prior snapshot until the complete
  Unicode CSV is ready. Low-level input/output hardlinks are rejected. Empty,
  invalid input, stale result, transport failure, API, and flow tests passed (60).
- R07b: structured facts must be a nonempty object; verification must contain
  boolean approval, and explicit errors/invented facts override approval.
  The manual demo now handles transport failures and uses strict approval too.
  Fenced JSON, invalid types, contradictions, rejections, batch continuation,
  and API/job integration passed (50 tests). Content length remains an explicitly
  documented generation target; semantic factual accuracy needs editorial review.
- R07a: AI transport rejects missing, non-string, empty, error, invalid-JSON, and
  truncated responses as stage failures instead of uncaught KeyError/AttributeError.
  Applied the existing configured output-token limit. Verified each of the three
  stages using the real extraction/generation/verification/CSV code with HTTP
  responses substituted; the next row still completes. 47 related tests passed.
- R06: failed rows now make a run fail, with disjoint approved/rejected/failed
  counts. Invalid runner output fails explicitly; worker startup failure returns
  503 and frees the slot; terminal snapshots update under the lock. Verified
  mixed results, empty inputs, failure recovery, concurrent-run rejection, and
  related pipeline/API/Swagger contracts (62 tests passed). Documented the real
  single-process/in-memory limits; durable workers remain roadmap item 15.
- R05: corrected nullable results/arrays and separated normalized run parameters
  (`limit: null`) from request input (`limit: "all"`). Added a standards validator
  to development requirements and validated real serialized queued/failed runs
  and processed results. All 38 relevant tests passed. Live Chromium rendered
  all 9 operations and the POST request schema; fixed a browser-check timing race
  before accepting the result.
- R04c: health executes a database query and checks the exact installed model
  tag; a different-size model no longer reports the requested model installed.
  Malformed model inventories and database outages tested; 28 API/review tests
  passed. A test-double teardown issue was fixed and the suite rerun successfully.
- R04b: out-of-range article pages return an empty page without passing enormous
  SQL offsets to SQLite. Negative/invalid bounds still reject correctly; checked
  list/detail/auth/run/review integration (26 tests passed).
- R04a: malformed encodings now return `invalid_json`; misleading content types
  are rejected; non-ASCII invalid API keys return 401 rather than crashing.
  Internal type/serialization errors are server errors, not client validation
  errors. Valid JSON charset/auth → job submission and related flows passed
  (46 tests). Query bounds and health dependency checks remain under review.
- R03: fixed filtered CSV results being renumbered (a listed row could open an
  unrelated detail). Source row indexes now survive every filter and page.
  Status/source/search/combined filters, second-page detail equality, empty pages,
  and the related API/flow tests passed (42 tests).
- R02: restricted flow/API paths to resolved `.csv` files beneath `data/`;
  rejected code/credential/database paths, directories, malformed paths and raw
  hardlink aliases before work starts. Valid CSV → content-check → result-save
  flow verified with temporary files. All 49 API/pipeline/Swagger/review tests
  passed; README and Swagger path descriptions updated in the same change.
- R01 baseline: clean `Demo-v1`; both remote branches started at `37442a3`.
  No AGENTS.md files found. `manage.py test` passed all 47 tests;
  `manage.py check`, `makemigrations --check --dry-run`, and `pip check` passed.
  PostgreSQL is listening on 5432, but credentials/database integration have not
  been verified. No listener was found on 8000, 11434, or 6379 at baseline.
  The installed hook auto-pushes commits; explicit pushes and remote-tip checks
  are still required for this review. Checklist reviewed against all 32 supplied
  roadmap stages and the first-version integration gate.
