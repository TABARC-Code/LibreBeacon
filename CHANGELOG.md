# Changelog

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
