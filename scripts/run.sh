#!/bin/zsh
set -euo pipefail

# Load env if present
if [ -f .env ]; then
	export $(grep -v '^#' .env | xargs -I{} echo {})
fi

# Prefer local venv if available
if [ -d .venv ]; then
	source .venv/bin/activate
fi

python3 -m src.main


