import base64
import hashlib
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models.tenant import SecretRef


def _fernet_from_master_key(master_key: str) -> Fernet:
    digest = hashlib.sha256(master_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class SecretService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self._fernet = _fernet_from_master_key(settings.encryption_master_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise AppError(
                "Failed to decrypt secret",
                code="secret_decrypt_failed",
                status_code=500,
            ) from exc

    def create(
        self,
        *,
        tenant_id: UUID,
        name: str,
        value: str,
        purpose: str = "generic",
    ) -> SecretRef:
        existing = self.db.scalar(
            select(SecretRef).where(SecretRef.tenant_id == tenant_id, SecretRef.name == name)
        )
        if existing is not None:
            raise AppError(
                "Secret with this name already exists",
                code="secret_exists",
                status_code=409,
            )
        secret = SecretRef(
            tenant_id=tenant_id,
            name=name,
            purpose=purpose,
            ciphertext=self.encrypt(value),
            key_version="v1",
        )
        self.db.add(secret)
        self.db.commit()
        self.db.refresh(secret)
        return secret

    def get_for_tenant(self, *, tenant_id: UUID, secret_id: UUID) -> SecretRef | None:
        return self.db.scalar(
            select(SecretRef).where(SecretRef.id == secret_id, SecretRef.tenant_id == tenant_id)
        )

    def list_for_tenant(self, *, tenant_id: UUID) -> list[SecretRef]:
        return list(
            self.db.scalars(select(SecretRef).where(SecretRef.tenant_id == tenant_id)).all()
        )

    def reveal(self, *, tenant_id: UUID, secret_id: UUID) -> str:
        """Internal-only decrypt. Never expose via public API responses."""
        secret = self.get_for_tenant(tenant_id=tenant_id, secret_id=secret_id)
        if secret is None:
            raise AppError("Secret not found", code="secret_not_found", status_code=404)
        return self.decrypt(secret.ciphertext)
