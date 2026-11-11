# Guided Meshtastic field check

I've added this as a three-page **TEST ONLY** window under **Start Here** and **Emergency contacts**. It uses Home Assistant for gateway and node checks. It sends absolutely nothing until a person explicitly confirms the exact test message.

The wizard is part of LibreBeacon 4.11.0. It hasn't been tried with two physical radios or a live Windows screen reader yet. A passing automated test doesn't fix that.

## Run a field check

1. Configure the Meshtastic gateway in Home Assistant and a single individual-node notification entity. Make sure the contact has agreed to test messages. Add the contact in LibreBeacon and **save** its settings.
2. Open **Guided Mesh Field Check**. On **1 · Check**, select **Check Gateway**. The window only treats one explicitly connected Home Assistant gateway as ready. That is a gateway observation, not a reception guarantee.
3. Select your saved recipient and choose **Check Selected Node**. LibreBeacon asks Home Assistant whether the destination still has the approved node identity.
4. Ask the recipient to confirm the actual device by a trusted separate contact method, then select **Confirm Node Owner**. That confirmation lasts only for this session.
5. On **2 · Send test**, select **Preview TEST ONLY Message**. Read the exact text. The preview does not send anything.
6. Choose **Send Confirmed TEST ONLY Message**. A confirmation dialogue shows the destination and the exact message. Cancelling leaves the radio alone. Confirming issues **one** Home Assistant notification request, after checking gateway state, saved recipient consent and node identity again.
7. Ask the other person to read the test reference back by phone or another trusted method. If they do, choose **Record User-Reported Receipt**. This is a note from the operator, not an independently verified receipt.
8. On **3 · Report**, review the case list and choose **Save Redacted Report** only if you want a local text file. Nothing is saved or uploaded automatically.

## What the statuses mean

- **HA REPORTS CONNECTED:** Home Assistant says one gateway is connected. No radio coverage test has passed.
- **NODE ID MATCHED:** The current Home Assistant destination still maps to the pinned node number. Ownership needs checking separately.
- **HA REQUEST ACCEPTED ONLY:** Home Assistant accepted the notification request. Delivery remains unknown.
- **USER REPORTED RECEIPT:** The operator says the intended contact confirmed the message through another route. No inference about medical assistance.
- **NOT RUN:** No field observation recorded. The wizard deliberately leaves other checklist cases alone.

## Record the other field checks

On **3 · Report**, pick one of the remaining numbered field cases and choose **PASS**, **FAIL** or **NOT RUN**. Press **Record Operator-Reported Result** and confirm only if you actually witnessed the check. LibreBeacon labels these **OPERATOR REPORTED**; they're not independent evidence and they don't change the alert engine.

Cases **02–04** remain controlled by the guided identity check and actual test request, so they can't be overwritten with a tick. Cases **05–06** are cleared when you change the recipient, repeat a gateway check or prepare a new message. Otherwise an old reply could make a fresh trial look rather more convincing than it is.

The report contains result categories only. No free-form notes, node IDs, recipients or message contents are exported. Keep detailed observations separately and privately if needed.

## Local report and privacy

The report includes the application version, session start time, gateway/recipient result categories and the numbered cases from [the field checklist](MESH_FIELD_TRIAL.md). It leaves out names, entity IDs, node numbers, message bodies, references, passwords and glucose readings. The file is written only when you select a location.

This wizard doesn't create a real low glucose event, enable emergency contacts, launch an automated backup or amend any medical threshold. The safe simulation remains available separately for timeouts, Windows sleep and failed replies. For actual field measurements, use the existing checklist and mark what was observed, including failures. Don't dress a radio experiment up as something it isn't.

## Next improvements

- Check keyboard-only access, NVDA, magnification and small screens on Windows. The controls have ordinary labels but no actual screen-reader field check yet.
- Try the real gateway, two consented radios and a phone for read-back. Record dropped tests and device versions locally.
- I may add a multi-step walk-through for disconnected gateway tests after the first real field notes arrive. There are enough ways to get a false green tick already.
- Consider binding gateways to each contact more precisely once the integration exposes reliable gateway-scoped identity information.

Keep official Libre alarms active. The whole feature is supplementary and must not be relied upon for treatment or emergency assistance.

## A gateway changing mid-check

I now keep the Home Assistant gateway entity ID used during the check. Before a real test send, the app asks Home Assistant again and refuses to switch to a different gateway silently. This is an HA entity check, **not** proof of radio ownership or signal coverage; the device registry can still be misconfigured.

If contact settings become invalid before the test starts, the prepared message is discarded and a new preview is needed. No retry happens on its own. If a send request fails after it starts, the app leaves delivery **unknown**, since a timeout doesn't prove the radio stayed silent.

## Approval expiry

I keep the gateway check, recipient check and preview valid for at most five minutes. If I leave the window open or Windows sleeps, I need to check again and prepare a fresh TEST ONLY message.

Closing the window revokes pending permission, including while Home Assistant is still answering a gateway or recipient query. The sender checks once more immediately before requesting the notification. A request that's already been accepted cannot be withdrawn, so I still need the recipient to confirm what actually arrived.

This is a guard against old test requests, not a radio coverage guarantee.

## Consent changes while a test is being prepared

A send confirmation doesn't freeze the recipient's permission. The wizard checks the currently saved recipient again after asking Home Assistant for the node's identity, immediately before the notification request. If consent, node number or destination approval changes, the test is **BLOCKED BEFORE SEND** and a new preview is required. If the notification request itself fails or times out, delivery is still **UNKNOWN**; there is no automatic retry. Once a request has been handed to Home Assistant it cannot be recalled.

This closes a software race. It doesn't prove that a Meshtastic receiver obtained or displayed the packet.
