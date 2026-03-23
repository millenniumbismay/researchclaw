#!/bin/bash
# Scheduled wrapper for ResearchClaw — called by OpenClaw cron
# ANTHROPIC_API_KEY must be set in environment before calling this script.

set -e
cd "$(dirname "$0")"

export TELEGRAM_BOT_TOKEN="TELEGRAM_BOT_TOKEN_REDACTED"
export TELEGRAM_CHAT_ID="TELEGRAM_CHAT_ID_REDACTED"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "[researchclaw] ERROR: ANTHROPIC_API_KEY not set. Aborting."
  exit 1
fi

echo "[researchclaw] Starting crawl at $(date)"
python crawl.py
python summarize.py
echo "[researchclaw] Done at $(date)"
