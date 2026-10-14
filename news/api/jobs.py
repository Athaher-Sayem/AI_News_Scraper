import logging
import threading
import uuid
from collections import OrderedDict

from django.utils import timezone

from news.api.http import ApiError
from news.api.serializers import serialize_job
from pipeline import flow, progress

logger = logging.getLogger(__name__)

MAX_JOBS = 20
ACTIVE_STATUSES = ("queued", "running")
FINISHED_STATUSES = ("succeeded", "failed", "cancelled")

_lock = threading.Lock()
_jobs = OrderedDict()


class PipelineJob:
    def __init__(self, request):
        self.id = uuid.uuid4().hex
        self.request = dict(request)
        self.status = "queued"
        self.error = None
        self.summary = None
        self.created_at = timezone.now()
        self.started_at = None
        self.finished_at = None
        self.done = threading.Event()
        self.tracker = progress.RunTracker(
            progress.plan_for(
                scrape=bool(self.request.get("scrape")),
                deduplicate=bool(self.request.get("deduplicate")),
            )
        )

    def to_dict(self):
        with _lock:
            return serialize_job(self)


def reset():
    """Clear stored runs (used by tests)."""
    with _lock:
        _jobs.clear()


def get(job_id):
    with _lock:
        return _jobs.get(job_id)


def recent(limit=MAX_JOBS):
    with _lock:
        return list(reversed(_jobs.values()))[:limit]


def cancel(job_id):
    """Ask an active run to stop at its next checkpoint."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise ApiError("not_found", "Pipeline run not found", 404)
        if job.status not in ACTIVE_STATUSES:
            raise ApiError("not_cancellable", f"Run already {job.status}", 409)
    job.tracker.request_cancel()
    return job


def submit(request, runner=None):
    """Queue a pipeline run; only one run may be active at a time."""
    with _lock:
        if any(job.status in ACTIVE_STATUSES for job in _jobs.values()):
            raise ApiError(
                "job_conflict",
                "A pipeline run is already in progress",
                409,
            )
        job = PipelineJob(request)
        _jobs[job.id] = job
        while len(_jobs) > MAX_JOBS:
            oldest_id, oldest = next(iter(_jobs.items()))
            if oldest.status in ACTIVE_STATUSES:
                break
            del _jobs[oldest_id]

    try:
        thread = threading.Thread(
            target=_execute,
            args=(job, runner or flow.run_flow),
            daemon=True,
            name=f"pipeline-run-{job.id[:8]}",
        )
        job.thread = thread
        thread.start()
    except RuntimeError:
        with _lock:
            job.status = "failed"
            job.error = "Could not start the pipeline worker"
            job.finished_at = timezone.now()
        job.done.set()
        logger.exception("Could not start pipeline run %s", job.id)
        raise ApiError("worker_unavailable", job.error, 503) from None
    return job


def _summarize(result):
    if result is None or not hasattr(result, "columns") or "status" not in result.columns:
        raise ValueError("Pipeline did not return a result with statuses")
    statuses = result["status"].astype(str)
    return {
        "processed": int(len(result)),
        "approved": int((statuses == "APPROVED").sum()),
        "rejected": int(statuses.str.endswith("_REJECTED").sum()),
        "failed": int(statuses.str.endswith("_FAILED").sum()),
        "by_status": {str(key): int(value) for key, value in statuses.value_counts().items()},
    }


def _execute(job, runner):
    from django.db import close_old_connections

    with _lock:
        job.status = "running"
        job.started_at = timezone.now()
    status, error, summary = "failed", None, None
    progress.bind(job.tracker)
    job.tracker.log("Run started")
    try:
        close_old_connections()
        result = runner(**job.request)
        summary = _summarize(result)
        status = "failed" if summary["failed"] else "succeeded"
        if summary["failed"]:
            error = f"{summary['failed']} article(s) failed processing; see saved results"
    except progress.RunCancelled as cancelled:
        status = "cancelled"
        try:
            summary = _summarize(cancelled.result)
        except ValueError:
            summary = None
    except Exception as exception:
        logger.exception("Pipeline run %s failed", job.id)
        error = str(exception) or exception.__class__.__name__
    finally:
        progress.unbind()
        job.tracker.finalize(status)
        job.tracker.log(
            {"succeeded": "Run finished", "cancelled": "Run cancelled"}.get(
                status, f"Run failed: {error}" if error else "Run failed"
            ),
            "info" if status == "succeeded" else "warn" if status == "cancelled" else "error",
        )
        try:
            close_old_connections()
        finally:
            with _lock:
                job.summary, job.error = summary, error
                job.finished_at = timezone.now()
                job.status = status
            job.done.set()
