"""Phase 1 worker stub.

Later phases register Celery/Dramatiq tasks only when the matching FEATURE_* flag is enabled.
"""

from __future__ import annotations

import os
import time

FEATURE_FLAGS = {
    "FEATURE_ODOO_CONNECTOR": os.getenv("FEATURE_ODOO_CONNECTOR", "false").lower() == "true",
    "FEATURE_FAST_AI": os.getenv("FEATURE_FAST_AI", "false").lower() == "true",
    "FEATURE_DEEP_RESEARCH": os.getenv("FEATURE_DEEP_RESEARCH", "false").lower() == "true",
    "FEATURE_SMART_RPT": os.getenv("FEATURE_SMART_RPT", "false").lower() == "true",
    "FEATURE_WEB_NEWS_COLLECTORS": os.getenv("FEATURE_WEB_NEWS_COLLECTORS", "false").lower()
    == "true",
}


def main() -> None:
    enabled = [name for name, on in FEATURE_FLAGS.items() if on]
    print("leadintel-workers stub started")
    print(f"enabled feature flags: {enabled or 'none (Phase 1)'}")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
