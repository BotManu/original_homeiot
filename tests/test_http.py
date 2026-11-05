"""Exercise the actual server boundary rather than only adapter helpers."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request


class HTTPTests(unittest.TestCase):
    def test_authenticated_local_ui_and_rejected_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {key: value for key, value in os.environ.items() if not key.startswith(('GATEWAY_', 'OPENEMS_', 'THINGSBOARD_'))}
            env.update(GATEWAY_PORT='0', GATEWAY_HOST='127.0.0.1', GATEWAY_MODE='demo',
                       GATEWAY_DATA=folder, GATEWAY_PASSWORD='test-password')
            process = subprocess.Popen([sys.executable, '-m', 'gateway'], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                line = process.stdout.readline()
                self.assertIn('http://127.0.0.1:', line)
                url = line.split()[3]
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(url, timeout=5)
                self.assertEqual(caught.exception.code, 401)
                caught.exception.close()
                headers = {'Authorization': 'Basic ' + base64.b64encode(b'admin:test-password').decode()}
                for path in ('/', '/style.css', '/app.js', '/api/overview'):
                    with urllib.request.urlopen(urllib.request.Request(url + path, headers=headers), timeout=5) as response:
                        body = response.read()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                        if path == '/api/overview':
                            data = json.loads(body)
                            self.assertEqual(data['mode'], 'demo')
                            self.assertFalse(data['control_enabled'])
                            self.assertNotIn('test-password', body.decode())
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(urllib.request.Request(url + '/api/control', headers=headers, data=b'{}'), timeout=5)
                self.assertEqual(caught.exception.code, 405)
                caught.exception.close()
            finally:
                process.terminate()
                process.communicate(timeout=10)


if __name__ == '__main__':
    unittest.main()
