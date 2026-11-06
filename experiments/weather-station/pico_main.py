"""Save to the Pico as main.py alongside your private pico_config.py.
Requires picobricks.py and MicroPython's requests package on the Pico.
This version uses the SHTC3 temperature/humidity sensor.
"""
# Hardware controls and the PicoBricks display/sensor drivers.
from machine import Pin, I2C
from pico_config import WIFI_NAME, WIFI_PASSWORD, SERVER_URL, UPLOAD_TOKEN
from picobricks import SSD1306_I2C, SHTC3, WS2812
import fan_starter as fs
import network   # Connect the Pico W to Wi-Fi.
import utime     # Delays and elapsed-time measurements.
import requests  # Send HTTP requests to the computer's webserver.

# Network settings and the upload key are imported from pico_config.py.
# Copy pico_config.example.py to that name and configure it privately.

# The OLED and SHTC3 share the I2C communication bus.
# SDA carries data on GPIO 4; SCL carries the clock signal on GPIO 5.
# Use 400 kHz so a full OLED update completes within the I2C timeout.
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
# Give the hardware a moment to settle before initializing it.
utime.sleep_ms(200)
# The OLED has 128 columns and 64 rows of pixels.
oled = SSD1306_I2C(128, 64, i2c)
sensor = SHTC3(i2c)
# Configure the single onboard RGB LED on GPIO 6 at 10% brightness.
# Named arguments distinguish the LED count from the GPIO number.
ws = WS2812(num_leds=1, pin_num=6, brightness=0.1)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
BLACK = (0, 0, 0)
ws.pixels_fill(BLACK)
ws.pixels_show()
# Station mode joins an existing Wi-Fi network.
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Pin Initialization
button = Pin(10, Pin.IN) # setting GP10 PIN as input

def connect_wifi():
    """Return True if connected, or False after waiting up to 15 seconds."""
    # Reuse an existing connection rather than reconnecting every upload.
    if wlan.isconnected():
        return True
    # Clear any unfinished connection attempt before starting another one.
    wlan.disconnect()
    wlan.connect(WIFI_NAME, WIFI_PASSWORD)
    start = utime.ticks_ms()
    while not wlan.isconnected():
        # ticks_diff handles the timer wrapping back to zero correctly.
        if utime.ticks_diff(utime.ticks_ms(), start) > 15000:
            print('Wi-Fi not connected; will retry on the next upload.')
            return False
        utime.sleep_ms(200)
    print('Pico IP:', wlan.ifconfig()[0])
    return True

def heat_index(temp, humidity):
    t = temp * 9 / 5 + 32
    rh = humidity
    
    # Initial estimate for cooler conditions
    simple = 0.5 * (t + 61 + (t - 68) * 1.2 + rh * 0.094)
    hi = (simple + t) / 2
    
    if hi >= 80:
        hi = (
            -42.379
            + 2.04901523 * t
            + 10.14333127 * rh
            - 0.22475541 * t * rh
            - 0.00683783 * t * t
            - 0.05481717 * rh * rh
            + 0.00122874 * t * t * rh
            + 0.00085282 * t * rh * rh
            - 0.00000199 * t * t * rh * rh
            )
        
        if rh < 13 and 80 <= t <= 112:
            hi -= ((13 - rh) / 4) * (
                (17 - abs(t-95)) / 17
                ) ** 0.5
        elif rh > 85 and 80 <= t <= 87:
            hi += ((rh - 85) / 10) * ((87 - t) / 5)
            
    return (hi - 32) * 5/9


# None makes the first reading upload immediately.
last_upload = None
# Server-selected mode. If command contact is lost for 60 seconds, use Auto.
fan_mode = 'auto'
last_command_contact = None
last_reported_fan = None
fan_on = False
while True:
    try:
        # Read temperature in degrees Celsius and relative humidity in percent.
        temperature = sensor.temperature()
        humidity = sensor.humidity()
        # Get heat index
        hi = heat_index(temperature, humidity)
        # Clear the display buffer, then draw the new readings into it.
        # text() takes the text followed by its x and y pixel coordinates.
        oled.fill(0)
        oled.text('Climate', 30, 0)
        oled.text('TEMP:     {:.1f}C'.format(temperature), 0, 10)
        oled.text('HUMIDITY: {:.1f}%'.format(humidity), 0, 20)
        oled.text('HI:       {:.1f}C'.format(hi), 0, 30)
        # This is the Pico's IP address; SERVER_URL uses the computer's IP.
        oled.text('IP:' + wlan.ifconfig()[0], 0, 50)
        oled.show()  # Send the finished buffer to the physical screen.
        print('Temperature:', temperature, 'Humidity:', humidity, 'Heat Index:', hi)
    except Exception as error:
        # Report hardware errors and try again rather than ending the program.
        print('Sensor/display error:', error)
        ws.pixels_fill(BLACK)
        ws.pixels_show()
        fs.stop()
        fan_on = False
        utime.sleep(2)
        continue

    # Match the temperature thresholds used by the web dashboard.
    try:
        if temperature >= 24:
            ws.pixels_fill(RED)
        elif temperature > 16:
            ws.pixels_fill(YELLOW)
        else:
            ws.pixels_fill(BLUE)
        ws.pixels_show()
    except Exception as error:
        print('LED error:', error)
        utime.sleep(2)
        continue
    
    # Ask the server for Auto / On / Off. The upload token authenticates the Pico.
    # This request runs between readings; a failed request waits at most 2 seconds.
    command_response = None
    try:
        if wlan.isconnected():
            command_url = SERVER_URL.rsplit('/api/readings', 1)[0] + '/api/fan'
            command_response = requests.get(command_url,
                headers={'X-Upload-Token': UPLOAD_TOKEN}, timeout=2)
            if command_response.status_code == 200:
                received_mode = command_response.json().get('mode')
                if received_mode in ('auto', 'on', 'off'):
                    fan_mode = received_mode
                    last_command_contact = utime.ticks_ms()
    except Exception as error:
        print('Fan command unavailable:', error)
    finally:
        if command_response is not None:
            command_response.close()

    # Automatic control continues locally if Wi-Fi or the server goes away.
    if last_command_contact is None or utime.ticks_diff(
            utime.ticks_ms(), last_command_contact) > 60000:
        fan_mode = 'auto'

    # Auto uses temperature or the button; manual modes override both.
    try:
        fan_on = (fan_mode == 'on' or
                  (fan_mode == 'auto' and (temperature >= 24 or button.value() == 1)))
        if fan_on:
            fs.start()
        else:
            fs.stop()
    except Exception as error:
        print('Relay error:', error)
        utime.sleep(2)
        continue

    now = utime.ticks_ms()
    # Attempt an upload every 30,000 milliseconds (30 seconds).
    # Display readings are refreshed more often than uploads.
    # Report relay/mode changes immediately so the dashboard can confirm commands.
    fan_report = (fan_on, fan_mode)
    if (last_upload is None or utime.ticks_diff(now, last_upload) >= 30000
            or fan_report != last_reported_fan):
        response = None
        try:
            if connect_wifi():
                # JSON is a named collection of values that the server can read.
                # Limit the HTTP wait to five seconds if the server is unavailable.
                response = requests.post(SERVER_URL,
                    headers={'X-Upload-Token': UPLOAD_TOKEN},
                    json={'temperature': temperature, 'humidity': humidity,
                          'heat_index': hi, 'fan_on': fan_on,
                          'applied_mode': fan_mode}, timeout=5)
                print('Upload HTTP status:', response.status_code)  # 200 means success.
        except Exception as error:
            print('Upload failed:', error)
        finally:
            # Always release the network connection after receiving a response.
            if response is not None:
                response.close()
            # Wait 30 seconds after an attempt, including a failed one.
            last_upload = utime.ticks_ms()
            last_reported_fan = fan_report
    # Pause between readings. Wi-Fi connection/upload waits can add extra time.
    utime.sleep(2)
