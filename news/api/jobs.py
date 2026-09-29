import logging
import threading
import uuid
from collections import OrderedDict

from django.utils import timezone

from news.api.http import ApiError
from news.api.serializers import serialize_job
from pipeline import flow

logger = logging.getLogger(__name__)

MAX_JOBS = 20
ACTIVE_STATUSES = ("queued", "running")

_lock = threading.Lock()
_jobs = OrderedDict()


class PipelineJob:
    def __init__(self, request):
        self.id = uuid.uuid4().hex
        self.request = request
        self.status = "queued"
        self.error = None
        self.summary = None
        self.created_at = timezone.now()
        self.started_at = None
        self.finished_at = None
        self.done = threading.Event()

    def to_dict(self):
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

    thread = threading.Thread(
        target=_execute,
        args=(job, runner or flow.run_flow),
        daemon=True,
        name=f"pipeline-run-{job.id[:8]}",
    )
    job.thread = thread
    thread.start()
    return job


def _summarize(result):
    if result is None or not hasattr(result, "columns") or "status" not in result.columns:
        return {"processed": 0, "approved": 0, "rejected": 0, "failed": 0, "by_status": {}}
    statuses = result["status"].astype(str)
    return {
        "processed": int(len(result)),
        "approved": int((statuses == "APPROVED").sum()),
        "rejected": int((statuses != "APPROVED").sum()),
        "failed": int(statuses.str.endswith("_FAILED").sum()),
        "by_status": {str(key): int(value) for key, value in statuses.value_counts().items()},
    }


def _execute(job, runner):
    from django.db import close_old_connections

    close_old_connections()
    job.status = "running"
    job.started_at = timezone.now()
    try:
        result = runner(**job.request)
        job.summary = _summarize(result)
        job.status = "succeeded"
    except Exception as error:
        logger.exception("Pipeline run %s failed", job.id)
        job.status = "failed"
        job.error = str(error) or error.__class__.__name__
    finally:
        job.finished_at = timezone.now()
        close_old_connections()
        job.done.set()
