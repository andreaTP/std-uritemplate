#!/usr/bin/env bash
# Backend for `specc.py build --backend command`: the Claude Messages API through curl.
# Needs ANTHROPIC_API_KEY, curl and jq. Model from $SPECC_MODEL (--model), default claude-opus-5-5.
set -euo pipefail
model=${SPECC_MODEL:-claude-opus-5-5}
jq -n --arg model "$model" --arg system "$SPECC_SYSTEM_PROMPT" --rawfile user /dev/stdin \
  '{model: $model, max_tokens: 32000, system: $system, messages: [{role: "user", content: $user}]}' |
curl -sS https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
  --data-binary @- |
jq -r '.content[] | select(.type == "text") | .text'
