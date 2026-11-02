# Guided Meshtastic field check — idea to build

Status: proposed. I haven't built the wizard or tested it with actual radios.

I want one window that takes someone from the safe rehearsal to a proper, recorded hardware check. No YAML scavenger hunt. Home Assistant stays in charge of the gateway; LibreBeacon only asks it for the information and services it already exposes.

## The flow I'd like

1. **Check the gateway.** Show what Home Assistant reports, when it was checked, and what's still unknown. A connected gateway isn't a delivery receipt.
2. **Confirm the receiver.** Show the pinned node ID, current destination and consent. If any identity doesn't match, stop. No guessing from a friendly name.
3. **Preview the test.** Display the exact `TEST ONLY` message and recipient. Nothing goes over the air until I press a separate **Send Test** confirmation.
4. **Check real receipt.** Record Home Assistant's request result first. Ask the recipient to read back the reference by another route. Keep **request accepted**, **radio reply observed** and **person confirmed receipt** as separate answers.
5. **Try a controlled failure.** Use the existing simulator for lost listening, timeout and Windows sleep. Physical disconnect tests happen only with someone present and no live medical event.
6. **Save a local report.** Record software versions, test case, date, observed result and next fix. Strip personal details, node identifiers, message text and glucose values from exports unless the user explicitly opts in.

## What I won't let it do

- Send a genuine emergency alert for a test, alter glucose thresholds or turn official Libre alarms off.
- Quietly enable a previously disabled contact, swap recipients or fall back to a public radio channel.
- Describe an HTTP response or packet acknowledgement as a person turning up.
- Run an unattended fallback during the trial. If Windows sleeps, the report must say monitoring was interrupted.
- Publish logs or identities anywhere. A local report is enough.

## Bits to settle when coding

- Use the existing `docs/MESH_FIELD_TRIAL.md` case numbers rather than inventing another checklist.
- Decide whether the Windows app should keep reports only for the session or save them with an explicit Save button. I'd start with memory only.
- Check keyboard focus, magnification and NVDA on Windows. Bigger text alone isn't an accessibility pass.
- Add a dry-run test that proves the wizard cannot reach the real Home Assistant notification call before the send-confirmation step. That's a guard worth keeping.
- Try it with a real gateway and two consenting receivers. Until then, all hardware rows stay **NOT RUN**.

Next job: wire the read-only gateway and recipient checks into the window, then add the deliberately confirmed test send. Keep it small enough to understand when something goes wrong.
