# Accessible operation — current design and gaps

## Built in now

- A tab for each setup step, with labelled buttons and test controls.
- Large glucose numbers; adjustable interface text size after restart.
- Offline Windows speech warning (requires working Windows speech components).
- Local audible tone, slow visual pulse and optional Home Assistant light/script triggers.
- Plain reading-age/error states. Missing data is never portrayed as a fresh safe reading.
- Independent outputs so a failure in one external route does not automatically stop the next.

A colour by itself must never be the only cue. Avoid fast strobing. Give users control over noise and flashing, including for someone sensitive to sudden changes.

## Not yet established

This Tk interface has not undergone proper testing with NVDA, Windows Narrator, switch access, magnification, high DPI, keyboard-only navigation or a visually impaired tester. The final size of controls and some pop-up behaviour may need changes. Windows speech can fail or target the wrong sound output device without the program knowing. Please report actual problems with the device and version used, without posting glucose readings or personal identifiers.

The most useful accessibility work would be: proper labelled focus order, keyboard shortcuts, a tested non-flashing high-contrast theme, a screen-reader review, and a clear indication when an alert is waiting to be acknowledged locally. Such an acknowledgement must not pretend to silence the official Libre alarm or confirm an external delivery.

## Version 4.0.6 practical checks

The **Start Here** tab provides large individual setup buttons, and the Dashboard's **Reading health** label uses words as well as state rather than colour alone. A missing or stale reading is shown as an em dash, not an old value. Contact attempt labels likewise distinguish a request being accepted from a manually confirmed human reply.

Try every output with the actual person and their assistive equipment. Test at a comfortable volume, test both normal and high-contrast Windows settings, and confirm whether slow light pulses are suitable for the household. Switching on large text does not guarantee screen-reader compatibility. Let the person decide which alerts they want, then test them with someone present.
