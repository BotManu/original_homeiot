import time
import unittest
from unittest.mock import patch, MagicMock
import struct
from gateway.growatt_serial import crc, read_registers, decode
from gateway.core import OpenEMS, Settings, CHANNELS


class SerialTests(unittest.TestCase):
    def test_real_identity_reply_crc_and_decoder(self):
        reply = bytes.fromhex('01030a39383736353433323130dc38')
        self.assertEqual(crc(reply[:-2]), reply[-2:])
        identity = [0x3938, 0x3736, 0x3534, 0x3332, 0x3130, 0x1100, 0xf25d]
        sph = [0] * 30
        sph[4:6] = [536, 50]
        sph[13] = 7300
        sph[29] = 7300
        result = decode(identity, [0, 9], sph, 'GT1100F25D')
        self.assertEqual(result['reported_serial'], '9876543210')
        self.assertEqual(result['values'], dict(solar_w=.9, load_w=730,
                         grid_w=730, battery_w=0, battery_soc=50))
        sph[1], sph[3], sph[21] = 2000, 1000, 3000
        result = decode(identity, [0, 0], sph, 'GT1100F25D')
        self.assertEqual(result['values']['battery_w'], 100)
        self.assertEqual(result['values']['grid_w'], 430)
        with self.assertRaises(ValueError): decode(identity, [0, 0], sph, 'wrong')
        sph[5] = 101
        with self.assertRaises(ValueError): decode(identity, [0, 0], sph, 'GT1100F25D')

    def test_writes_and_unqualified_reads_are_rejected_before_io(self):
        for args in ((6, 23, 7), (16, 1009, 30), (3, 0, 50), (4, 0, 125)):
            with self.assertRaises(ValueError): read_registers(None, *args)

    def test_serial_framing_rejects_corruption_and_wrong_function(self):
        registers = [0x3938, 0x3736, 0x3534, 0x3332, 0x3130, 0x1100, 0xf25d]
        body = bytes((1, 3, 14)) + struct.pack('>7H', *registers)
        port = MagicMock()
        port.read.return_value = body + crc(body)
        self.assertEqual(read_registers(port, 3, 23, 7), registers)
        request = bytes.fromhex('010300170007')
        port.write.assert_called_once_with(request + crc(request))
        for invalid in (body + b'\0\0', body[:-1], bytes((1, 4, 14)) + body[3:] + crc(body)):
            port.read.return_value = invalid
            with self.assertRaises(ValueError): read_registers(port, 3, 23, 7)

    @patch('gateway.core.request_json')
    def test_equipment_freshness_and_simulator_isolation(self, request):
        component = 'growatt0'
        rows = [{'address':component+'/'+name, 'value':50} for name in CHANNELS.values()]
        rows += [{'address':'_sum/'+name, 'value':999} for name in CHANNELS.values()]
        settings = Settings(mode='openems', openems_component=component)
        request.return_value = rows
        with self.assertRaises(ValueError): OpenEMS(settings).read()
        stamp = {'address':component+'/LastSuccessfulRead', 'value':time.time()*1000}
        request.return_value = rows + [stamp]
        self.assertEqual(OpenEMS(settings).read()['solar_w'], 50)
        stamp['value'] -= 60000
        with self.assertRaises(ValueError): OpenEMS(settings).read()


if __name__ == '__main__': unittest.main()
