import json
from pathlib import Path
import tempfile
import unittest

from gateway.growatt import PROFILE, connection_status, select_adapter


class GrowattTests(unittest.TestCase):
    def test_switch_to_serial_wifi_preserves_identity_and_resets_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'device.json'
            profile = json.loads(PROFILE.read_text())
            profile['connection'].update(adapter_model='ShineWiFi-X', local_ip='192.0.2.10', adapter_serial_number='old', physical_interface_verified=True)
            profile['qualification'].update(telemetry_verified=True, equipment_writes_enabled=True)
            path.write_text(json.dumps(profile))
            result = select_adapter(path, 'ShineWiFi-S')
            self.assertEqual(result['serial_number'], 'NUCPB2101P')
            self.assertIsNone(result['connection']['local_ip'])
            self.assertIsNone(result['connection']['adapter_serial_number'])
            self.assertFalse(result['connection']['physical_interface_verified'])
            self.assertFalse(result['qualification']['telemetry_verified'])
            self.assertFalse(result['qualification']['equipment_writes_enabled'])
            status = connection_status(path)
            self.assertEqual(status['adapter_options']['ShineWiFi-S']['inverter_interface'], 'RS232')
            self.assertFalse(status['receiver_implemented'])
            self.assertEqual(status['profile']['connection']['adapter_model'], 'ShineWiFi-S')
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                select_adapter(path, 'unknown')
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
