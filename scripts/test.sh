#!/usr/bin/env bash
set -euo pipefail
cd apps/api && python -m pytest -q
