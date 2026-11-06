"""Run on your computer: python3 pico_server.py (Python standard library only)."""
import json  # Convert between JSON messages and Python dictionaries.
import math  # Reject non-finite numbers such as infinity.
import os    # Read the upload token from the computer's environment.
import hmac  # Compare tokens without stopping at the first mismatching character.
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# Keep the secret out of the webpage and out of downloadable source code.
# Set PICO_UPLOAD_TOKEN in the terminal before starting this server.
UPLOAD_TOKEN = os.environ.get('PICO_UPLOAD_TOKEN', '')

# This webpage is sent to a browser visiting http://localhost:8080/.
# HTML provides the content; CSS controls its appearance; JavaScript refreshes it.
# The raw bytes string preserves JavaScript's escape sequence for the degree sign.
PAGE = br'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PicoBricks readings</title>
<style>body{font:20px system-ui;max-width:650px;margin:60px auto;padding:20px;
background:#f3f7f5;color:#163b30}article{padding:30px;background:white;border-radius:16px}
strong{font-size:36px}small{color:#52665d}
/* A circular indicator matches the Pico LED. Text appears only without data. */
.temperature-indicator{display:flex;align-items:center;gap:12px}
.temperature-state{display:inline-block;width:24px;height:24px;border-radius:50%;
flex-shrink:0;background:#000}
.temperature-state.red{background:#c62828}
.temperature-state.yellow{background:#ffdf40}
.temperature-state.green{background:#19703b}
</style>
<article><h1>PicoBricks</h1><p>Temperature<br><strong id="temp">--</strong></p>
<p class="temperature-indicator" aria-live="polite">
<span id="temperature-state" class="temperature-state" role="img" aria-label="Waiting for data"></span>
<span id="waiting-label">Waiting for data</span></p>
<p>Humidity<br><strong id="humidity">--</strong></p>
<small id="status">Waiting for the first reading...</small></article>
<script>
// Compare the unrounded reading, using the same thresholds as the Pico.
function updateTemperatureColor(temperature){
const indicator=document.getElementById('temperature-state');
let color='black';
let label='Waiting for data';
if(Number.isFinite(temperature)){
if(temperature>=24){color='red';label='Red - 24 \u00b0C or above';}
else if(temperature>16){color='yellow';label='Yellow - above 16 and below 24 \u00b0C';}
else{color='green';label='Green - 16 \u00b0C or below';}
}
indicator.className='temperature-state '+color;
// Describe the color to screen readers without displaying a text badge.
indicator.setAttribute('aria-label',label);
document.getElementById('waiting-label').hidden=Number.isFinite(temperature);
}
async function update(){try{
// Ask the server for its most recent reading without using a cached copy.
const response=await fetch('/api/readings',{cache:'no-store'});
if(!response.ok)throw Error('Server error');
const data=await response.json();
if(data===null){
// Reset the screen if the server restarted and is waiting for a new reading.
document.getElementById('temp').textContent='--';
document.getElementById('humidity').textContent='--';
updateTemperatureColor(null);
document.getElementById('status').textContent='Waiting for the first reading...';
return;
}
updateTemperatureColor(data.temperature);
// Replace the placeholders with values rounded to one decimal place.
document.getElementById('temp').textContent=data.temperature.toFixed(1)+' \u00b0C';
document.getElementById('humidity').textContent=data.humidity.toFixed(1)+' %';
// Warn when the most recent reading is over 60 seconds old.
const age=(Date.now()-Date.parse(data.received_at))/1000;
document.getElementById('status').textContent=(age>60?'No recent readings. Last received: ':'Last received: ')
+new Date(data.received_at).toLocaleString();
}catch(error){document.getElementById('status').textContent='Cannot reach the server';}}
// Refresh immediately, then every three seconds, without reloading the page.
update();setInterval(update,3000);
</script></html>'''


class Handler(BaseHTTPRequestHandler):
    """Handle browser requests and sensor readings sent by the Pico."""
    # A class variable shares the latest reading between requests.
    # It is kept in memory, so restarting the server clears it.
    latest = None

    def setup(self):
        super().setup()
        # Avoid waiting indefinitely for a client to finish sending a request.
        self.connection.settimeout(10)

    def reply(self, status, body, content_type='application/json'):
        """Send a status code, response headers, and a bytes body to a client."""
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Browsers use GET to retrieve the webpage or the latest reading.
        if self.path == '/':
            self.reply(200, PAGE, 'text/html; charset=utf-8')
        elif self.path == '/api/readings':
            # None becomes JSON null until the Pico sends its first reading.
            self.reply(200, json.dumps(Handler.latest).encode())
        else:
            self.reply(404, b'{"error":"Not found"}')

    def do_POST(self):
        # The Pico uses POST to submit a new temperature/humidity reading.
        if self.path != '/api/readings':
            self.reply(404, b'{"error":"Not found"}')
            return
        # Authenticate before reading or accepting the submitted sensor values.
        # Missing server configuration also rejects all uploads (fails closed).
        supplied_token = self.headers.get('X-Upload-Token', '')
        if not UPLOAD_TOKEN or not hmac.compare_digest(
                supplied_token.encode('utf-8'), UPLOAD_TOKEN.encode('utf-8')):
            self.reply(401, b'{"error":"Unauthorized"}')
            return
        try:
            # Read only a small message; a reading needs far less than 1 KB.
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024:
                raise ValueError('Invalid body length')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected an object')
            for key in ('temperature', 'humidity'):
                # Require both values to be finite numbers, not strings or booleans.
                value = data[key]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('Expected finite numbers')
            if not 0 <= data['humidity'] <= 100:
                raise ValueError('Humidity outside 0-100')
        except (ValueError, KeyError, TypeError, OSError):
            # HTTP 400 tells the sender that the submitted message is invalid.
            self.reply(400, b'{"error":"Expected numeric temperature and humidity"}')
            return
        # Timestamp the reading using the computer's clock in UTC.
        Handler.latest = dict(temperature=data['temperature'], humidity=data['humidity'],
                              received_at=datetime.now(timezone.utc).isoformat())
        self.reply(200, b'{"ok":true}')  # Acknowledge a successful upload.


if __name__ == '__main__':
    # Start only when this file is run directly, not when it is imported.
    if not UPLOAD_TOKEN:
        raise SystemExit('Set the PICO_UPLOAD_TOKEN environment variable before starting the server.')
    print('Open http://localhost:8080 on this computer.', flush=True)
    print('Keep this terminal open. Press Ctrl+C to stop.', flush=True)
    try:
        # Listen on all local network interfaces so the Pico can reach this PC.
        # Port 8080 must match the port in the Pico's SERVER_URL setting.
        # The computer needs to stay awake with this process running.
        HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
    except KeyboardInterrupt:
        # Ctrl+C in the terminal stops the server without printing a traceback.
        pass
