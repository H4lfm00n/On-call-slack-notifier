import os
import re
import time
import json
import logging
import threading
import subprocess
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Set, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError, SlackClientError
from dotenv import load_dotenv


# Load environment variables from .env if present
load_dotenv()


def get_env_list(key: str, default: Optional[str] = None) -> List[str]:
	raw = os.getenv(key, default or "")
	return [item.strip() for item in raw.split(",") if item.strip()]


def str_to_bool(value: Optional[str], default: bool = False) -> bool:
	if value is None:
		return default
	return value.strip().lower() in {"1", "true", "t", "y", "yes"}


@dataclass
class AlertStats:
    total_alerts: int = 0
    last_alert_time: Optional[datetime] = None
    alerts_today: int = 0
    last_reset_date: str = ""

@dataclass
class SoundConfig:
    path: str
    volume: float = 0.7
    repeat: int = 3
    interval: float = 0.6

# Configuration
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")  # xapp-...
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")  # xoxb-...
KEYWORDS = [kw.lower() for kw in get_env_list("KEYWORDS", "@help, help me, urgent")]  # case-insensitive match
KEYWORD_PATTERNS = get_env_list("KEYWORD_PATTERNS", "")  # regex patterns
CHANNEL_ALLOWLIST = set([c for c in get_env_list("CHANNEL_ALLOWLIST", "")])  # channel names or IDs (comma-separated)
CHANNEL_BLOCKLIST = set([c for c in get_env_list("CHANNEL_BLOCKLIST", "")])
IGNORE_BOTS = str_to_bool(os.getenv("IGNORE_BOTS", "true"))
SOUND_PATH = os.getenv("SOUND_PATH", "/System/Library/Sounds/Submarine.aiff")
SOUND_VOLUME = float(os.getenv("SOUND_VOLUME", "0.7"))
BUZZ_REPEAT = int(os.getenv("BUZZ_REPEAT", "3"))
BUZZ_INTERVAL_SECONDS = float(os.getenv("BUZZ_INTERVAL_SECONDS", "0.6"))
SHOW_MAC_NOTIFICATION = str_to_bool(os.getenv("SHOW_MAC_NOTIFICATION", "true"))
RATE_LIMIT_MINUTES = int(os.getenv("RATE_LIMIT_MINUTES", "5"))  # cooldown between alerts
ENABLE_STATS = str_to_bool(os.getenv("ENABLE_STATS", "true"))
STATS_FILE = os.getenv("STATS_FILE", "alert_stats.json")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("oncall-buzzer")

# Global stats
alert_stats = AlertStats()


class ChannelDirectory:
	"""Caches Slack channel id<->name lookups for allow/block checks."""

	def __init__(self, app: App):
		self.app = app
		self.id_to_name = {}
		self.name_to_id = {}
		self._initialized = False

	def ensure_loaded(self):
		if self._initialized:
			return
		try:
			cursor = None
			while True:
				resp = self.app.client.conversations_list(limit=1000, cursor=cursor, types="public_channel,private_channel")
				for ch in resp.get("channels", []):
					cid = ch.get("id")
					name = ch.get("name")
					if cid and name:
						self.id_to_name[cid] = name
						self.name_to_id[name] = cid
				cursor = resp.get("response_metadata", {}).get("next_cursor")
				if not cursor:
					break
			self._initialized = True
			logger.info("Loaded %d channels into cache", len(self.id_to_name))
		except SlackApiError as e:
			logger.warning("Failed to load channel directory: %s", e)

	def name_for(self, channel_id: str) -> Optional[str]:
		self.ensure_loaded()
		return self.id_to_name.get(channel_id)

	def id_for(self, channel_name: str) -> Optional[str]:
		self.ensure_loaded()
		return self.name_to_id.get(channel_name)

	def is_allowed(self, channel_id: str) -> bool:
		# If allowlist is empty, allow all (unless blocked)
		if CHANNEL_ALLOWLIST:
			# Allowlist entries can be names or IDs
			name = self.name_for(channel_id) or ""
			if channel_id not in CHANNEL_ALLOWLIST and name not in CHANNEL_ALLOWLIST:
				return False
		# Blocklist check
		if CHANNEL_BLOCKLIST:
			name = self.name_for(channel_id) or ""
			if channel_id in CHANNEL_BLOCKLIST or name in CHANNEL_BLOCKLIST:
				return False
		return True


class StatsManager:
	def __init__(self, stats_file: str):
		self.stats_file = Path(stats_file)
		self.load_stats()

	def load_stats(self):
		if self.stats_file.exists():
			try:
				with open(self.stats_file, 'r') as f:
					data = json.load(f)
					alert_stats.total_alerts = data.get('total_alerts', 0)
					alert_stats.alerts_today = data.get('alerts_today', 0)
					alert_stats.last_reset_date = data.get('last_reset_date', "")
					if data.get('last_alert_time'):
						alert_stats.last_alert_time = datetime.fromisoformat(data['last_alert_time'])
			except Exception as e:
				logger.warning("Failed to load stats: %s", e)

	def save_stats(self):
		try:
			data = {
				'total_alerts': alert_stats.total_alerts,
				'alerts_today': alert_stats.alerts_today,
				'last_reset_date': alert_stats.last_reset_date,
				'last_alert_time': alert_stats.last_alert_time.isoformat() if alert_stats.last_alert_time else None
			}
			with open(self.stats_file, 'w') as f:
				json.dump(data, f, indent=2)
		except Exception as e:
			logger.warning("Failed to save stats: %s", e)

	def record_alert(self):
		now = datetime.now()
		today = now.date().isoformat()
		
		# Reset daily counter if new day
		if alert_stats.last_reset_date != today:
			alert_stats.alerts_today = 0
			alert_stats.last_reset_date = today
		
		alert_stats.total_alerts += 1
		alert_stats.alerts_today += 1
		alert_stats.last_alert_time = now
		self.save_stats()

	def is_rate_limited(self) -> bool:
		if not alert_stats.last_alert_time or RATE_LIMIT_MINUTES <= 0:
			return False
		cooldown = timedelta(minutes=RATE_LIMIT_MINUTES)
		return datetime.now() - alert_stats.last_alert_time < cooldown


class Buzzer:
	def __init__(self, sound_config: SoundConfig):
		self.sound_config = sound_config
		self.is_playing = False
		self._lock = threading.Lock()

	def _play_once(self):
		try:
			# Use osascript to control volume and play sound
			volume_script = f'set volume output volume {int(self.sound_config.volume * 100)}'
			play_script = f'do shell script "afplay \\"{self.sound_config.path}\\""'
			subprocess.run(["osascript", "-e", volume_script, "-e", play_script], check=False)
		except Exception as e:
			logger.error("Failed to play sound: %s", e)

	def buzz(self):
		with self._lock:
			if self.is_playing:
				return
			self.is_playing = True

		def run():
			try:
				for i in range(self.sound_config.repeat):
					self._play_once()
					if i < self.sound_config.repeat - 1:
						time.sleep(self.sound_config.interval)
			finally:
				with self._lock:
					self.is_playing = False
		
		threading.Thread(target=run, daemon=True).start()


def show_notification(title: str, message: str):
	if not SHOW_MAC_NOTIFICATION:
		return
	try:
		# Use AppleScript notification for macOS
		script = f'display notification "{message}" with title "{title}"'
		subprocess.run(["osascript", "-e", script], check=False)
	except Exception as e:
		logger.debug("Failed to show macOS notification: %s", e)


def text_matches(text: str, keywords: List[str], patterns: List[str]) -> bool:
	lowered = text.lower()
	
	# Check simple keyword matches
	if any(kw in lowered for kw in keywords):
		return True
	
	# Check regex patterns
	for pattern in patterns:
		try:
			if re.search(pattern, text, re.IGNORECASE):
				return True
		except re.error as e:
			logger.warning("Invalid regex pattern '%s': %s", pattern, e)
	
	return False


def get_available_sounds() -> List[str]:
	"""Get list of available macOS system sounds."""
	sound_paths = [
		"/System/Library/Sounds/Submarine.aiff",
		"/System/Library/Sounds/Glass.aiff", 
		"/System/Library/Sounds/Ping.aiff",
		"/System/Library/Sounds/Pop.aiff",
		"/System/Library/Sounds/Purr.aiff",
		"/System/Library/Sounds/Sosumi.aiff",
		"/System/Library/Sounds/Tink.aiff",
		"/System/Library/Sounds/Basso.aiff",
		"/System/Library/Sounds/Blow.aiff",
		"/System/Library/Sounds/Bottle.aiff",
		"/System/Library/Sounds/Frog.aiff",
		"/System/Library/Sounds/Funk.aiff",
		"/System/Library/Sounds/Hero.aiff",
		"/System/Library/Sounds/Morse.aiff",
		"/System/Library/Sounds/Ping.aiff",
		"/System/Library/Sounds/Popcorn.aiff",
		"/System/Library/Sounds/Sonar.aiff",
		"/System/Library/Sounds/Strum.aiff"
	]
	return [path for path in sound_paths if Path(path).exists()]


def build_app() -> App:
	app = App(token=SLACK_BOT_TOKEN)
	directory = ChannelDirectory(app)
	
	# Initialize sound config and buzzer
	sound_config = SoundConfig(
		path=SOUND_PATH,
		volume=SOUND_VOLUME,
		repeat=BUZZ_REPEAT,
		interval=BUZZ_INTERVAL_SECONDS
	)
	buzzer = Buzzer(sound_config)
	
	# Initialize stats manager
	stats_manager = StatsManager(STATS_FILE) if ENABLE_STATS else None

	# Keep a small LRU-like set to avoid buzzing multiple times for the same event
	recent_event_ids: Set[str] = set()
	MAX_RECENT = 500

	def should_process(event: dict) -> bool:
		# Dedup by event_id if available
		event_id = event.get("client_msg_id") or event.get("ts")
		if event_id:
			if event_id in recent_event_ids:
				return False
			recent_event_ids.add(event_id)
			if len(recent_event_ids) > MAX_RECENT:
				# Drop oldest arbitrarily by recreating set from last N (not strictly ordered)
				recent_event_ids.clear()
				recent_event_ids.add(event_id)
		# Ignore bot messages when configured
		if IGNORE_BOTS and (event.get("subtype") == "bot_message" or event.get("bot_id")):
			return False
		return True

	@app.event("message")
	def handle_message_events(body, logger: logging.Logger, event, say):  # type: ignore
		try:
			channel = event.get("channel")
			text = event.get("text") or ""
			user = event.get("user", "unknown")
			
			if not text or not channel:
				return

			if not should_process(event):
				return

			# Channel allow/block
			if not directory.is_allowed(channel):
				return

			# Check for rate limiting
			if stats_manager and stats_manager.is_rate_limited():
				logger.debug("Rate limited, skipping alert")
				return

			if text_matches(text, KEYWORDS, KEYWORD_PATTERNS):
				channel_name = directory.name_for(channel) or channel
				logger.info("🚨 ALERT: channel=%s user=%s text=%s", channel_name, user, text[:200])
				
				# Record stats
				if stats_manager:
					stats_manager.record_alert()
				
				# Trigger buzzer and notification
				buzzer.buzz()
				show_notification("🚨 On-Call Alert", f"Channel: {channel_name}\n{text[:180]}")
				
		except Exception as e:
			logger.exception("Error handling message event: %s", e)

	# Add health check endpoint for monitoring
	@app.command("/buzzer-stats")
	def handle_stats_command(ack, respond):
		ack()
		if not stats_manager:
			respond("Stats tracking is disabled")
			return
		
		stats_text = f"""📊 Buzzer Stats:
• Total alerts: {alert_stats.total_alerts}
• Alerts today: {alert_stats.alerts_today}
• Last alert: {alert_stats.last_alert_time.strftime('%Y-%m-%d %H:%M:%S') if alert_stats.last_alert_time else 'Never'}
• Rate limit: {RATE_LIMIT_MINUTES} minutes"""
		respond(stats_text)

	@app.command("/buzzer-sounds")
	def handle_sounds_command(ack, respond):
		ack()
		sounds = get_available_sounds()
		sound_list = "\n".join([f"• {Path(s).stem}" for s in sounds[:10]])
		respond(f"🔊 Available sounds:\n{sound_list}\n\nCurrent: {Path(SOUND_PATH).stem}")

	return app


def signal_handler(signum, frame):
	logger.info("Received signal %d, shutting down gracefully...", signum)
	sys.exit(0)


def main():
	if not SLACK_APP_TOKEN or not SLACK_BOT_TOKEN:
		logger.error("Missing SLACK_APP_TOKEN or SLACK_BOT_TOKEN. See README.md to set them.")
		raise SystemExit(1)

	# Set up signal handlers for graceful shutdown
	signal.signal(signal.SIGINT, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)

	# Validate sound file exists
	if not Path(SOUND_PATH).exists():
		logger.warning("Sound file not found: %s", SOUND_PATH)
		available = get_available_sounds()
		if available:
			logger.info("Available sounds: %s", ", ".join([Path(s).stem for s in available[:5]]))

	app = build_app()
	logger.info("🚀 Starting On-Call Buzzer...")
	logger.info("📊 Stats tracking: %s", "enabled" if ENABLE_STATS else "disabled")
	logger.info("🔊 Sound: %s (volume: %.1f)", Path(SOUND_PATH).stem, SOUND_VOLUME)
	logger.info("⏰ Rate limit: %d minutes", RATE_LIMIT_MINUTES)
	logger.info("🎯 Keywords: %s", ", ".join(KEYWORDS))
	if KEYWORD_PATTERNS:
		logger.info("🔍 Patterns: %s", ", ".join(KEYWORD_PATTERNS))
	
	try:
		handler = SocketModeHandler(app, SLACK_APP_TOKEN)
		handler.start()
	except KeyboardInterrupt:
		logger.info("Shutting down...")
	except Exception as e:
		logger.error("Fatal error: %s", e)
		raise


if __name__ == "__main__":
	main()


