# Growatt on-site connection

Confirmed by the owner on 5 November 2026:

- Inverter: older Growatt SPH6000, serial NUCPB2101P. Owner corrected the earlier BL-UP designation. Exact nameplate suffix and firmware still need on-site verification.
- Selected datalogger: ShineWiFi-S (RS232 to Wi-Fi), not currently reachable from the development Pi. It will be available at the deployment location. Verify the physical port before commissioning.
- ShineWiFi-X (USB to Wi-Fi) remains a catalog alternative, not the selected adapter for this installation.
- Device inventory: `config/devices/growatt-sph6000.json`. This is a qualification record, not a loaded OpenEMS driver or an active connection.

## Connection boundary

The current OriginalHome UI still reads the existing OpenEMS **demo** installation. Do not change `OPENEMS_DATA_ORIGIN` to `equipment` until real equipment measurements are verified. No Growatt registers, network endpoints or firmware versions have been inferred from the inverter serial number.

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

Changing adapters clears previous transport settings and qualification. Changing serial settings invalidates the previous communication qualification. No port opens, register reads or inverter writes occur when saving this profile. `serial_driver_implemented` remains false: the installed OpenEMS image still requires a qualified older-SPH6000 serial driver/register map. The gateway UI continues to read the OpenEMS demo until that separate hardware integration is completed. Receiver work for Wi-Fi adapters is independent from this wired path.
