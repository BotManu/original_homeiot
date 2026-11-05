"""Growatt commissioning profiles; selecting an adapter does not establish a link."""
import argparse
import json
from pathlib import Path


ADAPTERS = {
    "ShineWiFi-X": {"inverter_interface": "USB", "network_interface": "Wi-Fi",
                    "integration_method": "growatt_upload_receiver", "qualification": "pending"},
    "ShineWiFi-S": {"inverter_interface": "RS232", "network_interface": "Wi-Fi",
                    "integration_method": "growatt_upload_receiver", "qualification": "pending"},
}
PROFILE = Path(__file__).resolve().parent.parent / "config/devices/growatt-sph6000.json"


def load_profile(path=PROFILE):
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    adapter = profile["connection"]["adapter_model"]
    if adapter not in ADAPTERS:
        raise ValueError("Unknown Growatt adapter")
    return profile


def select_adapter(path, adapter):
    if adapter not in ADAPTERS:
        raise ValueError("Unknown Growatt adapter")
    profile = load_profile(path)
    if profile["connection"]["adapter_model"] == adapter:
        return profile
    # Device identity remains; all adapter-specific evidence must be collected anew.
    profile["connection"].update(adapter_model=adapter, adapter_serial_number=None,
        adapter_firmware=None, local_ip=None, integration_method="pending_qualification",
        physical_interface_verified=False)
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
            "receiver_implemented": False,
            "notice": "Awaiting on-site qualification. ShineWiFi-S requires a compatible RS232 port; ShineWiFi-X requires USB. Selecting an adapter does not connect the inverter."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=PROFILE)
    parser.add_argument("--adapter", choices=ADAPTERS)
    args = parser.parse_args()
    if args.adapter:
        select_adapter(args.profile, args.adapter)
    print(json.dumps(connection_status(args.profile), indent=2))


if __name__ == "__main__":
    main()
