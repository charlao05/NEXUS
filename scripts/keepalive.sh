#!/bin/bash
# NEXUS Backend Keep-Alive
# Render Cron Job — schedule: */10 * * * *
# Build Command: (leave empty)
# Run Command:   bash scripts/keepalive.sh
set -e
TARGET="https://api.nexxusapp.com.br/health"
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Pinging NEXUS backend..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$TARGET")
if [ "$STATUS" = "200" ]; then
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] OK -- backend alive (HTTP $STATUS)"
  exit 0
else
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] WARN -- unexpected response (HTTP $STATUS)"
  exit 1
fi
