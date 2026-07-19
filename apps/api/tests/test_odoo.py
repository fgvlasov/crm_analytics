"""Phase 2 Odoo connector tests."""

import pytest

from app.core.config import get_settings
from app.core.errors import FeatureDisabledError
from app.core.tenancy import require_feature


def _enable_odoo(monkeypatch):
    monkeypatch.setenv("FEATURE_ODOO_CONNECTOR", "true")
    get_settings.cache_clear()


def _login(client, email="admin@coldex-demo.example", password="ChangeMeDemo123!", slug="coldex-demo"):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "tenant_slug": slug},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_odoo_routes_disabled_by_default(client, demo_tenant):
    token = _login(client)
    res = client.get("/api/v1/odoo/instances", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "feature_disabled"


def test_register_and_upsert_lead(client, demo_tenant, monkeypatch):
    _enable_odoo(monkeypatch)
    # Re-import settings into app by clearing cache; TestClient uses get_settings each call
    from app.main import app  # noqa: F401

    reg = client.post(
        "/api/v1/odoo/instances/register",
        json={
            "tenant_slug": "coldex-demo",
            "instance_name": "Test Odoo",
            "base_url": "https://odoo.test.example",
            "odoo_version": "19.0",
            "database_name": "test",
            "company_name": "Test Co",
            "module_version": "19.0.1.0.0",
        },
    )
    assert reg.status_code == 200, reg.text
    data = reg.json()
    instance_id = data["odoo_instance_id"]
    token = data["integration_token"]
    assert data["webhook_secret"]

    upsert = client.post(
        "/api/v1/odoo/leads/upsert",
        headers={
            "Authorization": f"Bearer {token}",
            "X-LeadIntel-Odoo-Instance": instance_id,
        },
        json={
            "idempotency_key": "crm.lead:1:2026-07-19T10:00:00Z",
            "odoo_instance_id": instance_id,
            "model": "crm.lead",
            "res_id": "1",
            "write_date": "2026-07-19T10:00:00Z",
            "lead": {
                "name": "Freezer warehouse",
                "company_name": "Example Food Oy",
                "email": "buyer@examplefood.fi",
                "country_code": "FI",
            },
            "messages": [],
            "attachments": [],
        },
    )
    assert upsert.status_code == 200, upsert.text
    lead_id = upsert.json()["lead_id"]
    assert upsert.json()["created"] is True

    # Idempotent replay
    upsert2 = client.post(
        "/api/v1/odoo/leads/upsert",
        headers={
            "Authorization": f"Bearer {token}",
            "X-LeadIntel-Odoo-Instance": instance_id,
        },
        json={
            "idempotency_key": "crm.lead:1:2026-07-19T10:00:00Z",
            "odoo_instance_id": instance_id,
            "model": "crm.lead",
            "res_id": "1",
            "lead": {"name": "Freezer warehouse"},
        },
    )
    assert upsert2.status_code == 200
    assert upsert2.json()["lead_id"] == lead_id

    access = _login(client)
    leads = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {access}"})
    assert leads.status_code == 200
    assert leads.json()["total"] >= 1

    summary = client.get(
        "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {access}"}
    )
    assert summary.status_code == 200
    assert summary.json()["leads_from_odoo"] >= 1


def test_dashboard_create_instance_shows_token_once(client, demo_tenant, monkeypatch):
    _enable_odoo(monkeypatch)
    access = _login(client)
    res = client.post(
        "/api/v1/odoo/instances",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "name": "From Dashboard",
            "base_url": "https://crm.example.com",
            "company_name": "Demo",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["integration_token"]
    assert body["webhook_secret"]
    assert "api_token_hash" not in body["instance"]


def test_require_feature_helper():
    get_settings.cache_clear()
    with pytest.raises(FeatureDisabledError):
        require_feature("odoo_connector")
