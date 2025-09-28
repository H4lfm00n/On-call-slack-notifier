## 🚨 On-Call Slack Buzzer (macOS)

A powerful Slack integration that monitors messages and triggers audio alerts when specific keywords or patterns are detected. Perfect for IT support teams who need immediate notification when classroom issues arise.

### ✨ Features
- **Real-time monitoring**: Listens to Slack messages via Socket Mode (no public server needed)
- **Smart keyword matching**: Simple keywords + regex patterns for complex matching
- **Channel filtering**: Allowlist/blocklist specific channels
- **Audio alerts**: Plays customizable macOS sounds with volume control
- **Rate limiting**: Prevents alert spam with configurable cooldown periods
- **Statistics tracking**: Monitors alert frequency and patterns
- **Web dashboard**: Real-time monitoring and configuration overview
- **Slack commands**: `/buzzer-stats` and `/buzzer-sounds` for quick info
- **Graceful shutdown**: Proper signal handling and cleanup

### Requirements
- macOS (uses `afplay` and `osascript`)
- Python 3.9+
- A Slack App with Socket Mode enabled

### 1) Create Slack App
1. Go to [Slack API](https://api.slack.com/apps) and create a new app (From scratch).
2. **Enable Socket Mode**: 
   - App Home → Socket Mode → Enable
   - Generate an App Token with scope `connections:write`
   - You'll get `SLACK_APP_TOKEN` starting with `xapp-...`
3. **Bot Token Scopes** (OAuth & Permissions → Scopes → Bot Token Scopes):
   - `channels:history`
   - `groups:history` 
   - `im:history`
   - `mpim:history`
   - `channels:read`
   - `groups:read`
   - `commands` (for `/buzzer-stats` and `/buzzer-sounds`)
4. **Install App**: Install to your workspace to get `SLACK_BOT_TOKEN` starting `xoxb-...`
5. **Event Subscriptions**: Subscribe to bot events:
   - `message.channels`
   - `message.groups` 
   - `message.im`
   - `message.mpim`
   - With Socket Mode, no public Request URL needed
6. **Slash Commands** (optional): Create `/buzzer-stats` and `/buzzer-sounds` commands

### 2) Configure
Copy `.env.example` to `.env` and fill in tokens:

```bash
cp .env.example .env
open .env
```

**Required Settings:**
- `SLACK_APP_TOKEN`: xapp-... (Socket Mode token)
- `SLACK_BOT_TOKEN`: xoxb-... (Bot token)

**Alert Configuration:**
- `KEYWORDS`: comma-separated keywords (e.g. `@help, urgent, projector down, tv not working`)
- `KEYWORD_PATTERNS`: regex patterns (e.g. `classroom\s+\d+,room\s+\d+,humanities\s+\d+`)
- `CHANNEL_ALLOWLIST`: specific channels to monitor (e.g. `customer-requests,it-support`)
- `CHANNEL_BLOCKLIST`: channels to ignore (e.g. `general,random`)

**Audio Settings:**
- `SOUND_PATH`: audio file path (default: `/System/Library/Sounds/Submarine.aiff`)
- `SOUND_VOLUME`: volume level 0.0-1.0 (default: 0.7)
- `BUZZ_REPEAT`: number of times to play sound (default: 3)
- `BUZZ_INTERVAL_SECONDS`: delay between repetitions (default: 0.6)

**Advanced Settings:**
- `RATE_LIMIT_MINUTES`: cooldown between alerts (default: 5)
- `ENABLE_STATS`: track statistics (default: true)
- `SHOW_MAC_NOTIFICATION`: show macOS notifications (default: true)

**Tip:** Channel names are without `#` (e.g. `customer-requests`).

### 3) Install and Run

**Quick Start:**
```bash
# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure tokens
cp .env.example .env
# Edit .env with your Slack tokens

# Run the buzzer
chmod +x scripts/run.sh
./scripts/run.sh
```

**Available Scripts:**
- `./scripts/run.sh` - Start the main buzzer app
- `./scripts/start-dashboard.sh` - Start web dashboard (http://localhost:5000)
- `./scripts/test-sound.sh` - Test audio configuration

**Web Dashboard:**
```bash
./scripts/start-dashboard.sh
# Open http://localhost:5000 in your browser
```

**Expected Output:**
```
🚀 Starting On-Call Buzzer...
📊 Stats tracking: enabled
🔊 Sound: Submarine (volume: 0.7)
⏰ Rate limit: 5 minutes
🎯 Keywords: @help, help me, urgent
Starting Socket Mode handler...
```

When a matching message arrives, you'll hear the sound and see a macOS notification.

### 4) Usage Examples

**Slack Commands:**
- `/buzzer-stats` - View alert statistics
- `/buzzer-sounds` - List available sounds

**Example Messages that Trigger Alerts:**
- "The TV is not working in humanities 229"
- "@help projector down in classroom 101"
- "urgent: room 205 needs assistance"
- "classroom 150 has technical issues"

### 5) Advanced Configuration

**Custom Sound Files:**
```bash
# Test different sounds
./scripts/test-sound.sh

# Use custom sound
echo 'SOUND_PATH=/path/to/your/sound.aiff' >> .env
```

**Regex Patterns for Complex Matching:**
```bash
# Match room numbers
KEYWORD_PATTERNS=classroom\s+\d+,room\s+\d+,humanities\s+\d+

# Match specific equipment issues
KEYWORD_PATTERNS=projector\s+(down|broken|not\s+working),tv\s+(down|broken|not\s+working)
```

**Auto-start on Login:**
```bash
# Add to macOS Login Items
sudo cp scripts/run.sh /usr/local/bin/oncall-buzzer
# Then add /usr/local/bin/oncall-buzzer to Login Items in System Preferences
```

### 6) Monitoring & Troubleshooting

**Web Dashboard Features:**
- Real-time alert statistics
- Configuration overview
- Auto-refresh capability
- Alert history tracking

**Common Issues:**
- **Missing scopes**: Re-add scopes and reinstall app to workspace
- **No sound**: Try different system sounds or check volume settings
- **Private channels**: Ensure app is invited to private channels
- **Rate limiting**: Adjust `RATE_LIMIT_MINUTES` if getting too many/few alerts

**Logs:**
- Check console output for connection status
- Use `LOG_LEVEL=DEBUG` for detailed logging
- Statistics saved to `alert_stats.json`

**Performance:**
- App uses minimal resources
- Socket Mode maintains persistent connection
- Statistics tracking is lightweight
- Rate limiting prevents alert spam


