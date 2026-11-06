"""Save to the Pico as main.py after editing the settings below.
Requires picobricks.py and MicroPython's requests package on the Pico.
This version uses the SHTC3 temperature/humidity sensor.
"""
# Hardware controls and the PicoBricks display/sensor drivers.
from machine import Pin, I2C
from picobricks import SSD1306_I2C, SHTC3, WS2812
import network   # Connect the Pico W to Wi-Fi.
import utime     # Delays and elapsed-time measurements.
import requests  # Send HTTP requests to the computer's webserver.

# Edit these settings before saving this file to the Pico as main.py.
# The server address is your COMPUTER's IP address, not the Pico's IP.
WIFI_NAME = 'YOUR_WIFI_NAME'
WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'
SERVER_URL = 'http://192.168.1.1:8080/api/readings'  # Use your computer's LAN IP
# Use the same secret as PICO_UPLOAD_TOKEN on the computer. Do not share it.
UPLOAD_TOKEN = 'PASTE_YOUR_RANDOM_TOKEN_HERE'

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
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
BLACK = (0, 0, 0)
ws.pixels_fill(BLACK)
ws.pixels_show()
# Station mode joins an existing Wi-Fi network.
wlan = network.WLAN(network.STA_IF)
wlan.active(True)


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


# None makes the first reading upload immediately.
last_upload = None
while True:
    try:
        # Read temperature in degrees Celsius and relative humidity in percent.
        temperature = sensor.temperature()
        humidity = sensor.humidity()
        # Clear the display buffer, then draw the new readings into it.
        # text() takes the text followed by its x and y pixel coordinates.
        oled.fill(0)
        oled.text('Climate', 30, 0)
        oled.text('TEMP:     {:.1f}C'.format(temperature), 0, 20)
        oled.text('HUMIDITY: {:.1f}%'.format(humidity), 0, 30)
        # This is the Pico's IP address; SERVER_URL uses the computer's IP.
        oled.text('IP:' + wlan.ifconfig()[0], 0, 50)
        oled.show()  # Send the finished buffer to the physical screen.
        print('Temperature:', temperature, 'Humidity:', humidity)
    except Exception as error:
        # Report hardware errors and try again rather than ending the program.
        print('Sensor/display error:', error)
        ws.pixels_fill(BLACK)
        ws.pixels_show()
        utime.sleep(2)
        continue

    # Match the temperature thresholds used by the web dashboard.
    try:
        if temperature >= 24:
            ws.pixels_fill(RED)
        elif temperature > 16:
            ws.pixels_fill(YELLOW)
        else:
            ws.pixels_fill(GREEN)
        ws.pixels_show()
    except Exception as error:
        print('LED error:', error)
        utime.sleep(2)
        continue

    now = utime.ticks_ms()
    # Attempt an upload every 30,000 milliseconds (30 seconds).
    # Display readings are refreshed more often than uploads.
    if last_upload is None or utime.ticks_diff(now, last_upload) >= 30000:
        response = None
        try:
            if connect_wifi():
                # JSON is a named collection of values that the server can read.
                # Limit the HTTP wait to five seconds if the server is unavailable.
                response = requests.post(SERVER_URL,
                    headers={'X-Upload-Token': UPLOAD_TOKEN},
                    json={'temperature': temperature, 'humidity': humidity}, timeout=5)
                print('Upload HTTP status:', response.status_code)  # 200 means success.
        except Exception as error:
            print('Upload failed:', error)
        finally:
            # Always release the network connection after receiving a response.
            if response is not None:
                response.close()
            # Wait 30 seconds after an attempt, including a failed one.
            last_upload = utime.ticks_ms()
    # Pause between readings. Wi-Fi connection/upload waits can add extra time.
    utime.sleep(2)
