"""Optional public-web research abstraction used by deep lead research."""

from __future__ import annotations

from typing import Any, Protocol


class WebResearchProvider(Protocol):
    def research_company(self, company_identity: dict[str, Any]) -> list[dict[str, Any]]:
        """Return evidence-shaped public B2B sources."""


class DisabledWebResearchProvider:
    """Default provider: deep research remains useful with internal data only."""

    def research_company(self, company_identity: dict[str, Any]) -> list[dict[str, Any]]:
        _ = company_identity
        return []


def build_web_research_provider() -> WebResearchProvider:
    """Factory boundary for future search APIs without coupling workflow code."""
    return DisabledWebResearchProvider()
