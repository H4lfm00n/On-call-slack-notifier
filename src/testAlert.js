import 'dotenv/config';
import { triggerMacAlert } from './macAlert.js';

await triggerMacAlert({
  title: 'Test On-Call Alert',
  message: 'This is a local test of the alert system',
});

// eslint-disable-next-line no-console
console.log('Test alert triggered. If you did not hear a sound, check Notifications settings and ALERT_SOUND env.');



