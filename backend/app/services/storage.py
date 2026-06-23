"""File storage abstraction — local filesystem or S3-compatible object store."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.core.config import settings


def store(content: bytes, filename: str) -> str:
    """Persist file bytes and return an opaque storage key."""
    key = f"{uuid.uuid4()}/{filename}"
    if settings.storage_backend == "s3":
        return _store_s3(content, key)
    return _store_local(content, key)


def load(key: str) -> bytes:
    if settings.storage_backend == "s3":
        return _load_s3(key)
    return _load_local(key)


# ── Local ──
def _local_path(key: str) -> Path:
    base = Path(settings.storage_local_dir)
    return base / key


def _store_local(content: bytes, key: str) -> str:
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return key


def _load_local(key: str) -> bytes:
    return _local_path(key).read_bytes()


# ── S3 / MinIO ──
def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def _store_s3(content: bytes, key: str) -> str:
    _s3_client().put_object(Bucket=settings.s3_bucket, Key=key, Body=content)
    return key


def _load_s3(key: str) -> bytes:
    obj = _s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
    return obj["Body"].read()
