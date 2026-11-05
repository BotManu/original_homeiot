# Growatt on-site connection

Confirmed by the owner on 5 November 2026:

- Inverter: Growatt SPH6000TL BL-UP, serial NUCPB2101P.
- Datalogger: ShineWiFi-X, not currently reachable from the development Pi. It will be available at the deployment location.
- Device inventory: `config/devices/growatt-sph6000tl-bl-up.json`. This is a qualification record, not a loaded OpenEMS driver or an active connection.

## Connection boundary

The current OriginalHome UI still reads the existing OpenEMS **demo** installation. Do not change `OPENEMS_DATA_ORIGIN` to `equipment` until real equipment measurements are verified. No Growatt registers, network endpoints or firmware versions have been inferred from the inverter serial number.

The stock ShineWiFi-X uploads data to a monitoring server. A local upload receiver/proxy is a candidate; a direct standard Modbus TCP server must not be assumed just because the adapter uses Wi-Fi. Grott documents a proxy mode that receives uploads, decodes telemetry and forwards the original traffic to Growatt. It includes SPH support, but that does not establish the exact BL-UP firmware's data layout or writable capabilities. A receiver would require an additional OpenEMS telemetry integration; the current REST reader does not perform that role. Monitoring via uploads is not proof that the offline energy-control requirement is met.

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

- [Growatt SPH 3000–6000TL BL-UP product and downloads](https://en.growatt.com/products/sph-3000-6000tl-bl-up)
- [Grott upstream: proxy mode and SPH support](https://github.com/johanmeijer/grott)
- [Growatt Datalogger upstream: ShineWiFi-X server configuration](https://github.com/FezVrasta/growatt-datalogger)

These are investigation references, not claims that the installed OpenEMS image or this exact device firmware is supported.
