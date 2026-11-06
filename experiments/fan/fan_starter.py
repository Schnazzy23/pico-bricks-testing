# Hardware controls and the PicoBricks display/sensor drivers.
from machine import Pin

# Pin Initialization
relay = Pin(12, Pin.OUT, value=0)
led = Pin(7, Pin.OUT, value=0)

def start():
    relay.high()
    led.high()
    #print(relay.value(), led.value())
    
def stop():
    relay.low()
    led.low()
    #print(relay.value(), led.value())

relay.low()
led.low()