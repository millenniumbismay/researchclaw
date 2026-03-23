#!/bin/bash
# Scheduled wrapper for ResearchCrawl — called by OpenClaw cron
# ANTHROPIC_API_KEY must be set in environment before calling this script.

set -e
cd "$(dirname "$0")"

export TELEGRAM_BOT_TOKEN="TELEGRAM_BOT_TOKEN_REDACTED"
export TELEGRAM_CHAT_ID="TELEGRAM_CHAT_ID_REDACTED"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "[researchcrawl] ERROR: ANTHROPIC_API_KEY not set. Aborting."
  exit 1
fi

echo "[researchcrawl] Starting crawl at $(date)"
python crawl.py
python summarize.py
echo "[researchcrawl] Done at $(date)"
