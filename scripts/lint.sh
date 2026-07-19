#!/usr/bin/env bash
set -euo pipefail
cd apps/api && ruff check app tests
