# Meshtastic messages and tests

## What the radio contact does

1. Set up the Meshtastic integration in Home Assistant. Make sure a single person has agreed to receive messages.
2. Open LibreBeacon **Emergency contacts**. Press **Find Destinations**, **Show Mesh Nodes**, then confirm the person's actual node ID using a separate contact method.
3. Add and save that contact. **Preview Mesh Messages** shows the wording without transmitting anything.
4. Select the recipient and press **Test Selected**. The confirmation dialogue displays the exact test content and requires a deliberate Yes.
5. Ask the person to confirm through an independent channel. Home Assistant accepting the request is not evidence of delivery.

## Automatic supplementary messages

Automatic messages are disabled by default. They require consent, an explicitly configured critical-low threshold and an enabled recipient. The template is shorter than ordinary email notifications and has a unique `LB-` reference. It does not include glucose numbers, names, home addresses or location unless a privacy option explicitly adds the glucose value. Messages are limited to **180 UTF-8 bytes** to leave room under Meshtastic's usual application payload budget.

One alert produces one request per configured contact. There is no automatic resend or escalation. The official Libre alarm and existing assistance arrangements remain essential.

## Things to revisit

- The reference is only for local diagnostics. I don't treat it as a signed acknowledgement; that needs recipient-node checks, expiry and replay protection in the next stage.
- Radio packets aren't reliable enough to justify endlessly repeating them. Need field measurements and a proper airtime budget before even considering bounded retries.
- The node and gateway checks currently don't prove which gateway carries the outgoing packet. Fix binding before presenting a green 'delivery ready' badge.
- Some users need a large message preview, some need spoken confirmation. Future interface work can expose both without changing the sender.

The Meshtastic integration supplies the actual radio notifications via Home Assistant. Contact nodes are checked before each send. No public channel fallback is used, and a successful HTTP response is **not a human receipt**.

Reference: https://github.com/meshtastic/home-assistant and https://www.home-assistant.io/actions/notify.send_message/.
