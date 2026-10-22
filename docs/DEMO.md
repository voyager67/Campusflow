# Demo walkthrough

This guide is for a short local demonstration of CampusFlow v0.1.0. It uses a fictional roster and does not connect to college systems.

## Before presenting

1. Install Python 3.10+ and follow the setup in [README.md](../README.md).
2. Start the local server and open `http://127.0.0.1:8000`.
3. Confirm that no real student names, IDs or records are entered.
4. Keep the server local unless you deliberately choose a trusted private Wi-Fi demo. Never expose this unauthenticated prototype to the public internet.

## Suggested 90-second walkthrough

1. **Overview (10 sec):** point out the faculty dashboard and the fictional/demo-mode boundary.
2. **Start a session (15 sec):** open Live attendance, choose a subject and start a session.
3. **QR token (15 sec):** show the time-limited QR and the expiry countdown. Explain that it identifies a session; it does not authenticate a student or prove presence.
4. **Check-in (20 sec):** simulate a fictional student check-in, then try the same student again to demonstrate duplicate rejection.
5. **Live list (10 sec):** show the updated present count and roster state.
6. **Reports (10 sec):** open Reports and export the CSV.
7. **Close with the next step (10 sec):** explain that real use would require institutional approval, identity integration, authorization, and security/privacy review.

## Questions worth asking a college stakeholder

- Which attendance workflow causes the most work today?
- Who should be allowed to start, review and correct a session?
- What identity provider and roster source are approved?
- What evidence is required to handle proxy attendance fairly?
- What retention period, audit trail and appeal process are required?
- What manual fallback is used if Wi-Fi or the service fails?

## Truthful demo statement

> CampusFlow is an early, student-built demonstration of a potential digital attendance workflow. It is not connected to the college's systems and is not approved for official attendance. This demo uses fictional records. The aim is to validate the workflow and learn what security, privacy and operational requirements a real pilot would need to satisfy.
