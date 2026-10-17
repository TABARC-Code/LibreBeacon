# Contributing

This began as an accessibility companion for one person, but it should be useful to others without becoming complicated. Small, well-tested modules are preferable to adding another heavyweight dependency for every new option.

Fork the project, describe the problem you're solving, and keep changes limited to the part of the program that owns that behaviour. Add tests alongside code, particularly for stale readings, transport errors, privacy, contact consent and disabled-by-default settings. Don't send real messages from automated tests.

**Comments are useful when they explain a decision.** Keep them clear and fairly conversational. Short reminders such as “Watch for duplicate notifications when the connection returns” are welcome; invented work histories, personal diaries and unrelated filler make maintenance harder. Record reasonable future ideas as TODOs or in the architecture notes, with enough context that the next person can act on them.

No medical thresholds belong in defaults. Don't add unverified assurances about delivery or protection. A contact send returning HTTP 200 is a request accepted, not proof that anybody saw it.

Version numbers should reflect real changes. Keep the changelog accurate; a large release can have a short summary and several useful bullet points. Routine commits can be very brief. Run `python -m unittest discover -s tests -v` before proposing changes. Please avoid including personal readings, addresses, access tokens or live contact details in issues and logs.
