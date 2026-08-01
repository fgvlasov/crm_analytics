"""AI provider CRUD (BYOK). Keys encrypted; never returned after save."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models.ai import AiProviderConnection, AiProviderStatus, AiProviderType
from app.services.ai_clients import build_client
from app.services.secret_service import SecretService


class AiProviderService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.secrets = SecretService(db, settings)

    def create(
        self,
        *,
        tenant_id: UUID,
        name: str,
        provider_type: AiProviderType,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
        is_default: bool = False,
    ) -> AiProviderConnection:
        if provider_type != AiProviderType.mock and not api_key:
            raise AppError("api_key required", code="api_key_required", status_code=400)

        if is_default:
            self._clear_default(tenant_id)

        row = AiProviderConnection(
            tenant_id=tenant_id,
            name=name,
            provider_type=provider_type,
            base_url=base_url,
            api_key_encrypted=self.secrets.encrypt(api_key) if api_key else None,
            default_model=default_model,
            status=AiProviderStatus.active,
            is_default=is_default or provider_type == AiProviderType.mock,
        )
        # Ensure at least one default mock-friendly provider
        if not is_default and provider_type == AiProviderType.mock:
            existing_default = self.get_default(tenant_id)
            row.is_default = existing_default is None
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _clear_default(self, tenant_id: UUID) -> None:
        self.db.execute(
            update(AiProviderConnection)
            .where(
                AiProviderConnection.tenant_id == tenant_id,
                AiProviderConnection.is_default.is_(True),
            )
            .values(is_default=False)
        )

    def list_for_tenant(self, tenant_id: UUID) -> list[AiProviderConnection]:
        return list(
            self.db.scalars(
                select(AiProviderConnection)
                .where(AiProviderConnection.tenant_id == tenant_id)
                .order_by(AiProviderConnection.created_at.desc())
            ).all()
        )

    def get_for_tenant(self, tenant_id: UUID, provider_id: UUID) -> AiProviderConnection | None:
        return self.db.scalar(
            select(AiProviderConnection).where(
                AiProviderConnection.id == provider_id,
                AiProviderConnection.tenant_id == tenant_id,
            )
        )

    def delete(self, tenant_id: UUID, provider_id: UUID) -> None:
        provider = self.get_for_tenant(tenant_id, provider_id)
        if provider is None:
            raise AppError("Provider not found", code="provider_not_found", status_code=404)

        was_default = provider.is_default
        self.db.delete(provider)
        self.db.flush()

        if was_default:
            replacement = self.db.scalar(
                select(AiProviderConnection)
                .where(
                    AiProviderConnection.tenant_id == tenant_id,
                    AiProviderConnection.status == AiProviderStatus.active,
                )
                .order_by(AiProviderConnection.created_at.desc())
            )
            if replacement is not None:
                replacement.is_default = True
        self.db.commit()

    def get_default(self, tenant_id: UUID) -> AiProviderConnection | None:
        row = self.db.scalar(
            select(AiProviderConnection).where(
                AiProviderConnection.tenant_id == tenant_id,
                AiProviderConnection.is_default.is_(True),
                AiProviderConnection.status == AiProviderStatus.active,
            )
        )
        if row:
            return row
        return self.db.scalar(
            select(AiProviderConnection).where(
                AiProviderConnection.tenant_id == tenant_id,
                AiProviderConnection.status == AiProviderStatus.active,
            )
        )

    def ensure_mock_default(self, tenant_id: UUID) -> AiProviderConnection:
        existing = self.get_default(tenant_id)
        if existing:
            return existing
        return self.create(
            tenant_id=tenant_id,
            name="Mock AI (local)",
            provider_type=AiProviderType.mock,
            is_default=True,
            default_model="mock-v1",
        )

    def reveal_api_key(self, provider: AiProviderConnection) -> str | None:
        if not provider.api_key_encrypted:
            return None
        return self.secrets.decrypt(provider.api_key_encrypted)

    def test_connection(self, tenant_id: UUID, provider_id: UUID) -> dict:
        provider = self.get_for_tenant(tenant_id, provider_id)
        if provider is None:
            raise AppError("Provider not found", code="provider_not_found", status_code=404)
        try:
            client = build_client(
                provider_type=provider.provider_type.value,
                api_key=self.reveal_api_key(provider),
                base_url=provider.base_url,
            )
            # Prefer lightweight ping (GET /v1/models) over chat/completions to avoid 429 quota burns.
            ping = client.ping()
            provider.last_test_at = datetime.now(UTC)
            provider.last_error = None
            provider.status = AiProviderStatus.active
            self.db.commit()
            return {"ok": True, "ping": ping}
        except Exception as exc:  # noqa: BLE001 — surface provider test errors to API
            provider.last_error = str(exc)[:2000]
            provider.status = AiProviderStatus.error
            self.db.commit()
            raise AppError(
                f"Provider test failed: {exc}",
                code="provider_test_failed",
                status_code=400,
            ) from exc
