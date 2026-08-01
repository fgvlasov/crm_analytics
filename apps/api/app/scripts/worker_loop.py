"""Background worker loop for Fast Assessment and Deep Research jobs.

Polls the database for queued jobs. Long-running AI work must never run inside HTTP requests.
"""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import SessionLocal
from app.services.assessment_service import AssessmentService

logger = get_logger(__name__)


def run_once() -> bool:
    """Process at most one job. Returns True if a job was handled."""
    settings = get_settings()
    if not settings.feature_fast_ai:
        return False
    db = SessionLocal()
    try:
        service = AssessmentService(db, settings)
        job = service.claim_next_queued_job()
        if job is None:
            return False
        logger.info("Processing assessment job_id=%s lead_id=%s", job.id, job.lead_id)
        service.process_job(job.id)
        logger.info("Finished assessment job_id=%s", job.id)
        return True
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info(
        "LeadIntel worker started feature_fast_ai=%s feature_deep=%s feature_odoo=%s",
        settings.feature_fast_ai,
        settings.feature_deep_research,
        settings.feature_odoo_connector,
    )
    while True:
        try:
            handled = run_once()
            time.sleep(2 if handled else 5)
        except Exception:  # noqa: BLE001 — keep worker alive
            logger.exception("Worker loop error")
            time.sleep(5)


if __name__ == "__main__":
    main()
