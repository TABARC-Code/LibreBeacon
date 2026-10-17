# Contacts, messages and Meshtastic

A contact destination is an already available Home Assistant action. LibreBeacon doesn't maintain a phone book full of sensitive details, and it doesn't need access to your email password or your mobile contacts.

## Phone notification

Set up the [Home Assistant mobile companion app](https://companion.home-assistant.io/) and enable its notifications. If it exposes a `notify.*` entity, use **Find Destinations** in LibreBeacon, add a nickname, pick the entity and send a labelled test. If your installation uses only a legacy notification *action* rather than a `notify.*` entity, create a Home Assistant script for that action and select the script instead.

## Email

Configure an email-capable notification action or a script in Home Assistant using its visual configuration wherever supported. Use a dedicated script with a specific intended recipient; don't use a generic action that forwards to unknown contacts. When finished, select the script in LibreBeacon. It is **not** a one-click SMTP account wizard yet, because handling provider passwords, MFA and delivery confirmations securely needs additional work.

## Meshtastic

Meshtastic can relay messages through compatible radio nodes without mobile signal, but a radio network is not guaranteed to be present or reachable. It isn't an emergency-service connection.

1. Set up and test the person's Meshtastic devices with the official Meshtastic phone or desktop application first.
2. Install the [Meshtastic Home Assistant integration](https://github.com/meshtastic/home-assistant) and connect a suitable gateway to Home Assistant (TCP, serial or supported Bluetooth arrangements).
3. In the Meshtastic integration, expose the intended **individual recipient node** as a notification target, not a channel broadcast.
4. Open LibreBeacon → **5 · Emergency contacts → Find Destinations → Show Mesh Nodes**.
5. Select the matching `notify.mesh_*` entity, give it a human-readable nickname, confirm consent and add it.
6. Test it with the other person standing at their device. If it doesn't arrive consistently, don't count on it.

Meshtastic notification entities are documented by the integration. Actual generated names can vary by setup. If you can't find one, check the integration before guessing its identifier. **Never assume packet transmission means that the intended person read the message.**

**Privacy note:** Mesh broadcasts can be read by members sharing a channel key. Prefer a specific individual destination and a protected network. LibreBeacon leaves exact glucose values out of contact messages unless you choose otherwise. Even the basic alert text reveals sensitive medical context, so get the recipient's permission and secure the devices.

## Two contacts are better than one message route — but still not dependable

You can add a phone destination for one trusted person and a Meshtastic node for another. LibreBeacon attempts each separately when a critical-low condition is freshly detected. It will not automatically retry forever or verify that either human has responded. The next useful improvement would be an acknowledgement mechanism which doesn't mistake a transport-level success for a human response.

**A Windows computer must be awake, the monitoring chain must work and the app must remain open** before any of this happens. Keep independent monitoring and a normal agreed emergency plan.
