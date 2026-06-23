"""Prometheus metrics for observability dashboards."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

referrals_received = Counter(
    "flowcare_referrals_received_total",
    "Total referrals ingested",
    ["source"],
)
referral_processing_seconds = Histogram(
    "flowcare_referral_processing_seconds",
    "End-to-end referral processing latency",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
)
ocr_confidence = Histogram(
    "flowcare_ocr_confidence",
    "OCR confidence scores",
    buckets=(0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0),
)
extraction_failures = Counter(
    "flowcare_extraction_failures_total",
    "AI extraction failures",
    ["reason"],
)
insurance_verification_failures = Counter(
    "flowcare_insurance_verification_failures_total",
    "Insurance verification failures",
    ["reason"],
)
workflow_executions = Counter(
    "flowcare_workflow_executions_total",
    "Workflow executions by terminal status",
    ["status"],
)
queue_depth = Gauge(
    "flowcare_queue_depth",
    "Approximate Celery queue depth",
    ["queue"],
)
