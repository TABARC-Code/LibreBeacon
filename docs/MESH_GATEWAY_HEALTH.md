# Meshtastic gateway health — what the Windows button actually checks

**Introduced in LibreBeacon v4.5.0.** Open **Start Here → Check Meshtastic Gateway Status** or use the same button on Emergency contacts. You need Home Assistant and its Meshtastic integration configured first.

1. Choose **Check Meshtastic Gateway Status**. It reads Home Assistant's existing states; it does not send a radio test or contact a receiver.
2. Read the status window. **HA reports connected** only means the integration reported a connection, not that a carer will hear a radio message.
3. If the gateway is missing or disconnected, open **Settings → Devices & services → Meshtastic** in Home Assistant. Check gateway power, Bluetooth, USB or TCP connection as appropriate.
4. Where the Meshtastic integration exposes *Last Heard* timestamp sensors for a saved recipient, LibreBeacon reports their age. An ambiguous, absent, future or old timestamp is not a successful connection test.
5. Use the independent, clearly labelled **Test Selected** contact action with consent, and ask the person to confirm they saw it. That is a separate test and sends a real message.

## What we know, what we don't

| Input | Meaning | Limits |
| --- | --- | --- |
| `meshtastic.*` entity tagged as gateway | Integration’s gateway entity | Entity state is not proof of current LoRa reachability |
| `Connected` / `Disconnected` | What Home Assistant currently reports | Not a radio packet receipt |
| Entity last-changed timestamp | Time HA state changed | **Not** a heartbeat; don't present it as one |
| Last-heard node timestamp sensor | Time the integration says a packet was heard | May come through another gateway; not proof of outgoing delivery |
| Home Assistant notify action success | Request accepted by HA | Neither a radio receipt nor a human reply |

Don't automatically block every mesh recipient on a missing gateway entity yet. The notify integration can expose nodes from multiple gateways, and this version does not have a trustworthy gateway-to-notify binding. Individual-node checks remain mandatory, and a missing or clearly disconnected gateway must be shown for diagnosis. A future implementation can gate delivery only once we can prove the mapping.

## Next checks for contributors

- Verify against a real Home Assistant instance: ensure the installed Meshtastic version exposes the expected `device_class` and state values. If it doesn't, show the type as unverified until the registry can be queried reliably.
- Try two gateways, pull one USB cable, restart Home Assistant, and check the status changes. Don't use a ten-minute-old page as a current connection test.
- Compare `sensor.meshtastic_*_<node_id>_node_last_heard` across firmware versions. Names may change. Registry metadata is the better long-term answer.
- Make the window usable with 200% Windows display scaling, Narrator and keyboard-only navigation. A bigger font isn't an accessibility audit.
- Keep all health checks read-only. No raw radio keys, private medical values or provider responses in logs. We can chase bugs without publishing someone's personal data.

The design roadmap is in [MESHTASTIC_DESIGN_PLAN.md](MESHTASTIC_DESIGN_PLAN.md). The main Meshtastic integration is at https://github.com/meshtastic/home-assistant.
