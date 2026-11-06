#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["openai>=1.50"]
# ///
"""Backend for `specc.py build --backend`: any OpenAI-compatible chat completions endpoint.

Reads the user prompt on stdin and the system prompt from $SPECC_SYSTEM_PROMPT, prints the
answer. Configuration is the OpenAI SDK's own: OPENAI_API_KEY (required), OPENAI_BASE_URL
(optional, default api.openai.com), model from $SPECC_MODEL (the tool's --model).
"""
import os
import sys

from openai import OpenAI

model = os.environ.get("SPECC_MODEL")
if not model:
    sys.exit("openai_sdk.py: set --model (SPECC_MODEL)")
client = OpenAI()  # OPENAI_API_KEY, OPENAI_BASE_URL
response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": os.environ.get("SPECC_SYSTEM_PROMPT", "")},
        {"role": "user", "content": sys.stdin.read()},
    ],
)
choice = response.choices[0]
if choice.finish_reason == "length":
    sys.exit("openai_sdk.py: the answer was cut off by the model's output limit")
sys.stdout.write(choice.message.content or "")
