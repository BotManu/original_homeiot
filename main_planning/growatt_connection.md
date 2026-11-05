# Growatt on-site connection

Confirmed by the owner on 5 November 2026:

- Inverter: older Growatt SPH6000, serial NUCPB2101P. Owner corrected the earlier BL-UP designation. Exact nameplate suffix and firmware still need on-site verification.
- Selected datalogger: ShineWiFi-S (RS232 to Wi-Fi), not currently reachable from the development Pi. It will be available at the deployment location. Verify the physical port before commissioning.
- ShineWiFi-X (USB to Wi-Fi) remains a catalog alternative, not the selected adapter for this installation.
- Device inventory: `config/devices/growatt-sph6000.json`. This is a qualification record, not a loaded OpenEMS driver or an active connection.

## Connection boundary

As of 5 November 2026, the deployed OriginalHome UI reads the connected inverter through the isolated OpenEMS `growatt0` telemetry component. The owner confirmed nighttime SoC, battery voltage and grid power against the inverter display. The existing simulated OpenEMS components remain separate; their `_sum` channels are not used by OriginalHome. Daylight generation and battery charge/discharge sign checks remain outstanding. No register writes are enabled.

Stock ShineWiFi dongles upload data to a monitoring server. A local upload receiver/proxy is a candidate; a direct standard Modbus TCP server must not be assumed just because the adapter uses Wi-Fi. Grott documents a proxy mode that receives uploads, decodes telemetry and forwards the original traffic to Growatt. It includes SPH support, but that does not establish this exact older inverter firmware's data layout or writable capabilities. A receiver would require an additional OpenEMS telemetry integration; the current REST reader does not perform that role. Monitoring via uploads is not proof that the offline energy-control requirement is met.

No dongle configuration, Growatt cloud account, inverter setting, receiver listener, or existing OpenEMS component has been changed for this device.

## On-site sequence

1. Connect the Pi and dongle to the deployment LAN. Record the dongle serial, firmware, IP, inverter firmware, battery and grid-meter models. Reserve the Pi's local address; its current development address may differ at the site.
2. Capture the dongle's existing upload destination/port and reporting settings so they can be restored. Confirm whether continued ShinePhone/cloud reporting is required.
3. Qualify a pinned local receiver/proxy and the exact SPH payload parser. Configure the dongle upload destination only after the Pi receiver is ready. The destination is the Pi's on-site address, not necessarily 192.168.1.122. Initial upload cadence must be measured; it is not the gateway's five-second REST polling interval.
4. Verify NUCPB2101P in actual inverter records. Keep the inverter serial distinct from the datalogger serial. Check timestamps, buffered-vs-live records, units, signs, solar/grid/battery/load power and SoC against the inverter display. Preserve sanitized payload fixtures; never merge historical replay into live readings.
5. Implement and validate the corresponding OpenEMS telemetry component/bridge. Isolate physical equipment from the existing simulated components; do not let the `_sum` values silently combine both installations.
6. Point OriginalHome at the qualified component/channel mapping and show actual observation age. Test LAN/WAN loss, stale readings, restart and any proxy forwarding. Only then label the data as equipment measurements.
7. Qualify energy control separately through OpenEMS with exact protocol documentation. If the stock dongle cannot meet the needed local communication/control behavior, decide on an appropriate local interface before promising unattended control. No guessed register writes or second control writer.

## References

- Obtain the older SPH6000 manual matching the nameplate/firmware. Previously referenced BL-UP documentation is not qualification evidence for this installation.
- [Grott upstream: proxy mode and SPH support](https://github.com/johanmeijer/grott)
- [Growatt Datalogger upstream: ShineWiFi-X server configuration](https://github.com/FezVrasta/growatt-datalogger)

These are investigation references, not claims that the installed OpenEMS image or this exact device firmware is supported.

## Selecting the serial Wi-Fi adapter

The application now has a validated adapter catalog for `ShineWiFi-X` and `ShineWiFi-S`, an authenticated read-only profile endpoint at `/api/devices/growatt`, and a commissioning summary in the local UI. To select the serial Wi-Fi option on the Pi:

```sh
cd ~/OriginalHomeIOT
python3 -m gateway.growatt --adapter ShineWiFi-S
```

To choose the USB Wi-Fi alternative, pass `--adapter ShineWiFi-X`. Switching adapters preserves inverter identity but clears adapter IP/serial/firmware and previous communication qualification. It does not start a receiver or send inverter commands. The current selection is ShineWiFi-S following the owner's correction to the older inverter variant.

For ShineWiFi-S, verify the inverter provides the compatible RS232 connector and pinout before attaching it; do not substitute an RS485 port. Join the deployment's 2.4 GHz Wi-Fi, record the datalogger identity separately from NUCPB2101P, and qualify the local receiver using actual uploads. Receiver and OpenEMS bridge implementation remain outstanding for both adapter choices. No physical connection can be tested while the dongle is off site.

Manufacturer reference: [Growatt ShineWiFi-X and ShineWiFi-S instructions](https://cdn.growatt.com/user_manual_file/Growatt_Datalog_WIFI-X%26WIFI-S_Instrctions.pdf).

## Direct wired USB-to-RS232 option

`USB-RS232` is a third commissioning option. Topology: Pi USB port → USB-to-RS232 adapter → inverter's verified RS232 monitoring connector. This bypasses the Wi-Fi dongle. An RS485 converter or bare USB-to-TTL UART is not an interchangeable RS232 adapter. Confirm the manufacturer's connector pinout and cable arrangement before attaching equipment.

Inspect the available Pi serial interfaces and current profile:

```sh
cd ~/OriginalHomeIOT
python3 -m gateway.growatt
```

The JSON status includes `serial_ports`, with persistent `/dev/serial/by-id/…` paths when available and `/dev/ttyUSB…` or `/dev/ttyACM…` device nodes. Discovery only lists paths; it never opens a port or transmits a frame. The local UI also displays these paths.

Select wired commissioning with:

```sh
python3 -m gateway.growatt --adapter USB-RS232
```

Additional CLI options are `--serial-port`, `--baud-rate`, `--parity` (`none`, `even`, `odd`), `--stop-bits` (`1` or `2`), and `--unit-id`. Supply values confirmed for the exact older SPH6000 firmware; none are guessed or automatically applied. The unit ID setting is reserved for a verified Modbus integration. Supported configuration values do not establish that a protocol/baud is supported by the inverter. Prefer a persistent by-id port when selecting the actual adapter. Ensure the OpenEMS service user has serial-device access when commissioning the real driver.

Changing adapters clears previous transport settings and qualification. Changing serial settings invalidates the previous communication qualification. No port opens, register reads or inverter writes occur when saving this profile. Serial telemetry is now implemented for the installation described below. Receiver work for Wi-Fi adapters remains independent and unimplemented.

## Wired commissioning result — 5 November 2026

The Pi detected USB VID/PID `067b:23a3`, a Prolific/ATEN serial bridge, with the `pl2303` kernel driver. Persistent path: `/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BHBLd143M08-if00-port0` (`/dev/ttyUSB0`). The owner confirmed connection to the inverter's RS232 monitoring port. The existing service account belongs to `dialout`.

The inverter responded with valid Modbus CRCs at **9600 baud, 8N1, address 1**. Holding registers 28–29 read `0x1100, 0xF25D`, matching the display code **GT1100F25D**. This is a display/model code, not confirmation of a nameplate suffix. Holding registers 23–27 reported serial **9876543210**; the owner reconfirmed nameplate **NUCPB2101P**. That mismatch is unresolved and preserved in the profile. Do not overwrite or reprogram the inverter serial.

The owner confirmed roughly **50% SoC, 53.6 V battery voltage and 730 W grid import** against the display. Subsequent reads showed changing load/grid power around 660–730 W. Solar was near zero at night; daytime PV and battery power signs still need comparison under those operating conditions.

The register reference is the Growatt-authored [Modbus RTU Protocol II document](https://github.com/henols/growatt-client/blob/dev/docs/growatt-inverter-modbus-rtu-protocol-ii-series-modbus-growatt-inverter-modbus.pdf), whose title page identifies V1.05 and revision history includes V1.06. The downloaded filename on the Pi contains `v120` for historical reasons; it is not evidence of that document version. Input register pairs: 1–2 PV input power; 1009–1010 battery discharge; 1011–1012 battery charge; 1021–1022 import; 1029–1030 export; 1037–1038 local load, all in 0.1 W. Input 1013 is 0.1 V; 1014 is SoC percent. Solar reflects PV input/DC power, so it should not be treated as an exact AC energy-balance term.

### Installed data path

1. The user service `originalhome-growatt-serial` runs `gateway.growatt_serial` with pyserial, polling only three allowlisted blocks using functions 03/04. It verifies framing, CRC, display model code and measurement bounds. Requests are at least one second apart. It never issues register writes. Its atomic, private snapshot is `data/growatt-live/sample.json`.
2. `tools/openems-growatt/` builds a small OSGi component against the exact installed OpenEMS JAR using JDK 21, deriving bundle imports with `jdeps`. The component reads that snapshot on the OpenEMS cycle and exports five **read-only** channels plus `LastSuccessfulRead` under `growatt0`. It implements no managed ESS/control interface. Invalid or older-than-15-second snapshots clear its measurement channels and raise `CommunicationFailed` with OpenEMS fault state 3.
3. OriginalHome uses `OPENEMS_COMPONENT=growatt0`, `OPENEMS_DATA_ORIGIN=equipment`, and `GATEWAY_DATA=data/growatt-gt1100f25d` in its private environment file. The REST adapter rejects missing/stale equipment timestamps. Existing demo history is preserved separately.

The bundle is embedded as `jar/org.originalhome.growatt.readonly.jar` in `/home/original_volt_gateway/original/openems-edge.jar` and listed in `launcher.properties`. A full OpenEMS restart successfully loaded it. The original JAR is preserved as `openems-edge.pre-growatt.jar`; the original private environment is `~/.config/originalhome/gateway.env.pre-growatt`. Both user services are enabled, with user lingering already enabled. Reboot recovery remains untested.

Build after source changes with `python3 tools/openems-growatt/build.py ~/original/openems-edge.jar`. This creates `data/openems-build/originalhome-growatt-readonly.jar`; it does not deploy it. Replacing the OpenEMS distribution in future requires reincluding this bundle and its launcher entry.

Validated authenticated OriginalHome UI/assets/APIs over the Tailscale URL, advancing equipment-only history and disabled control. Stopping the collector cleared OpenEMS telemetry after 15 seconds; restarting it restored measurements. Raw initial replies and protocol text remain under the Pi's ignored `data/commissioning/` directory. No firmware, address, baud or inverter settings were written.

To roll back: stop/disable `originalhome-growatt-serial`; restore `gateway.env.pre-growatt` to `gateway.env` and restart `originalhome-gateway`. To also remove the OpenEMS bundle, stop `original-edge`, restore `openems-edge.pre-growatt.jar` to `openems-edge.jar`, and start `original-edge` again. Preserve live history for investigation.
