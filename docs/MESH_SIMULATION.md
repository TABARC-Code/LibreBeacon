# Rehearse Meshtastic backup decisions

Open **Start Here → Practise Mesh Backup (Simulation Only)** or **Emergency contacts → Run Safe Mesh Simulation**.

Pick an example and press **Run Simulation**. The window lists the decisions in order. You can compare an OK reply, a CANT reply, an unanswered message, an expired incident, a disconnected reply listener and a computer that stops responding. It also shows what happens when a contact is selected twice or when an OK reply arrives too late.

**The rehearsal itself sends nothing.** The samples use fictional node names, one fixed incident reference and a made-up clock. They do not load your contacts, talk to Home Assistant, send a radio message, read glucose data or change your settings. Nothing needs to be enabled for the demonstration.

The line **WOULD TRY one request** is a hypothetical decision. It is not a successful message, delivery receipt or welfare check. In particular, the simulator cannot prove that a real radio has power, a gateway is available, somebody has heard a warning or a human can attend.

## Notes for the next person in the code

- The live fallback still lives in `mesh_fallback.py`. The rehearsal calls the same state machine, but it never calls a sender. Keep that wall in place. A dry run that sends a real alert is a spectacularly poor feature.
- If the real dispatch policy changes, add an example here before claiming the rehearsal covers it. Cases worth adding: consent revoked mid-wait, a gateway change and two simultaneous incidents.
- Actual Windows sleep/resume behaviour still needs checking on a Windows machine. The rehearsal merely tests the intended cancellation path with a fixed clock.
- For a real field trial use `MESH_FIELD_TRIAL.md` and obtain the recipient's permission before sending any labelled TEST message. Keep the official alarms independent.
