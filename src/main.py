import os
import time
import logging
import threading
import subprocess
from typing import List, Optional, Set

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
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


# Configuration
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")  # xapp-...
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")  # xoxb-...
KEYWORDS = [kw.lower() for kw in get_env_list("KEYWORDS", "@help, help me, urgent")]  # case-insensitive match
CHANNEL_ALLOWLIST = set([c for c in get_env_list("CHANNEL_ALLOWLIST", "")])  # channel names or IDs (comma-separated)
CHANNEL_BLOCKLIST = set([c for c in get_env_list("CHANNEL_BLOCKLIST", "")])
IGNORE_BOTS = str_to_bool(os.getenv("IGNORE_BOTS", "true"))
SOUND_PATH = os.getenv("SOUND_PATH", "/System/Library/Sounds/Submarine.aiff")
BUZZ_REPEAT = int(os.getenv("BUZZ_REPEAT", "3"))
BUZZ_INTERVAL_SECONDS = float(os.getenv("BUZZ_INTERVAL_SECONDS", "0.6"))
SHOW_MAC_NOTIFICATION = str_to_bool(os.getenv("SHOW_MAC_NOTIFICATION", "true"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("oncall-buzzer")


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


class Buzzer:
	def __init__(self, sound_path: str, repeat: int, interval_seconds: float):
		self.sound_path = sound_path
		self.repeat = max(1, repeat)
		self.interval = max(0.05, interval_seconds)

	def _play_once(self):
		try:
			subprocess.run(["afplay", self.sound_path], check=False)
		except Exception as e:
			logger.error("Failed to play sound: %s", e)

	def buzz(self):
		def run():
			for i in range(self.repeat):
				self._play_once()
				if i < self.repeat - 1:
					time.sleep(self.interval)
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


def text_matches(text: str, keywords: List[str]) -> bool:
	lowered = text.lower()
	return any(kw in lowered for kw in keywords)


def build_app() -> App:
	app = App(token=SLACK_BOT_TOKEN)
	directory = ChannelDirectory(app)
	buzzer = Buzzer(SOUND_PATH, BUZZ_REPEAT, BUZZ_INTERVAL_SECONDS)

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
			if not text or not channel:
				return

			if not should_process(event):
				return

			# Channel allow/block
			if not directory.is_allowed(channel):
				return

			if text_matches(text, KEYWORDS):
				logger.info("Triggering buzzer for channel=%s text=%s", directory.name_for(channel) or channel, text[:200])
				buzzer.buzz()
				show_notification("On-Call Alert", text[:180])
		except Exception as e:
			logger.exception("Error handling message event: %s", e)

	return app


def main():
	if not SLACK_APP_TOKEN or not SLACK_BOT_TOKEN:
		logger.error("Missing SLACK_APP_TOKEN or SLACK_BOT_TOKEN. See README.md to set them.")
		raise SystemExit(1)

	app = build_app()
	logger.info("Starting Socket Mode handler...")
	handler = SocketModeHandler(app, SLACK_APP_TOKEN)
	handler.start()


if __name__ == "__main__":
	main()


