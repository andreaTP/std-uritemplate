#!/usr/bin/env bash
# Backend for `specc.py build --backend command`: any OpenAI-compatible chat completions endpoint
# (OpenAI, a local server, most hosted models). Needs OPENAI_API_KEY, curl and jq.
# OPENAI_BASE_URL defaults to https://api.openai.com/v1. Model from $SPECC_MODEL (--model).
set -euo pipefail
base=${OPENAI_BASE_URL:-https://api.openai.com/v1}
jq -n --arg model "${SPECC_MODEL:?set --model}" --arg system "$SPECC_SYSTEM_PROMPT" --rawfile user /dev/stdin \
  '{model: $model, messages: [{role: "system", content: $system}, {role: "user", content: $user}]}' |
curl -sS "$base/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" -H "content-type: application/json" \
  --data-binary @- |
jq -r '.choices[0].message.content'
