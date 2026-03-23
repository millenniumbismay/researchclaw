#!/bin/bash
# Scheduled wrapper for ResearchClaw — called by OpenClaw cron
# All credentials loaded from .env — never hardcode tokens here.

set -e
cd "$(dirname "$0")"

# Load credentials from .env
if [ -f .env ]; then
  set -a && source .env && set +a
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "[researchclaw] ERROR: ANTHROPIC_API_KEY not set. Aborting."
  exit 1
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
  echo "[researchclaw] WARNING: Telegram credentials not set. Notifications will be skipped."
fi

echo "[researchclaw] Starting crawl at $(date)"
.venv/bin/python crawl.py
.venv/bin/python summarize.py
echo "[researchclaw] Done at $(date)"
