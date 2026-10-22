# CampusFlow v0.1.0 — First Demonstration Release

CampusFlow is a student-built concept for reducing manual classroom-attendance work with a faculty-controlled, short-lived QR code and an exportable digital register.

## Highlights

- A polished, responsive faculty dashboard.
- Live lecture sessions with a QR token that expires after 25 seconds.
- A fictional 40-student roster for presentations without using real records.
- Duplicate check-in rejection within a session.
- Local SQLite persistence and CSV exports.
- Windows and macOS/Linux launch scripts.
- A local-only network default, with explicit opt-in for trusted-LAN phone demonstrations.
- Automated smoke tests and a GitHub Actions workflow.

## Get started

1. Extract the source archive.
2. Install Python 3.10 or newer.
3. Run `run_windows.bat` on Windows, or run `python3 -m pip install -r requirements.txt` followed by `python3 server.py` on macOS/Linux.
4. Open `http://127.0.0.1:8000`.
5. Choose **Live attendance**, start a demo lecture, simulate a fictional student check-in, and export the CSV from **Reports**.

For setup variations and the optional trusted-LAN phone demo, read `README.md`.

## Important notice


## Recommended tag

`v0.1.0`
