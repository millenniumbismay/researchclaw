#!/bin/bash
cd "$(dirname "$0")"
set -a && source .env && set +a
.venv/bin/uvicorn ui:app --host 0.0.0.0 --port 7337 --reload
