# Native Growatt strategy commissioning

The gateway has a native OpenEMS schedule driver and a local strategy form.
General interface writes remain disarmed pending charging-power calibration.
The owner withdrew the extra 15% reserve; existing inverter protection is unchanged.
The requested charge ceiling remains 2990 W; this is not claimed as a globally
enforced inverter limit.

## Actual write path

- Holding 1090: battery-first charge percentage, written with FC06.
- Holding 1100?1102: first battery-first schedule, written together with FC16.
  `ScheduleSlotElement` represents the entire triple as one native element,
  so the bridge cannot emit a partially queued schedule.
- Holding 1044: priority readback only. No writes to 1044 or 1045 remain.
- Holding 1092: AC-charge readback only; it must remain zero.
- No writes to grid-first, protection, chemistry, test or factory registers.

Python only submits trusted private JSON commands/configuration. All physical
register writes use the installed OpenEMS Modbus bridge. The original serial
collector is stopped during native ownership and restored afterward.
This is a device-mode controller, not a ManagedSymmetricEss power actuator.
Do not attach stock ESS balancing directly to these channels.

## Qualification and evidence

See [CONTROL_MAP.md](CONTROL_MAP.md) for identity and source references.
Firmware is RA1.0 / RAAA181703 / ZCBA-0003, model code GT1100F25D.
Reported serial 9876543210 and owner nameplate NUCPB2101P remain distinct.

The evidence directory contains real commissioning observations. Single FC06
schedule writes did not stick; an FC16 triple activated battery-first and
stopped battery discharge at night. Each attempt restores the original cap,
empty disabled slot and original serial collector, verified by readback.
The schedule ending minute is treated conservatively as inclusive. Timed
requests use 120?180 seconds in the UI, with an absolute maximum of 180 seconds.
The end is computed using inverter time with half the wall-clock lease reserved
for observed clock drift, then rounded down; midnight-crossing
requests are rejected. Slots are daily schedules: disabling/clearing them after
use is essential. A timed end is not evidence of safe daily replay or recovery
from every communication/process failure.

`verification.json` is the historical initial read-only snapshot; it does not
represent the later hardware trials. Never reuse its bundle hash or test count
for the current build. Updated trial summaries are recorded separately.

## Tests and deployment

```sh
cd ~/OriginalHomeIOT
python3 tools/openems-growatt-control/build.py ~/original/openems-edge.jar
python3 tools/openems-growatt-control/deploy_shadow.py
python3 tools/openems-growatt-control/commission_read_only.py
```

Native checks cover 880 power-bound cases, 10800 clock/lease cases and an
atomic FC16 payload/consumption/cancellation test. The installer refuses an
armed policy or an existing native bridge. It preserves the private policy.
The native driver has no configuration/serial bridge during ordinary shadow
operation. Its boot backup is `~/original/openems-edge.pre-strategy-shadow.jar`.

## Bounded hardware commissioning

```sh
python3 tools/openems-growatt-control/commission_schedule.py --require-solar
```

Daylight preflight requires fresh PV surplus >=1500 W, battery SoC below 95%,
general control disarmed, all competing schedules disabled, and exactly one
serial owner. It saves baseline/evidence before enabling the separate temporary
commissioning path. The test reduces 1090 to 10%, verifies readback, activates
a <=180 second wall-clock lease with a shorter inverter-timed slot, observes physical measurements and expiry,
then restores settings in finally. General qualification flags are not forged.
Without `--require-solar`, the test can verify mode behavior at night but cannot
calibrate charging power. Evidence is uniquely named under data/commissioning.

Private documents live in `~/.config/originalhome/`: policy growatt-control.json,
request growatt-command.json, status growatt-control-status.json and durable
control ledger. Temporary commissioning uses growatt-commission.json and a
separate status file. It requires commissioning_enabled=true and an expiring
request; the orchestrator removes both authority and request during cleanup.

The authenticated local form submits short-lived requests; submission is not
application. Missing qualification returns HTTP 409, cross-origin/missing
custom header returns 403, and unsupported endpoints return 405. Grid charging,
forced discharge, export and tariff optimization remain outside this version.
