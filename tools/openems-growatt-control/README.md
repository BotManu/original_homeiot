# Native Growatt strategy commissioning

The gateway has a native OpenEMS schedule driver and a local strategy form.
Controls on original-volt-gateway are armed at an initial 1000 W operating
limit. The nightly 02:00?05:00 Europe/Bucharest plan targets 90%.
The owner withdrew the extra 15% reserve; existing inverter protection is unchanged.
The requested charge ceiling remains 2990 W; this is not claimed as a globally
enforced inverter limit.

## Actual write path

- Holding 1090: battery-first charge percentage, written with FC06.
- Holding 1100?1102: first battery-first schedule, written together with FC16.
  `ScheduleSlotElement` represents the entire triple as one native element,
  so the bridge cannot emit a partially queued schedule.
- Holding 1044: priority readback only. No writes to 1044 or 1045 remain.
- Holding 1091: per-strategy charge-stop SoC, written before charging.
- Holding 1092: explicit AC-charge enable for GRID_CHARGE only; cleared first on cancellation.
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
custom header returns 403, and unsupported endpoints return 405. Forced discharge, export and price-driven optimization remain outside this version.

## Grid charging and nightly window ? 18 November

GRID_CHARGE now sets a bounded charge percentage and target SoC before enabling
AC charging and the timed slot. Cancel, expiry, target reached and a switch to
solar/self-consumption disable AC charging first. A grid-specific qualification
gate is checked in both Python submission and the native controller.

The real night trial passed: 10% charge request, target 90%, zero PV, median
battery charging 225.5 W across 24 samples. Grid import increased above home
consumption. The inverter timed mode expired, AC charging was disabled, and
the original 100% cap/100% stop SoC/empty disabled slot were restored.
See [grid-charge-verification.json](grid-charge-verification.json).
This establishes working grid charging, not a calibrated full-range watt map.

The owner's night window is 02:00?05:00 Europe/Bucharest. The configured initial
request is 1000 W to a 90% target, under the 2990 W owner ceiling. The local
planner submits rolling <=180-second leases, stops at target/outside the window,
and respects an unexpired manual request. The local UI can pause/enable the
night plan separately from submitting an individual strategy. Saving the plan
does not arm unqualified hardware. The gateway is now armed at 1000 W after the operating-rate and restart tests.

Private schedule: ~/.config/originalhome/growatt-night-schedule.json.
Planner state: growatt-night-status.json. The gateway polls every 15 seconds.
Use the Linux system timezone database; Windows development requires tzdata
for Europe/Bucharest. Timezone-aware planner tests were run on the Pi.

## Armed deployment ? 18 November

See [armed-controls.json](armed-controls.json) and the saved arming evidence.
A 33% request measured 930?970 W. The live profile caps requests at 1000 W;
the owner ceiling remains 2990 W and higher operating rates remain unqualified.
The 3000 W percentage reference is a conservative bound for the tested range,
not a claim that every requested watt is delivered exactly.

A real OpenEMS service restart exposed late bridge binding without protocol
registration. The driver now registers its protocol when a bridge binds after
activation. The repeated cold-start test resumed fresh readings, cleared AC
charging and the daily slot, and cleared the durable fallback marker without
replaying the old request. The test authority expired independently; the broad
recovery qualification was recorded only after the real test passed.

The legacy Python serial collector is disabled. OpenEMS owns the adapter and
publishes telemetry into the existing sample contract. The local gateway and
night planner remain active. The UI shows armed readiness only with fresh
native equipment readings and all required qualifications. API requests above
the live operating limit are rejected before submission.

Before maintenance: pause the night plan, cancel the active request and verify
AC=0 and slot enable=0. Disarm the private policy before removing the native
bridge or returning serial ownership to the legacy collector. Do not run a
direct serial probe while the native bridge owns the adapter. Shadow deployment
and commissioning scripts deliberately refuse the currently armed configuration.

## Olinuxino migration validation — 24 November 2026

The same inverter and Prolific adapter now have verified native reads on
`original-home-olinuxino`. Owner-authorized write tests passed: 10% cap
readback, grid charging (210 W median), hardware timed expiry, 33% operating
response (930–942 W), explicit cancellation, and recovery after a real
OpenEMS restart without replaying the old request. See
[gateway commissioning](../../main_planning/olinuxino_gateway.md) and
[sanitized evidence](evidence/olinuxino-control-validation-20261124.json).

Olinuxino control was qualified at the initial 1000 W level on 24 November
and **armed on 25 November at the owner's request**. Its 02:00–05:00
Europe/Bucharest night plan is enabled at 1000 W to 90% SoC. See the
[arming record](evidence/olinuxino-armed-20261125.json).
Final commissioning readback verified AC=0, load-first,
empty disabled slots, original 33% cap and 90% stop SoC. The Pi-specific
collector handoff scripts above are historical procedures; do not run them
unchanged against the Olinuxino's existing native bridge. Update its actual
factory configuration PID rather than creating a second bridge with the
same component ID.
