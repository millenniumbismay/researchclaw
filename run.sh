#!/bin/bash
# Required env vars: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
set -e
cd "$(dirname "$0")"
set -a && source .env && set +a
python crawl.py
python summarize.py
echo "ResearchClaw complete. See output/index.md"
