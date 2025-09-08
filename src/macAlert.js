import notifier from 'node-notifier';
import { exec } from 'node:child_process';
import { promisify } from 'node:util';

const execAsync = promisify(exec);

const DEFAULT_SOUND = process.env.ALERT_SOUND || 'Submarine';

export async function triggerMacAlert({ title, message, channel, ts }) {
  const subtitle = channel ? `Channel: ${channel}` : undefined;
  notifier.notify({
    title: title || 'On-Call Alert',
    message: message || 'You have a new on-call mention',
    subtitle,
    sound: DEFAULT_SOUND,
    wait: false,
  });

  // Extra loud beep using osascript
  try {
    await execAsync(`osascript -e 'beep 5'`);
  } catch {}

  // Flash Terminal icon via bouncing dock (requires focus switch workaround)
  try {
    await execAsync(`osascript -e 'tell application "System Events" to set frontmost of process "Terminal" to true'`);
  } catch {}

  // Optionally open Slack thread with optional team id
  if (channel && ts) {
    const teamId = process.env.SLACK_TEAM_ID || '';
    const teamParam = teamId ? `team=${encodeURIComponent(teamId)}&` : '';
    const slackDeepLink = `slack://channel?${teamParam}id=${encodeURIComponent(channel)}&message=${encodeURIComponent(ts)}`;
    try {
      await execAsync(`open "${slackDeepLink}"`);
    } catch {}
  }
}


