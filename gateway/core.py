"""Read-only energy adapter and bounded durable telemetry delivery."""
import base64
import json
import math
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass


CHANNELS = {
    "solar_w": "ProductionActivePower",
    "grid_w": "GridActivePower",
    "battery_w": "EssActivePower",
    "load_w": "ConsumptionActivePower",
    "battery_soc": "EssSoc",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to a redirect target.


def request_json(url, headers=None, payload=None):
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=4) as response:
        body = response.read(1024 * 1024)
        return json.loads(body) if body else None


def validate_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an HTTP(S) base URL without credentials, query or fragment")
    return value.rstrip("/")


@dataclass
class Settings:
    mode: str = "demo"
    data_origin: str = "unverified"
    openems_url: str = "http://127.0.0.1:8084"
    openems_user: str = "x"
    openems_password: str = ""
    openems_component: str = "_sum"
    thingsboard_url: str = ""
    thingsboard_token: str = ""
    interval: float = 5
    capacity: int = 17280

    def __post_init__(self):
        if self.mode not in ("demo", "openems"):
            raise ValueError("GATEWAY_MODE must be demo or openems")
        if self.data_origin not in ("unverified", "simulated", "equipment"):
            raise ValueError("OPENEMS_DATA_ORIGIN must be unverified, simulated or equipment")
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', self.openems_component):
            raise ValueError('Invalid OpenEMS component ID')
        if not math.isfinite(self.interval) or self.interval < 1 or self.capacity < 1:
            raise ValueError("Poll interval must be >= 1 second and capacity >= 1")
        validate_url(self.openems_url)
        if bool(self.thingsboard_url) != bool(self.thingsboard_token):
            raise ValueError("Set both THINGSBOARD_URL and THINGSBOARD_TOKEN")
        if self.thingsboard_url:
            validate_url(self.thingsboard_url)
        if self.mode == "demo" and self.thingsboard_url:
            raise ValueError("Demo telemetry cannot be forwarded to ThingsBoard")


class OpenEMS:
    def __init__(self, settings):
        self.settings = settings

    def read(self):
        if self.settings.mode == "demo":
            solar = round(3600 + 500 * math.sin(time.time() / 30))
            load, battery = 1700, -900
            return {"solar_w": solar, "load_w": load, "battery_w": battery,
                    "grid_w": load - solar - battery, "battery_soc": 67}
        auth = base64.b64encode(f"{self.settings.openems_user}:{self.settings.openems_password}".encode()).decode()
        # One response minimizes cross-request sample skew. Explicit allowlist below.
        component = self.settings.openems_component
        rows = request_json(self.settings.openems_url + "/rest/channel/" + component + "/.*",
                            {"Authorization": "Basic " + auth})
        if not isinstance(rows, list):
            raise ValueError("Expected OpenEMS channel array")
        mapped = {row.get("address"): row.get("value") for row in rows if isinstance(row, dict)}
        if component != '_sum':
            observed = mapped.get(component + '/LastSuccessfulRead')
            if (isinstance(observed, bool) or not isinstance(observed, (int, float))
                    or not math.isfinite(observed)
                    or not -2000 <= time.time()*1000 - observed <= 15000):
                raise ValueError('Equipment sample is unavailable or stale')
        values = {key: mapped.get(component + "/" + channel) for key, channel in CHANNELS.items()}
        for key, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError("Missing or invalid energy channel: " + key)
        if not 0 <= values["battery_soc"] <= 100:
            raise ValueError("Battery SoC outside 0..100")
        return values


class Store:
    def __init__(self, path, capacity=17280):
        self.path, self.capacity = str(path), capacity
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, payload TEXT NOT NULL, pending INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS counters (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO counters VALUES ('dropped',0)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, values, pending=False, ts=None):
        with self.connect() as db:
            db.execute("INSERT INTO samples(ts,payload,pending) VALUES (?,?,?)",
                       (ts if ts is not None else int(time.time()*1000), json.dumps(values, allow_nan=False), int(pending)))
            excess = db.execute("SELECT MAX(COUNT(*)-?,0) FROM samples", (self.capacity,)).fetchone()[0]
            if excess:
                dropped = db.execute("SELECT COUNT(*) FROM (SELECT pending FROM samples ORDER BY id LIMIT ?) WHERE pending=1", (excess,)).fetchone()[0]
                db.execute("UPDATE counters SET value=value+? WHERE key='dropped'", (dropped,))
                db.execute("DELETE FROM samples WHERE id IN (SELECT id FROM samples ORDER BY id LIMIT ?)", (excess,))

    def samples(self, limit=120, pending=False):
        with self.connect() as db:
            rows = db.execute("SELECT id,ts,payload FROM samples " + ("WHERE pending=1 ORDER BY id" if pending else "ORDER BY id DESC") + " LIMIT ?", (limit,)).fetchall()
        return [{"id": row[0], "ts": row[1], "values": json.loads(row[2])} for row in rows]

    def acknowledge(self, ids):
        with self.connect() as db:
            db.executemany("UPDATE samples SET pending=0 WHERE id=?", [(i,) for i in ids])

    def status(self):
        with self.connect() as db:
            pending = db.execute("SELECT COUNT(*) FROM samples WHERE pending=1").fetchone()[0]
            dropped = db.execute("SELECT value FROM counters WHERE key='dropped'").fetchone()[0]
        return {"pending": pending, "dropped": dropped, "capacity": self.capacity}


def forward(settings, store):
    batch = store.samples(limit=100, pending=True)
    if not batch:
        return
    url = settings.thingsboard_url + "/api/v1/" + urllib.parse.quote(settings.thingsboard_token, safe="") + "/telemetry"
    request_json(url, {"Content-Type": "application/json"},
                 [{"ts": sample["ts"], "values": sample["values"]} for sample in batch])
    store.acknowledge([sample["id"] for sample in batch])
