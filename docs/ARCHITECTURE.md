# LibreBeacon architecture and extension notes

## Data path

FreeStyle Libre sensor → official Libre phone application → Abbott LibreLinkUp sharing → community LibreLinkUp Home Assistant integration → Home Assistant REST API → LibreBeacon desktop program.

LibreBeacon does **not** read Windows Phone Link notifications or send Abbott credentials to the unofficial cloud API. It relies on two Home Assistant entities: glucose value (with units) and the source measurement timestamp. Home Assistant's own `last_updated` timestamp is not sufficient.

## Code map

- `librebeacon/core.py`: parse data and classify a reading as normal, low, critical-low or high. Reject stale or invalid readings before classifying.
- `librebeacon/homeassistant.py`: REST operations with bounded timeouts and blocked redirects. New Home Assistant commands live here.
- `librebeacon/settings.py`: per-user configuration and access-token retrieval from the OS credential system.
- `librebeacon/contacts.py`: destination validation, privacy-conscious contact messages and independent dispatch to `notify.*` or `script.*` destinations.
- `librebeacon/outputs.py`: optional Windows sound/speech.
- `librebeacon/app.py`: settings screens, polling, local displays and calls into the adapters.
- `tests/`: simulated readings and mock notifications. Tests do not send real messages.

## Adding another notification provider

Use the contact dispatcher as the extension point. A new route should offer three things: a clear human-readable destination label, validation without sending data, and an explicit send/test operation. Its result must say **request accepted**, **rejected** or **unknown**, never **delivered** unless the actual recipient has verifiably acknowledged it. Don't put API keys in the settings JSON or source; use OS credentials and limit what goes into logs.

A new provider should be independently optional. Failure must not halt local alarms or attempts to other enabled recipients. Test invalid credentials, network timeouts, duplicate contacts and message privacy. Prefer documented integrations — there is little value in writing and maintaining a second Meshtastic radio driver while Home Assistant already offers suitable notify entities.

## Future notes

- The desktop app stops monitoring during sleep or shutdown. An optional Home Assistant-side automation could provide continuity, but must be a *separate* configuration with explicit duplicate-event controls.
- Acknowledgements should require a deliberate action from the person. A transport ACK is not a human reply; this becomes particularly important with mesh radios.
- Safe troubleshooting logs would be useful. Strip sensor values, personal information, tokens and recipient identifiers by default.
- The Tk interface is straightforward to develop but accessibility verification with actual assistive technology remains unfinished. Don't equate larger fonts with a screen-reader-ready application.
- A connector interface for other CGM systems may be worthwhile, provided each source reports genuinely measured timestamps rather than guessed update times.

## Release discipline

Start from v1.9.3 for this development line. Increase versions for changes that genuinely exist, and list those changes in `CHANGELOG.md`. Don't invent intervening releases or claim hardware testing before it happens. The code is intended to welcome contributors who can extend a module without understanding the entire application.

## Version 4.0.6 modules

- `librebeacon/readiness.py`: button-led setup checklist. It checks saved choices only, never pretends to have tested a live service.
- `librebeacon/health.py`: the measurement clock and request failures. Keep the measured-at time separate from when a successful request returned.
- `librebeacon/delivery.py`: in-memory outcome labels for configured contact routes. An accepted request is not the same thing as a reply from another person.

The emergency recipient confirmation currently lives only in the Windows session. A future acknowledgement service would need authenticated, deliberate responses and a replay-resistant correlation ID. Don't assume a Meshtastic ACK, an email provider's 200 OK or a Home Assistant script returning successfully means the person has seen the alert. More work here before anybody should depend on it.
