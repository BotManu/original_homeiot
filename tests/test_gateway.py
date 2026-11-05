from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gateway.core import CHANNELS, OpenEMS, Settings, Store, forward


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'test.sqlite'

    def test_spool_survives_restart_and_reports_overflow(self):
        store = Store(self.path, 2)
        for ts in range(3):
            store.add({'solar_w': ts}, pending=True, ts=ts)
        restarted = Store(self.path, 2)
        self.assertEqual(restarted.status(), {'pending': 2, 'dropped': 1, 'capacity': 2})
        self.assertEqual([s['ts'] for s in restarted.samples(pending=True)], [1, 2])

    @patch('gateway.core.request_json')
    def test_failed_delivery_keeps_samples_and_retry_preserves_timestamp(self, request):
        settings = Settings(mode='openems', thingsboard_url='https://example.test', thingsboard_token='secret')
        store = Store(self.path)
        store.add({'solar_w': 100}, pending=True, ts=123)
        request.side_effect = OSError('offline')
        with self.assertRaises(OSError):
            forward(settings, store)
        self.assertEqual(store.status()['pending'], 1)
        request.side_effect = None
        forward(settings, store)
        self.assertEqual(request.call_args.args[2], [{'ts': 123, 'values': {'solar_w': 100}}])
        self.assertEqual(store.status()['pending'], 0)

    @patch('gateway.core.request_json')
    def test_openems_mapping_filters_other_channels_and_rejects_null(self, request):
        rows = [{'address': '_sum/' + name, 'value': 50} for name in CHANNELS.values()]
        rows.append({'address': 'private/Password', 'value': 'secret'})
        request.return_value = rows
        adapter = OpenEMS(Settings(mode='openems'))
        self.assertEqual(set(adapter.read()), set(CHANNELS))
        rows[0]['value'] = None
        with self.assertRaises(ValueError):
            adapter.read()

    def test_demo_energy_balance_and_no_external_delivery(self):
        values = OpenEMS(Settings()).read()
        self.assertEqual(values['solar_w'] + values['battery_w'] + values['grid_w'], values['load_w'])
        with self.assertRaises(ValueError):
            Settings(thingsboard_url='https://example.test', thingsboard_token='secret')

    def test_invalid_settings(self):
        for kwargs in ({'mode': 'typo'}, {'interval': 0}, {'interval': float('nan')},
                       {'capacity': 0}, {'thingsboard_url': 'https://example.test'},
                       {'openems_url': 'http://admin:secret@example.test'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Settings(**kwargs)


if __name__ == '__main__':
    unittest.main()
