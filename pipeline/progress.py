"""Optional progress reporting and cooperative cancellation for pipeline runs.

The pipeline code calls the module-level helpers below (``stage``, ``step``,
``row_start``, ``row_done``, ``log``, ``checkpoint``). They do nothing unless the
current thread has a :class:`RunTracker` bound, so the CLI and direct calls to
``run_pipeline`` behave exactly as before. The background job runner binds a
tracker for the duration of one run; the operations dashboard reads snapshots of
it to show live stage state, counters, and a log.

Cancellation is cooperative: ``request_cancel`` only sets a flag, and the run
stops at the next ``checkpoint()`` (between sources, stages, and article rows).
A request already in flight (one publisher page, one generation call) finishes
first.
"""

import threading
from collections import deque
from contextlib import contextmanager

from django.utils import timezone

STAGES = (
    ("scrape", "Scrape"),
    ("deduplicate", "Deduplicate"),
    ("content_check", "Content check"),
    ("fact_extraction", "Fact extraction"),
    ("article_generation", "Article generation"),
    ("verification", "Verification"),
)
STAGE_KEYS = tuple(key for key, _label in STAGES)
LABELS = dict(STAGES)
# Stages every processed row passes through, in order.
ROW_STAGES = STAGE_KEYS[2:]

# Row status -> (number of row stages passed, (failing stage, outcome) or None).
ROW_OUTCOMES = {
    "APPROVED": (4, None),
    "CONTENT_REJECTED": (0, ("content_check", "rejected")),
    "FACT_EXTRACTION_FAILED": (1, ("fact_extraction", "failed")),
    "ARTICLE_GENERATION_FAILED": (2, ("article_generation", "failed")),
    "ARTICLE_VERIFICATION_FAILED": (3, ("verification", "failed")),
    "ARTICLE_REJECTED": (3, ("verification", "rejected")),
}

LOG_LIMIT = 500
TITLE_LIMIT = 160


class RunCancelled(Exception):
    """Raised at a checkpoint after cancellation was requested.

    ``result`` optionally carries the partial results saved before stopping.
    """

    def __init__(self, result=None):
        super().__init__("Run cancelled")
        self.result = result


def plan_for(scrape=False, deduplicate=False):
    """Stages a run with these options will execute."""
    planned = set(ROW_STAGES)
    if scrape:
        planned.add("scrape")
    if scrape or deduplicate:
        planned.add("deduplicate")
    return planned


def _now():
    return timezone.now().isoformat()


class RunTracker:
    def __init__(self, planned=None):
        planned = set(STAGE_KEYS if planned is None else planned)
        self._lock = threading.Lock()
        self.cancel_event = threading.Event()
        self._sequence = 0
        self._log = deque(maxlen=LOG_LIMIT)
        self._stages = {
            key: {
                "key": key,
                "label": LABELS[key],
                "state": "pending" if key in planned else "skipped",
                "passed": 0,
                "failed": 0,
                "rejected": 0,
                "started_at": None,
                "finished_at": None,
            }
            for key in STAGE_KEYS
        }
        self._row = {"index": 0, "total": 0, "title": "", "stage": None}

    # -- writers -----------------------------------------------------------
    def log(self, message, level="info"):
        with self._lock:
            self._sequence += 1
            self._log.append(
                {"n": self._sequence, "t": _now(), "level": level, "msg": str(message)[:400]}
            )

    def begin(self, key):
        with self._lock:
            stage = self._stages[key]
            if stage["state"] in ("pending", "skipped"):
                stage["state"] = "running"
                stage["started_at"] = _now()

    def finish(self, key, state="done"):
        with self._lock:
            stage = self._stages[key]
            stage["state"] = state
            stage["finished_at"] = _now()

    def set_total(self, total):
        with self._lock:
            self._row["total"] = int(total)

    def row_start(self, index, total, title):
        with self._lock:
            self._row.update(index=index, total=total, title=str(title or "")[:TITLE_LIMIT], stage=None)

    def step(self, key):
        with self._lock:
            self._row["stage"] = key
        self.begin(key)

    def row_done(self, status):
        passed_count, failure = ROW_OUTCOMES.get(status, (0, None))
        with self._lock:
            for key in ROW_STAGES[:passed_count]:
                self._stages[key]["passed"] += 1
            if failure:
                key, outcome = failure
                self._stages[key][outcome] += 1
            self._row["stage"] = None
        self.log(f"{self._row['index']}/{self._row['total']} {status} · {self._row['title']}",
                 "info" if status == "APPROVED" else "warn" if status.endswith("_REJECTED") else "error")

    def request_cancel(self):
        first = not self.cancel_event.is_set()
        self.cancel_event.set()
        if first:
            self.log("Cancel requested; stopping at the next checkpoint", "warn")

    def finalize(self, outcome):
        """Settle stages still marked running once the run has ended."""
        state = {"succeeded": "done", "failed": "failed", "cancelled": "cancelled"}.get(outcome, "done")
        with self._lock:
            for stage in self._stages.values():
                if stage["state"] == "running":
                    stage["state"] = state
                    stage["finished_at"] = _now()
            self._row["stage"] = None

    # -- readers -----------------------------------------------------------
    @property
    def cancel_requested(self):
        return self.cancel_event.is_set()

    def snapshot(self, after=0, include_log=True):
        with self._lock:
            data = {
                "stages": [dict(self._stages[key]) for key in STAGE_KEYS],
                "row": dict(self._row),
                "cancel_requested": self.cancel_event.is_set(),
            }
            if include_log:
                data["log"] = [dict(entry) for entry in self._log if entry["n"] > after]
                data["log_next"] = self._sequence
            return data


_local = threading.local()


def bind(tracker):
    _local.tracker = tracker


def unbind():
    _local.tracker = None


def current():
    return getattr(_local, "tracker", None)


def log(message, level="info"):
    tracker = current()
    if tracker:
        tracker.log(message, level)


def checkpoint():
    tracker = current()
    if tracker and tracker.cancel_event.is_set():
        raise RunCancelled()


def step(key):
    tracker = current()
    if tracker:
        tracker.step(key)


def set_total(total):
    tracker = current()
    if tracker:
        tracker.set_total(total)


def row_start(index, total, title):
    tracker = current()
    if tracker:
        tracker.row_start(index, total, title)


def row_done(status):
    tracker = current()
    if tracker:
        tracker.row_done(status)


@contextmanager
def stage(key):
    """Mark a whole-run stage (scrape, deduplicate) as running, then done or failed."""
    tracker = current()
    if tracker is None:
        yield
        return
    tracker.begin(key)
    tracker.log(f"{LABELS[key]} started")
    try:
        yield
    except RunCancelled:
        tracker.finish(key, "cancelled")
        raise
    except BaseException:
        tracker.finish(key, "failed")
        tracker.log(f"{LABELS[key]} failed", "error")
        raise
    else:
        tracker.finish(key, "done")
        tracker.log(f"{LABELS[key]} finished")
