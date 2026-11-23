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

The native serial bridge is staged disabled with the existing Prolific
adapter's stable path, 9600 baud, 8N1. The native control policy is disarmed
and the night planner is disabled. No Pi command, recovery ledger or armed
policy was copied to this board. Null equipment channels are expected
until the adapter is moved and fresh reads are verified.

## Cloud identity

The existing server is `100.122.80.43`; owner login remains the existing
`admin` account at `http://100.122.80.43:8080`.

The new native Edge identity is `original-home-olinuxino`, with a unique
private API key. Its site is `olinuxino-home`, displayed as
`Olinuxino gateway`, and owned by the same `admin` membership. Origin is
`unverified` during commissioning. The existing Pi's `first-home` site,
gateway API key and history were preserved. The server's prior metadata
was backed up privately as `metadata.pre-olinuxino.json`.

## Physical migration state

The owner intends to move the existing inverter adapter from the Pi.
Before requesting the move, the Pi night planner was paused, a MONITOR
request submitted, and fresh native readback verified AC-charge enable=0,
schedule enable=0 and fallback_required=false. Its private policy was
then disarmed. Previous policy/schedule files are preserved in the Pi's
`~/.config/originalhome/olinuxino-migration-backup/`.

The owner subsequently reported that the adapter had **not moved yet**.
Do not describe Olinuxino equipment telemetry or control as commissioned.
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

Remaining acceptance checks are the physical serial migration, fresh local
and cloud equipment telemetry, and board-specific control recovery before
re-arming control or the night planner.
