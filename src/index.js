import 'dotenv/config';
import { App, LogLevel } from '@slack/bolt';
import { triggerMacAlert } from './macAlert.js';

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  appToken: process.env.SLACK_APP_TOKEN,
  socketMode: true,
  logLevel: LogLevel.INFO,
});

const alertKeywords = (process.env.ALERT_KEYWORDS || '').split(',').map(k => k.trim()).filter(Boolean);

function shouldAlert(text, mentions) {
  const lower = (text || '').toLowerCase();
  if (mentions && mentions.length > 0) return true;
  return alertKeywords.some(k => lower.includes(k.toLowerCase()));
}

app.event('app_mention', async ({ event, client, logger }) => {
  try {
    const channel = event.channel;
    const text = event.text || '';

    logger.info(`Mention in ${channel}: ${text}`);

    if (shouldAlert(text, ['mention'])) {
      await triggerMacAlert({
        title: 'On-Call Alert',
        message: text || 'You were mentioned',
        channel,
        ts: event.ts,
      });
    }
  } catch (error) {
    logger.error(error);
  }
});

app.message(async ({ message, say, logger }) => {
  try {
    if (!('text' in message)) return;
    const text = message.text || '';

    if (shouldAlert(text, [])) {
      await triggerMacAlert({
        title: 'On-Call Alert',
        message: text,
        channel: message.channel,
        ts: message.ts,
      });
    }
  } catch (error) {
    logger.error(error);
  }
});

(async () => {
  await app.start();
  // eslint-disable-next-line no-console
  console.log('On-call Slack notifier is running in Socket Mode');
})();


