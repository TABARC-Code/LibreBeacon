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

## Connection watchdog (v4.9.0)

The reply listener sends an authenticated Home Assistant WebSocket ping about every 20 seconds and requires the matching pong inside 10 seconds. A missing, wrong or late answer drops the listener. That prevents a **no reply** fallback from continuing while the connection is quietly dead. It is not a radio-delivery test. Disconnecting the gateway may still leave the Home Assistant WebSocket healthy; use the gateway diagnostics too.

My next check is actual Windows sleep and radio loss, recorded in [the field checklist](MESH_FIELD_TRIAL.md). Until then keep automatic backup switched off unless you understand the limitations.

## Queued messages and cancellation (v4.15.0)

I now check the approved contact list, emergency alert switches and live reply-listener state immediately before a queued backup asks Home Assistant to transmit. That matters when somebody cancels or withdraws consent while the node lookup is taking its time. A matching CANT also stops short if the listener has disconnected.

**Cancel Pending Backup** can revoke a queued request. It cannot recall one already accepted by Home Assistant, and an HTTP timeout isn't reliable evidence either way. Keep the official Libre alarm running independently. This check still needs a controlled trial with the actual gateway and receivers.

## Listener restarts

Queued Home Assistant events are bound to the listening session that received them. When a listener stops, its late replies and status messages cannot affect a subsequent session. An interrupted listener still cancels the pending automatic backup; restarting listening does not restore a missed fallback or replay an incident. A healthy Home Assistant socket is not proof of a delivered radio packet.

## Old reply events (v4.17.0)

A queued Home Assistant event more than two minutes old is not accepted as a fresh acknowledgement. This avoids treating a late event after reconnection as a new `OK` or `CANT` response. It can also miss a delayed genuine reply, which is another reason the radio backup cannot be relied on as a safety-critical alarm. Matching event metadata is not proof of the sender's identity or attendance.

## Reply tracking and gateway checks (v4.20.0)

A no-reply timer only starts after the first Home Assistant request is accepted **and** the reply tracker registers the incident with a confirmed gateway node number. If tracking fails, the optional backup remains held; an accepted notification request on its own is not sufficient. Before a queued backup transmission, LibreBeacon queries Home Assistant again and requires one verified, connected Meshtastic gateway. It checks current contact consent and listener state again after that query.

A connected gateway still does not establish end-to-end delivery or a known radio owner. This deliberately favours withholding an uncertain second message. Phone and email routes and the official Libre alarms are unaffected.

## Cancellation during a Home Assistant request (v4.21.0)

The backup distinguishes a queued request from a request already in flight. **Cancel Pending Backup** prevents a queued message from being requested. Once the application begins calling Home Assistant, cancellation is a stop request only; it cannot recall what Home Assistant or the radio may already have received. The display says the outcome is unknown until a Home Assistant response arrives. An accepted response is still not a radio receipt; a timeout does not establish that the message never went out.

The automatic fallback never retries the same incident. If a matching `OK` arrives while the backup is queued but before the Home Assistant request, the queued backup is held instead.
