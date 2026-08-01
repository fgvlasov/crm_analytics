"""AI provider clients: mock (default for tests) and OpenAI-compatible HTTP.

Phase 3 Fast Assessment uses the Chat Completions API
(POST /v1/chat/completions), not the Agents SDK.
See OpenAI Chat Completions docs; Agents quickstart is a separate product.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from app.core.logging import get_logger
from app.services.ai_schemas import FAST_ASSESSMENT_SYSTEM_PROMPT

logger = get_logger(__name__)


class AiClientError(Exception):
    """Provider HTTP / protocol error with a clear user-facing message."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AiClient(Protocol):
    def ping(self) -> dict[str, Any]:
        """Lightweight connectivity check (prefer no billable generation)."""

    def complete_json(self, *, system: str, user: str, model: str) -> dict[str, Any]: ...


def _http_error_message(response: httpx.Response) -> str:
    status = response.status_code
    detail = ""
    try:
        body = response.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            detail = str(err.get("message") or err.get("code") or "")
        elif isinstance(err, str):
            detail = err
    except Exception:  # noqa: BLE001
        detail = (response.text or "")[:300]

    if status == 401:
        return (
            "OpenAI rejected the API key (401 Unauthorized). "
            "Check the key in the provider settings."
        )
    if status == 429:
        return (
            "OpenAI rate limit or quota exceeded (429 Too Many Requests). "
            "Check billing/usage at https://platform.openai.com/usage and retry later. "
            "Provider Test uses GET /v1/models and does not call chat/completions."
        )
    if status == 404:
        return f"OpenAI endpoint or model not found (404). {detail}".strip()
    return f"OpenAI HTTP {status}: {detail or response.reason_phrase}".strip()


class MockAiClient:
    """Deterministic mock provider for local/dev and tests. Never calls the network."""

    def ping(self) -> dict[str, Any]:
        return {"ok": True, "provider": "mock"}

    def complete_json(self, *, system: str, user: str, model: str) -> dict[str, Any]:
        # Prompt-injection hardening: ignore "instructions" embedded in user payload.
        _ = system
        lowered = user.lower()
        if "ignore previous instructions" in lowered or "disregard system" in lowered:
            logger.info("Mock provider ignored embedded instruction attempt")

        text = user.lower()
        if "deep-research schema" in system.lower():
            allowed_ids: list[str] = []
            try:
                marker = "DEEP_RESEARCH_DATA:\n"
                deep_data = json.loads(user.split(marker, 1)[1])
                allowed_ids = [
                    str(item["similar_deal_id"])
                    for item in deep_data.get("similar_deals", [])[:2]
                ]
            except (IndexError, KeyError, TypeError, json.JSONDecodeError):
                pass
            website = ""
            try:
                website = str(deep_data.get("lead", {}).get("website") or "")
            except UnboundLocalError:
                pass
            sources = []
            if website.startswith(("http://", "https://")):
                sources.append(
                    {
                        "source_url": website,
                        "title": "Company website",
                        "short_quote": None,
                        "claim_supported": "CRM-provided official company website.",
                        "confidence": 70,
                    }
                )
            return {
                "enhanced_scoring_breakdown": {
                    "business_fit": 28,
                    "project_potential": 18,
                    "customer_quality": 12,
                    "urgency": 10,
                    "technical_completeness": 8,
                    "geography": 9,
                },
                "identity_confidence": 82 if website else 55,
                "commercial_relevance_confidence": 84,
                "overall_assessment_confidence": 80 if website else 55,
                "company_profile": "Mock deep profile based on CRM and internal history.",
                "contact_professional_profile": "Professional role requires confirmation.",
                "market_signals": ["Active industrial project inquiry"],
                "internal_relationship_summary": "Internal CRM history was reviewed.",
                "similar_deal_ids": allowed_ids,
                "risks": ["Public identity evidence is limited"] if not website else [],
                "recommended_action": "Validate decision makers and prepare a technical discovery call.",
                "sources": sources,
            }

        business_fit = 22
        project_potential = 14
        urgency = 8
        technical = 6
        geography = 8
        customer_quality = 10

        if any(k in text for k in ("freezer", "cold room", "refrigeration", "warehouse")):
            business_fit = 28
            project_potential = 18
            technical = 8
        if any(k in text for k in ("urgent", "asap", "this week", "deadline")):
            urgency = 14
        if "fi" in text or "finland" in text or "helsinki" in text:
            geography = 10

        return {
            "scoring_breakdown": {
                "business_fit": business_fit,
                "project_potential": project_potential,
                "customer_quality": customer_quality,
                "urgency": urgency,
                "technical_completeness": technical,
                "geography": geography,
            },
            "confidence": 78,
            "relevant_to_customer": True,
            "project_type": "freezer_warehouse" if "freezer" in text else "cold_storage",
            "customer_industry": "food_processing" if "food" in text else "industrial",
            "summary": "Mock assessment: lead appears relevant based on structured CRM fields.",
            "positive_signals": ["Structured inquiry", "Industrial context"],
            "risks": ["Budget not confirmed"],
            "missing_information": ["Exact dimensions"],
            "recommended_action": "Call the contact and confirm technical requirements.",
            "deep_research_recommended": business_fit >= 25,
            "model_used": model or "mock-v1",
        }


class OpenAICompatibleClient:
    """OpenAI / OpenAI-compatible Chat Completions client.

    Scoring uses POST /v1/chat/completions with response_format=json_object.
    Connectivity test uses GET /v1/models (no generation quota).
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def ping(self) -> dict[str, Any]:
        """Verify API key via models list — avoids burning chat completion quota."""
        url = f"{self.base_url}/models"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self._headers())
        if response.status_code >= 400:
            raise AiClientError(_http_error_message(response), status_code=response.status_code)
        data = response.json()
        models = data.get("data") if isinstance(data, dict) else None
        count = len(models) if isinstance(models, list) else 0
        return {"ok": True, "models_visible": count}

    def complete_json(self, *, system: str, user: str, model: str) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system or FAST_ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=self._headers(), json=body)
        if response.status_code >= 400:
            raise AiClientError(_http_error_message(response), status_code=response.status_code)
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _parse_json_content(content)


def _parse_json_content(content: str) -> dict[str, Any]:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def build_client(
    *,
    provider_type: str,
    api_key: str | None,
    base_url: str | None,
) -> AiClient:
    if provider_type == "mock":
        return MockAiClient()
    if provider_type in {"openai", "openai_compatible"}:
        if not api_key:
            raise ValueError("API key required for OpenAI-compatible providers")
        return OpenAICompatibleClient(api_key=api_key, base_url=base_url)
    raise ValueError(f"Unsupported provider type: {provider_type}")
