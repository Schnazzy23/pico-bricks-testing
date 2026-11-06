"""Integration checks using temporary data and a local test server, never the Pico."""
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DashboardChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ['PICO_UPLOAD_TOKEN'] = 'test-upload'
        os.environ['PICO_CONTROL_TOKEN'] = 'test-control'
        os.environ['PICO_DB_PATH'] = str(Path(cls.temp.name) / 'readings.sqlite3')
        spec = importlib.util.spec_from_file_location('dashboard_server', ROOT / 'experiments/weather-station/pico_server.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.init_database()
        cls.server = cls.module.ThreadingHTTPServer(('127.0.0.1', 0), cls.module.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def setUp(self):
        with self.module.database() as conn:
            conn.execute('DELETE FROM readings')
        self.module.requested_mode = 'auto'

    def request(self, path, data=None, token=None, control=False):
        headers = {}
        if token is not None:
            headers['X-Control-Token' if control else 'X-Upload-Token'] = token
        if data is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.base + path,
              data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, json.loads(body) if body.startswith((b'{', b'[', b'null')) else body

    def test_page_and_empty_state(self):
        status, page = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'Climate history', page)
        state = self.request('/api/dashboard')[1]
        self.assertIsNone(state['latest'])
        self.assertEqual(state['history'], [])
        self.assertEqual(state['requested_mode'], 'auto')

    def test_upload_authentication(self):
        for token in (None, 'wrong', 'test-control'):
            self.assertEqual(self.request('/api/readings', {'temperature':25,'humidity':50}, token)[0], 401)
        self.assertIsNone(self.request('/api/readings')[1])

    def test_history_and_legacy_upload(self):
        self.assertEqual(self.request('/api/readings', {'temperature':25,'humidity':50}, 'test-upload')[0], 200)
        data = self.request('/api/dashboard?hours=24')[1]
        self.assertEqual(data['latest']['temperature'], 25)
        self.assertIsInstance(data['latest']['heat_index'], float)
        self.assertIsNone(data['latest']['fan_on'])
        self.assertEqual(len(data['history']), 1)
        self.module.init_database()  # Initializing again must preserve history.
        self.assertEqual(len(self.request('/api/dashboard')[1]['history']), 1)

    def test_commands_and_confirmation(self):
        self.assertEqual(self.request('/api/fan', {'mode':'on'}, 'test-upload', control=True)[0], 401)
        self.assertEqual(self.request('/api/fan', {'mode':'on'}, 'test-control', control=True)[0], 200)
        self.assertEqual(self.request('/api/fan', token='test-upload')[1]['mode'], 'on')
        self.assertEqual(self.request('/api/fan')[0], 401)
        reading = {'temperature':20,'humidity':40,'heat_index':19.4,'fan_on':False,'applied_mode':'auto'}
        self.request('/api/readings', reading, 'test-upload')
        snapshot = self.request('/api/dashboard')[1]
        self.assertEqual(snapshot['requested_mode'], 'on')
        self.assertEqual(snapshot['latest']['applied_mode'], 'auto')
        reading.update(fan_on=True, applied_mode='on')
        self.request('/api/readings', reading, 'test-upload')
        self.assertTrue(self.request('/api/readings')[1]['fan_on'])
        self.assertEqual(self.request('/api/fan', {'mode':'off'}, 'test-control', control=True)[0], 200)
        self.assertEqual(self.request('/api/fan', {'mode':'auto'}, 'test-control', control=True)[0], 200)

    def test_invalid_data(self):
        for data in ({'temperature':True,'humidity':50}, {'temperature':20,'humidity':101},
                     {'temperature':float('nan'),'humidity':50}, {'temperature':20,'humidity':50,'fan_on':'yes'},
                     {'temperature':20,'humidity':50,'heat_index':None}, {'temperature':20,'humidity':50,'applied_mode':'bad'}):
            self.assertEqual(self.request('/api/readings',data,'test-upload')[0],400)
        self.assertEqual(self.request('/api/fan', {'mode':'bad'}, 'test-control', control=True)[0], 400)
        self.assertEqual(self.request('/api/dashboard?hours=999')[0],400)
        self.assertIsNone(self.request('/api/readings')[1])

if __name__ == '__main__':
    unittest.main()
