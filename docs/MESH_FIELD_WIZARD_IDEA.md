# Guided Meshtastic field check — idea and remaining work

The first button-led wizard is implemented in LibreBeacon 4.11.0. See [the working guide](MESH_FIELD_WIZARD.md).

The original idea was to check one gateway, confirm an individual node, preview a test, send only after an explicit second confirmation, and keep a private local report. Those steps now exist in the desktop application. No automatic fallback or real medical event is triggered by the wizard.

**Still needs testing:** Windows and NVDA, a physical Home Assistant Meshtastic gateway, two actual radios, message receipt, radio dropouts, Windows sleep and owner identification. The wizard cannot independently prove a human read the message. If the report says the recipient confirmed it, that means the operator recorded the claim.

Next: use [the 13 field cases](MESH_FIELD_TRIAL.md) with genuine hardware. Repair the failures rather than polishing a hypothetical success story.
