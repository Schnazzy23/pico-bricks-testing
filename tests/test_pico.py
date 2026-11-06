"""Run the actual main loop with fake hardware; never connect to a physical relay."""
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/weather-station/pico_main.py'
# Parse source without copying or printing the user's Wi-Fi credentials.
TREE = ast.parse(SOURCE.read_text())
for node in TREE.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
        ('WIFI_NAME', 'WIFI_PASSWORD', 'SERVER_URL', 'UPLOAD_TOKEN') for t in node.targets):
        node.value = ast.Constant('test-only')
CODE = compile(ast.fix_missing_locations(TREE), '<pico-program-with-test-settings>', 'exec')

class EndRun(BaseException): pass


def run_case(temp, button, modes, sensor_error=False):
    events, reports, ticks = [], [], [1000]
    loops = [0]
    module = lambda **kw: types.SimpleNamespace(**kw)
    class Pin:
        IN, OUT = 0, 1
        def __init__(self, number, *args, **kwargs): self.number=number
        def value(self): return button
    class OLED:
        def __init__(self,*args,**kw): pass
        def fill(self,*args): pass
        def text(self,*args): pass
        def show(self): pass
    class Sensor:
        def __init__(self,*args): pass
        def temperature(self):
            if sensor_error: raise OSError('test sensor failure')
            return temp
        def humidity(self): return 45
    class LED:
        def __init__(self,*args,**kw): pass
        def pixels_fill(self,*args): pass
        def pixels_show(self): pass
    class WLAN:
        def active(self,*args): pass
        def isconnected(self): return True
        def ifconfig(self): return ('192.0.2.1',)*4
    class Response:
        status_code = 200
        def __init__(self, mode): self.mode=mode
        def json(self): return {'mode':self.mode}
        def close(self): pass
    def get(*args, **kw):
        mode=modes[loops[0]]
        if mode is None: raise OSError('test offline')
        return Response(mode)
    def post(*args,**kw):
        reports.append(kw['json'])
        return Response(None)
    def sleep(seconds):
        loops[0]+=1
        if loops[0]>=len(modes): raise EndRun()
        ticks[0]+=70000  # Force the command-contact expiry on the next loop.
    modules = {
        'pico_config':module(WIFI_NAME='test-network',WIFI_PASSWORD='test-password',
                             SERVER_URL='http://192.0.2.1:8080/api/readings',UPLOAD_TOKEN='test-upload'),
        'machine':module(Pin=Pin,I2C=lambda *a,**k:None),
        'picobricks':module(SSD1306_I2C=OLED,SHTC3=Sensor,WS2812=LED),
        'fan_starter':module(start=lambda:events.append(True),stop=lambda:events.append(False)),
        'network':module(WLAN=lambda *a:WLAN(),STA_IF=0),
        'utime':module(sleep_ms=lambda ms:None,ticks_ms=lambda:ticks[0],ticks_diff=lambda a,b:a-b,sleep=sleep),
        'requests':module(get=get,post=post),
    }
    with patch.dict(sys.modules, modules):
        try: exec(CODE, {'print':lambda *args:None})
        except EndRun: pass
    return events,reports

class PicoChecks(unittest.TestCase):
    def test_auto_temperature_and_button(self):
        for temp,button,expected in [(25,0,True),(15,0,False),(15,1,True),(24,0,True)]:
            events,reports=run_case(temp,button,['auto'])
            self.assertEqual(events,[expected])
            self.assertEqual(reports[-1]['fan_on'],expected)
    def test_manual_overrides(self):
        for mode,temp,button,expected in [('on',15,0,True),('off',25,1,False)]:
            events,reports=run_case(temp,button,[mode])
            self.assertEqual(events,[expected])
            self.assertEqual(reports[-1]['applied_mode'],mode)
    def test_offline_returns_to_auto(self):
        events,reports=run_case(15,0,['on',None])
        self.assertEqual(events,[True,False])
        self.assertEqual(reports[-1]['applied_mode'],'auto')
    def test_sensor_failure_stops_fan(self):
        events,reports=run_case(25,0,['on'],sensor_error=True)
        self.assertEqual(events,[False])
        self.assertEqual(reports,[])

if __name__=='__main__': unittest.main()
