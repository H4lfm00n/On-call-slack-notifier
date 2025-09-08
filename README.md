## On-call Slack Notifier (macOS)

A small local Socket Mode listener that plays a loud alert and macOS notification when your Slack user or keywords are mentioned.

### 1) Create a Slack App
- Enable Socket Mode
- Enable Event Subscriptions (via Socket Mode)
- Add Bot Token Scopes: `app_mentions:read`, `channels:history`, `groups:history`, `im:history`, `mpim:history`
- Install the app to your workspace and copy:
  - App Token (starts with `xapp-`)
  - Bot Token (starts with `xoxb-`)
  - Signing Secret
  - Optional: Team ID (find in Slack → About → Workspace name → Team ID)

### 2) Configure environment
Create `.env` in the project root:

```
SLACK_APP_TOKEN=xapp-...
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
ALERT_KEYWORDS=@your_handle,urgent,emergency
ALERT_SOUND=Submarine
SLACK_TEAM_ID=T01234567
```

### 3) Run

```
npm start
```

You'll see: "On-call Slack notifier is running in Socket Mode".

### Notes
- Alerts:
  - Triggers on `app_mention` and any message containing `ALERT_KEYWORDS` (comma-separated)
  - Plays a loud macOS beep and a notification
  - Attempts to open the Slack channel/thread via deep link
- macOS permissions: grant Terminal/Node access to Notifications and Accessibility if prompted.
- Auto-start on login: use `launchd` or create a simple Automator app that runs `npm start` in this folder.

### Local test without Slack

Run a notification + sound test locally:

```
npm run test:alert
```

### Auto-start on login (launchd)

1) Edit the plist path if needed: `launchd/com.oncall.slacknotifier.plist` (ProgramArguments path points to this folder; adjust Node/npm path if using nvm)
2) Copy plist to LaunchAgents:

```
mkdir -p ~/Library/LaunchAgents
cp launchd/com.oncall.slacknotifier.plist ~/Library/LaunchAgents/
```

3) Load and start now:

```
launchctl load ~/Library/LaunchAgents/com.oncall.slacknotifier.plist
launchctl start com.oncall.slacknotifier
```

4) Check logs if needed:

```
tail -f ~/Library/Logs/com.oncall.slacknotifier.out.log ~/Library/Logs/com.oncall.slacknotifier.err.log
```

5) To unload/stop:

```
launchctl unload ~/Library/LaunchAgents/com.oncall.slacknotifier.plist
```



