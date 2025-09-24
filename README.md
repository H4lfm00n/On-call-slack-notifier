## On-call Slack Buzzer (macOS)

This small app listens to Slack messages (via Events API using Socket Mode) and plays a buzzer sound on your Mac when messages containing specific keywords (e.g., `@help`) appear, optionally restricted to specific channels.

### What it does
- Listens to Slack `message` events in real time using Socket Mode (no public web server needed)
- Matches messages by keywords (case-insensitive) like `@help`
- Optional channel allowlist/blocklist (by channel names or IDs)
- Plays a macOS sound using `afplay` and optionally shows a macOS notification

### Requirements
- macOS (uses `afplay` and `osascript`)
- Python 3.9+
- A Slack App with Socket Mode enabled

### 1) Create Slack App
1. Create a new app (From scratch).
2. Enable Socket Mode: App Home → Socket Mode → Enable. Generate an App Token with scope `connections:write`.
   - You'll get `SLACK_APP_TOKEN` starting with `xapp-...`.
3. Bot Token scopes (OAuth & Permissions → Scopes): add at minimum:
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `channels:read`
   - `groups:read`
4. Install the app to your workspace to get `SLACK_BOT_TOKEN` starting `xoxb-...`.
5. Event Subscriptions → Subscribe to bot events:
   - `message.channels`, `message.groups`, `message.im`, `message.mpim`.
   - With Socket Mode you do not need a public Request URL.

### 2) Configure
Copy `.env.example` to `.env` and fill in tokens:

```bash
cp .env.example .env
open .env
```

Edit values:
- `SLACK_APP_TOKEN`: xapp-... (Socket Mode)
- `SLACK_BOT_TOKEN`: xoxb-...
- `KEYWORDS`: comma-separated keywords to match (e.g. `@help, urgent, projector down`)
- `CHANNEL_ALLOWLIST`: optional comma-separated channel names or IDs to include
- `CHANNEL_BLOCKLIST`: optional comma-separated channel names or IDs to exclude
- `SOUND_PATH`: path to an audio file. Defaults to `/System/Library/Sounds/Submarine.aiff`
- `BUZZ_REPEAT`, `BUZZ_INTERVAL_SECONDS`: control buzzer repetitions

Tip: channel names are without `#` (e.g. `customer-requests`).

### 3) Install and Run
```bash
# from project root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# copy env and set tokens
cp .env.example .env
# edit .env to add your xapp/xoxb tokens

# run
chmod +x scripts/run.sh
./scripts/run.sh
```

You should see logs like "Starting Socket Mode handler...". When a matching message arrives, your Mac will play the sound and show a notification.

### Notes
- The app ignores bot messages by default (`IGNORE_BOTS=true`).
- If you want this to auto-start, add `scripts/run.sh` to Login Items, or create a LaunchAgent.
- To target only your Customer Response channel(s), put their names in `CHANNEL_ALLOWLIST`.

### Troubleshooting
- If you get missing scopes errors, re-add scopes and reinstall the app to workspace.
- If you hear no sound, try another system sound path like `/System/Library/Sounds/Glass.aiff`.
- Ensure the app is invited to the channels you care about if they are private.


