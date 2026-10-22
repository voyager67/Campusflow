"""Integration smoke tests for the CampusFlow demo server (stdlib only)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class CampusFlowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="campusflow-tests-")
        cls.port = reserve_local_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env["PORT"] = str(cls.port)
        env["CAMPUSFLOW_DB_PATH"] = str(Path(cls.temp_dir.name) / "test.sqlite3")
        env.pop("CAMPUSFLOW_LAN", None)
        cls.process = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError("CampusFlow server exited before becoming ready.")
            try:
                cls.request("/api/state")
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            cls.process.terminate()
            raise RuntimeError("CampusFlow server did not become ready within 10 seconds.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=5)
        cls.temp_dir.cleanup()

    @classmethod
    def request(cls, path: str, method: str = "GET", payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            cls.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def test_dashboard_and_fictional_roster_load(self):
        status, _, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"CampusFlow", body)

        status, _, body = self.request("/api/state")
        state = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(state["demo"])
        self.assertEqual(state["metrics"]["studentCount"], 40)
        self.assertEqual(len(state["students"]), 40)

    def test_invalid_token_is_rejected(self):
        status, _, body = self.request(
            "/api/checkin", "POST", {"token": "not-a-valid-token", "studentId": "STU001"}
        )
        self.assertEqual(status, 410)
        self.assertIn(b"expired", body.lower())

    def test_session_qr_checkin_duplicate_and_csv_flow(self):
        status, _, body = self.request(
            "/api/session/start",
            "POST",
            {"subject": "Release Smoke Test", "division": "IT-3", "faculty": "Demo Faculty"},
        )
        self.assertEqual(status, 200, body.decode("utf-8"))
        self.assertTrue(json.loads(body)["ok"])

        status, _, body = self.request("/api/state")
        active = json.loads(body)["activeSession"]
        self.assertIsNotNone(active)
        token = active["token"]

        status, headers, image = self.request(f"/api/qr?token={token}")
        self.assertEqual(status, 200)
        self.assertTrue(headers.get("Content-Type", "").startswith("image/png"))
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))

        status, _, body = self.request(
            "/api/checkin", "POST", {"token": token, "studentId": "STU001"}
        )
        self.assertEqual(status, 200, body.decode("utf-8"))

        status, _, body = self.request(
            "/api/checkin", "POST", {"token": token, "studentId": "STU001"}
        )
        self.assertEqual(status, 409)
        self.assertIn(b"already recorded", body.lower())

        status, _, body = self.request("/api/export.csv")
        self.assertEqual(status, 200)
        self.assertIn(b"Release Smoke Test", body)
        self.assertIn(b"Student Name", body)

        status, _, body = self.request("/api/session/stop", "POST", {})
        self.assertEqual(status, 200)
        status, _, _ = self.request(
            "/api/checkin", "POST", {"token": token, "studentId": "STU002"}
        )
        self.assertEqual(status, 410)


if __name__ == "__main__":
    unittest.main(verbosity=2)
