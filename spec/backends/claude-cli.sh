#!/usr/bin/env bash
# Backend for `specc.py build --backend`: the Claude Code CLI, non-interactive, tools disabled.
# Needs an authenticated `claude`. Model from $SPECC_MODEL (--model), default opus.
set -euo pipefail
claude -p --model "${SPECC_MODEL:-opus}" --output-format json --no-session-persistence --tools "" \
  --system-prompt "$SPECC_SYSTEM_PROMPT" | jq -r '.result'
