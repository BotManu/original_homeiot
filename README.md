# OriginalHomeIOT local gateway

First implementation slice: a local browser UI, read-only OpenEMS energy adapter, bounded SQLite history and optional durable ThingsBoard telemetry forwarding. Runs on Python 3.11+ using only the standard library. The UI loads entirely from the gateway; no CDN or internet connection is required.

## Run locally

```powershell
python -m gateway
```

Open http://127.0.0.1:8080. Default mode is an explicitly labeled simulator. It cannot forward example data to ThingsBoard. Stop with Ctrl+C.

## Connect OpenEMS

Enable the OpenEMS REST controller in **read-only** mode on the local Edge. Supply its actual URL and credentials through environment variables. In PowerShell:

```powershell
$env:GATEWAY_MODE = 'openems'
$env:OPENEMS_URL = 'http://127.0.0.1:8084'
$env:OPENEMS_USER = 'x'
$env:OPENEMS_PASSWORD = '<your OpenEMS read-only password>'
$env:GATEWAY_PASSWORD = '<your local UI password>'
python -m gateway
```

Sign into the local UI as `admin` using `GATEWAY_PASSWORD`. For LAN development set `GATEWAY_HOST=0.0.0.0`; a password is required outside loopback or in live mode. This development HTTP server uses Basic authentication: use a trusted LAN/VPN for development and terminate HTTPS at a reverse proxy before deployment. It is not a production identity service and must not be exposed to the internet.

The adapter reads `/rest/channel/_sum/.*` and selects only `ProductionActivePower`, `ConsumptionActivePower`, `GridActivePower`, `EssActivePower`, and `EssSoc`. Null, missing, nonnumeric or invalid SoC values reject the sample. Power is W; SoC is percent. Grid positive means import; battery positive means discharge. Confirm these channels, units, signs, permissions and sensor freshness against the actual OpenEMS release and hardware. The UI timestamp is gateway collection time, not a guarantee of equipment sample freshness. An HTTP response alone cannot establish device health. Failed reads retain the last measurement with an unavailable warning; there is no automatic switch to simulated values.

## Forward to ThingsBoard

Create a device in your existing ThingsBoard instance for this gateway and supply its device access token. Set both variables before starting in `openems` mode:

```powershell
$env:THINGSBOARD_URL = 'https://your-thingsboard-host'
$env:THINGSBOARD_TOKEN = '<device access token>'
python -m gateway
```

Only normalized energy measurements leave the gateway. The HTTP device telemetry API receives original collection timestamps. Delivery is at least once: a crash after upstream acceptance may retry the same timestamps. No physical commands are queued or sent. This adapter complements ThingsBoard; it does not install ThingsBoard CE, replace its registry/history/rules, implement cloud UI, or deploy OpenEMS itself.

Local collection and delivery use separate workers. During a ThingsBoard outage, collection and UI continue. `data/openems/gateway.sqlite3` retains both history and delivery state across restarts. Demo data uses a separate database. Default retention is 17,280 samples (about 24 hours at 5-second polling). At capacity the oldest samples are removed, including unsent samples; the UI reports a cumulative unsent-drop count. Back up SQLite using its backup API or while the gateway is stopped; WAL files matter during live operation. Restart after changing the destination only once the existing queue is drained, or use a new `GATEWAY_DATA` directory to avoid delivering old queued samples to a different device.

| Environment variable | Default |
| --- | --- |
| `GATEWAY_MODE` | `demo` (`openems` for actual reads) |
| `GATEWAY_HOST` / `GATEWAY_PORT` | `127.0.0.1` / `8080` |
| `GATEWAY_DATA` | `data` |
| `GATEWAY_PASSWORD` | Empty; allowed only for loopback demo |
| `POLL_SECONDS` | `5` |
| `SAMPLE_CAPACITY` | `17280` |
| `OPENEMS_URL` / `OPENEMS_USER` | `http://127.0.0.1:8084` / `x` |
| `OPENEMS_PASSWORD` | Empty |
| `OPENEMS_DATA_ORIGIN` | `unverified`; use `simulated` for OpenEMS demo equipment, `equipment` only after qualification |
| `THINGSBOARD_URL` / `THINGSBOARD_TOKEN` | Empty; forwarding disabled |

## Verify

Growatt commissioning supports ShineWiFi-X (USB/Wi-Fi), ShineWiFi-S (RS232/Wi-Fi), and direct USB-RS232 adapter profiles. Inspect the profile and detected Pi serial paths with `python -m gateway.growatt`; select wired commissioning with `python -m gateway.growatt --adapter USB-RS232`. Optional serial settings are validated and saved without opening the port. The authenticated `/api/devices/growatt` endpoint and UI report the selected profile. Adapter selection is preparation only: upload receiver, wired serial driver and OpenEMS integration are not implemented, and physical compatibility and telemetry require on-site qualification. See `main_planning/growatt_connection.md`.

```powershell
python -m unittest discover -s tests -v
```

Tests cover persisted offline delivery, retention overflow, retries with original timestamps, channel filtering, invalid upstream values, and demo isolation.

## Next integration gates

This is a development foundation, not the hardware-qualified pilot. Next: qualify the reference gateway and Growatt SPH6000 variant, connect an actual OpenEMS instance, verify measurements and freshness, then implement allowlisted strategy requests with authentication, expiry, duplicate rejection, bounds and observed feedback. Integrate general IoT device onboarding through ThingsBoard and add a production local identity/deployment profile. The local UI and later cloud UI will share normalized contracts while OpenEMS remains the sole energy writer.

Protocol references: [OpenEMS REST implementation](https://github.com/OpenEMS/openems/blob/develop/io.openems.edge.controller.api.rest/src/io/openems/edge/controller/api/rest/RestHandler.java), [ThingsBoard HTTP telemetry](https://thingsboard.io/docs/reference/http-api/telemetry/). These are reference contracts; a specific installed release still needs qualification.
