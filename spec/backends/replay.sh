#!/usr/bin/env bash
# Backend that returns the committed output unchanged: exercises the pipeline with no model.
# Usage: specc.py build --target python --force --backend 'spec/backends/replay.sh python/stduritemplate/__init__.py'
set -euo pipefail
printf '```\n'; cat "$1"; printf '```\n'
