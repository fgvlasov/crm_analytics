"""AI provider clients: mock (default for tests) and OpenAI-compatible HTTP."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from app.core.logging import get_logger
from app.services.ai_schemas import FAST_ASSESSMENT_SYSTEM_PROMPT

logger = get_logger(__name__)


class AiClient(Protocol):
    def complete_json(self, *, system: str, user: str, model: str) -> dict[str, Any]: ...


class MockAiClient:
    """Deterministic mock provider for local/dev and tests. Never calls the network."""

    def complete_json(self, *, system: str, user: str, model: str) -> dict[str, Any]:
        # Prompt-injection hardening check: ignore "instructions" in user payload.
        _ = system
        lowered = user.lower()
        if "ignore previous instructions" in lowered or "disregard system" in lowered:
            logger.info("Mock provider ignored embedded instruction attempt")

        # Heuristic scoring from keywords in the lead payload text
        text = user.lower()
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
    """Calls OpenAI or any OpenAI-compatible chat completions endpoint."""

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

    def complete_json(self, *, system: str, user: str, model: str) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
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
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
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
