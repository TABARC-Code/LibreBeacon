# LibreBeacon setup — a practical guide

This is written for the person using the app, not someone who likes editing configuration files.

## What you need

A Windows 10 or 11 PC; a working Libre sensor and approved phone app with the official alarms left on; Home Assistant already running; an existing community LibreLinkUp-to-Home Assistant integration; and Home Assistant login access. The PC must remain awake and connected for the extra alerts to run. A separate notification setup is needed if you want texts, emails, smart lights or Meshtastic messages.

Nothing in this guide replaces medical advice. Set thresholds with the person and their healthcare professional. Don't use someone else's values just because they appear in an online example.

## First-time installation

1. Extract the ZIP. Don't run files straight from inside the ZIP.
2. If necessary, install Python 3.11 or newer from [python.org](https://www.python.org/downloads/windows/), with the Python launcher enabled.
3. Double-click `INSTALL-WINDOWS.bat` once. It may need a network connection to install a Python library.
4. Double-click `run-windows.bat` and keep LibreBeacon open during setup.
5. The **Dashboard** should initially show **Reading unavailable**. That's expected until you finish the connection and sensor steps.

## Button 1 — Connect Home Assistant

In Home Assistant, open your user profile and create a **long-lived access token**. Copy it. In LibreBeacon choose **1 · Connection**, enter your server address (for example `http://homeassistant.local:8123`) and the token. Press **Save Connection**, then **Test Connection**. Keep the token private; never paste it into a screenshot or share it online. On an untrusted network, use a properly secured HTTPS connection.

## Button 2 — Select readings

Open **2 · Sensors** and press **Find Sensors**. Choose the glucose value and the **actual sensor measurement time**. It isn't enough to choose Home Assistant's `last_updated` time — that field can refresh even when the phone hasn't supplied a new measurement. Press **Save Sensor Selection**, then **Test Reading**. If a reading is old or missing, the big number should disappear rather than appear safe.

## Button 3 — Test local warnings

In **3 · Accessibility**, test the audible sound, offline Windows speech and visual notice separately. Check actual volume on the device the person uses, including after the PC is locked or resumes from sleep. Don't assume the speech worked just because a button was pressed. The built-in notice pulses gently, but any flashing may be unsuitable for people with photosensitivity. The local visual notice can be switched off.

## Button 4 — Lights and ordinary contact scripts

If you already have scripts in Home Assistant, choose one in **4 · Alerts**, press **Find Home Assistant Scripts**, then run the clearly labelled test. A script can switch a particular smart bulb on or send a message. Home Assistant must know how that script works. See the examples and test the full process at the intended device.

## Button 5 — Emergency contacts

In **5 · Emergency contacts**, press **Find Destinations**. Enter a short nickname, choose one destination, tick the person's consent and press **Add Contact**. Repeat for a second person if wanted. Press **Save Emergency Contact Settings**.

Select one contact and press **Test Selected**. This really sends a test request; warn the person first and ask them to confirm receipt. It is especially worth testing after a router restart, a Home Assistant update and any new phone purchase.

You can use an existing `notify.*` destination or `script.*` script. If a Meshtastic gateway is connected to Home Assistant, use **Show Mesh Nodes** to filter the list. Avoid choosing a channel-wide broadcast. There is a [separate guide](CONTACTS_AND_MESHTASTIC.md) for connecting email, a phone or a radio node.

## Button 6 — Alert thresholds

In **6 · Alert rules**, enter the person's own low and high values, then (optionally) a *lower* critical-low value to trigger the extra emergency contacts. All numbers are in **mmol/L**. Nothing is filled in automatically. Set the age limit for the sensor reading and check interval, then press **Save and Validate Alert Rules**.

Return to **5 · Emergency contacts** and tick **Enable automatic critical-low contact messages** only after every contact route has been tested and the person agrees. Tick the delivery/consent statement. Save again. Lastly, enable supplementary alerts on **Dashboard**.

## Things to test before someone uses it

- Simulate a test using the labelled test buttons. Confirm the intended light, sound and recipient actually respond.
- Shut down Home Assistant temporarily. Check the software reports unavailable data; it mustn't keep showing an old glucose value as if it were current.
- Check Wi-Fi loss, Windows sleep, network changes, muted sound and a powered-off smart device. Some failures may not raise a separate alarm.
- Keep a non-computer route for actual assistance. LibreBeacon doesn't call the emergency services and cannot guarantee a message or acknowledgement.

## If nothing happens

**No connection:** check the URL, the Home Assistant token and the network.  
**No sensors:** check that LibreLinkUp is updating Home Assistant.  
**No sound:** check Windows output device, app volume and speech components.  
**No contacts:** the contact channel must already exist in Home Assistant. Selecting `notify.*` does not automatically create a phone or email service.  
**Old readings:** fix the Libre → phone → LibreLinkUp → Home Assistant path. Do not switch off freshness checks to hide errors.

The program does not monitor anything when closed.
