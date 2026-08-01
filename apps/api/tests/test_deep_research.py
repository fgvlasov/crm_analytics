"""Phase 4 Deep Research acceptance and tenant-isolation tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.db.models.ai import JobStatus
from app.db.models.odoo import Lead, LeadSourceType
from app.services.ai_schemas import validate_deep_and_finalize


def _enable_deep(monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_FAST_AI", "true")
    monkeypatch.setenv("FEATURE_DEEP_RESEARCH", "true")
    monkeypatch.setenv("FEATURE_ODOO_CONNECTOR", "false")
    get_settings.cache_clear()


def _login(
    client,
    *,
    tenant_slug="coldex-demo",
    email="admin@coldex-demo.example",
    password="ChangeMeDemo123!",
):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": tenant_slug,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_lead(db_session, tenant_id, *, name="Deep lead") -> Lead:
    lead = Lead(
        tenant_id=tenant_id,
        source_type=LeadSourceType.manual,
        name=name,
        company_name="Evidence Foods Oy",
        website="https://example.com",
        country_code="FI",
        description="Freezer warehouse expansion with an urgent delivery target.",
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


def _run_fast(client, token: str, lead_id) -> None:
    queued = client.post(
        f"/api/v1/leads/{lead_id}/assessments/queue",
        headers=_auth(token),
        json={"assessment_mode": "fast", "force": True},
    )
    assert queued.status_code == 200, queued.text
    completed = client.post(
        f"/api/v1/jobs/{queued.json()['id']}/run",
        headers=_auth(token),
        json={},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "succeeded"


def test_deep_requires_fast_feature(monkeypatch):
    monkeypatch.setenv("FEATURE_FAST_AI", "false")
    monkeypatch.setenv("FEATURE_DEEP_RESEARCH", "true")
    with pytest.raises(ValidationError, match="requires FEATURE_FAST_AI"):
        Settings()


def test_deep_route_is_feature_gated(client, demo_tenant, monkeypatch, db_session):
    monkeypatch.setenv("FEATURE_FAST_AI", "true")
    monkeypatch.setenv("FEATURE_DEEP_RESEARCH", "false")
    get_settings.cache_clear()
    tenant, _ = demo_tenant
    lead = _create_lead(db_session, tenant.id)
    token = _login(client)

    response = client.post(
        f"/api/v1/leads/{lead.id}/assessments/queue",
        headers=_auth(token),
        json={"assessment_mode": "deep"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "feature_disabled"


def test_deep_flow_persists_validated_evidence(
    client,
    demo_tenant,
    monkeypatch,
    db_session,
):
    _enable_deep(monkeypatch)
    tenant, _ = demo_tenant
    lead = _create_lead(db_session, tenant.id)
    token = _login(client)
    _run_fast(client, token, lead.id)

    queued = client.post(
        f"/api/v1/leads/{lead.id}/assessments/queue",
        headers=_auth(token),
        json={"assessment_mode": "deep", "force": True},
    )
    assert queued.status_code == 200, queued.text
    completed = client.post(
        f"/api/v1/jobs/{queued.json()['id']}/run",
        headers=_auth(token),
        json={},
    )
    assert completed.status_code == 200, completed.text
    deep = completed.json()
    assert deep["workflow"] == "deep_lead_research"
    assert deep["status"] == "succeeded"

    evidence = client.get(
        f"/api/v1/assessments/{deep['id']}/evidence",
        headers=_auth(token),
    )
    assert evidence.status_code == 200
    assert len(evidence.json()) == 1
    assert "object_key" not in evidence.json()[0]
    assert evidence.json()[0]["source_url"] == "https://example.com/"

    signed = client.post(
        f"/api/v1/evidence/{evidence.json()[0]['id']}/signed-url",
        headers=_auth(token),
        json={},
    )
    assert signed.status_code == 200
    assert "Signature=" in signed.json()["url"]


def test_changed_lead_marks_deep_job_stale_and_requeues(
    client,
    demo_tenant,
    monkeypatch,
    db_session,
):
    _enable_deep(monkeypatch)
    tenant, _ = demo_tenant
    lead = _create_lead(db_session, tenant.id)
    token = _login(client)
    _run_fast(client, token, lead.id)
    queued = client.post(
        f"/api/v1/leads/{lead.id}/assessments/queue",
        headers=_auth(token),
        json={"assessment_mode": "deep"},
    )
    assert queued.status_code == 200

    lead.description = "The scope changed after queueing: add a second cold room."
    db_session.commit()
    completed = client.post(
        f"/api/v1/jobs/{queued.json()['id']}/run",
        headers=_auth(token),
        json={},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "stale"

    jobs = client.get("/api/v1/jobs", headers=_auth(token))
    replacement = [
        job
        for job in jobs.json()
        if job["workflow"] == "deep_lead_research" and job["id"] != queued.json()["id"]
    ]
    assert replacement
    assert replacement[0]["status"] == JobStatus.queued.value


def test_successful_fast_rerun_requeues_deep_after_lead_update(
    client,
    demo_tenant,
    monkeypatch,
    db_session,
):
    _enable_deep(monkeypatch)
    tenant, _ = demo_tenant
    lead = _create_lead(db_session, tenant.id)
    token = _login(client)
    _run_fast(client, token, lead.id)

    jobs = client.get("/api/v1/jobs", headers=_auth(token)).json()
    first_deep = next(job for job in jobs if job["workflow"] == "deep_lead_research")
    completed = client.post(
        f"/api/v1/jobs/{first_deep['id']}/run",
        headers=_auth(token),
        json={},
    )
    assert completed.json()["status"] == "succeeded"

    lead.description = "Updated scope with a larger freezer and a new deadline."
    db_session.commit()
    _run_fast(client, token, lead.id)

    jobs = client.get("/api/v1/jobs", headers=_auth(token)).json()
    deep_jobs = [job for job in jobs if job["workflow"] == "deep_lead_research"]
    assert len(deep_jobs) >= 2
    assert deep_jobs[0]["status"] == JobStatus.queued.value
    assert deep_jobs[0]["input_fingerprint"] != first_deep["input_fingerprint"]


def test_invalid_similar_deal_id_is_rejected():
    payload = {
        "enhanced_scoring_breakdown": {
            "business_fit": 20,
            "project_potential": 10,
            "customer_quality": 10,
            "urgency": 10,
            "technical_completeness": 5,
            "geography": 5,
        },
        "identity_confidence": 80,
        "commercial_relevance_confidence": 80,
        "overall_assessment_confidence": 80,
        "company_profile": "Professional company profile.",
        "internal_relationship_summary": "No prior relationship.",
        "similar_deal_ids": ["not-allowed"],
        "recommended_action": "Call the customer.",
        "sources": [],
    }
    with pytest.raises(ValueError, match="Invalid similar_deal_id"):
        validate_deep_and_finalize(payload, allowed_similar_deal_ids={"allowed"})


def test_deep_openai_schema_uses_supported_url_constraints():
    from app.services.ai_schemas import DEEP_RESEARCH_RESPONSE_SCHEMA

    source_url_schema = DEEP_RESEARCH_RESPONSE_SCHEMA["properties"]["sources"]["items"][
        "properties"
    ]["source_url"]
    assert source_url_schema["type"] == "string"
    assert "format" not in source_url_schema


def test_evidence_is_tenant_scoped(
    client,
    demo_tenant,
    other_tenant,
    monkeypatch,
    db_session,
):
    _enable_deep(monkeypatch)
    tenant, _ = demo_tenant
    lead = _create_lead(db_session, tenant.id)
    token = _login(client)
    _run_fast(client, token, lead.id)
    queued = client.post(
        f"/api/v1/leads/{lead.id}/assessments/queue",
        headers=_auth(token),
        json={"assessment_mode": "deep", "force": True},
    )
    deep = client.post(
        f"/api/v1/jobs/{queued.json()['id']}/run",
        headers=_auth(token),
        json={},
    ).json()

    other_token = _login(
        client,
        tenant_slug="other-co",
        email="owner@other.example",
        password="OtherPass123!",
    )
    response = client.get(
        f"/api/v1/assessments/{deep['id']}/evidence",
        headers=_auth(other_token),
    )
    assert response.status_code == 200
    assert response.json() == []
