# SPH control-map investigation ? 2026-11-17

Hardware was probed using FC03 only. The collector was stopped for exclusive
serial access and restored automatically. Both services were active afterward.
Raw observations are in [the evidence file](evidence/control-map-read-2026-11-17.json).
The machine-readable result is [the candidate profile](../../config/devices/growatt-sph-control-map.json).

## Findings

Decoded identity: RA1.0 / RAAA181703 / ZCBA-0003; model code GT1100F25D;
DTC 3501; holding 88 is 305. That last word does not establish which battery
control extension is implemented. Main version RA1.0 alone is insufficient.
Reported serial remains 9876543210; it was not replaced with nameplate NUCPB2101P.

All tested legacy and scheduled control blocks respond. Holding 1090/1091/1092
are 100/100/0, while 1070/1071 are 100/10. Every schedule word at 1080?1088,
1100?1108, and 1110?1118 is zero. Thus the scheduled SPH map is read-compatible,
but the results cannot distinguish live controls from compatibility aliases.

## Documented candidate

Growatt Protocol II V1.24, pages 31?34, documents priority 1044 as read-only,
1045 as reserved, battery-first charge rate at 1090, stop SoC at 1091, AC charge
at 1092, and three start/end/enable slots at 1100?1108. Packed times use the
high byte for hour and low byte for minute. Grid-first uses 1070/1071 and
1080?1088. Do not confuse holding registers with same-numbered input registers.

Source: https://www.amosplanet.org/wp-content/uploads/2023/06/Growatt-Inverter-Modbus-RTU-Protocol_II-V1_24-English.pdf
Cross-check: Growatt Protocol II V1.39, pages 39?41.

## Implementation consequence

Use a timed battery-first slot as the candidate strategy mechanism, and read
1044 as resulting status. The driver has been replaced: 1090 uses FC06, and 1100?1102 use a single
indivisible FC16 element. The old 1044/1045 write tasks have been removed.
General control remains disarmed during commissioning.
Never write 1047 (aging test), 1048 (battery chemistry), or the broad system
bitfield at 1008 to discover strategy behavior.

A successful read is not write qualification. The next commissioning sequence
is a temporary reduction at 1090 with exact readback and restoration, followed
by a short timed solar-charge slot with AC charging remaining disabled. Check
measured power and automatic expiry before exposing persistent control.
The inverter clock currently reads 2026-11-17 12:07; gateway timestamps must
not be substituted when constructing slots.

Growatt's SPH family certificate lists a 3000 W battery rating, but variant
ratings differ; it supports a 3000 W conversion hypothesis, not a calibrated
limit for this unit. Do not derive a guaranteed 2990 W ceiling from one observed
charging sample. At a proven 3000 W reference, integer percentage control would
round 2990 W down to 99%, or 2970 W. Existing protection settings remain intact.

## Physical commissioning follow-up ? 18 November

Real native OpenEMS trials established that 1090 accepts a reduction from
100 to 10 and returns to 100 on restoration. Individual FC06 writes to the
schedule did not stick. Grouping the triple using FC16 activated battery-first;
priority became 1 and measured battery discharge fell from roughly 440 W to
0 W while the grid supplied the load. Disabling the slot returned priority to
0 and restored battery support. These are physical observations, not just
successful Modbus responses.

The FC16 requirement is also documented by the integration maintainers:
https://docs.evcc.io/en/meters/growatt-hybrid-inverter/

Timing required additional qualification: the inverter remained active during
the ending minute, and its reported clock advanced 98 seconds in 122 seconds
of gateway time. The driver therefore reserves half the wall-clock lease for
device time, treats the ending minute as inclusive, and starts in the previous
minute. This is a conservative margin for the measured drift, not proof that
the clock can never stop. A persistent daily slot must still be disabled after
use. Communication/process-loss qualification remains separate.

The night trials cannot establish the charging percentage-to-watts conversion:
PV was zero. The bounded daylight test has a fresh-PV/SoC preflight and must
verify charge response before charging-power calibration is marked complete.
Original charge cap, empty disabled schedule and collector are checked by
readback/restoration after every attempt. Raw trials retain unsuccessful
expiry observations rather than labeling them successes.

## Final bounded trial

The final trial activated battery-first, verified battery discharge stopped,
observed priority return to load-first while the slot enable was still 1, then
explicitly cleared the daily slot and restored 100% charge rate. The existing
collector was restored. See [commissioning-verification.json](commissioning-verification.json)
and its raw evidence link. Solar charging calibration remains unverified.
