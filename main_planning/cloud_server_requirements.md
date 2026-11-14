# Cloud server to provision now

14 November 2026. For the [energy-only release plan](release_1_energy_cloud_plan.md). These are engineering provisioning estimates for development and a small supervised pilot, not vendor minimums or tested fleet capacity. No ThingsBoard or LoRa services are required.

## Recommended order

Provision **one expandable x86-64 Linux VM: 8 vCPU, 32 GB RAM, 300 GB SSD/NVMe**, Ubuntu Server 24.04 LTS, wired/datacenter networking, a stable public IPv4 address and DNS control. A dedicated physical server with equivalent available resources also works. Prefer an EU region if the first users are in Romania/EU; confirm actual residency, backup location and provider terms. GPU and Kubernetes are unnecessary.

| Resource | Minimum for initial engineering | Recommended now |
| --- | --- | --- |
| CPU | 4 vCPU | 8 vCPU, expandable; avoid heavily contended burst-only capacity |
| RAM | 16 GB | 32 GB to allow backend, databases, app and builds/testing |
| Storage | 150 GB SSD | 300 GB SSD/NVMe with online expansion and disk monitoring |
| OS | Supported 64-bit server Linux | Ubuntu Server 24.04 LTS, minimal installation |
| Network | Reliable outbound HTTPS and inbound HTTPS | Stable public address, 1 Gbit/s interface; start with at least 1 TB/month transfer allowance and monitor |
| Backup | Separate destination | Encrypted off-host/object storage, initially at least 300 GB, expandable |
| Administration | Key-based SSH with restricted access | VPN/private administration, non-root named accounts, provider console/rescue access |

The minimum excludes concurrent CI builds and a full second environment. The recommended VM can host development and pilot during early integration, but it is one failure domain, without high availability. Before paid operation, use a separate production host and staging host; a 4-vCPU/8–16-GB staging VM is a starting estimate. Keep load tests and deploy experiments off the live pilot.

Illustrative 32-GB RAM allocation: 8 GB for the two OpenEMS backend processes together, 8 GB for business/timedata databases, 4 GB for application/worker, 2 GB for proxy/monitoring/identity and 10 GB for OS/cache/headroom. Measure actual JVM and database needs; these are budgets, not prescribed heap settings. Build containers on a workstation/CI when practical.

## What the host will run

Use Docker Engine and Compose from supported packages, with versioned configuration, pinned images/digests, restart policies, health checks, resource limits and persistent volumes:

- TLS reverse proxy (Caddy or nginx), serving OriginalHome static UI and routing API/WebSocket traffic.
- OpenEMS Backend and compatible Backend.Edge.App where required by the pinned release. Older installed versions may have a different topology; qualify the pairing before upgrading the Pi.
- OriginalHome application and worker for site registry, authorization, alarms, export and VPP supervisory workflows.
- PostgreSQL for OriginalHome business/audit data, plus the timedata store selected in the OpenEMS compatibility spike. Do not assume the upstream example contains a complete production identity/history setup.
- An established identity integration and basic metrics/log collection, with bounded log retention. Start small; no broker or extra queue cluster without a concrete need.

Only host provisioning is ready to execute from this document. A production Compose bundle, actual enrollment implementation, database migrations and server deployment remain development deliverables. Do not expose the current Python development HTTP server directly to the internet.

## DNS, firewall and access

Create names under a domain you control, for example `app.<domain>` for UI/API and `edge.<domain>` for gateway ingress. They can resolve to the same VM. Use trusted TLS certificates and WebSocket upgrade support. Gateways initiate outbound connections over TCP 443; no customer router port forwarding is needed.

| Port/path | Exposure |
| --- | --- |
| TCP 443 | Public reverse proxy only; authenticated application/API and TLS gateway ingress |
| TCP 80 | Optional certificate issuance/HTTPS redirect only; can be omitted with DNS-based issuance |
| SSH 22 | VPN or explicit administrator source addresses only; keys, no public password login |
| OpenEMS ingress/UI service ports | Private container network or loopback; proxy only the intended endpoints |
| OpenEMS 8083 Edge.Manager, 8078/8079 Felix admin | Private trusted network; never public |
| PostgreSQL 5432, timedata DB, monitoring/admin endpoints | Private only; no public database publishing |

The current OpenEMS architecture explicitly describes the backend inter-service link as trusting its network. Isolate that link from arbitrary containers/users, as well as from the internet. Container-published ports can bypass simplistic host firewall expectations: verify the effective rules from an external host and scan both IPv4 and IPv6. Do not copy the upstream example's published Felix/admin ports onto a public interface.

Permit required outbound DNS, time synchronization, HTTPS updates/registries and backup traffic. Use host time synchronization, disk/clock alarms, automatic security updates with controlled restarts, private secret files or a secret manager, separate service credentials and log redaction. Keep gateway and user credentials distinct. Plan SMTP/email delivery for invitations, password recovery and alarms; choose a provider before those flows enter the pilot.

## Data sizing and initial retention

Planning workload: 10 pilot gateways, each sending one normalized sample containing roughly 10–20 selected energy/status fields every 5 seconds. This is 172,800 sample envelopes/day, not 172,800 individual scalar values. At an assumed effective 1–2 KB per stored envelope including typical overhead, it is about 0.17–0.35 GB/day or 5–10 GB per 30 days, before additional indexes, WAL, replication and backup copies. Scalar-schema writes can differ substantially. Benchmark the chosen store with real payloads before treating this as capacity.

At 100 gateways the same envelope estimate is about 52–104 GB/month before those extras. That is an expansion/load-test milestone, not guaranteed capacity of this VM. One-second uploads increase sample counts fivefold; avoid enabling all OpenEMS channels by default. Local control cadence and cloud storage cadence are separate.

Proposed pilot policy: 30 days of raw 5-second cloud samples, 12 months of 1-minute aggregates initially, separately retained audit/dispatch records, and explicit deletion/aggregation jobs. Define energy counter/interval preservation before downsampling. Size the aggregates after measuring the actual schema. Reserve space for OS/images, database maintenance, logs and at least 30% free headroom; alert at 70% disk use and act before 80%.

Gateway target: 72 hours of telemetry buffering at the selected cadence, subject to qualification and a documented overflow policy. The current 17,280-sample default is only about 24 hours at 5 seconds and is not already a 72-hour implementation. Test cloud replay rate limiting, deduplication and live-data priority. Preserve observation time and gaps; never backfill old data as current live state.

## Backups and operator readiness

Take encrypted daily database/configuration backups to a different host/provider account; retain an initial 7 daily and 4 weekly copies, adjusting storage after measuring. Back up OpenEMS metadata/configuration, OriginalHome records, timedata and required key material through an approved secret backup process. A provider snapshot alone is insufficient. Keep keys separate from the encrypted backup and test restore onto a clean VM.

Initial pilot targets: recovery point within 24 hours, operator-led restore within 4 hours. These are objectives to prove in a drill, not an SLA. Add database point-in-time recovery if dispatch/audit or commercial requirements cannot tolerate that loss. Watch ingress failures, offline gateways, observation age, backlog, command failures, JVM memory, DB size, disk, certificate expiry and backup age. Assign a human operator and an incident contact before unattended pilot operation.

## Provisioning handoff checklist

1. VM ready with the recommended resources, supported OS, filesystem space and expansion path.
2. Public IP, domain/DNS administration, VPN/restricted key-based SSH, rescue console and named administrator available.
3. Firewall policy above applied; inbound reachability checked from outside, including IPv6.
4. Docker/Compose installed; secrets and persistent data paths outside the source repository; no default admin credentials exposed.
5. Separate encrypted backup destination, retention policy and restore credentials available; clock synchronization healthy.
6. Supply host name/IP, domain names and SSH public-key onboarding through a private channel. Do not put private keys or passwords in Git or planning documents.
7. Next engineering task: deploy a pinned minimal OpenEMS connectivity spike, connect the existing real Pi, then add registry/history/UI. Server provisioning does not authorize inverter writes.

## Sources and limits

The host size and operational targets above are project estimates. Backend component layout and private-port requirements are based on [OpenEMS architecture](https://openems.github.io/openems.io/openems/latest/backend/architecture.html) and [Docker deployment](https://openems.github.io/openems.io/openems/latest/backend/deploy/docker.html), reviewed 14 November 2026. Outbound connection and replay capabilities are described in the [Edge Backend API](https://openems.github.io/openems.io/openems/latest/edge/controller.d/io.openems.edge.controller.api.backend.html); configuration and loss limits still require tests against our pinned release.
