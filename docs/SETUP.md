# Start here: Windows and Home Assistant

## Option A — Windows setup package (no Python installation)

1. Visit the [Windows package workflow](https://github.com/TABARC-Code/LibreBeacon/actions/workflows/build-windows.yml). Choose a successful run for the release you want.
2. Download its **LibreBeacon-Windows-unsigned** artefact, unzip it and find `LibreBeacon-Setup-v4.2.0.exe`.
3. Check the version and source. The package is **unsigned** and has not been tested on your Windows hardware. Don't dismiss a security warning without deciding if you trust the code and the build.
4. Open the setup program, choose an install folder if you wish, and finish. You'll find LibreBeacon in the Windows Start menu. No administrator access is needed.
5. Open **Start Here** and follow the numbered buttons. The program does not automatically begin warning or contacting anyone.

If no successful Windows package is available, use the source installation below. The installer requires an existing LibreLinkUp integration in Home Assistant; it cannot set up Abbott sharing on your behalf.

## Option B — Install from the source folder

Extract the source ZIP to a folder, install Python 3.11 or newer, and double-click `INSTALL-WINDOWS.bat`. Then use `run-windows.bat` to open the app. Internet access is required to install dependencies. This route is useful for contributors, not necessary once a tested Windows package is available.

## Numbered setup buttons

1. **Connection** — enter the Home Assistant base URL and a long-lived access token, choose Save, then Test. Tokens are kept in the Windows credential store, not the ordinary settings JSON. **Forget Saved Token** clears it locally and pauses supplementary alerts; revoke it in Home Assistant separately if necessary.
2. **Sensors** — Find Sensors, choose glucose and **actual measurement timestamp**, then Save and Test Reading. Never use Home Assistant `last_updated` as if it were a new Libre measurement.
3. **Accessibility** — choose your local sound pattern, voice and visual choices. Steady visual notices are the default. Save, then test. Select motion only if suitable for the person using the system.
4. **Alerts** — choose compatible Home Assistant scripts for lights or optional notifications, then test explicitly.
5. **Emergency contacts** — Find Destinations; add consented people one at a time. Test Selected sends a real **test** request only after confirmation. Check Contact Delivery Status tells you which requests were accepted, not whether a person read one. Call the recipient to verify.
6. **Alert rules** — set low, high, critical-low if required, age limit and poll interval with the intended user's clinical guidance. Save, then return to Dashboard and enable supplementary alerts only once the tests make sense.

**Keyboard:** F1 opens setup; Ctrl+1 to Ctrl+9 selects tabs. More detailed screen-reader verification remains to be done on actual Windows equipment.

## Common traps

- No result? Confirm the Libre app itself has a current reading, LibreLinkUp is sharing, and Home Assistant displays the actual measurement time.
- Sounds not heard? Check Windows output device, volume, speakers and power. A successful sound-button press doesn't mean anyone heard it.
- Email, Meshtastic and other messages rely on working Home Assistant destinations. The application doesn't create these accounts or verify a final recipient received a message.
- Laptop closed, sleeping, rebooting or offline? LibreBeacon does not monitor reliably during those conditions. Keep the official Libre warnings and existing arrangements active.
- Uninstalling removes the program and shortcuts; settings in the Windows user profile and credential-store entries are deliberately preserved. Use **Forget Saved Token** first to remove the local credential, and revoke it in Home Assistant as appropriate.

For extra advice see [contacts and Meshtastic](CONTACTS_AND_MESHTASTIC.md), [accessibility](ACCESSIBILITY.md), and the [safety notice](../DISCLAIMER.md).
