# Optional Meshtastic backup contact

This is a small staged contact route, not a replacement medical alarm. Home Assistant remains the gateway.

## Configure

1. Add and test two **individual** Meshtastic notification destinations in Emergency contacts. Both must be enabled, consented and pinned to their node IDs. Don't use a channel entity.
2. Open **Set Up Meshtastic Replies**, save the real gateway node ID, and start listening. This must stay connected for a no-reply timeout.
3. Open **Set Up Backup Contact**. Pick the first node, second node and a 2–20-minute delay. Tick the backup option and save. Both must be in the existing approved contact list.
4. Enable ordinary critical-low contact alerts separately, with an agreed threshold. Keep the official Libre app's alarms active.
5. Select **Cancel Pending Backup** to stop a waiting follow-up. This won't cancel an already-sent request or resolve a glucose alert.

## What actually happens

- For a genuine eligible critical-low event, LibreBeacon requests the **first** chosen mesh node and independently attempts other ordinary phone and email contacts. No other mesh contact is sent at that point.
- If Home Assistant accepts the first request *and* the reply listener is running, the fallback timer starts. An observed matching `OK` radio reply stops the fallback. A matching `CANT` can send the second message immediately. No reply can send the second after the chosen delay, **only** if the listener remained connected.
- No reply is not proof that a person is absent or needs help. An accepted request is not a delivery receipt. A matching response is not proof of assistance.
- One backup attempt, no repeats, and no automatic re-arming in the current Windows session. A failed request remains failed. No message is sent after a reboot or while the program is closed.
- Stop listening, lose the connection, change settings or forget the HA token: pending timeouts stop. No one gets an invented status.

## Limitations and thoughts

Everything is in memory. This is deliberately conservative but it means no unattended escalation. The next iteration should test recipient identity changes, Windows sleep, queue timing and real radios. The Windows interface still needs a screen-reader pass.

I considered falling back to a channel broadcast when the recipient vanished. No. That would send private information to people who never consented.
