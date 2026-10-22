# Changelog

Notable changes to CampusFlow are documented here.

## [0.1.0] — 2026-10-22

First packaged demonstration release.

### Added
- Responsive faculty dashboard with overview, live attendance, roster and report views.
- Short-lived rotating QR tokens for live demo sessions.
- Fictional 40-student roster and sample history generated locally.
- Duplicate check-in prevention within a lecture session.
- Local SQLite persistence and CSV export.
- Windows and macOS/Linux launch scripts.
- Security notes, a SAKEC pilot discussion guide, smoke tests and GitHub Actions CI.

### Changed
- Server now binds to the local computer by default; LAN access requires explicit opt-in with `CAMPUSFLOW_LAN=1`.
- Demo branding and version labels clarified.

