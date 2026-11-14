# Release 1: local energy gateway and OriginalHome cloud

Decision date: 14 November 2026. Status: agreed product direction; proposed engineering architecture and estimates. This document supersedes the release scope, topology and schedule in the older implementation, ThingsBoard and local gateway plans. It does not claim that the services below have been implemented or deployed.

## Product decision

Release 1 is an energy management product: OriginalHome provides the local application and cloud application; OpenEMS provides on-site energy integration and control. Use a real server and real equipment throughout integration. Keep simulators for repeatable failure tests, isolated from customer data and physical dispatch.

ThingsBoard, LoRa/LoRaWAN, ChirpStack, general home automation, cameras, 3D home modeling, voice, generic sensor onboarding and machine learning are deferred. No ThingsBoard account, broker or deployment is a release dependency. Existing optional ThingsBoard forwarding is legacy code, not the new cloud transport; leave its environment variables unset and remove it from the release packaging/configuration in a subsequent implementation task.

The product must work locally without a cloud subscription or WAN connection. Cloud adds remote access, longer history, fleet operations and an initial VPP capability. Cloud failure must not stop the local energy strategy. There is one equipment writer: OpenEMS. Cloud requests are supervisory intentions, never a second inverter feedback loop.

## Actual starting point

The repository contains a Python local UI/API, SQLite history/spool, OpenEMS read adapter, adapter inventory, serial collector and a custom read-only OpenEMS bundle. The documented Pi installation has actual older Growatt SPH6000 telemetry over USB-RS232, checked at night against its display. Daytime PV, battery power signs, nameplate/firmware identity, the reported serial mismatch and reboot recovery still need qualification. See [commissioning record](growatt_connection.md).

The `growatt0` bundle exposes telemetry; it does not implement managed ESS control. No verified physical write path, automatic energy strategy, cloud backend/UI, production enrollment, VPP dispatch or manufactured gateway is complete. The earlier 10–12 week release estimate cannot be carried forward to this larger cloud-plus-hardware scope. A real server removes a development constraint, not these integration gates.

## Architecture and ownership

```text
Qualified inverter / battery / site meter
        | verified wired protocol (RS485 or model-specific RS232)
OpenEMS Edge + qualified device driver + local strategy
        | local API                         | outbound TLS WebSocket
OriginalHome local UI/API + SQLite          OpenEMS cloud ingress/backend
                                                |
                                  OriginalHome API + worker + cloud UI
                                    | accounts/sites, audit, fleet/VPP
                                    | business DB + qualified timedata store
```

Keep the current collector/read-only bridge until a replacement is qualified. Implement any new writable energy-device integration inside OpenEMS, including the managed device interfaces required by the selected controllers. Avoid replacing a working data path solely to make the diagram simpler.

Prefer OpenEMS Backend for Edge connectivity, routing and historical data access rather than inventing another remote equipment protocol. Its current documentation describes a central Backend and a separate Backend.Edge.App, which can share one server. This is a proposed reuse decision: in the first two weeks, pin a compatible Edge/Backend release, test the existing custom bundle, choose supported metadata and timedata implementations, and prove authenticated reconnection and history replay. Latest upstream documentation is not evidence of compatibility with our installed JAR.

Use one OriginalHome cloud application (proposed FastAPI plus worker) for customer/site enrollment, authorization, alarms, exports, dispatch lifecycle and a branded UI. PostgreSQL owns those business records and audit events. Choose the timedata store supported by the pinned OpenEMS deployment in the spike; reserve resources for it now. Do not assume PostgreSQL is a drop-in OpenEMS timedata provider. Do not deploy Odoo or an additional database unless the selected metadata/timedata implementation needs it. Use file metadata only for the engineering spike; production enrollment must have one authoritative registry and tested authorization mapping.

OriginalHome owns customer/site/gateway identity and permissions; OpenEMS metadata is a controlled projection of those assignments. OpenEMS Edge owns commissioned device configuration, active strategy, limits and actual control state. Cloud history is a projection, never the source of immediate control truth. Distinguish requested configuration, gateway acknowledgement and applied revision. Physical limits remain locally enforced. Use supported APIs, not direct writes into another service's database.

No Kubernetes, Kafka or custom generic rules engine is required for the first pilot. Add MQTT only if a concrete energy integration needs it; the native Edge/backend path is WebSocket. Ordinary customers use OriginalHome locally and remotely; OpenEMS engineering tools remain installer tools.

## Required implementation

| Area | Release 1 deliverable |
| --- | --- |
| Local energy | Qualified PV/grid/load/battery/SoC, source timestamps, quality/staleness, useful history, supported manual override and one automatic self-consumption strategy |
| Control | Verified Growatt write path, managed OpenEMS device integration, power/SoC/export bounds, priorities, local override, command lease and measured feedback |
| Local application | Locally served assets, production authentication, installer commissioning, strategy/status screens, offline history and clear communication errors |
| Cloud identity | Owner/installer/operator roles, site isolation, invitations/revocation, operator MFA through an established identity solution, audited privileged operations |
| Enrollment | One-time gateway bootstrap, unique gateway credential, site binding, rotation/revocation, replacement/decommission workflow; no shared fleet token |
| Cloud experience | Sites/fleet, live/stale state, charts, interval energy, alarms, strategy requests, command results and bounded CSV export |
| Data | Versioned units/signs/channel contract, source versus receipt time, stable sample identity, deduplication, bounded replay, explicit gaps and retention |
| Operations | Reproducible images/install, health monitoring, backups/restore, controlled upgrades/rollback, diagnostics without credentials and support runbooks |
| VPP pilot | Opt-in fleet groups, eligibility/capability envelopes, bounded dispatch, per-site outcomes, aggregate measured response and operator cancellation |
| Gateway product | One qualified board/BOM, isolated serial interfaces, enclosure/power/storage, commissioning image, watchdog, recovery and traceable device identity |

Store UTC timestamps; display the site's configured timezone. Separate W from Wh/kWh. Prefer qualified cumulative counters for energy; if integrating power, retain coverage and calculation method and mark gaps. Never treat PV DC input and AC power as an exact energy balance. Keep simulated, unverified and equipment data visibly distinct in local and cloud views.

## VPP in the first release

Include a controlled technical VPP pilot: a small consenting fleet can respond to a scheduled aggregate import/export or charge/discharge request. This is feasible in the architecture, conditional on qualifying writable hardware at multiple sites. A single gateway plus simulated followers proves software only; require at least two physical controllable sites for VPP pilot acceptance.

Each site advertises direction, available power, energy/SoC headroom, freshness, ramp limits and local restrictions. Allocate the fleet request only among eligible opted-in sites; record unfulfilled power rather than promising unavailable capacity. Define the dispatch reference point (site grid meter), sign convention, interval, tolerances and maximum duration before testing. Measure achieved response at that point. Battery power alone does not prove aggregate grid response.

Every command has a unique ID, site scope, issuance/start/expiry timestamps, bounded target, duration/lease and dispatch revision. Enforce authentication and authorization at the cloud boundary and an allowlist/limits at Edge. Deduplicate requests, reject late or cancelled revisions, and never replay physical commands from the telemetry retry spool. Track requested, delivered, accepted, applied, observed, expired/cancelled/failed separately. Gateway restart and lease expiry return to a tested local strategy. Local operator override, equipment protection and site limits take priority over fleet dispatch.

On stale meter data, revoked consent, unavailable gateway or WAN failure, remove the site from available capacity and use the tested local fallback. Treat clock skew and loss of time synchronization as reasons to reject scheduled commands. Verify API timeout behavior on the pinned OpenEMS release; transport timeout is not proof that an inverter undoes an already applied mode.

Commercial balancing/ancillary-service participation, aggregator/market APIs, contractual availability, regulated metering, settlement, billing and revenue guarantees are a separate workstream. Before making market claims, commission jurisdiction-specific regulatory and market-entry review and agree partner requirements. No legal eligibility is asserted here. A technical VPP pilot can ship before that work is complete.

## Physical gateway

Use the existing Pi 4/4 GB for development. Recommended first product reference: Raspberry Pi 5 with 4 GB RAM, 64–128 GB SSD, wired Ethernet, suitable 5 V/5 A supply, thermal solution, RTC backup and enclosed isolated USB-RS485 interface. Qualify a pinned 64-bit Linux image, matching JRE and service definitions. RAM/storage are engineering targets, not measured minima. No desktop is needed. Prefer an assembled off-the-shelf enclosure/carrier for v1; a custom PCB changes the schedule.

OLinuXino is a credible alternative, but select an exact model rather than promising family-wide support. A64-OLinuXino-2Ge16G-IND has 2 GB RAM and 16 GB flash per its vendor, so it needs a separate Java/OpenEMS memory, OS, storage-endurance and thermal qualification. Its board temperature rating does not qualify the completed enclosure, PSU or serial assembly. Do not put two board families on the critical path; add the second after the first passes release gates.

RS485 is the gateway's standard expansion path, not proof of compatibility with the current inverter. The existing older SPH6000 uses a confirmed RS232 monitoring connection. Retain a separate isolated USB-RS232 option for that installation. RS232, RS485 and TTL UART are electrically different; match pinout and protocol to each supported device. RS485 planning includes galvanic isolation, surge/ESD protection, terminal labeling, cable/shielding instructions and documented termination/biasing. Have an electrical engineer review the assembly and intended installation.

Hardware work includes BOM and supplier availability, enclosure/DIN mounting, strain relief, serial-port ownership, stable device paths, watchdog, power-loss recovery, log rotation, storage limits, factory enrollment, unique serial/label, installation guide and replacement procedure. Do not clone gateway credentials in the image. Include staged authenticated updates, a tested rollback/recovery image and a commissioning checklist.

Before selling the assembled gateway, obtain a qualified assessment of applicable electrical/EMC/radio/environmental and product obligations in target markets. Module/board declarations alone do not establish compliance of the complete product. Reserve external lab/engineering time; scope and quotations determine the actual hardware launch date.

## Schedule and realistic market timing

Assumptions: one experienced full-time software/integration engineer using AI, owner access to equipment each week, fractional electrical/mechanical support and installer access, prompt procurement, one inverter family, one board, one local strategy, and 3–5 consenting pilot sites. AI helps implementation and test preparation; it cannot compress equipment access, field observation or product qualification. Dates below assume work starts 16 November 2026 and allow broadly for year-end interruptions; they are planning windows, not commitments.

| Elapsed time | Milestone and evidence | Approximate window |
| --- | --- | --- |
| Weeks 1–2 | Provision server, pin stack, prove real Edge/backend connection, identify metadata/timedata path; qualify Growatt physical write feasibility and obtain hardware BOM | Late November 2026 |
| Weeks 3–6 | Real monitoring cloud alpha, enrollment/site isolation, history; managed device control and one useful local strategy; assemble reference gateway | December 2026 to early January 2027 |
| Weeks 7–10 | Unified local/cloud strategy UX, leased commands and observed response; WAN/power/stale-data tests; begin 3–5 site supervised pilot | January–February 2027 |
| Weeks 11–16 | Pilot fixes, backups/restore, upgrades/recovery, fleet capability and dispatch; at least two real sites demonstrate VPP response | February–March 2027 |
| Weeks 17–24 | Longer field operation, installation/support tooling, security review and gateway qualification; limited paid release only after acceptance | March–May 2027 |

Budget **5–7 calendar months for a limited supported energy product with an assembled gateway and technical VPP pilot**. A more broadly sold packaged hardware product is more realistically **7–10 months**, depending on external qualification, supply and redesign. A two-person complementary software team can overlap cloud/UI with Edge work, but must replan from the hardware spike rather than assume twice the speed. Part-time engineering extends these dates materially.

If exact Growatt control cannot be demonstrated in weeks 1–2, investigate the matching protocol/driver immediately and re-estimate. Allow a provisional additional 4–8 engineering weeks for narrow driver work; unsupported protocol or missing documentation may require longer or prevent the chosen control scope entirely. Do not silently downgrade the release to monitoring. A hardware substitution or monitoring-only interim product requires an explicit scope decision. Extra boards, inverter families, custom PCB, advanced optimization or commercial VPP participation each require separate estimates.

## Release acceptance and immediate order of work

1. Provision the host using [server requirements](cloud_server_requirements.md). First deploy the pinned connectivity spike, not every proposed service at once.
2. Resolve control feasibility and device identity, validate daylight values/signs and agree a written supported hardware/firmware matrix. Keep the current installation read-only until its write path is qualified.
3. Demonstrate real gateway telemetry in cloud with device identity, observation age and no simulator mixing. Restore service after network/server restart with deduplicated history and explicit overflow gaps.
4. Show one manual change and one automatic strategy with readback and measured physical effect. Exercise stale meters, communication loss, crash/restart, bounds, local override, expiry and conflicting commands.
5. Test cross-site API access, export and WebSocket authorization; credential rotation/revocation; lost/replaced gateway; privileged-operation audit. Do not rely on hiding UI buttons.
6. Disconnect WAN and stop cloud services: local login/UI, history and strategy remain usable with the tested fallback. Reconnect without replaying expired physical actions.
7. Dispatch to two or more qualified real sites; record capacity, requested/achieved grid response, partial failure and cancellation. Simulated larger-fleet/load tests supplement this evidence.
8. Run a target minimum 30-day field soak on the reference build, including deliberate recovery tests. Restore a cloud backup on a clean host, recover a failed gateway image, and complete upgrade/rollback drills. Agree acceptable incidents and response tolerances before the soak.
9. Release only with a supported BOM/firmware matrix, installation and support guide, operating limits, completed product assessment and a named operator. Reassess schedule at weeks 2, 6 and pilot exit.

## Technical references

Reviewed 14 November 2026; pin exact versions during implementation. These sources describe upstream capabilities, not completed OriginalHome functionality.

- [OpenEMS Backend architecture](https://openems.github.io/openems.io/openems/latest/backend/architecture.html): backend responsibilities, separate ingress application and private inter-service trust boundary.
- [OpenEMS Docker deployment](https://openems.github.io/openems.io/openems/latest/backend/deploy/docker.html): current component layout; do not copy public admin-port exposure or mutable latest tags into a release.
- [OpenEMS Edge Backend API](https://openems.github.io/openems.io/openems/latest/edge/controller.d/io.openems.edge.controller.api.backend.html): outbound connection, telemetry/replay and supervisory APIs; verify persistence configuration and bounded behavior on the actual release.
- [OpenEMS Edge architecture](https://openems.github.io/openems.io/openems/latest/edge/architecture.html): device interfaces and local control cycle.
- [Raspberry Pi 5 specifications](https://www.raspberrypi.com/products/raspberry-pi-5/): board, power and storage options.
- [Olimex A64-OLinuXino specifications](https://www.olimex.com/Products/OLinuXino/A64/A64-OLinuXino/): variant-specific RAM, flash and operating ratings.
