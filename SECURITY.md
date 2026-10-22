# Security notes

CampusFlow is an educational prototype, not a secure production system.

## Safe use

- Use only fictional sample data.
- The server binds to `127.0.0.1` by default. Keep it local unless you explicitly enable a trusted-LAN phone demonstration.
- Do not expose the development server directly to the public internet.
- Stop the server when the demo is finished.
- Do not commit student records, SQLite database files, credentials, API keys, private network information or other sensitive data.

To opt in to a same-Wi-Fi phone demo, set `CAMPUSFLOW_LAN=1` before starting the server. This changes the bind address to all network interfaces; the demo endpoints do not have production authentication. Use this option only on a trusted private network you control, then stop the server and return to local-only mode.

## Known limitations

- There is no production-grade user authentication or role-based access control.
- The demo student selector is for simulation, not proof of identity.
- A rotating QR token identifies a session; it does not prove that a student is physically present and cannot fully prevent proxy attendance.
- The demo API is unauthenticated, and data is stored in a local SQLite file.
- The project has not undergone a formal security or privacy assessment.

## Before a real pilot

Obtain institutional approval and complete a security/privacy review. Implement institution-managed authentication, server-side authorisation, transport security, rate limiting and abuse controls, robust session/token handling, auditable edits, data minimisation, backup and retention controls, dependency updates, monitoring and a tested manual fallback. Have deployment and threat-model decisions reviewed by qualified staff before using real records.

If you discover a security issue, do not publish real personal data or exploit details in a public issue. Contact the project maintainer privately first.
