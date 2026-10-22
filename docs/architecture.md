# Architecture overview

CampusFlow is a small local web prototype designed to make a classroom-attendance workflow easy to demonstrate without a separate student app.

## Components

- **Browser UI (`index.html`, `styles.css`, `app.js`)** — faculty dashboard, fictional student check-in flow, session summaries and reports.
- **Python HTTP server (`server.py`)** — serves the UI, exposes the demo API, generates QR images and validates short-lived tokens.
- **SQLite (`campusflow_demo.sqlite3`)** — stores the fictional roster, sessions, tokens, check-ins and basic demo audit events. Created on first launch; it is not bundled.
- **QR generator (`qrcode[pil]`)** — renders a QR that opens the student check-in page with a session token.

## Demo flow

1. Faculty starts a session and chooses a subject, division and display name.
2. The server creates a random token that expires after 25 seconds; expired tokens are invalidated when a new token is issued.
3. The UI displays a QR image linked to the active session.
4. A fictional demo account is selected and submitted with the token.
5. The server verifies token expiry, session status and roster membership, then relies on a database uniqueness constraint to reject repeat check-ins for the same student in a session.
6. The dashboard reads current state and can export a CSV report.

## Trust boundaries and non-goals

The QR token identifies the current demo session, not the human scanning it. The student selector is not authentication. Because the API is unauthenticated, even LAN mode is only suitable for a trusted, private demonstration network. Local-only binding is the default. The prototype does not integrate with any college gate, face terminal, LMS, portal or official register.

A real deployment would require institution-approved authentication, authorisation, secure transport, roster ownership, correction workflows and auditable change records, data retention and backup rules, threat modelling, abuse controls, operational monitoring, and privacy/security approval. Those requirements are not implemented here.
