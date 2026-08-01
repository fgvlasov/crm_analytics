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


def test_delete_instance_for_own_tenant_only(client, demo_tenant, other_tenant, monkeypatch):
    _enable_odoo(monkeypatch)
    demo_token = _login(client)
    other_token = _login(
        client, "owner@other.example", "OtherPass123!", "other-co"
    )

    demo_create = client.post(
        "/api/v1/odoo/instances",
        headers={"Authorization": f"Bearer {demo_token}"},
        json={"name": "Demo CRM", "base_url": "https://demo.example.com"},
    )
    assert demo_create.status_code == 201
    demo_id = demo_create.json()["instance"]["id"]

    other_create = client.post(
        "/api/v1/odoo/instances",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"name": "Other CRM", "base_url": "https://other.example.com"},
    )
    assert other_create.status_code == 201
    other_id = other_create.json()["instance"]["id"]

    # Other tenant cannot delete demo's integration (scoped 404, not leak)
    forbidden = client.delete(
        f"/api/v1/odoo/instances/{demo_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 404

    listed_other = client.get(
        "/api/v1/odoo/instances",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert listed_other.status_code == 200
    assert {i["id"] for i in listed_other.json()} == {other_id}

    deleted = client.delete(
        f"/api/v1/odoo/instances/{demo_id}",
        headers={"Authorization": f"Bearer {demo_token}"},
    )
    assert deleted.status_code == 204

    listed_demo = client.get(
        "/api/v1/odoo/instances",
        headers={"Authorization": f"Bearer {demo_token}"},
    )
    assert listed_demo.status_code == 200
    assert listed_demo.json() == []

    # Other tenant's integration untouched
    still = client.get(
        "/api/v1/odoo/instances",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert {i["id"] for i in still.json()} == {other_id}


def test_register_merges_http_https_duplicate(client, demo_tenant, monkeypatch):
    _enable_odoo(monkeypatch)
    first = client.post(
        "/api/v1/odoo/instances/register",
        json={
            "tenant_slug": "coldex-demo",
            "instance_name": "Coldex Demo",
            "base_url": "http://stage-hub.coldex.fi",
            "odoo_version": "19.0",
            "module_version": "19.0.1.0.0",
        },
    )
    assert first.status_code == 200
    first_id = first.json()["odoo_instance_id"]

    second = client.post(
        "/api/v1/odoo/instances/register",
        json={
            "tenant_slug": "coldex-demo",
            "instance_name": "Coldex Demo",
            "base_url": "https://stage-hub.coldex.fi",
            "odoo_version": "19.0",
            "module_version": "19.0.1.0.0",
        },
    )
    assert second.status_code == 200
    assert second.json()["odoo_instance_id"] == first_id

    access = _login(client)
    listed = client.get(
        "/api/v1/odoo/instances", headers={"Authorization": f"Bearer {access}"}
    )
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["base_url"] == "https://stage-hub.coldex.fi"


def test_require_feature_helper():
    get_settings.cache_clear()
    with pytest.raises(FeatureDisabledError):
        require_feature("odoo_connector")


def test_build_assessment_payload_maps_temperature_and_extra_fields():
    from uuid import uuid4

    from app.integrations.odoo_client import OdooClient

    payload = OdooClient().build_assessment_payload(
        event_id="evt-1",
        lead_id=uuid4(),
        odoo_res_id="42",
        score_total=82,
        temperature="not_relevant",
        summary="Summary",
        recommended_action="Call",
        confidence=78,
        project_type="cold_storage",
        customer_industry="industrial",
    )
    assert payload["temperature"] == "cold"
    assert payload["recommended_action"] == "Call"
    assert payload["confidence"] == 78
    assert payload["project_type"] == "cold_storage"
    assert payload["customer_industry"] == "industrial"
    assert payload["odoo_res_id"] == "42"


def test_odoo_callback_accepts_json_rpc_response(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    from app.integrations.odoo_client import OdooClient

    class FakeResponse:
        status_code = 200
        is_success = True

        def json(self):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "result": {"status": "processed", "odoo_res_id": 42},
            }

    class FakeHttpClient:
        def __init__(self, **kwargs):
            _ = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, *, content, headers):
            _ = (url, content, headers)
            return FakeResponse()

    monkeypatch.setattr("app.integrations.odoo_client.httpx.Client", FakeHttpClient)
    instance = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        base_url="https://odoo.example.com",
        database_name="production",
    )
    result = OdooClient().push_assessment_result(
        instance=instance,
        webhook_secret="secret",
        payload={"event_id": "event-1", "odoo_res_id": "42"},
    )
    assert result["ok"] is True
    assert result["body_status"] == "processed"


def test_odoo_callback_retries_with_json_rpc_envelope(monkeypatch):
    import json
    from types import SimpleNamespace
    from uuid import uuid4

    from app.integrations.odoo_client import OdooClient

    sent_payloads = []

    class FakeResponse:
        status_code = 200
        is_success = True

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    class FakeHttpClient:
        def __init__(self, **kwargs):
            _ = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, *, content, headers):
            _ = (url, headers)
            sent_payloads.append(json.loads(content))
            if len(sent_payloads) == 1:
                return FakeResponse({"status": "error", "message": "event_id required"})
            return FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "result": {"status": "processed", "odoo_res_id": 42},
                }
            )

    monkeypatch.setattr("app.integrations.odoo_client.httpx.Client", FakeHttpClient)
    instance = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        base_url="https://odoo.example.com",
        database_name="production",
    )
    payload = {"event_id": "event-2", "odoo_res_id": "42", "summary": "Summary"}
    result = OdooClient().push_assessment_result(
        instance=instance,
        webhook_secret="secret",
        payload=payload,
    )

    assert result["ok"] is True
    assert len(sent_payloads) == 2
    assert sent_payloads[0] == payload
    assert sent_payloads[1]["params"] == payload
    assert sent_payloads[1]["id"] == "event-2"
