from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time


DB_PATH = Path(__file__).with_name("rics_portal.db")
SESSION_COOKIE = "rics_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def now_ts():
    return int(time.time())


def normalize_username(value):
    return (value or "").strip().lower()


def normalize_email(value):
    return (value or "").strip().lower()


def normalize_mobile(value):
    return (value or "").strip()


def mobile_digits(value):
    return re.sub(r"\D", "", normalize_mobile(value))


def hash_password(password):
    if not isinstance(password, str) or not password:
        raise ValueError("password_required")
    iterations = 210000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        algo, iteration_text, salt_hex, digest_hex = (stored or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    db = get_db()
    try:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK(role IN ('admin','learner')),
                password_hash TEXT NOT NULL,
                email TEXT,
                mobile_raw TEXT,
                mobile_digits TEXT,
                created_at INTEGER NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
            ON users(email) WHERE email IS NOT NULL AND email != '';

            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_mobile_digits_unique
            ON users(mobile_digits) WHERE mobile_digits IS NOT NULL AND mobile_digits != '';

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','learner')),
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS progress (
                user_id INTEGER NOT NULL,
                lesson_key TEXT NOT NULL,
                completed_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, lesson_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value_text TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            """
        )

        admin_username = normalize_username(os.getenv("RICS_ADMIN_USERNAME", "admin"))
        admin_password = os.getenv("RICS_ADMIN_PASSWORD", "admin123123")
        existing = db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (admin_username,),
        ).fetchone()
        if existing is None:
            db.execute(
                """
                INSERT INTO users(username, role, password_hash, email, mobile_raw, mobile_digits, created_at)
                VALUES(?, 'admin', ?, '', '', '', ?)
                """,
                (admin_username, hash_password(admin_password), now_ts()),
            )
        elif not verify_password(admin_password, existing["password_hash"]):
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(admin_password), existing["id"]),
            )

        db.commit()
    finally:
        db.close()


class RangeRequestHandler(SimpleHTTPRequestHandler):
    """Static server with HTTP Range support and a local auth/data API."""

    def _send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _parse_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def _cookie_value(self, name):
        cookie_header = self.headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            if key.strip() == name:
                return value.strip()
        return ""

    def _session_cookie_header(self, token):
        return (
            f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL_SECONDS}"
        )

    def _expired_session_cookie_header(self):
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    def _load_session(self, db):
        token = self._cookie_value(SESSION_COOKIE)
        if not token:
            return None

        row = db.execute(
            """
            SELECT s.token, s.user_id, s.role, s.created_at, s.expires_at, u.username
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            return None

        if int(row["expires_at"]) <= now_ts():
            db.execute("DELETE FROM sessions WHERE token = ?", (token,))
            db.commit()
            return None

        return {
            "token": row["token"],
            "user_id": int(row["user_id"]),
            "username": row["username"],
            "role": row["role"],
            "loginAt": int(row["created_at"]) * 1000,
        }

    def _require_session(self, db):
        session = self._load_session(db)
        if session is None:
            self._send_json(401, {"ok": False, "error": "Not authenticated."})
            return None
        return session

    def _require_admin(self, db):
        session = self._require_session(db)
        if session is None:
            return None
        if session["role"] != "admin":
            self._send_json(403, {"ok": False, "error": "Admin access required."})
            return None
        return session

    def _api_get_auth_session(self, db):
        session = self._load_session(db)
        if session is None:
            self._send_json(200, {"ok": True, "session": None})
            return

        self._send_json(
            200,
            {
                "ok": True,
                "session": {
                    "username": session["username"],
                    "role": session["role"],
                    "loginAt": session["loginAt"],
                },
            },
        )

    def _api_post_auth_login(self, db):
        body = self._parse_json_body()
        if body is None:
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload."})
            return

        username = normalize_username(body.get("username"))
        password = body.get("password") or ""
        if not username or not password:
            self._send_json(400, {"ok": False, "error": "Username and password are required."})
            return

        row = db.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            self._send_json(401, {"ok": False, "error": "Invalid username or password."})
            return

        token = secrets.token_urlsafe(32)
        created = now_ts()
        expires = created + SESSION_TTL_SECONDS
        db.execute(
            "INSERT INTO sessions(token, user_id, role, created_at, expires_at) VALUES(?, ?, ?, ?, ?)",
            (token, int(row["id"]), row["role"], created, expires),
        )
        db.commit()

        self._send_json(
            200,
            {
                "ok": True,
                "session": {
                    "username": row["username"],
                    "role": row["role"],
                    "loginAt": created * 1000,
                },
            },
            extra_headers={"Set-Cookie": self._session_cookie_header(token)},
        )

    def _api_post_auth_logout(self, db):
        token = self._cookie_value(SESSION_COOKIE)
        if token:
            db.execute("DELETE FROM sessions WHERE token = ?", (token,))
            db.commit()
        self._send_json(
            200,
            {"ok": True},
            extra_headers={"Set-Cookie": self._expired_session_cookie_header()},
        )

    def _api_post_auth_register(self, db):
        body = self._parse_json_body()
        if body is None:
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload."})
            return

        username = normalize_username(body.get("username"))
        password = body.get("password") or ""
        email = normalize_email(body.get("email"))
        mobile_raw = normalize_mobile(body.get("mobile"))
        mobile_key = mobile_digits(mobile_raw)

        if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
            self._send_json(
                400,
                {
                    "ok": False,
                    "error": "Username must be 3-32 chars and use letters, numbers, dot, underscore, or hyphen.",
                },
            )
            return

        admin_name = normalize_username(os.getenv("RICS_ADMIN_USERNAME", "admin"))
        if username == admin_name:
            self._send_json(400, {"ok": False, "error": "This username is reserved."})
            return

        if len(password) < 6:
            self._send_json(400, {"ok": False, "error": "Password must be at least 6 characters."})
            return

        if not re.fullmatch(r"[a-z0-9._%+-]+@gmail\.com", email):
            self._send_json(
                400,
                {"ok": False, "error": "Please provide a valid Gmail address (example@gmail.com)."},
            )
            return

        if len(mobile_key) < 7 or len(mobile_key) > 15:
            self._send_json(400, {"ok": False, "error": "Please provide a valid mobile number."})
            return

        exists = db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            self._send_json(409, {"ok": False, "error": "User already exists."})
            return

        email_exists = db.execute(
            "SELECT 1 FROM users WHERE email = ? AND email != ''",
            (email,),
        ).fetchone()
        if email_exists:
            self._send_json(409, {"ok": False, "error": "This Gmail is already registered."})
            return

        mobile_exists = db.execute(
            "SELECT 1 FROM users WHERE mobile_digits = ? AND mobile_digits != ''",
            (mobile_key,),
        ).fetchone()
        if mobile_exists:
            self._send_json(409, {"ok": False, "error": "This mobile number is already registered."})
            return

        db.execute(
            """
            INSERT INTO users(username, role, password_hash, email, mobile_raw, mobile_digits, created_at)
            VALUES(?, 'learner', ?, ?, ?, ?, ?)
            """,
            (username, hash_password(password), email, mobile_raw, mobile_key, now_ts()),
        )
        db.commit()
        self._send_json(200, {"ok": True, "username": username})

    def _api_get_users_exists(self, db, query):
        username = normalize_username((query.get("username") or [""])[0])
        if not username:
            self._send_json(200, {"ok": True, "exists": False})
            return

        row = db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        self._send_json(200, {"ok": True, "exists": bool(row)})

    def _api_get_progress(self, db, query):
        session = self._require_session(db)
        if session is None:
            return

        requested = normalize_username((query.get("username") or [""])[0])
        target_username = requested or session["username"]
        if session["role"] != "admin":
            target_username = session["username"]

        user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (target_username,),
        ).fetchone()
        if user is None:
            self._send_json(404, {"ok": False, "error": "User not found."})
            return

        rows = db.execute(
            "SELECT lesson_key, completed_at FROM progress WHERE user_id = ?",
            (int(user["id"]),),
        ).fetchall()
        progress = {r["lesson_key"]: int(r["completed_at"]) for r in rows}
        self._send_json(200, {"ok": True, "progress": progress})

    def _api_put_progress(self, db):
        session = self._require_session(db)
        if session is None:
            return

        body = self._parse_json_body()
        if body is None:
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload."})
            return

        requested = normalize_username(body.get("username"))
        target_username = requested or session["username"]
        if session["role"] != "admin":
            target_username = session["username"]

        progress = body.get("progress")
        if not isinstance(progress, dict):
            self._send_json(400, {"ok": False, "error": "Progress payload must be an object."})
            return

        user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (target_username,),
        ).fetchone()
        if user is None:
            self._send_json(404, {"ok": False, "error": "User not found."})
            return

        user_id = int(user["id"])
        db.execute("DELETE FROM progress WHERE user_id = ?", (user_id,))
        for key, value in progress.items():
            lesson_key = (str(key) if key is not None else "").strip()
            if not lesson_key:
                continue
            if len(lesson_key) > 1200:
                continue
            try:
                completed_at = int(value)
            except Exception:
                completed_at = int(time.time() * 1000)
            db.execute(
                "INSERT INTO progress(user_id, lesson_key, completed_at) VALUES(?, ?, ?)",
                (user_id, lesson_key, completed_at),
            )
        db.commit()
        self._send_json(200, {"ok": True})

    def _api_get_meta(self, db):
        session = self._require_session(db)
        if session is None:
            return

        row = db.execute("SELECT value_text FROM meta WHERE key = 'portal_meta'").fetchone()
        if row is None:
            self._send_json(200, {"ok": True, "meta": {}})
            return

        try:
            meta = json.loads(row["value_text"])
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}
        self._send_json(200, {"ok": True, "meta": meta})

    def _api_put_meta(self, db):
        session = self._require_session(db)
        if session is None:
            return

        body = self._parse_json_body()
        if body is None:
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload."})
            return

        incoming = body.get("meta")
        if not isinstance(incoming, dict):
            self._send_json(400, {"ok": False, "error": "Meta payload must be an object."})
            return

        existing_row = db.execute("SELECT value_text FROM meta WHERE key = 'portal_meta'").fetchone()
        current = {}
        if existing_row:
            try:
                parsed = json.loads(existing_row["value_text"])
                if isinstance(parsed, dict):
                    current = parsed
            except Exception:
                current = {}

        current.update(incoming)
        serialized = json.dumps(current, separators=(",", ":"))
        ts = now_ts()
        db.execute(
            """
            INSERT INTO meta(key, value_text, updated_at) VALUES('portal_meta', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_text = excluded.value_text, updated_at = excluded.updated_at
            """,
            (serialized, ts),
        )
        db.commit()
        self._send_json(200, {"ok": True})

    def _api_get_admin_summary(self, db, query):
        session = self._require_admin(db)
        if session is None:
            return

        try:
            total = max(0, int((query.get("totalLessons") or ["0"])[0]))
        except Exception:
            total = 0

        rows = db.execute(
            """
            SELECT
                u.username,
                u.email,
                u.mobile_raw,
                u.created_at,
                COUNT(p.lesson_key) AS done,
                COALESCE(MAX(p.completed_at), 0) AS last_activity
            FROM users u
            LEFT JOIN progress p ON p.user_id = u.id
            WHERE u.role = 'learner'
            GROUP BY u.id
            ORDER BY u.username ASC
            """
        ).fetchall()

        users = []
        for r in rows:
            done = int(r["done"] or 0)
            pct = int(round((done / total) * 100)) if total > 0 else 0
            users.append(
                {
                    "username": r["username"],
                    "email": r["email"] or "",
                    "mobile": r["mobile_raw"] or "",
                    "done": done,
                    "pct": pct,
                    "lastActivity": int(r["last_activity"] or 0),
                    "createdAt": int(r["created_at"] or 0) * 1000,
                }
            )

        self._send_json(200, {"ok": True, "users": users})

    def _api_delete_admin_user(self, db, username):
        session = self._require_admin(db)
        if session is None:
            return

        name = normalize_username(username)
        if not name:
            self._send_json(400, {"ok": False, "error": "User not found."})
            return

        row = db.execute(
            "SELECT id, role FROM users WHERE username = ?",
            (name,),
        ).fetchone()
        if row is None:
            self._send_json(404, {"ok": False, "error": "User not found."})
            return
        if row["role"] != "learner":
            self._send_json(400, {"ok": False, "error": "Cannot delete this user."})
            return

        db.execute("DELETE FROM users WHERE id = ?", (int(row["id"]),))
        db.commit()
        self._send_json(200, {"ok": True})

    def _route_api(self, method, path, query):
        db = get_db()
        try:
            if method == "GET" and path == "/api/auth/session":
                self._api_get_auth_session(db)
                return True
            if method == "POST" and path == "/api/auth/login":
                self._api_post_auth_login(db)
                return True
            if method == "POST" and path == "/api/auth/logout":
                self._api_post_auth_logout(db)
                return True
            if method == "POST" and path == "/api/auth/register":
                self._api_post_auth_register(db)
                return True
            if method == "GET" and path == "/api/users/exists":
                self._api_get_users_exists(db, query)
                return True
            if method == "GET" and path == "/api/progress":
                self._api_get_progress(db, query)
                return True
            if method == "PUT" and path == "/api/progress":
                self._api_put_progress(db)
                return True
            if method == "GET" and path == "/api/meta":
                self._api_get_meta(db)
                return True
            if method == "PUT" and path == "/api/meta":
                self._api_put_meta(db)
                return True
            if method == "GET" and path == "/api/admin/summary":
                self._api_get_admin_summary(db, query)
                return True
            if method == "DELETE" and path.startswith("/api/admin/users/"):
                self._api_delete_admin_user(db, path.split("/api/admin/users/", 1)[1])
                return True
            return False
        finally:
            db.close()

    def _handle_api(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            return False

        query = parse_qs(parsed.query, keep_blank_values=False)
        routed = self._route_api(method, path, query)
        if not routed:
            self._send_json(404, {"ok": False, "error": "Not found."})
        return True

    def do_GET(self):
        if self._handle_api("GET"):
            return
        super().do_GET()

    def do_POST(self):
        if self._handle_api("POST"):
            return
        self.send_error(404, "Not found")

    def do_PUT(self):
        if self._handle_api("PUT"):
            return
        self.send_error(404, "Not found")

    def do_DELETE(self):
        if self._handle_api("DELETE"):
            return
        self.send_error(404, "Not found")

    def send_head(self):
        path = self.translate_path(urlparse(self.path).path)
        if os.path.isdir(path):
            return super().send_head()

        ctype = self.guess_type(path)
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        size = fs.st_size
        range_header = self.headers.get("Range")

        if range_header:
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                start_s, end_s = match.groups()
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else size - 1
                if start > end or end >= size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    f.close()
                    return None

                self.send_response(206)
                self.send_header("Content-type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()

                f.seek(start)
                self._range = (start, end)
                return f

        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._range = None
        return f

    def copyfile(self, source, outputfile):
        range_info = getattr(self, "_range", None)
        if range_info is None:
            return super().copyfile(source, outputfile)

        start, end = range_info
        remaining = end - start + 1
        chunk_size = 64 * 1024
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = source.read(read_size)
            if not data:
                break
            outputfile.write(data)
            remaining -= len(data)


def main():
    init_db()
    os.chdir(Path(__file__).parent)
    server = ThreadingHTTPServer(("0.0.0.0", 8080), RangeRequestHandler)
    print("Serving with range support on http://localhost:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
