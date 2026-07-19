import pytest

from app.core.config import Settings
from app.core.logging import redact_secrets
from app.services.secret_service import SecretService


def test_feature_deep_requires_fast():
    with pytest.raises(ValueError, match="FEATURE_DEEP_RESEARCH"):
        Settings(
            secret_key="test-secret-key-at-least-32-characters",
            encryption_master_key="test-encryption-master-key-32b!!",
            feature_deep_research=True,
            feature_fast_ai=False,
        )


def test_secret_roundtrip(db_session, demo_tenant):
    tenant, _ = demo_tenant
    settings = Settings(
        secret_key="test-secret-key-at-least-32-characters",
        encryption_master_key="test-encryption-master-key-32b!!",
    )
    svc = SecretService(db_session, settings)
    secret = svc.create(tenant_id=tenant.id, name="api-key", value="plain-secret-123")
    assert secret.ciphertext != "plain-secret-123"
    assert svc.reveal(tenant_id=tenant.id, secret_id=secret.id) == "plain-secret-123"


def test_log_redaction():
    assert "***REDACTED***" in redact_secrets("password=hunter2")
    assert "hunter2" not in redact_secrets("password=hunter2")
