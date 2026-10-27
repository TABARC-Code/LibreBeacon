# Meshtastic delivery, replies and accessibility — design plan

Status: DESIGN ONLY (v4.3.3). This is a build specification, not a claim that the listed features work.
Core principle: Home Assistant owns the Meshtastic gateway. LibreBeacon owns alert policy, recipient consent and its Windows interface.

## What we're building

Give an ordinary Windows/Home Assistant user a small, understandable way to send a supplementary alert to a trusted person over Meshtastic. The radio message can travel without a mobile data connection after Home Assistant has received it. The glucose data path via LibreLinkUp usually cannot. Keep these failures separate.

This is **not** a medical alarm, an emergency-service connection, a substitute for official Libre alerts, or a guarantee that somebody will answer. Everything starts off until the user actively enables it.

### Existing baseline: v4.3.2

- LibreBeacon can discover candidate \`notify.mesh_*\` entities from Home Assistant, reject obvious shared names, require consent and send via \`notify.send_message\`.
- Pre-send checks stop when a saved candidate is missing, unavailable or obviously shared.
- The app records **request accepted / failed**, not delivered. Contact confirmations are manual and only retained for the current session.
- It does not collect cryptographic identity, gateway health, incoming Meshtastic replies, transport acknowledgements or escalation state.
- **Gap worth fixing:** entity-name heuristics can be fooled by renaming a broadcast or channel entity. They are not a sound authorisation boundary. Don't hide that behind another checkbox.

## Proposed boundaries and components

\`\`\`text
Libre/LibreLinkUp --> Home Assistant glucose entities --> LibreBeacon alert policy
                                                  |             |
                                                  |       incident + routing
                                                  |             |
                                                  v             v
                                      HA Meshtastic gateway <-- notify.send_message
                                                  |
                                      LoRa individual direct message
                                                  |
                                           nominated node
                                                  |
                              deliberate reply -> HA incoming-message event
                                                  |
                           optional HA WebSocket event subscriber
                                                  |
                                      LibreBeacon incident tracker
\`\`\`

For the first implementation, all radio I/O stays inside the community Home Assistant Meshtastic integration. No own firmware code, no additional radio driver, no public MQTT broker and no requirement to open an inbound port on Windows.

Proposed modules (names subject to refactoring):

| Module | Owns | Does not own |
| --- | --- | --- |
| \`meshtastic.py\` | Identifying proposed HA destinations; validating node binding | Claiming friendly names prove identity |
| \`mesh_setup.py\` | Wizard state, saved consent and capability checks | Radio pairing or modifying channel keys |
| \`mesh_health.py\` | Gateway and recipient observations, aged timestamps | Invented online/coverage guarantees |
| \`mesh_messages.py\` | Short privacy-minimised templates and character/byte limits | Long medical records |
| \`mesh_incidents.py\` | Unique incident IDs, state transitions and escalation windows | Clinical decision-making |
| \`mesh_replies.py\` | Parsing and matching opted-in human replies | Equating a packet ACK with a human |
| \`homeassistant.py\` | REST send and later optional authenticated HA WebSocket events | Connecting to the radios directly |
| \`delivery.py\` | Per-route outcome history with redacted diagnostics | Calling HTTP 200 a delivery receipt |
| \`app.py\` | Button-led setup/status, accessible output | Complex network logic |

Introduce only the modules needed by the next working increment. A dozen empty files don't constitute progress.

## Setup wizard — design for someone who doesn't code

Place a **Meshtastic** page under Emergency Contacts and add a shortcut in Start Here.

**Step 1: Check Home Assistant** — buttons: **Test Home Assistant**, **Open Integrations**, **Help**. If disconnected, stop here with a plain explanation. Do not auto-install HACS or radio firmware.

**Step 2: Check gateway** — button: **Find Gateways**. Show known gateway names, observed availability, connection method if exposed, most recent evidence and a link to its HA device page. Treat \`unknown\`, missing metadata and old telemetry as **not verified**, not green. Only display fields confirmed by the installed integration.

**Step 3: Choose recipient** — buttons: **Find Nodes**, **Review Recipient**. Never offer channel or group notifications as a selectable personal recipient. Candidate selection must bind the explicit HA notify entity to the underlying Meshtastic node identity and gateway. Prefer entity/device registry metadata if the integration exposes it. If only friendly names are available, mark the route **unverified** and block automatic messages until it is checked out of band. Don't infer someone's identity from \`notify.mesh_alice\`.

**Step 4: Confirm identity and consent** — display label, node ID, gateway, identity/public-key fingerprint when available, intended receiver and who may read the message. Have the operator verify the device with the recipient using a separate trusted route. No health-data detail unless explicitly enabled. If a key or identity changes, disable the route pending reconfirmation.

**Step 5: Test safely** — button **Send Test Message** with a confirmation dialogue and prominently labelled \`TEST — NO EMERGENCY\` content. Ask the person to reply using an independent channel. A successful Home Assistant action is not the last step. Record the time and outcome separately.

**Step 6: Select alert rules** — default off. User chooses which conditions generate a mesh alert (critical-low, stale data, monitoring lost) and which contact(s) can receive which messages. Missing-glucose data is a connection issue, not evidence of low glucose. Existing approved Libre alarms must remain on.

**Step 7: Final check** — show one summary page: known/unknown gateway, verified/unverified node, test request result, observed human reply, privacy choice, enabled conditions and a prominent Disable button.

Use clear keyboard focus, readable status text (not colour alone), accessible labels and a screen-reader pass on Windows. Never hide safety status in a tooltip.

## Proposed saved recipient schema

Existing v4.3.2 contact records must remain loadable with **no silent activation**. Proposed additions are additive and optional:

\`\`\`json
{
  "label": "Trusted recipient",
  "target": "notify.mesh_receiver",
  "transport": "meshtastic_ha",
  "gateway_id": "configured-gateway-identity",
  "node_id": "configured-node-identity",
  "public_key_fingerprint": null,
  "verification_status": "unverified",
  "consent": false,
  "enabled": false,
  "allowed_events": ["critical_low"],
  "include_glucose_value": false
}
\`\`\`

These are *proposed* fields, not an implemented settings format. Existing code currently stores only label, target, consent and enabled. Node IDs can change if a radio's keys are regenerated. A blank fingerprint must not be represented as verified.

## Message format and incident tracking

Keep radio messages short. Use a small versioned text format rather than JSON over LoRa.

Proposed alert: \`LibreBeacon alert LB-K7P4M9: Please check your nominated contact. Reply LB-K7P4M9 OK if you can respond.\`

Proposed test: \`TEST ONLY — LibreBeacon radio check LB-R3T8V2. No action needed except to confirm receipt.\`

Identifiers shown here are examples, not a secure implementation. Real tokens must come from a cryptographic generator, be incident-bound, expire, and be validated alongside the approved sender node and direct-message destination. Keep message size within the actual integration/radio constraints measured in UTF-8 bytes; test with apostrophes, emojis and non-ASCII names. Never split a sensitive alert into uncontrolled broadcasts.

Default text should omit names, addresses, exact glucose values and location. The existence of a health alert is itself sensitive: explain that before the user consents. Private one-to-one messages are preferred; a default public channel is not private.

Model **three independent status axes**, not one optimistic 'sent' boolean:

1. Application request: \`not_requested\`, \`queued\`, \`accepted_by_HA\`, \`rejected\`, \`unknown\`.
2. Radio evidence: \`not_observed\`, \`tx_observed\`, \`packet_ack_observed\`, \`delivery_unknown\` (only expose observations the installed integration actually provides).
3. Human response: \`not_requested\`, \`awaiting_reply\`, \`matching_reply_observed\`, \`expired\`, \`manually_confirmed\`.

Do not infer an acknowledgement from an HA notify entity's 'last sent' timestamp. Meshtastic packet ACK is not evidence that someone noticed the message. A matched reply from an approved node only proves that a message was received from that node, not who physically held it.

Incident lifecycle: \`created -> sent_attempted -> awaiting_reply -> response_observed / expired / cancelled\`. Incidents must have unique identifiers, UTC creation time, expiry, per-recipient outcomes and a monotonic-clock scheduling strategy. The glucose reading's **measurement timestamp** must be separately validated before raising a fresh-glucose incident. A stale reading generates its own availability warning, never a critical-low incident.

## Two-way replies — optional second stage

The Meshtastic Home Assistant integration publishes incoming text-message events, including sender, destination, gateway and message. Home Assistant's authenticated WebSocket event subscription can be investigated as the preferred way for the Windows companion to observe replies; don't expose an unauthenticated Windows webhook on the LAN. Pin this to tested integration versions because the event schema may change.

Check all of: direct-message destination, gateway identity, approved sender's node ID, known node fingerprint where available, exact incident token, allowed reply command, time window, replay history and outstanding incident state. Unknown senders or malformed replies should never change alarm or escalation state. A route whose identity cannot be verified should remain in manual-confirmation mode.

Reply options could be:
- \`LB-K7P4M9 OK\` — observed response from the configured node, not a guarantee that someone has attended.
- \`LB-K7P4M9 CANT\` — recipient can't attend; consider notifying the next consenting contact.
- \`LB-K7P4M9 TEST\` — test-only confirmation, with no incident escalation.

Reply handling must not switch off the official Libre alarm, or presume treatment has occurred.

## Escalation and retry rules — opt-in, disabled at launch

Start with independent attempts to specifically consented destinations. User-configured escalation to another approved contact is a later feature, not an excuse for blasting all discovered nodes.

- No automatic escalation or repeated transmission by default.
- Distinguish **no human reply**, **gateway down**, **recipient unavailable**, and **glucose feed missing**.
- Deduplicate alerts by incident ID, event type and target. Use bounded retries, a cooldown and a total-airtime budget; do not loop every minute until a contact answers.
- Escalate *only* to another opted-in recipient; never to emergency services or public mesh channels.
- Allow the operator to cancel LibreBeacon's subsequent messages. Don't represent cancellation as medically resolving an event.
- If the Windows application exits or sleeps, show that unattended monitoring is unavailable. A separate Home Assistant-side always-on route may be considered later, with incident ownership and duplicate prevention designed first.

## Health reporting and failure matrix

| Situation | Display | Safe behaviour |
| --- | --- | --- |
| Libre glucose fresh, gateway ready, verified recipient | Ready for supplementary mesh messaging | Sending permitted when specifically enabled |
| Home Assistant offline | HA unavailable | Stop new HA requests; explain that local output may still work |
| LibreLinkUp stale, mesh operational | Glucose feed stale / mesh observed | Optionally send a distinct, consented feed-loss notification — never imply low glucose |
| Meshtastic gateway missing/disabled | Gateway not verified | Avoid mesh send; keep independent phone/light routes |
| Recipient seen previously but not recently | Recent availability unconfirmed | Mark uncertain; do not promise reachability |
| HA accepted notification request | Request accepted | Delivery and human reply still unknown |
| Radio packet ACK received | Radio acknowledged | Human response still unknown |
| Reply from wrong node / channel / expired token | Unmatched message | Do not acknowledge the incident |
| Person replies via approved node | Matching reply observed | Record evidence; do not silence Libre alarms |
| Contact removed, identity changed, consent revoked | Route disabled | Stop sending; remove or expire existing pending route actions |
| App suspended or machine rebooted | Monitoring not active | No assertion that emergency contacts remain protected |

**Gateway liveness is not a coverage guarantee.** Most mesh metrics describe last observation, not a measured guarantee of how quickly a message will reach a person.

## Privacy, radio and access controls

- Restrict outbound messages to specifically approved private destinations. No fallback to default/public channels when a send fails.
- Confirm recipients' public keys out of band where available. Do not store radio private keys in LibreBeacon.
- Treat all incoming messages as untrusted; cap lengths, enforce strict parsers and ignore message text as executable instructions.
- Store token/authentication material in OS-provided credential storage. Health values, message content and contact personal details should be absent from routine logs.
- Use a small rolling local diagnostics buffer with explicit opt-in export and redaction. Set a documented retention limit before any persistent event history is introduced.
- Do not enable Meshtastic's Home Assistant web-client proxy by default. Its own README warns about unauthenticated access to exposed gateway APIs.
- Meshtastic's public default channel key is known. Use an individual direct message and verify the intended receiver rather than assuming everything labelled 'mesh' is private.
- UK users must set their correct regulatory region and use legally compliant equipment, power and airtime. The Meshtastic \`EU_868\` configuration currently specifies a 10% duty-cycle cap. Do not override regional limits to push a message through.

## Build order: actual work, not placeholder versions

**M1 — Destination identity (first code task)**
- Define typed gateway/node/capability records and migration from existing contacts.
- Read HA registry/device metadata where actually available, distinguish explicit node vs channel via trustworthy integration fields, and fail closed otherwise.
- Build an accessible mesh-recipient review form.
- Tests: channel renamed 'Alice', node renamed 'public', duplicate gateways, changed identity, deleted entity, unverified node, migration.

**M2 — Gateway and receiver health**
- Discover accessible gateway/device metrics with age and provenance. Use unknown instead of fabricated health.
- Present status and plain-English recovery steps.
- Tests: disconnect, reboot, old telemetry, multiple gateways and swapped device.

**M3 — Message preparation and outbound tests**
- Short templates, redaction, exact recipient targeting, labelled test dialogue, bounded/explicit sending, event ID.
- Tests: multi-byte UTF-8, long text, no consent, wrong target, REST timeout, accepted-but-undelivered, multi-route partial failure.

**M4 — Inbound replies**
- Authenticate and consume HA event stream, parse direct messages, correlate with a unique open incident, observe reply status.
- Tests: wrong sender, wrong destination, wrong gateway, expired and replayed tokens, simultaneous incidents, event schema drift.

**M5 — Optional escalation**
- Add per-contact escalation policies, bounded schedules and clear cancellation. Keep this disabled by default.
- Tests: offline/online transitions, repeat suppression, revocation mid-incident, reboot/sleep, burst and queue limits.

**M6 — Accessible field trials**
- Test on an actual Windows installation, Home Assistant gateway and two Meshtastic devices with a consenting receiver.
- Run no-risk test messages first; record line-of-sight, wall penetration, battery, indoor audible/vibration notification, real reachability and screen-reader usability.
- Do not assert clinical or emergency reliability from passing unit tests.

No predicted versions are guaranteed: increment project versions when each milestone is actually implemented, tested and published.

## Release acceptance criteria

Minimum for a first *functional* mesh release:
- Ordinary user can select a known gateway and verify one private recipient with buttons.
- App refuses an obviously shared destination and requires explicit identity confirmation.
- Test message cannot be mistaken for a real emergency.
- Requests to one recipient cannot block unrelated alerts.
- All outcomes use honest terms: accepted, rejected, unknown, matched reply.
- No settings migration silently enables health-data sharing.
- End-to-end real-radio tests and accessibility tests are documented as pass/fail, not assumed.

For two-way replies, add tests for strict source binding, uniqueness, expiry and replay rejection before enabling any reply-driven escalation.

## Things to keep thinking about

- A personal node can silently become a public channel if someone changes the integration configuration. That is why labels alone won't do.
- Could we give users a one-page 'who gets what' route summary? It's safer than burying privacy behind three tabs.
- Offline doesn't mean everything is offline. The data, HA host, gateway, radio mesh and receiver can each fail independently. Model them independently.
- Perhaps an HA-side resident service would improve resilience; don't bolt it on until incident ownership and duplicate sends are sorted. No one needs six 'urgent' messages for a single test.
- If a contributor adds wearables, make sound/vibration behaviour separately testable. Flashing light is not a universal accessibility answer.
- Keep a short feedback loop: note the field observation, link it to the decision, name the next test. If we've not tried it with two real radios, write 'untested'.

## Reference links

- Meshtastic Home Assistant integration: https://github.com/meshtastic/home-assistant
- Its incoming-message trigger examples: https://github.com/meshtastic/home-assistant#automation
- Home Assistant notification actions: https://www.home-assistant.io/integrations/notify/
- Home Assistant notify entity send: https://www.home-assistant.io/actions/notify.send_message/
- Meshtastic encryption model: https://meshtastic.org/docs/overview/encryption/
- Meshtastic regional LoRa settings: https://meshtastic.org/docs/overview/radio-settings/

These references describe external software, not an endorsement or a guarantee of compatibility.