#!/bin/zsh
set -euo pipefail

# Load env if present
if [ -f .env ]; then
	export $(grep -v '^#' .env | xargs -I{} echo {})
fi

SOUND_PATH=${SOUND_PATH:-"/System/Library/Sounds/Submarine.aiff"}
SOUND_VOLUME=${SOUND_VOLUME:-0.7}
BUZZ_REPEAT=${BUZZ_REPEAT:-3}
BUZZ_INTERVAL_SECONDS=${BUZZ_INTERVAL_SECONDS:-0.6}

echo "🔊 Testing buzzer sound..."
echo "Sound: $SOUND_PATH"
echo "Volume: $SOUND_VOLUME"
echo "Repeat: $BUZZ_REPEAT times"
echo "Interval: $BUZZ_INTERVAL_SECONDS seconds"
echo ""

for i in $(seq 1 $BUZZ_REPEAT); do
	echo "Playing sound $i/$BUZZ_REPEAT..."
	osascript -e "set volume output volume $(echo "$SOUND_VOLUME * 100" | bc)" -e "do shell script \"afplay \\\"$SOUND_PATH\\\"\""
	if [ $i -lt $BUZZ_REPEAT ]; then
		sleep $BUZZ_INTERVAL_SECONDS
	fi
done

echo "✅ Sound test complete!"
