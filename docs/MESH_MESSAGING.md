# Meshtastic messages and tests

## What the radio contact does

1. Set up the Meshtastic integration in Home Assistant. Make sure a single person has agreed to receive messages.
2. Open LibreBeacon **Emergency contacts**. Press **Find Destinations**, **Show Mesh Nodes**, then confirm the person's actual node ID using a separate contact method.
3. Add and save that contact. **Preview Mesh Messages** shows the wording without transmitting anything.
4. Select the recipient and press **Test Selected**. The confirmation dialogue displays the exact test content and requires a deliberate Yes.
5. Ask the person to confirm through an independent channel. Home Assistant accepting the request is not evidence of delivery.

## Automatic supplementary messages

Automatic messages are disabled by default. They require consent, an explicitly configured critical-low threshold and an enabled recipient. The template is shorter than ordinary email notifications and has a unique `LB-` reference. It does not include glucose numbers, names, home addresses or location unless a privacy option explicitly adds the glucose value. Messages are limited to **180 UTF-8 bytes** to leave room under Meshtastic's usual application payload budget.

There are no automatic retries. If the optional, separately consented backup feature is enabled, one nominated second Meshtastic recipient may be contacted after a configured delay or a matching `CANT` reply. Other phone and email routes remain independent. The official Libre alarm and existing assistance arrangements remain essential.

## Reply tracking and expiry

When the optional Home Assistant reply listener is running, LibreBeacon will only recognise a direct `LB-...` reference followed by `OK` or `CANT`. It compares the sender, intended gateway, individual destination and incident reference against the saved request. A channel message is not an acknowledgement. The Home Assistant event must arrive within two minutes of its recorded event time and while the incident's 30-minute reply window remains open.

This is **metadata matching, not cryptographic proof of the sender or human assistance**. Radio node numbers can be impersonated or misconfigured. A recognised reply does not mean the nominated person has read it, attended or provided help. An independently confirmed phone call remains different evidence.

The app keeps reply history in memory. Records stay readable for one hour after the reply window closes and are cleaned up on subsequent tracker activity; the tracker refuses to grow past 512 recent incidents. Restarting LibreBeacon clears the records. A late message might be genuine but is ignored by the automatic decision logic. Don't infer that the person did not answer.

## Things still to test

- Real-radio loss, duplicate packets, clocks that disagree between Windows and Home Assistant, and actual sender identity across gateway replacements.
- Recipient receipt and response timing with two consenting devices in different locations, without generating a false medical alert.
- Keyboard, magnification and screen-reader operation on a Windows machine.
- Whether a separate, always-on Home Assistant component would improve reliability without causing duplicate alerts.

The Meshtastic integration supplies the actual radio notifications via Home Assistant. Contact nodes are checked before each send. No public channel fallback is used, and a successful HTTP response is **not a human receipt**.

Reference: https://github.com/meshtastic/home-assistant and https://www.home-assistant.io/actions/notify.send_message/.
