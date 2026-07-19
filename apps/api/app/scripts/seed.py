"""Seed Coldex Demo tenant (local/demo only)."""

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.models.tenant import Tenant
from app.db.session import SessionLocal
from app.services.auth_service import TenantService

logger = get_logger(__name__)


def seed() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.seed_demo:
        logger.info("SEED_DEMO=false — skipping seed")
        return

    db = SessionLocal()
    try:
        existing = db.scalar(select(Tenant).where(Tenant.slug == settings.seed_tenant_slug))
        if existing is not None:
            logger.info("Demo tenant already exists: %s", settings.seed_tenant_slug)
            return

        tenant, owner = TenantService(db).create_tenant_with_owner(
            name=settings.seed_tenant_name,
            slug=settings.seed_tenant_slug,
            owner_email=settings.seed_admin_email,
            owner_name=settings.seed_admin_name,
            owner_password=settings.seed_admin_password,
        )
        logger.info(
            "Seeded demo tenant slug=%s owner_email=%s tenant_id=%s",
            tenant.slug,
            owner.email,
            tenant.id,
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
