"""Local PicoBricks dashboard. Run: python3 pico_server.py

Keep dashboard.html beside this file. Set PICO_UPLOAD_TOKEN before starting.
Set a different PICO_CONTROL_TOKEN to enable authenticated fan controls.
Readings are saved to readings.sqlite3; no extra Python packages are needed.
"""
import hmac
import json
import math
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
PAGE = (ROOT / 'dashboard.html').read_bytes()
UPLOAD_TOKEN = os.environ.get('PICO_UPLOAD_TOKEN', '')
CONTROL_TOKEN = os.environ.get('PICO_CONTROL_TOKEN', '')
DB_PATH = Path(os.environ.get('PICO_DB_PATH', ROOT / 'readings.sqlite3'))
VALID_MODES = ('auto', 'on', 'off')
FRESH_SECONDS = 60
command_lock = threading.Lock()
requested_mode = 'auto'  # Restarting the server returns control to automatic mode.


@contextmanager
def database():
    """Each request gets its own SQLite connection for thread safety."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_database():
    with database() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY, received_at TEXT NOT NULL,
            temperature REAL NOT NULL, humidity REAL NOT NULL,
            heat_index REAL NOT NULL, fan_on INTEGER, applied_mode TEXT)''')
        conn.execute('CREATE INDEX IF NOT EXISTS reading_time ON readings(received_at)')


def heat_index(temperature, humidity):
    """Same Celsius heat-index calculation as the Pico, for older upload code."""
    t, rh = temperature * 9 / 5 + 32, humidity
    simple = 0.5 * (t + 61 + (t - 68) * 1.2 + rh * 0.094)
    hi = (simple + t) / 2
    if hi >= 80:
        hi = (-42.379 + 2.04901523*t + 10.14333127*rh - 0.22475541*t*rh
              - 0.00683783*t*t - 0.05481717*rh*rh + 0.00122874*t*t*rh
              + 0.00085282*t*rh*rh - 0.00000199*t*t*rh*rh)
        if rh < 13 and 80 <= t <= 112:
            hi -= ((13-rh)/4) * ((17-abs(t-95))/17) ** 0.5
        elif rh > 85 and 80 <= t <= 87:
            hi += ((rh-85)/10) * ((87-t)/5)
    return (hi-32) * 5/9


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def reading_dict(row):
    if row is None:
        return None
    result = dict(row)
    result.pop('id', None)
    if result['fan_on'] is not None:
        result['fan_on'] = bool(result['fan_on'])
    return result


class Handler(BaseHTTPRequestHandler):
    """Read-only dashboard plus separately authenticated upload/control routes."""
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def reply(self, status, body, content_type='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; script-src 'unsafe-inline'; "
                         "style-src 'unsafe-inline'; connect-src 'self'; "
                         "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, header, expected):
        supplied = self.headers.get(header, '')
        if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
            self.reply(401, {'error': 'Incorrect or missing key.'})
            return False
        return True

    def json_body(self):
        """Only small JSON objects are accepted; never execute submitted content."""
        if self.headers.get('Transfer-Encoding'):
            raise ValueError('Transfer encoding is not supported.')
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= 2048:
            raise ValueError('Expected a JSON message of 1 to 2048 bytes.')
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object.')
        return data

    def do_GET(self):
        route = urlsplit(self.path)
        if route.path == '/':
            self.reply(200, PAGE, 'text/html; charset=utf-8')
        elif route.path in ('/api/readings', '/api/dashboard'):
            try:
                hours = int(parse_qs(route.query).get('hours', ['6'])[0])
                if hours not in (1, 6, 24):
                    raise ValueError
            except ValueError:
                self.reply(400, {'error': 'Choose 1, 6, or 24 hours.'})
                return
            with database() as conn:
                latest = reading_dict(conn.execute(
                    'SELECT * FROM readings ORDER BY id DESC LIMIT 1').fetchone())
                if route.path == '/api/readings':
                    self.reply(200, latest)  # Preserve the original endpoint.
                    return
                cutoff = datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() - hours*3600, timezone.utc).isoformat()
                rows = conn.execute('SELECT * FROM readings WHERE received_at >= ? '
                                    'ORDER BY id DESC LIMIT 3000', (cutoff,)).fetchall()
            with command_lock:
                mode = requested_mode
            self.reply(200, dict(latest=latest, history=[reading_dict(r) for r in reversed(rows)],
                                 requested_mode=mode, controls_enabled=bool(CONTROL_TOKEN),
                                 fresh_seconds=FRESH_SECONDS,
                                 preview=os.environ.get('PICO_PREVIEW') == '1'))
        elif route.path == '/api/fan':
            # Only a Pico holding the upload key can retrieve relay commands.
            if self.authorized('X-Upload-Token', UPLOAD_TOKEN):
                with command_lock:
                    mode = requested_mode
                self.reply(200, {'mode': mode})
        else:
            self.reply(404, {'error': 'Not found.'})

    def do_POST(self):
        global requested_mode
        path = urlsplit(self.path).path
        if path not in ('/api/readings', '/api/fan'):
            self.reply(404, {'error': 'Not found.'})
            return
        # Changing fan mode needs a separate control key, never the upload key.
        header, secret = (('X-Control-Token', CONTROL_TOKEN) if path == '/api/fan'
                          else ('X-Upload-Token', UPLOAD_TOKEN))
        if not self.authorized(header, secret):
            return
        try:
            data = self.json_body()
            if path == '/api/fan':
                mode = data.get('mode')
                if mode not in VALID_MODES:
                    raise ValueError('Choose auto, on, or off.')
                with command_lock:
                    requested_mode = mode
                self.reply(200, {'requested_mode': mode})
                return
            temperature, humidity = data.get('temperature'), data.get('humidity')
            if not finite_number(temperature) or not finite_number(humidity):
                raise ValueError('Temperature and humidity must be finite numbers.')
            if not -100 <= temperature <= 150 or not 0 <= humidity <= 100:
                raise ValueError('Reading is outside the supported range.')
            hi = data.get('heat_index', heat_index(temperature, humidity))
            if not finite_number(hi):
                raise ValueError('Heat index must be a finite number.')
            fan_on, applied_mode = data.get('fan_on'), data.get('applied_mode')
            if fan_on is not None and type(fan_on) is not bool:
                raise ValueError('fan_on must be true or false.')
            if applied_mode is not None and applied_mode not in VALID_MODES:
                raise ValueError('Unknown applied fan mode.')
            timestamp = datetime.now(timezone.utc).isoformat()
            with database() as conn:
                conn.execute('INSERT INTO readings '
                             '(received_at,temperature,humidity,heat_index,fan_on,applied_mode) '
                             'VALUES (?,?,?,?,?,?)',
                             (timestamp, temperature, humidity, hi, fan_on, applied_mode))
                # Retain seven days of readings; graphs show up to the last 24 hours.
                cutoff = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp()
                                                - 7*86400, timezone.utc).isoformat()
                conn.execute('DELETE FROM readings WHERE received_at < ?', (cutoff,))
            self.reply(200, {'ok': True})
        except (ValueError, TypeError, OSError) as error:
            self.reply(400, {'error': str(error)})


if __name__ == '__main__':
    if not UPLOAD_TOKEN:
        raise SystemExit('Set PICO_UPLOAD_TOKEN before starting the server.')
    if CONTROL_TOKEN and hmac.compare_digest(CONTROL_TOKEN, UPLOAD_TOKEN):
        raise SystemExit('Use a different PICO_CONTROL_TOKEN from the upload token.')
    init_database()
    port = int(os.environ.get('PICO_PORT', '8080'))
    print('Dashboard: http://localhost:' + str(port), flush=True)
    print('Keep this terminal open. Press Ctrl+C to stop.', flush=True)
    print('Fan controls ' + ('enabled.' if CONTROL_TOKEN else 'disabled: set PICO_CONTROL_TOKEN.'), flush=True)
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
