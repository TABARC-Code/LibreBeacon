# Meshtastic field checks for LibreBeacon

This is a practical checklist for an owner with a Windows PC, Home Assistant, one gateway and two consenting Meshtastic users. I haven't run it against a real radio yet. Passing a mock test or a Windows installer build is not a successful field trial.

**Use TEST ONLY messages. Never deliberately create a dangerous glucose reading, change somebody's treatment, disable official Libre alarms or rely on this experiment for emergency contact.** Any medical context should use the real monitoring app and the person's agreed care plan.

## What to have on the bench

- Windows computer with LibreBeacon installed, powered and prevented from sleeping during the ordinary test. Test sleep separately, once messages have stopped.
- Home Assistant with the Meshtastic integration, a connected radio gateway, and the current working glucose integration if a read-only data-path check is needed.
- Two individually selected Meshtastic receiver nodes, verified with their owners; no default public-channel targets. Use known, consenting recipients.
- A separate way to contact each recipient (phone call is fine) so we can compare what the app claims with what they actually observed.
- Details recorded locally: Windows version, HA Core version, integration version, firmware version, gateway connection method, test date, environment and whether any messages were dropped. Don't post node identifiers or personal information in a public issue.

## Run in order

| Case | Do this using test messages or mock observations | Expected result | Actual result |
| --- | --- | --- | --- |
| 01. Install | Install on a standard user account, open all nine tabs, exercise keyboard shortcuts and scaling | Install runs without admin; controls are reachable | **Not run on hardware** |
| 02. Node identity | Confirm the receiver's node ID separately, then add its Home Assistant notify entity | Saved contact binds to that node, not merely a friendly name | **Not run on hardware** |
| 03. Private test | Preview and deliberately send one `TEST ONLY` message to the first node | No channel broadcast; request status is not called delivered | **Not run on hardware** |
| 04. Actual receipt | Ask recipient to read back the reference through a different communication route | Record actual receipt separately from HTTP request result | **Not run on hardware** |
| 05. Matching reply | Receiver sends `<reference> OK` to the gateway while listening | Matching radio reply observed; no claim of attendance | **Not run on hardware** |
| 06. Invalid replies | Send wrong reference, wrong node, expired reference or channel reply | None changes the incident's state | **Not run on hardware** |
| 07. Gateway offline | Disconnect gateway; attempt no real alert, only a labelled test | No fabricated successful delivery; other contacts stay independent | **Not run on hardware** |
| 08. HA WebSocket loss | Stop the HA WebSocket service or disconnect the network during a **simulated** pending backup | Heartbeat notices the loss; no-reply fallback cancels | **Not run on hardware** |
| 09. Windows sleep | Arm a simulated fallback, suspend Windows, resume after the chosen delay | Pending fallback cancels rather than firing on wake | **Not run on hardware** |
| 10. Recipient changed | Reconfigure a saved notify entity to point to another node; do not transmit | Node identity mismatch prevents the send | **Not run on hardware** |
| 11. Consent withdrawn | Disable the backup/contact and recheck its status | No new automatic request to that recipient | **Not run on hardware** |
| 12. Accessibility | Test keyboard alone, NVDA speech, high DPI, magnification, steady notices and separate sound | Clear focus, readable status and no undisclosed motion | **Not run on hardware** |
| 13. Physical radio | Repeat ordinary tests at intended indoor/outdoor positions and during low battery | Record real delivery, failure and latency without claims of guaranteed coverage | **Not run on hardware** |

If a case fails, mark it **FAILED**, describe only the observed behaviour, and record the version. Retest before closing it. No green ticks until a person or machine has actually checked it.

## Evidence to record without publishing private data

| Field | Example of acceptable wording |
| --- | --- |
| Case | `08` |
| Software | `LibreBeacon 4.9.0, Home Assistant version tested, integration version tested` |
| Network | `LAN disconnected for 40 seconds` |
| Observed | `Listener reported disconnected. Pending backup cancelled.` |
| Outcome | `PASS`, `FAIL` or `NOT RUN` |
| Next check | `Repeat with the actual gateway rather than a simulated socket` |

A useful short note after each run is: **What I expected / what I saw / what I'm changing.** That's enough to guide the next code change without a page of ceremony.

## Current automated coverage

Tests simulate the authenticated HA event stream, timeout and wrong-pong behaviour. They don't prove radio propagation, private direct-message delivery, the ability of a recipient to operate a handheld unit, or reliable performance under Windows sleep. The WebSocket heartbeat checks **Home Assistant connectivity**. It doesn't tell us whether the Meshtastic gateway is connected or the person is reading messages.

## Before enabling real-world backup notifications

Keep automatic backup **off** until at least the Windows, gateway, node identity, dropped-connection, recipient and accessibility cases have been exercised with the actual equipment. Even after that, this remains a supplementary notification system. Approved Libre alarms and an independent contact plan are still needed.

An always-running Home Assistant-side alert service is worth considering later. First prove incident ownership and duplicate prevention. Otherwise the system may produce two urgent messages, each convinced the other one didn't happen.
