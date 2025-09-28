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

echo "🌐 Starting On-Call Buzzer Dashboard..."
echo "📊 Dashboard will be available at: http://localhost:5000"
echo "🔄 Press Ctrl+C to stop"

python3 -m src.dashboard
