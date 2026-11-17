"""Read-only commissioning probe. No write function or arbitrary address API."""
import argparse
import json
from pathlib import Path
import struct
import time

from .growatt_serial import crc

# Manufacturer Protocol II V1.05/V1.06: identification and candidate control
# table inspection only. Reading a value does not establish write compatibility.
BLOCKS = {'firmware': (9, 6), 'identity': (23, 7), 'protocol_revision': (82, 7),
          'candidate_priority_settings': (1039, 10),
          'device_type_and_clock': (43, 9),
          'legacy_schedule': (1000, 37),
          'grid_first_controls': (1070, 2),
          'grid_first_schedule': (1080, 9),
          'battery_first_controls': (1090, 3),
          'battery_first_schedule': (1100, 9),
          'load_first_schedule': (1110, 9)}


def read_block(port, name):
    start, count = BLOCKS[name]
    request = struct.pack('>BBHH', 1, 3, start, count)
    port.reset_input_buffer()
    port.write(request + crc(request))
    port.flush()
    header = port.read(3)
    if len(header) != 3 or header[0] != 1:
        raise ValueError('Missing or wrong unit response')
    if header[1] == 0x83:
        reply = header + port.read(2)
        if len(reply) != 5 or crc(reply[:-2]) != reply[-2:]:
            raise ValueError('Corrupt exception frame')
        return {'available': False, 'exception_code': header[2]}
    if header[1] != 3 or header[2] != count * 2:
        raise ValueError('Unexpected function or byte count')
    reply = header + port.read(count * 2 + 2)
    if len(reply) != count * 2 + 5 or crc(reply[:-2]) != reply[-2:]:
        raise ValueError('Incomplete or corrupt response')
    values = struct.unpack('>' + str(count) + 'H', reply[3:-2])
    return {'available': True, 'holding_registers': {str(start + i): value for i, value in enumerate(values)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import serial
    port = serial.Serial(port=None, baudrate=9600, bytesize=8, parity='N', stopbits=1,
                         timeout=2, write_timeout=2, exclusive=True)
    port.dtr = False
    port.rts = False
    port.port = args.port
    results = {'observed_ms': int(time.time() * 1000), 'read_only': True, 'blocks': {}}
    try:
        port.open()
        time.sleep(1)
        for name in BLOCKS:
            try:
                results['blocks'][name] = read_block(port, name)
            except (ValueError, OSError) as error:
                results['blocks'][name] = {'available': False, 'error': type(error).__name__}
            time.sleep(1)
    finally:
        port.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
