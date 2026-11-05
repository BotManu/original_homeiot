"""Growatt commissioning profiles; selecting an adapter does not establish a link."""
import argparse
import json
import re
from pathlib import Path


ADAPTERS = {
    "ShineWiFi-X": {"inverter_interface": "USB", "network_interface": "Wi-Fi",
                    "integration_method": "growatt_upload_receiver", "qualification": "pending"},
    "ShineWiFi-S": {"inverter_interface": "RS232", "network_interface": "Wi-Fi",
                    "integration_method": "growatt_upload_receiver", "qualification": "pending"},
    "USB-RS232": {"inverter_interface": "RS232", "network_interface": "USB cable to Pi",
                  "integration_method": "openems_serial_driver", "qualification": "pending"},
}
PROFILE = Path(__file__).resolve().parent.parent / "config/devices/growatt-sph6000.json"


def load_profile(path=PROFILE):
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    adapter = profile["connection"]["adapter_model"]
    if adapter not in ADAPTERS:
        raise ValueError("Unknown Growatt adapter")
    return profile


def serial_ports(root=Path('/dev')):
    # Discovery only: never open a port, change line settings or transmit a frame.
    return sorted({str(p) for pattern in ('serial/by-id/*', 'ttyUSB*', 'ttyACM*')
                   for p in root.glob(pattern) if p.exists()})


def select_adapter(path, adapter):
    return configure_connection(path, adapter)


def configure_connection(path, adapter=None, **serial):
    profile = load_profile(path)
    adapter = adapter or profile['connection']['adapter_model']
    if adapter not in ADAPTERS:
        raise ValueError("Unknown Growatt adapter")
    serial = {key: value for key, value in serial.items() if value is not None}
    if serial and adapter != 'USB-RS232':
        raise ValueError('Serial settings require the USB-RS232 adapter')
    for key, value in serial.items():
        valid = {
            'serial_port': lambda v: isinstance(v, str) and bool(re.fullmatch(r'/dev/(serial/by-id/[A-Za-z0-9_.:+-]+|tty(?:USB|ACM)[0-9]+)', v)),
            'baud_rate': lambda v: type(v) is int and v in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200),
            'parity': lambda v: v in ('none', 'even', 'odd'),
            'stop_bits': lambda v: type(v) is int and v in (1, 2),
            'unit_id': lambda v: type(v) is int and 1 <= v <= 247,
        }
        if key not in valid or not valid[key](value):
            raise ValueError('Invalid serial setting: ' + key)
    changed_adapter = profile['connection']['adapter_model'] != adapter
    if not changed_adapter and all(profile['connection'].get(k) == v for k, v in serial.items()):
        return profile
    # Device identity remains; all adapter-specific evidence must be collected anew.
    if changed_adapter:
        profile["connection"].update(adapter_model=adapter, adapter_serial_number=None,
            adapter_firmware=None, local_ip=None, serial_port=None, baud_rate=None,
            parity=None, stop_bits=None, unit_id=None)
    profile['connection'].update(serial)
    profile['connection'].update(integration_method='pending_qualification', physical_interface_verified=False)
    profile["status"] = "awaiting_onsite_connection"
    profile["qualification"].update(telemetry_verified=False,
        openems_driver_verified=False, equipment_writes_enabled=False)
    target = Path(path)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return profile


def connection_status(path=PROFILE):
    profile = load_profile(path)
    return {"profile": profile, "adapter_options": ADAPTERS,
            "serial_ports": serial_ports(), "serial_driver_implemented": False,
            "receiver_implemented": False,
            "notice": "Awaiting on-site qualification. USB-RS232 and ShineWiFi-S require a compatible RS232 port; ShineWiFi-X requires USB. Receiver/serial driver integration is not implemented. Selecting an adapter does not connect the inverter."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=PROFILE)
    parser.add_argument("--adapter", choices=ADAPTERS)
    parser.add_argument('--serial-port')
    parser.add_argument('--baud-rate', type=int)
    parser.add_argument('--parity', choices=('none', 'even', 'odd'))
    parser.add_argument('--stop-bits', type=int, choices=(1, 2))
    parser.add_argument('--unit-id', type=int)
    args = parser.parse_args()
    serial = {key: getattr(args, key) for key in ('serial_port', 'baud_rate', 'parity', 'stop_bits', 'unit_id')}
    if args.adapter or any(value is not None for value in serial.values()):
        try:
            configure_connection(args.profile, args.adapter, **serial)
        except ValueError as error:
            parser.error(str(error))
    print(json.dumps(connection_status(args.profile), indent=2))


if __name__ == "__main__":
    main()
