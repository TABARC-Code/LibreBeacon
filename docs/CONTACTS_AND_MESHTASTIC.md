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
4. Open LibreBeacon → **5 · Emergency contacts**, press **Find Destinations**, then **Show Mesh Nodes**.
5. Choose a listed `notify.mesh_*` entity. Shared or unavailable targets that the app recognises are excluded. If no nodes appear, check the gateway and which nodes you have exposed in Home Assistant.
6. Give it a nickname, confirm the person agreed to alerts and press **Add Contact**. Check the displayed Home Assistant entity is an *individual* node when prompted. Entity names are not proof of identity.
7. Select the saved contact and press **Test Selected** while the person is next to their device. Ask them to reply by a separate route and record that reply if you want. If it doesn't arrive reliably, don't count on it.

Meshtastic notification entities are documented by the integration. Actual generated names can vary by setup. If you can't find one, check the integration before guessing its identifier. **Never assume packet transmission means that the intended person read the message.**

**Privacy note:** Mesh broadcasts can be read by members sharing a channel key. Prefer a specific individual destination and a protected network. LibreBeacon leaves exact glucose values out of contact messages unless you choose otherwise. Even the basic alert text reveals sensitive medical context, so get the recipient's permission and secure the devices.

## Two contacts are better than one message route — but still not dependable

You can add a phone destination for one trusted person and a Meshtastic node for another. LibreBeacon attempts each separately when a critical-low condition is freshly detected. It will not automatically retry forever or verify that either human has responded. The next useful improvement would be an acknowledgement mechanism which doesn't mistake a transport-level success for a human response.

**A Windows computer must be awake, the monitoring chain must work and the app must remain open** before any of this happens. Keep independent monitoring and a normal agreed emergency plan.

### What the node check actually proves

Very little about radio delivery. LibreBeacon checks the entity currently exists, excludes obvious channel/group labels and asks the operator to confirm its intended owner. It cannot read minds, verify node ownership or know whether a human has seen the message. Renaming a channel to look like a person defeats name filtering; check this in Home Assistant yourself.

A send is blocked if Home Assistant marks the destination unavailable or if it has changed to an obvious shared target since setup. Other contacts are still attempted independently. **No automatic acknowledgement or escalation is implemented.**
