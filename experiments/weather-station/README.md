# PicoBricks weather station

The dashboard follows the supplied sketch: temperature, humidity, and heat-index
cards above fan controls, a temperature indicator, and a climate-history graph.
It runs locally on Fedora using Python's standard library. No external web assets
or JavaScript packages are required.

## Files to keep together on the computer

- `pico_server.py`: the webserver and authenticated API.
- `dashboard.html`: the page, styles, and graph code; keep it beside the server.
- `readings.sqlite3`: created automatically when you start the server. It keeps
  seven days of readings. Copy this file if moving an existing installation.

## Start the server

Open a terminal in this folder. Set the existing upload token, then set a different
control token. The prompts do not display what you type. Use the same upload token
already configured on your Pico. The control token is only for the browser.

```bash
read -rs -p "Existing Pico upload token: " PICO_UPLOAD_TOKEN
printf '\n'
export PICO_UPLOAD_TOKEN
read -rs -p "Separate fan control token: " PICO_CONTROL_TOKEN
printf '\n'
export PICO_CONTROL_TOKEN
python3 pico_server.py
```

To generate a random control token, run this in another terminal and copy its
output to the control-token prompt above:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Open http://localhost:8080 on this computer. Other devices on your home network
can use `http://YOUR_COMPUTER_IP:8080`. Keep the computer awake and the terminal
running. Existing port-8080 firewall configuration still applies.

Without `PICO_CONTROL_TOKEN`, the dashboard works in read-only mode. The token is
never included in the webpage. Use **Unlock controls** to enter it in the browser;
it remains only in the current page's memory. **Lock controls** or reloading the
page forgets it. Locking does not change the selected fan mode.

These keys authenticate requests; they do not encrypt HTTP or restrict viewing.
Keep this service on a trusted LAN/private VPN. It is not a public-internet server.

## Update the Pico

Copy `pico_config.example.py` to `pico_config.py`, then put your Wi-Fi credentials,
server address, and upload token in that private file. It is ignored by Git.
If a private config already exists locally, keep it. Save it to the Pico as
`pico_config.py`. Open `pico_main.py` in Thonny and save it to the Pico as `main.py`.
Keep `picobricks.py` and the working
`fan_starter.py` in the Pico's root directory alongside it. The relay module is in
`../fan/fan_starter.py` on this computer.

The new program sends heat index, relay state, and applied mode with each reading.
The server also accepts the old temperature/humidity-only uploads, but fan buttons
remain unavailable until the updated Pico reports relay status.

## Fan modes

- **Auto:** relay on at 24°C or above, or while the Pico button is pressed.
- **On:** relay on regardless of temperature or button state.
- **Off:** relay off regardless of temperature or button state.

The page first shows **Pending** after a mode change. It confirms the applied
mode when the Pico uploads it. Polling normally happens between readings, so allow
a few seconds. A five-second upload or fifteen-second Wi-Fi reconnect attempt can
add delay. The relay status reports the output commanded by the Pico, not a sensor
confirming that a connected fan is physically spinning.

A sensor/display error stops the relay. After 60 seconds without successful
command contact, the Pico returns to Auto. Reconnecting retrieves the server's
selected mode again. Restarting the server resets its selected mode to Auto;
restarting the Pico starts it in Auto until it retrieves a command.

## Indicator and graphs

- Red: temperature at least 24°C.
- Yellow: temperature above 16°C and below 24°C.
- Blue: temperature at or below 16°C.
- Black with **Waiting for data**: no fresh reading, a reading older than 60
  seconds, or a failed connection to the server. Last known values stay visible
  with their timestamp when available.

The graph switches between temperature, humidity, and heat index. Choose 1, 6, or
24 hours. New readings arrive normally every 30 seconds, plus relay/mode changes.
History starts when this version of the server first receives readings; it is not
backfilled. Outages appear as gaps. Times use the browser's local timezone.
Hover over the graph or tap it to inspect the nearest plotted reading and its
timestamp. You can also focus the graph with Tab and use the left/right arrow
keys to step through readings; Escape dismisses the tooltip.

## Verification

The local test scripts in `../../tests/` cover authentication, command confirmation,
history persistence, invalid submissions, Auto/manual fan behavior, sensor errors,
and loss-of-contact fallback. Hardware tests use substitutes; they do not actuate
a real relay. Browser checks cover the desktop/mobile layouts, empty-data state,
key entry, mode selection, and graph controls.

```bash
python3 ../../tests/test_dashboard.py
python3 ../../tests/test_pico.py
```
