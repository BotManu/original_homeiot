import json
from pathlib import Path
import tempfile
import unittest

from gateway.growatt import PROFILE, connection_status, select_adapter, configure_connection, serial_ports


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

    def test_wired_settings_validate_before_saving_and_clear_on_adapter_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'device.json'
            path.write_bytes(PROFILE.read_bytes())
            before = path.read_bytes()
            for settings in ({'unit_id': 0}, {'serial_port': '/etc/passwd'},
                             {'serial_port': '/dev/serial/by-id/../bad'}, {'baud_rate': 7}):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    configure_connection(path, 'USB-RS232', **settings)
                self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(ValueError):
                configure_connection(path, 'ShineWiFi-S', baud_rate=9600)
            result = configure_connection(path, 'USB-RS232', serial_port='/dev/serial/by-id/usb-adapter-1',
                                          baud_rate=9600, parity='none', stop_bits=1, unit_id=1)
            self.assertEqual(result['connection']['baud_rate'], 9600)
            self.assertFalse(result['qualification']['equipment_writes_enabled'])
            status = connection_status(path)
            self.assertFalse(status['serial_driver_implemented'])
            result = select_adapter(path, 'ShineWiFi-S')
            self.assertIsNone(result['connection']['serial_port'])
            self.assertIsNone(result['connection']['baud_rate'])

    def test_port_discovery_has_no_device_io(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'serial/by-id').mkdir(parents=True)
            for name in ('ttyUSB0', 'ttyACM1', 'serial/by-id/usb-test', 'unrelated'):
                (root / name).touch()
            self.assertEqual(len(serial_ports(root)), 3)


if __name__ == '__main__':
    unittest.main()
