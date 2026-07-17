import json
import logging
import time
import uuid
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS = Counter(
    "fanoosai_http_requests_total",
    "Total HTTP requests",
    ("method", "route", "status_class"),
)
HTTP_DURATION = Histogram(
    "fanoosai_http_request_duration_seconds",
    "HTTP request duration",
    ("method", "route"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
AI_REQUESTS = Counter(
    "fanoosai_ai_requests_total",
    "AI provider requests",
    ("provider", "status"),
)
AI_DURATION = Histogram(
    "fanoosai_ai_request_duration_seconds",
    "AI provider request duration",
    ("provider",),
)
QUEUE_JOBS = Counter(
    "fanoosai_queue_jobs_total",
    "Prompt jobs handled by workers",
    ("status",),
)
QUEUE_DEPTH = Gauge("fanoosai_queue_depth", "Approximate pending prompt jobs")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        extra = getattr(record, "event_data", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def request_id() -> str:
    return uuid.uuid4().hex


def duration_seconds(start: float) -> float:
    return time.perf_counter() - start
