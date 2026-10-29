#!/usr/bin/env python3
"""CampusFlow prototype server. Demo only; not suitable for production deployment."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone
import json, os, socket, sqlite3, secrets, csv, io, mimetypes
from pathlib import Path

try:
    import qrcode
except ImportError:
    raise SystemExit("Missing dependency. Run: python -m pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("CAMPUSFLOW_DB_PATH", str(ROOT / "campusflow_demo.sqlite3"))).expanduser()
LAN_ENABLED = os.environ.get("CAMPUSFLOW_LAN", "").strip().lower() in {"1", "true", "yes", "on"}
# Safer by default: the demo is reachable only from this computer. Explicitly opt in
# to LAN access when presenting from a phone on a trusted private network.
HOST = "0.0.0.0" if LAN_ENABLED else "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))
TOKEN_TTL = 25

FIRST = ["Aarav", "Ananya", "Ishaan", "Diya", "Kabir", "Saanvi", "Reyansh", "Aditi", "Vivaan", "Myra", "Advik", "Sara", "Arjun", "Kiara", "Rohan", "Ira", "Dev", "Meera", "Neil", "Tara"]
LAST = ["Shah", "Mehta", "Patel", "Kulkarni", "Desai", "Rao", "Joshi", "Kapoor", "Nair", "Singh", "Pillai", "Malhotra", "Iyer", "Gupta", "Chopra", "Bose", "Khan", "Menon", "Jain", "Sethi"]


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt=None):
    return (dt or now_utc()).isoformat(timespec="seconds")


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS students (
          student_id TEXT PRIMARY KEY, roll_no TEXT UNIQUE NOT NULL, name TEXT NOT NULL, division TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          session_id TEXT PRIMARY KEY, subject TEXT NOT NULL, division TEXT NOT NULL, faculty TEXT NOT NULL,
          started_at TEXT NOT NULL, ended_at TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attendance (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, student_id TEXT NOT NULL,
          marked_at TEXT NOT NULL, method TEXT NOT NULL DEFAULT 'QR',
          UNIQUE(session_id, student_id),
          FOREIGN KEY(session_id) REFERENCES sessions(session_id), FOREIGN KEY(student_id) REFERENCES students(student_id)
        );
        CREATE TABLE IF NOT EXISTS tokens (
          token TEXT PRIMARY KEY, session_id TEXT NOT NULL, issued_at TEXT NOT NULL, expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
          entity TEXT NOT NULL, created_at TEXT NOT NULL, note TEXT NOT NULL
        );
        """)
        count = db.execute("SELECT COUNT(*) n FROM students").fetchone()["n"]
        if count == 0:
            students = []
            for i in range(40):
                name = f"{FIRST[i % len(FIRST)]} {LAST[(i * 7 + i // 3) % len(LAST)]}"
                sid = f"STU{i+1:03d}"
                students.append((sid, f"IT3-{i+1:03d}", name, "IT-3"))
            db.executemany("INSERT INTO students VALUES (?,?,?,?)", students)
            # Clearly fictional seeded history, so the pitch dashboard is populated on first launch.
            subjects = ["Data Structures", "Database Management Systems", "Discrete Mathematics", "Computer Networks"]
            student_ids = [r[0] for r in students]
            for si in range(6):
                started = now_utc() - timedelta(hours=(si + 1) * 2)
                sid = f"DEMO-HIST-{si+1:03d}"
                subject = subjects[si % len(subjects)]
                db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)", (sid, subject, "IT-3", "Prof. Demo Faculty", iso(started), iso(started + timedelta(minutes=55)), "completed"))
                present_count = 29 + ((si * 3) % 9)
                # Seed a subset of the fictional roster.
                for student_id in student_ids[:present_count]:
                    db.execute("INSERT OR IGNORE INTO attendance(session_id,student_id,marked_at,method) VALUES (?,?,?,?)", (sid, student_id, iso(started + timedelta(minutes=2)), "QR"))
            db.execute("INSERT INTO audit(actor,action,entity,created_at,note) VALUES (?,?,?,?,?)", ("System", "INITIALISE", "Demo data", iso(), "Created fictional prototype roster and sample history"))


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def fresh_token(db, session_id):
    current = db.execute("SELECT token, expires_at FROM tokens WHERE session_id=? ORDER BY issued_at DESC LIMIT 1", (session_id,)).fetchone()
    now = now_utc()
    if current:
        try:
            exp = datetime.fromisoformat(current["expires_at"])
        except Exception:
            exp = now
        if exp > now:
            return current["token"], current["expires_at"]
    token = secrets.token_urlsafe(16)
    expires = now + timedelta(seconds=TOKEN_TTL)
    # Immediately invalidate any previous token when rotating.
    db.execute("UPDATE tokens SET expires_at=? WHERE session_id=?", (iso(now), session_id))
    db.execute("INSERT INTO tokens(token,session_id,issued_at,expires_at) VALUES (?,?,?,?)", (token, session_id, iso(now), iso(expires)))
    db.commit()
    return token, iso(expires)


def session_dict(db, row):
    token, expiry = fresh_token(db, row["session_id"])
    present = db.execute("SELECT COUNT(*) n FROM attendance WHERE session_id=?", (row["session_id"],)).fetchone()["n"]
    total = db.execute("SELECT COUNT(*) n FROM students WHERE division=?", (row["division"],)).fetchone()["n"]
    return {"sessionId": row["session_id"], "subject": row["subject"], "division": row["division"], "faculty": row["faculty"], "startedAt": row["started_at"], "status": row["status"], "present": present, "total": total, "token": token, "expiresAt": expiry, "ttl": TOKEN_TTL}


def get_state():
    with connect() as db:
        students = [dict(studentId=r["student_id"], rollNo=r["roll_no"], name=r["name"], division=r["division"]) for r in db.execute("SELECT * FROM students ORDER BY roll_no")]
        live = db.execute("SELECT * FROM sessions WHERE status='live' ORDER BY started_at DESC LIMIT 1").fetchone()
        active = session_dict(db, live) if live else None
        sessions = []
        for r in db.execute("SELECT s.*, (SELECT COUNT(*) FROM attendance a WHERE a.session_id=s.session_id) AS present FROM sessions s ORDER BY started_at DESC LIMIT 8"):
            sessions.append({"sessionId": r["session_id"], "subject": r["subject"], "division": r["division"], "faculty": r["faculty"], "startedAt": r["started_at"], "endedAt": r["ended_at"], "status": r["status"], "present": r["present"]})
        recent = []
        rows = db.execute("SELECT a.*, st.name, st.roll_no, s.subject FROM attendance a JOIN students st ON st.student_id=a.student_id JOIN sessions s ON s.session_id=a.session_id ORDER BY a.marked_at DESC LIMIT 12")
        recent = [{"name": r["name"], "rollNo": r["roll_no"], "subject": r["subject"], "markedAt": r["marked_at"], "method": r["method"]} for r in rows]
        total_sessions = db.execute("SELECT COUNT(*) n FROM sessions WHERE status='completed'").fetchone()["n"]
        # Demo data is seeded from six fictional sessions. Use completed sessions as the sample dashboard baseline.
        completed_sessions = db.execute("SELECT session_id FROM sessions WHERE status='completed' ORDER BY started_at DESC LIMIT 6").fetchall()
        ratios = []
        for s in completed_sessions:
            present = db.execute("SELECT COUNT(*) n FROM attendance WHERE session_id=?", (s["session_id"],)).fetchone()["n"]
            roster = db.execute("SELECT COUNT(*) n FROM students").fetchone()["n"]
            if roster: ratios.append(present / roster)
        avg_pct = round(sum(ratios) / len(ratios) * 100) if ratios else 0
        today = now_utc().date().isoformat()
        today_sessions = db.execute("SELECT COUNT(*) n FROM sessions WHERE substr(started_at,1,10)=?", (today,)).fetchone()["n"]
        today_present = db.execute("SELECT COUNT(*) n FROM attendance WHERE substr(marked_at,1,10)=?", (today,)).fetchone()["n"]
        return {"students": students, "activeSession": active, "sessions": sessions, "recentAttendance": recent, "metrics": {"studentCount": len(students), "averageAttendance": avg_pct, "completedSessions": total_sessions, "todayCheckIns": today_present, "todaySessions": today_sessions}, "demo": True, "serverIp": local_ip() if LAN_ENABLED else "127.0.0.1", "tokenTtl": TOKEN_TTL}


class Handler(BaseHTTPRequestHandler):
    server_version = "CampusFlowDemo/0.1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_bytes(self, data, ctype="application/octet-stream", status=200, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra_headers:
            for k, v in extra_headers.items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, status=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def read_json(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n > 100_000: return {}
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_json(get_state()); return
        if parsed.path == "/api/session-attendance":
            params = parse_qs(parsed.query)
            session_id = params.get("sessionId", [""])[0]
            with connect() as db:
                rows = db.execute("SELECT a.student_id,st.roll_no,st.name,a.marked_at,a.method FROM attendance a JOIN students st ON st.student_id=a.student_id WHERE a.session_id=? ORDER BY a.marked_at DESC", (session_id,)).fetchall()
            self.send_json({"records":[{"studentId":r["student_id"],"rollNo":r["roll_no"],"name":r["name"],"markedAt":r["marked_at"],"method":r["method"]} for r in rows]}); return
        if parsed.path == "/api/qr":
            token = parse_qs(parsed.query).get("token", [""])[0]
            with connect() as db:
                token_row = db.execute("SELECT t.*,s.status FROM tokens t JOIN sessions s ON s.session_id=t.session_id WHERE token=?", (token,)).fetchone()
                if not token_row or token_row["status"] != "live" or datetime.fromisoformat(token_row["expires_at"]) <= now_utc():
                    self.send_bytes(b"QR expired", "text/plain", 410); return
            host = self.headers.get("Host", f"127.0.0.1:{PORT}")
            hostname = host.rsplit(":", 1)[0].strip("[]") if ":" in host else host
            port = host.rsplit(":", 1)[1] if ":" in host else str(PORT)
            if not LAN_ENABLED:
                hostname = "127.0.0.1"
            elif hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                hostname = local_ip()
            url = f"http://{hostname}:{port}/student?token={token}"
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=3)
            qr.add_data(url); qr.make(fit=True)
            image = qr.make_image(fill_color="#10231f", back_color="#ffffff")
            out = io.BytesIO(); image.save(out, format="PNG")
            self.send_bytes(out.getvalue(), "image/png"); return
        if parsed.path == "/api/export.csv":
            with connect() as db:
                rows = db.execute("SELECT s.session_id,s.subject,s.division,s.faculty,s.started_at,s.status,st.roll_no,st.name,a.marked_at,a.method FROM sessions s LEFT JOIN attendance a ON a.session_id=s.session_id LEFT JOIN students st ON st.student_id=a.student_id ORDER BY s.started_at DESC, st.roll_no")
                out = io.StringIO(); writer = csv.writer(out)
                writer.writerow(["Session ID", "Subject", "Division", "Faculty", "Session Started", "Session Status", "Roll No", "Student Name", "Attendance Time", "Method"])
                writer.writerows([tuple(r) for r in rows])
            self.send_bytes(out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", extra_headers={"Content-Disposition":"attachment; filename=campusflow-attendance-demo.csv"}); return
        # App shell for both teacher dashboard and phone-based student check-in.
        if parsed.path.startswith("/static/"):
            name = Path(parsed.path).name
            allowed = {"styles.css", "app.js"}
            if name not in allowed:
                self.send_bytes(b"Not found", "text/plain", 404); return
            p = ROOT / name
            self.send_bytes(p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream"); return
        if parsed.path in ("/", "/index.html", "/student"):
            self.send_bytes((ROOT / "index.html").read_bytes(), "text/html; charset=utf-8"); return
        self.send_bytes(b"Not found", "text/plain", 404)

    def do_POST(self):
        path = urlparse(self.path).path
        data = self.read_json()
        if path == "/api/session/start":
            subject = str(data.get("subject", "Data Structures"))[:100]
            division = str(data.get("division", "IT-3"))[:30]
            faculty = str(data.get("faculty", "Demo Faculty"))[:100]
            with connect() as db:
                live = db.execute("SELECT session_id FROM sessions WHERE status='live' LIMIT 1").fetchone()
                if live:
                    self.send_json({"error":"A demo session is already live. End it before starting another."}, 409); return
                session_id = "CF-" + now_utc().strftime("%y%m%d-%H%M%S") + "-" + secrets.token_hex(2).upper()
                db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)", (session_id, subject, division, faculty, iso(), None, "live"))
                db.execute("INSERT INTO audit(actor,action,entity,created_at,note) VALUES (?,?,?,?,?)", (faculty, "START_SESSION", session_id, iso(), f"Started {subject} for {division}"))
                db.commit(); fresh_token(db, session_id)
            self.send_json({"ok":True,"sessionId":session_id}); return
        if path == "/api/session/stop":
            with connect() as db:
                row = db.execute("SELECT * FROM sessions WHERE status='live' ORDER BY started_at DESC LIMIT 1").fetchone()
                if not row:
                    self.send_json({"error":"There is no live session to end."}, 400); return
                db.execute("UPDATE sessions SET status='completed',ended_at=? WHERE session_id=?", (iso(), row["session_id"]))
                db.execute("UPDATE tokens SET expires_at=? WHERE session_id=?", (iso(), row["session_id"]))
                db.execute("INSERT INTO audit(actor,action,entity,created_at,note) VALUES (?,?,?,?,?)", (row["faculty"], "END_SESSION", row["session_id"], iso(), "Attendance session closed"))
                db.commit()
            self.send_json({"ok":True}); return
        if path == "/api/checkin":
            token = str(data.get("token", ""))
            student_id = str(data.get("studentId", ""))
            with connect() as db:
                tok = db.execute("SELECT t.*,s.status,s.subject,s.division FROM tokens t JOIN sessions s ON s.session_id=t.session_id WHERE t.token=?", (token,)).fetchone()
                if not tok or tok["status"] != "live" or datetime.fromisoformat(tok["expires_at"]) <= now_utc():
                    self.send_json({"error":"This QR code has expired. Please scan the latest code shown by your teacher."}, 410); return
                student = db.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
                if not student or student["division"] != tok["division"]:
                    self.send_json({"error":"Student is not in this session's roster."}, 403); return
                try:
                    db.execute("INSERT INTO attendance(session_id,student_id,marked_at,method) VALUES (?,?,?,?)", (tok["session_id"], student_id, iso(), "QR"))
                    db.execute("INSERT INTO audit(actor,action,entity,created_at,note) VALUES (?,?,?,?,?)", (student_id, "CHECK_IN", tok["session_id"], iso(), f"QR check-in for {tok['subject']}"))
                    db.commit()
                except sqlite3.IntegrityError:
                    self.send_json({"error":"Attendance is already recorded for this student in this lecture."}, 409); return
            self.send_json({"ok":True,"message":"Attendance recorded for the demo session.","subject":tok["subject"],"studentId":student_id}); return
        if path == "/api/attendance/manual":
            session_id = str(data.get("sessionId", "")); student_id = str(data.get("studentId", "")); actor = str(data.get("actor", "Demo Faculty"))[:100]
            with connect() as db:
                session = db.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
                student = db.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
                if not session or not student or student["division"] != session["division"]:
                    self.send_json({"error":"Session or student not found."}, 404); return
                if session["status"] != "live":
                    self.send_json({"error":"Manual attendance can only be added while a demo session is live."}, 409); return
                try:
                    db.execute("INSERT INTO attendance(session_id,student_id,marked_at,method) VALUES (?,?,?,?)", (session_id, student_id, iso(), "Faculty correction"))
                except sqlite3.IntegrityError:
                    self.send_json({"error":"Attendance is already recorded for this student in this lecture."}, 409); return
                db.execute("INSERT INTO audit(actor,action,entity,created_at,note) VALUES (?,?,?,?,?)", (actor, "MANUAL_MARK", session_id, iso(), f"Marked {student_id} present by faculty correction"))
                db.commit()
            self.send_json({"ok":True}); return
        self.send_json({"error":"Not found"}, 404)


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    ip = local_ip()
    print("\n  CampusFlow • Smart Classroom Attendance")
    print("  ----------------------------------------")
    print(f"  Local dashboard: http://127.0.0.1:{PORT}")
    if LAN_ENABLED:
        print(f"  Same Wi-Fi phones: http://{ip}:{PORT}")
        print("  WARNING: LAN demo mode exposes unauthenticated demo endpoints to the network.")
        print("  Use a trusted private network only, and turn LAN mode off when finished.")
    else:
        print("  Network access: OFF (safe local-only default)")
        print("  For a phone demo on trusted private Wi-Fi, set CAMPUSFLOW_LAN=1 and restart.")
    print("  Keep this terminal open while presenting. Ctrl+C stops the demo.")
    print("  DEMO ONLY: fictional students, no authentication, local SQLite storage.\n")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nStopping CampusFlow demo...")
    finally: server.server_close()

if __name__ == "__main__": main()
