# Olinuxino gateway commissioning

## Hardware and network recovery — 23 November 2026

Serial console: PC `COM4`, 115200 baud, 8N1. Detected A64, ARM64,
2 GiB RAM, approximately 58 GiB SD storage. The card originally booted
Linux 6.6.28 from its FAT partition, but the Debian 11 root filesystem
contained only 5.10.180-olimex modules. Ethernet required a missing module.
The root filesystem UUID in `/etc/fstab` was also wrong, leaving `/` read-only.

Recovery preserved the old FAT `boot.scr`, kernel Image, device tree and
fstab in `/root/originalhome-recovery/`. The original FAT script is also
retained as `/boot.scr.original` on partition 1. The repaired script loads
the installed 5.10.180-olimex kernel and its 2Ge8G device tree from partition
2. No partition was formatted. The root UUID was corrected.

Ethernet also needed the Micrel KSZ9031 driver rather than Generic PHY.
`/etc/modules-load.d/originalhome-ethernet.conf` loads `micrel` at boot;
module indexes were regenerated. A 1 Gbps/full-duplex link, DHCP lease
`192.168.1.122/24`, default route through `192.168.1.2` and an internet ping
were verified. The router-provided DNS server did not resolve Tailscale;
`1.1.1.1` was added through resolvconf's persistent head configuration.

Tailscale 1.104.7 is installed and enrolled on the existing owner's tailnet:

- Name: `original-home-olinuxino`
- Address: `100.67.173.78`
- Existing OpenSSH provides login; no exit node, subnet route or Funnel.
- Tailscale DNS acceptance is disabled, preserving the working local resolver.

This recovers the existing mixed installation. It does not establish that
this old OS/kernel is the final supported production board image.

## Gateway deployment

The Linux service user is `original_volt_gateway` on this board as well,
preserving paths embedded in the existing custom OpenEMS telemetry bundle.
The machine and cloud gateway identities are distinct from the Pi.

- Source: `/home/original_volt_gateway/OriginalHomeIOT`.
- OpenEMS: `/home/original_volt_gateway/original/openems-edge.jar`, copied
  from the deployed Pi distribution, with its custom telemetry/control bundles.
  SHA-256: `356eae81441f41310969dbb3ce8b0ee083841b8045be664e00da42bff4766da2`.
- Java: checksum-verified Temurin 21.0.13.1+2 ARM64 under
  `/opt/originalhome-java/current`.
- Python: independent Python 3.13.18 source build under `/opt/originalhome-python`;
  system Python remains unchanged.
- System units: `original-edge`, `originalhome-gateway`,
  `originalhome-firewall`, `tailscaled`, and `nginx`.
- Private runtime configuration: `~/.config/originalhome/`.
- Generated local credentials: board root-only
  `/root/originalhome-recovery/access.json`, with a Git-ignored PC copy in
  `local/olinuxino_access.json`. UI username is `admin`; use its
  `gateway_password` field, not the cloud or Linux password.

`systemd-timesyncd` was installed and enabled. NTP synchronization and
Europe/Bucharest timezone were verified. Build dependencies used available
Bullseye main packages after the security mirror advertised missing package
files; security sources remain enabled. This was not a full OS upgrade.

The gateway binds to loopback port 8080. Nginx proxies port 80 for Tailscale
IPv4 clients and loopback; gateway Basic authentication remains required.
Persistent IPv4/IPv6 filtering rejects non-loopback access to OpenEMS
ports 8081 and 8084. These ports are for SSH-tunnel/board-local maintenance.
ThingsBoard forwarding is disabled.

The native serial bridge was initially staged disabled with the existing
Prolific adapter's stable path, 9600 baud, 8N1. It was enabled and validated
for real reads on 24 November. The native control policy remains disarmed
and the night planner remains disabled. No Pi command, recovery ledger or
armed policy was copied to this board.

## Cloud identity

The existing server is `100.122.80.43`; owner login remains the existing
`admin` account at `http://100.122.80.43:8080`.

The new native Edge identity is `original-home-olinuxino`, with a unique
private API key. Its site is `olinuxino-home`, displayed as
`Olinuxino gateway`, and owned by the same `admin` membership. Origin was
initially `unverified` and became `equipment` after real-read validation on
24 November. The existing Pi's `first-home` site,
gateway API key and history were preserved. The server's prior metadata
was backed up privately as `metadata.pre-olinuxino.json`.

## Physical migration state

The owner intends to move the existing inverter adapter from the Pi.
Before requesting the move, the Pi night planner was paused, a MONITOR
request submitted, and fresh native readback verified AC-charge enable=0,
schedule enable=0 and fallback_required=false. Its private policy was
then disarmed. Previous policy/schedule files are preserved in the Pi's
`~/.config/originalhome/olinuxino-migration-backup/`.

On 23 November the owner reported that the adapter had **not moved yet**.
On 24 November the owner confirmed that it was connected to the Olinuxino;
read-only serial validation is recorded below. Control is not commissioned.
Before enabling control, move the physical adapter, verify its exact stable
device path, give the new service process dialout membership, enable only
the new native bridge, and verify advancing equipment samples and identity.
Qualify restart/recovery on this board before restoring armed operation or
the 02:00–05:00 night plan. Do not attach two serial masters to the inverter.

Python installation and all 25 tests in the six gateway test modules completed successfully.
Authenticated UI/assets/overview/device API requests returned HTTP 200 both
on loopback port 8080 and through nginx port 80. Unauthenticated access
returned HTTP 401. The overview correctly reported unavailable equipment,
unverified origin, no fabricated history and control_enabled=false.

An actual board reboot passed: the matching kernel, writable root, Ethernet
carrier and DHCP address, Tailscale address, NTP synchronization, all six
enabled services, OpenEMS Backend/REST/custom components and authenticated
UI access from the PC over Tailscale recovered. No failed system units were
reported. REST authentication also survived reboot.

Board-specific control recovery subsequently passed on 24 November, as
recorded below. General control and the night planner remain disabled.

## Inverter read validation — 24 November 2026

Found the original Prolific adapter as `/dev/ttyUSB0`, with stable path
`/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CYBCb2A5414-if00-port0`.
The Java service has dialout membership. Physical control policy and the
night planner were confirmed disabled before serial activation.

An initial activation exposed two configurations with component ID
`modbusGrowattNative0`: the staged disabled configuration and a newly
created enabled factory instance. Felix's factory POST creates a new UUID
instance even when a descriptive PID is supplied. The disabled duplicate
was backed up privately and removed; OpenEMS was restarted to bind the
driver to the single retained enabled bridge. Future updates must discover
and use the actual existing configuration PID without `factoryPid`.

At 9600 baud, 8N1, the native driver produced four advancing, fresh,
available samples. Its identity gate matched model code `GT1100F25D`
and reported serial `9876543210`, consistent with the previous Pi reader.
The previously documented difference from nameplate `NUCPB2101P` remains
unresolved; this test does not establish a new nameplate match.

Initial observations: battery 68%, 52.9 V, approximately 630–636 W
discharge, household load approximately 630 W, near-zero grid power and
near-zero nighttime PV. Small nonzero nighttime PV readings are retained
as measured; this is not daylight generation qualification. The inverter
clock was roughly eight minutes behind the gateway during the test; do not
restore timed charging without the existing clock/lease checks.

`fuser` confirmed one serial owner: the OpenEMS Java process. Native
readback showed AC charging disabled and all schedule enable flags zero.
No physical write authority was enabled. Local source origin was changed
to `equipment` after successful native identity/freshness checks; the
authenticated local UI returned connected, non-stale real samples and
accumulating history with control disabled.

Private detailed evidence is at
`~/OriginalHomeIOT/data/commissioning/olinuxino-read-validation-2026-11-24.json`.

Cloud validation also passed through the existing owner's authenticated API:
`olinuxino-home` reported `connection=connected`, `status=live`, and an
observation age of approximately 1.5 seconds. The native Backend exposed all
six allowlisted channels, including advancing `LastSuccessfulRead` values.
A later sample showed 68% SoC, 850 W battery discharge, 860 W load and 10 W
grid import, consistent with the local gateway's contemporaneous readings.
The cloud source origin was changed to `equipment` only with a fresh stored
sample present. Cloud control remains disabled. The original Pi's site and
history remain intact; it no longer receives the moved inverter's readings.

## Bounded write qualification — 24 November 2026

The owner explicitly requested the Pi-equivalent write validation. Preflight
verified fresh native identity/readback, a single Java serial owner, idle AC
and all disabled schedule flags, 68% battery SoC, and the paused night plan.
Measured inverter clock progression was approximately 0.839 device seconds
per wall second, consistent with the existing half-lease schedule margin.

Tests used the deployed native OpenEMS writer and its temporary commissioning
path. No direct serial writer, protection-register write, or competing bridge
was introduced. Existing charge cap was 33% and stop SoC was 90%.

- Holding 1090 changed to 10% and was verified by native readback.
- A short grid-charge window activated AC charging and the atomic FC16 slot.
  Across 54 useful observations, median battery charging was 210 W, with
  negligible PV and grid import above household load.
- Hardware timed expiry was observed before the wall-clock lease ended.
- The existing 33% operating setting produced 930–942 W charging across six
  useful samples, below the initial 1000 W operating ceiling.
- Explicit cancellation cleared AC charging, disabled the slot and returned
  the inverter to load-first mode.
- A separate bounded 1000 W request was active when `original-edge` was
  genuinely restarted (PID 4222 to 5461). Fresh readings returned; native
  fallback cleared AC charging and the slot, the durable fallback marker
  became false, and the old command was not replayed during observation.

Cleanup verified charge cap 33%, stop SoC 90%, AC=0, priority=0, and all
schedule times/enables zero. Temporary requests and commissioning authority
were removed. The policy records board-specific qualification evidence but
`writes_enabled=false`; the night plan is still disabled. The owner ceiling
remains 2990 W, while rates above 1000 W are not qualified. Existing inverter
discharge protection was not changed or newly claimed as qualified.

Sanitized summary:
[olinuxino-control-validation-20261124.json](../tools/openems-growatt-control/evidence/olinuxino-control-validation-20261124.json).
Detailed observations and recovery records remain under the board's
`~/OriginalHomeIOT/data/commissioning/`. Authenticated live monitoring was
verified after final cleanup.

## Armed operation — 25 November 2026

At the owner's explicit request, enabled the qualified native control policy
with its 1000 W operating ceiling and enabled the 02:00–05:00
Europe/Bucharest night plan at 1000 W to 90% SoC. The owner ceiling remains
2990 W; higher operating rates are still unqualified.

Preflight confirmed synchronized time, fresh idle native readback, one Java
serial owner, no pending fallback, no temporary commissioning authority or
old command, and the saved successful write/restart qualification. Native
readiness and the authenticated control API confirmed armed state and the
configured plan. At activation, the planner was outside its window; AC
charging and the inverter slot remained disabled. No immediate manual
charge request was submitted. Both services remain enabled for startup.

Previous private policy/plan/status were preserved on the board in
`data/commissioning/olinuxino-pre-arm-20261125.json`. The arming snapshot is
[olinuxino-armed-20261125.json](../tools/openems-growatt-control/evidence/olinuxino-armed-20261125.json).
