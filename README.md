# LibreBeacon

**Accessible glucose notifications for Windows and Home Assistant.**  
Current version: **4.0.6** · experimental community prototype · MIT licence

LibreBeacon adds a second, optional layer of accessibility around existing FreeStyle Libre monitoring. Rather than interfere with the sensor, it reads the glucose and *actual measurement time* from Home Assistant, where a LibreLinkUp integration is already installed. It can show larger readings, play local sounds, speak a warning and trigger compatible lights or contact messages.

The emergency contact screen is designed around buttons rather than code. Add a name, choose a Home Assistant notification destination, test it, and decide whether automatic contact messages should be enabled. Supported destinations include an individual **Meshtastic** node if its Home Assistant integration exposes a `notify.*` entity.

> **Safety first:** This is NOT a medical device, a reliable emergency alarm or an alternative to Libre's official monitoring and warnings. It has not been clinically evaluated or fully tested on Windows with live Libre equipment. It may fail silently, miss readings or lose connectivity. Do not use it for treatment decisions or as your only route to help. Keep all approved glucose alarms active. See [DISCLAIMER.md](DISCLAIMER.md).

## Start on Windows

1. Install [Python 3.11 or later](https://www.python.org/downloads/windows/) if your computer doesn't already have it. During installation ensure the Windows Python Launcher is available.
2. Extract the project ZIP into a normal folder such as **Documents → LibreBeacon**.
3. Double-click **`INSTALL-WINDOWS.bat`**. It creates an isolated local installation and installs the necessary dependency. Internet access is required for this first step.
4. Double-click **`run-windows.bat`** to open LibreBeacon.
5. Open **Start Here** and use the large numbered setup buttons. Return there and choose **Check Saved Setup** to see what still needs configuring.
6. Follow the numbered tabs. No terminal commands or code editing are required inside the app, although Home Assistant and its integrations must already be configured.

There is also a developer build script and a GitHub Actions recipe for an unsigned Windows `.exe`. **No tested `.exe` is included in this ZIP.** See [the complete setup guide](docs/SETUP.md).

## What you can configure

| Tab | Buttons and options |
| --- | --- |
| Dashboard | Check reading and connection health, open setup, switch supplementary alerts on/off |
| Start Here | Step-by-step setup buttons and saved-configuration checklist |
| Connection | Save connection, test connection, open Home Assistant |
| Sensors | Find glucose sensors, select measurement timestamp, test reading |
| Accessibility | Test sound, spoken message, visual notice; larger text |
| Alerts | Select and test a Home Assistant lighting script; older contact-script support |
| Emergency contacts | Find destinations, Show Mesh Nodes, Add, Remove, Test Selected, Record Recipient Reply, Save, Help |
| Alert rules | Set ordinary low and high thresholds, optional critical-low threshold, age and check interval |

**Contact sending is off by default.** Consent is required for every recipient and for enabling automatic critical-low messages. Thresholds deliberately have no default. A configured critical-low alert is distinct from an ordinary low alert, so a reading moving into the critical band can generate an additional event even during an existing low episode. Multiple contact requests are attempted independently; a failed request to one destination need not stop another. That still doesn't confirm actual delivery.

By default, emergency contact messages do **not** include an exact glucose value. There is a separate, clearly labelled privacy option to include it. Messages are only sent to explicitly configured destinations, not automatically to everyone on a mesh network.

## What does and doesn't work yet

**Implemented in source and checked with automated tests:** Home Assistant REST client, secure local token-store integration, desktop setup screens, sensor selection, measurement timestamp checks, ordinary/critical-low detection, duplicate suppression, sound, Windows speech, desktop visual notice, Home Assistant scripts, and opt-in notification targets. A Linux virtual-display smoke test can instantiate the desktop interface.

**Not established:** real Abbott/Libre end-to-end operation, native Windows testing, Windows installer/executable compatibility, successful delivery by actual phone/email/Meshtastic devices, clinical threshold suitability, and comprehensive keyboard/screen-reader accessibility. The application only runs while the Windows app is open and awake; its contact alerts are not a reliable unattended safety service. The API returning success means a request was accepted, not that a person received it.

Windows Phone Link may mirror the official Libre phone notifications, but LibreBeacon does not read or scrape Phone Link. Data comes through Home Assistant instead. No Abbott login credentials or access tokens are added to the code repository.

## Guides

- [Windows and Home Assistant: start here](docs/SETUP.md)
- [Adding contacts, including Meshtastic](docs/CONTACTS_AND_MESHTASTIC.md)
- [Accessibility and testing notes](docs/ACCESSIBILITY.md)
- [Architecture and contributor extension points](docs/ARCHITECTURE.md)
- [Example Home Assistant scripts](docs/EXAMPLE_SCRIPTS.yaml)
- [Safety and limitations](DISCLAIMER.md)

## Running tests

```shell
python -m unittest discover -s tests -v
```

No live messages are sent by this test suite. The [contribution guide](CONTRIBUTING.md) explains how a new notification transport should fit into the project.

## Independence

LibreBeacon is independent, unaffiliated software. Abbott, FreeStyle Libre, LibreLinkUp, Home Assistant, Meshtastic and Microsoft are trademarks or projects belonging to their respective owners. See [references](docs/REFERENCES.md).

## Version 1.9.3 — Major update

This update brings the accessibility and contact features together in one Windows companion. The aim is to make everyday setup less fiddly, especially for someone who doesn't write code.

- **Emergency contacts:** added a dedicated screen to add, remove, save and test several nominated contacts. Each route needs consent before automatic messages can be enabled.
- **Critical-low glucose alerts:** added a separately configurable critical-low level, distinct from the usual low and high warnings, with an escalation path for contact notifications.
- **Home Assistant messaging:** added individually configured notification destinations and scripts for compatible phone notifications, email services and other supported outputs. Messages are requests to those services; delivery isn't guaranteed.
- **Meshtastic integration:** added discovery and selection of individual mesh notification destinations *through Home Assistant*. A configured gateway and supported devices are still required; LibreBeacon does not connect to radios directly.
- **Accessible warnings:** developed local audible alarms, spoken messages, larger on-screen notices and optional lighting actions. Flashing or pulsing smart lights require a suitable Home Assistant script.
- **Simpler settings:** improved button-led connection, sensor, accessibility, alerts and contact setup, with discovery, save and test controls where available.
- **Safer alert handling:** added measurement-age checks, duplicate-warning controls, opt-in contact sending and the option to omit numerical glucose readings from outgoing messages.
- **Windows setup:** added double-click installation and launch scripts, plus an optional build workflow for a Windows executable. A fully tested standalone installer is not yet available.
- **Community work:** separated contacts, reading validation and service access into maintainable modules; expanded the user guides, examples and automated tests.

**Status:** v1.9.3 remains a work-in-progress prototype. Live sensor, Windows-device and message-delivery testing are still needed. Keep the official Libre app and its alarms enabled; this software is only an additional notification layer.

## Version 4.0.6 — Guided setup and monitoring improvements

- **Start Here:** larger, numbered buttons open each settings section without typing commands. The checklist flags missing configuration; it doesn't claim equipment has been tested.
- **Reading health:** visible current, stale, unavailable and clock-error information. Expired glucose readings are hidden automatically from the main display.
- **Contact test status:** each configured contact shows whether the last request was accepted or failed. An accepted request does **not** mean somebody received it.
- **Manual recipient reply:** after testing, you can record a reply you personally received. This record is temporary and isn't a remote delivery receipt.
- **Safer contact names:** duplicate nicknames are rejected so the right contact is matched to the right test result.
- **More tests and guides:** expanded offline checks for setup, contact requests, timestamps and connection failures.

**Remaining work:** full Windows/device testing, delivery confirmation from independent channels, an easier installer and genuinely unattended monitoring. Keep the official Libre alarms enabled.
