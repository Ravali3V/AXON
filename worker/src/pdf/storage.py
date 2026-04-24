"""PDF storage — GCS in prod, local filesystem in dev.

Which backend is used is chosen automatically: if `GOOGLE_APPLICATION_CREDENTIALS` is
set OR we're running on GCP (ADC available), we upload to the configured bucket.
Otherwise we write to a local path and return a file:// URL.
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog

from ..config import get_settings

log = structlog.get_logger(__name__)


async def store_pdf(*, audit_id: str, org_id: str, pdf_bytes: bytes) -> str:
    """Persist a generated PDF and return its canonical path (`gs://...` or `file://...`)."""
    settings = get_settings()
    object_path = f"{org_id}/{audit_id}.pdf"

    if _gcs_available():
        return await _upload_gcs(settings.gcs_reports_bucket, object_path, pdf_bytes)

    # Dev fallback: write to a local folder
    local_root = Path("tmp-pdfs") / org_id
    local_root.mkdir(parents=True, exist_ok=True)
    local_file = local_root / f"{audit_id}.pdf"
    local_file.write_bytes(pdf_bytes)
    log.info("pdf_written_local", path=str(local_file), size=len(pdf_bytes))
    return f"file://{local_file.resolve().as_posix()}"


def _gcs_available() -> bool:
    # Explicit credentials path OR running inside GCP (metadata server responds)
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    # Don't try to hit the metadata server from dev machines — require explicit opt-in.
    return os.environ.get("USE_GCS_STORAGE", "").lower() in ("1", "true", "yes")


async def _upload_gcs(bucket_name: str, object_path: str, data: bytes) -> str:
    # Imported here so local dev without google-cloud creds doesn't pay import cost.
    from google.cloud import storage  # type: ignore[import-not-found]

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    blob.upload_from_string(data, content_type="application/pdf")
    gcs_uri = f"gs://{bucket_name}/{object_path}"
    log.info("pdf_uploaded_gcs", path=gcs_uri, size=len(data))
    return gcs_uri
