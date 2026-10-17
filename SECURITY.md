# Security and privacy

No Abbott account credentials, email addresses or historical glucose database are required by LibreBeacon. Home Assistant access is through a bearer token. The app attempts to store the token using `keyring` and the operating-system credential vault; configuration JSON intentionally excludes it. Contact routing is configured inside Home Assistant. Contact labels, threshold settings and entity IDs remain in the local settings JSON, so back it up responsibly.

The Home Assistant long-lived token can be powerful. Do not share it, put it in screenshots or commit it. Use HTTPS for off-network access, and do not expose the REST API directly to the public internet without proper authentication and network safeguards. You may also restrict the PC's network exposure.

Optional Home Assistant scripts can send messages to external organisations or individuals. Use explicit consent and sensible testing. Home Assistant API acceptance does not equal confirmed message delivery. Never integrate directly with emergency-service numbers for automatic dispatch.

Please report security vulnerabilities privately to the repository maintainer when the repository has been published. Do not include tokens or personal medical readings in public issues. Testing is welcome, but do not exercise this application against someone else's accounts or equipment.
