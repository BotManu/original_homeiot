"""Read-only, qualified older SPH serial telemetry; never sends register writes.

Requires pyserial on the Pi. Run with --port, --output and --model-code.
Register units follow Growatt Modbus RTU Protocol II, SPH input group 1000.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import time


def crc(data):
    value = 0xffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ 0xa001 if value & 1 else value >> 1
    return struct.pack('<H', value)


def read_registers(port, function, start, count):
    if (function, start, count) not in ((3, 23, 7), (4, 1, 2), (4, 1009, 30)):
        raise ValueError('Only qualified read blocks are allowed')
    body = struct.pack('>BBHH', 1, function, start, count)
    port.reset_input_buffer()
    port.write(body + crc(body))
    port.flush()
    reply = port.read(5 + count * 2)
    if (len(reply) != 5 + count * 2 or reply[:3] != bytes((1, function, count * 2))
            or crc(reply[:-2]) != reply[-2:]):
        raise ValueError('Incomplete, unexpected or corrupt Modbus reply')
    return list(struct.unpack('>' + str(count) + 'H', reply[3:-2]))


def decode(identity, pv, sph, expected_model):
    model = 'GT' + ''.join(f'{v:04X}' for v in identity[5:7])
    if model != expected_model:
        raise ValueError('Connected inverter model code does not match qualification')
    def power(index):
        return ((sph[index] << 16) + sph[index + 1]) / 10
    soc, voltage = sph[5], sph[4] / 10
    solar = ((pv[0] << 16) + pv[1]) / 10
    discharge, charge = power(0), power(2)
    imported, exported, load = power(12), power(20), power(28)
    if not 0 <= soc <= 100 or not 10 <= voltage <= 100:
        raise ValueError('Invalid battery measurements')
    if any(not 0 <= value <= 30000 for value in
           (solar, discharge, charge, imported, exported, load)):
        raise ValueError('Power measurement outside qualified installation bounds')
    wire_serial = struct.pack('>5H', *identity[:5]).decode('ascii')
    return {'model_code': model, 'reported_serial': wire_serial,
            'battery_voltage_v': voltage,
            'values': {'solar_w': solar, 'load_w': load,
                       'grid_w': imported - exported, 'battery_w': discharge - charge,
                       'battery_soc': soc}}


def publish(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        os.chmod(temporary, 0o600)
        json.dump(payload, output, allow_nan=False)
        output.write('\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--model-code', required=True)
    args = parser.parse_args()
    import serial  # Optional dependency; gateway web service stays stdlib-only.
    os.umask(0o077)
    while True:
        started = time.monotonic()
        try:
            port = serial.Serial(port=None, baudrate=9600, bytesize=8, parity='N',
                                 stopbits=1, timeout=2, write_timeout=2, exclusive=True)
            port.dtr = False
            port.rts = False
            port.port = args.port
            try:
                port.open()
                time.sleep(1)
                identity = read_registers(port, 3, 23, 7)
                time.sleep(1)
                pv = read_registers(port, 4, 1, 2)
                time.sleep(1)
                sph = read_registers(port, 4, 1009, 30)
                result = decode(identity, pv, sph, args.model_code)
                result.update(ts=int(time.time() * 1000), available=True)
                publish(args.output, result)
            finally:
                port.close()
        except Exception as error:
            publish(args.output, {'ts': int(time.time() * 1000), 'available': False})
            print('Growatt telemetry unavailable: ' + type(error).__name__, flush=True)
        time.sleep(max(1, 5 - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
