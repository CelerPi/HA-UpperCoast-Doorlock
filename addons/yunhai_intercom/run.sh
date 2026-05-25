#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=/app
exec python3 -m yunhai_intercom.server
