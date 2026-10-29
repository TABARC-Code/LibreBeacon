# Changelog

## 4.5.0 — Meshtastic gateway diagnostics

- Added a read-only gateway check from Home Assistant, with clear reported-connected, disconnected, unknown and unverified states.
- Added a button-driven status window, plus a Start Here shortcut and a refresh control.
- Shows each configured mesh recipient’s last-heard observation if a single matching timestamp sensor is available. Old, missing, future or ambiguous observations are not treated as live radio coverage.
- Does not send radio messages, enable contacts or infer human acknowledgement. Existing alert routing remains unchanged.
- Expanded mock-based failure and clock tests; real Windows/radio testing remains outstanding.


## 4.4.0 — Meshtastic recipient identity

- Require integration-provided numeric node IDs and matching user IDs when adding a mesh recipient.
- Pin each approved recipient to their node number and check it again before sending.
- Block renamed channels, invalid identities and changed recipients without interrupting other contact routes.
- Keep older contacts visible but disabled until someone checks and re-adds them.
- Update the setup guide, display the saved node ID and expand the offline regression tests.
- No live radio or Windows hardware testing in this update.

## 4.3.2 — Home Assistant mesh setup

- Show only plausible personal Meshtastic notify entities in the emergency-contact selector.
- Ask the user to confirm the intended individual recipient before adding a mesh contact.
- Re-check saved mesh destinations against live Home Assistant state before each send; stop if missing, unavailable or now presented as shared.
- Better setup guidance and tests around destination changes. Message requests remain distinct from delivery and human acknowledgement.

## 4.3.0 — Mesh destination checks

- Added a small module to identify possible individual Meshtastic notification entities in Home Assistant.
- Filtered obvious channel, group and broadcast targets, including their displayed names.
- Kept radio communication in Home Assistant; LibreBeacon does not manage keys or radio connections.
- Added tests for unavailable nodes, misleading names and shared destinations.


## 4.2.0 — Windows packaging and accessibility controls

- Added per-user NSIS installer source and Windows CI packaging for unsigned setup and executable artefacts.
- Made desktop visual alerts steady by default. Background pulses now require an explicit choice.
- Added three short, selectable Windows sound patterns and kept playback off the main UI thread.
- Added F1 setup shortcut and Ctrl+1 through Ctrl+9 tab navigation.
- Added per-contact last-request time, outcome summary and redacted error categories.
- Added a button to forget the locally stored Home Assistant token without silently deleting settings.
- Validation now rejects emergency messaging when no configured recipient is actually enabled.
- Updated beginner guides, developer notes and offline regression tests. Real Windows hardware and medical-service verification remain outstanding.


## 4.0.6 — Guided setup and monitoring status

- Added a **Start Here** screen with large step buttons and a saved-settings checklist. Each option opens its existing setup tab; enabling alerts remains a separate choice.
- Added live reading-health notices with distinct current, stale, unavailable and clock-error states. A reading is hidden when it expires, even if the Windows application is still open.
- Added per-contact test results in the emergency contact list. An accepted service request remains labelled *delivery unconfirmed* until someone manually records an actual reply.
- Added a separate **Record Recipient Reply** control. Confirmation is local to the current session, deliberately not a delivery claim.
- Added distinct-contact-name checks to avoid confusing one recipient with another in the activity list.
- Expanded offline coverage to 51 tests and checked the full nine-tab interface in a Linux virtual display.
- Updated setup, accessibility and contributor guides. Real-device and Windows validation are still required.

## 1.9.3 — Accessible contacts and setup

- Added a dedicated button-led emergency contact screen, including Add, Remove, Test Selected, Find Destinations, Show Mesh Nodes and help.
- Added multiple consent-controlled routes through Home Assistant notification entities or scripts. This includes individual Meshtastic destinations when available in Home Assistant.
- Added an optional, user-defined critical-low threshold distinct from ordinary low/high events.
- Contact alerts use a privacy-conscious message without a numerical glucose reading unless the user opts in.
- Independent contact request attempts continue after a destination returns an error; delivery remains unverified.
- Corrected a conflicting Tk geometry manager in the earlier contact settings screen, discovered during the visual-display smoke test.
- Added Windows installer and package-build scripts, a proposed GitHub Windows build workflow, contributor guidance and accessibility notes.
- Expanded simulated tests and exercised Tk screen creation under a Linux virtual display. Still untested with an actual Libre sensor or Windows notification delivery.

## 0.1.0 — initial prototype

First desktop prototype with Home Assistant REST reads, conservative measurement validation, local sound/speech, visual notices, optional scripts and an initial setup screen. The early build was not an independently verified production release.
