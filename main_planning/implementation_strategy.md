# OriginalHomeIOT implementation strategy

> Superseded for initial delivery by [the 1 to 3 month implementation plan](implementation_plan_1_to_3_months.md), following review of `More_Realistic_Approach.docx` on 5 November 2026. The estimates below apply to the original broad custom-platform scope and are retained for reference. They are not the current MVP schedule.

Prepared: 5 November 2026. Status: proposed engineering plan, not an implementation or delivery commitment.

## 1. Recommendation and planning basis

Build OriginalHomeIOT as a local-first home platform with optional cloud services. Start with OriginalHomeMain (OHM): MQTT onboarding, virtual entities, room assignment, local control, history, and reliable installation. Add energy management through OpenEMS, camera security through an existing detection engine, then cloud synchronization, the 3D editor, analytics, and voice assistance.

Use AI for most routine implementation, fixtures, documentation, and initial test generation. A human technical owner must still own architecture, review, hardware validation, security, and release decisions. The limiting factors will be integration behavior and reliability in real homes, rather than typing code.

This document executes the tasks in [copilot_tasks.md](copilot_tasks.md) and uses [scope_of_originalhomeiot.md](scope_of_originalhomeiot.md) as the product scope. The repository currently contains planning documents and no application implementation. There is no existing codebase whose maturity can shorten the estimates.

Recommended delivery expectations for one experienced full-time engineer using AI heavily:

- Local OHM MVP: **12–16 working weeks**.
- Integrated pilot covering every named module at limited scope: **36–48 working weeks**.
- Hardened v1 covering the defined hardware and integration matrix: **48–64 working weeks**, approximately **12–16 calendar months** with holidays and ordinary interruptions.

These are estimates derived from the work breakdown below, not measured AI productivity claims. They assume prompt access to hardware, a small pilot group, and no custom energy-device driver or camera recognition model. New drivers, many device brands, arbitrary Olinuxino boards, or commercial service requirements require re-estimation.

## 2. Product boundaries and release scope

The first supported user is a technical homeowner comfortable entering an MQTT topic and configuring a gateway. Do not make universal device discovery a prerequisite for release.

| Scope requirement | Implementation approach | First delivery |
| --- | --- | --- |
| Local gateway and server component | Linux gateway profile plus optional server profile; same contracts | Gateway in MVP; server in pilot |
| Raspberry Pi and Olinuxino | Reference Raspberry Pi plus one explicitly selected Olinuxino model | Board qualification begins immediately; both required for v1 core support |
| Local-only operation | Local broker, identity, UI assets, configuration, rules, and history | MVP |
| Local, server, or both databases | Storage adapters and explicit deployment modes; durable gateway spool | MVP local; other modes in pilot |
| Local LAN/VPN UI and cloud UI | Shared web application, deployment-specific API endpoint | Local in MVP; cloud in pilot |
| Manual MQTT topic and JSON discovery | Capture samples, preview fields, map and validate | MVP |
| Virtual sensor and actuator catalog | Versioned entity templates and device mappings | Basic types in MVP; full listed catalog in pilot |
| Existing devices | Tested integration profiles over generic MQTT and dedicated adapters | Selected devices in MVP; compatibility matrix grows through pilot |
| Minecraft-like house editor | Grid model, room volumes, walls, floors, roof, entity placement | Pilot |
| OEMM based on OpenEMS | Dedicated adapter, energy UI, bounded strategy configuration | Pilot |
| OCSM camera management and alarms | Discovery, camera registry, detection adapter, deterministic alarm engine | Pilot |
| ODAM timestamped data and predictions | Historical event ingestion, query API, later opt-in predictions | History in MVP; predictions in pilot |
| Intelligent assistant and voice | Restricted tools over existing module contracts | Pilot |
| Decoupled modules and endpoints | MQTT for cross-module commands/events; authenticated HTTP for clients and operations | Foundation onward |

The MVP deliberately does not complete the whole scope. Its purpose is to validate the common platform before investing in the specialized modules. v1 means the stated integration matrix works reliably, not compatibility with every commercial IoT product.

## 3. Architecture and technology choices

Use a monorepo with a small number of deployable services. Keep domain boundaries explicit without making every entity its own process.

Proposed stack, subject to a short hardware feasibility check:

| Component | Choice | Reason |
| --- | --- | --- |
| Broker | Eclipse Mosquitto | Dedicated MQTT infrastructure with persistence and access control |
| OHM/API, rules, adapters | Python, FastAPI, Pydantic, MQTT client | Shared language for backend, integrations, and later analytics |
| UI | TypeScript, React, Vite; Three.js for the editor | Shared local/cloud UI with a browser-native 3D scene |
| Local persistence | SQLite with WAL, batching, one writer per database | Low operational overhead on gateways |
| Server persistence | PostgreSQL, time-partitioned telemetry where needed | Central history, tenant metadata, and server queries |
| Deployment | Docker Compose on qualified Linux systems | Reproducible gateway/server installs; no Kubernetes for v1 |
| Validation | pytest, browser end-to-end tests, broker integration tests, real-device fixtures | Verify behavior at actual system boundaries |

Pin dependency versions, runtime versions, images, and supported CPU architectures after the feasibility spike. These are proposed choices, not claims that every package or image runs on every board. SQLite WAL allows concurrent readers but only one writer at a time; route writes through a bounded writer queue and benchmark sustained ingestion. [SQLite WAL documentation](https://www.sqlite.org/wal.html).

Runtime layout:

```text
Physical MQTT devices --> local broker <--> OHM / mapping and rules
                               ^                 ^
                               |                 | HTTP + browser updates
                OEMM / OCSM / ODAM / assistant   local web UI
                               |
                         sync adapter
                               |
                 outbound authenticated connection
                               |
                server broker + API + database <--> cloud web UI

OCSM adapter <--> local camera/detection service <--> IP cameras
OEMM adapter <--> OpenEMS Edge <--> energy equipment
```

All OriginalHomeIOT module-to-module business events and commands cross MQTT. Browser requests, health checks, administration, and large historical queries use HTTP endpoints. Upstream systems can have native protocols behind their adapters. Video travels over appropriate streaming/HTTP protocols, with references and detection events on MQTT; do not route video frames through the platform event bus.

Each module owns its configuration and storage. Other modules use its API or published contracts rather than reading its tables. The API layer routes requests to the owning module; it must not become a second implementation of its rules.

## 4. Contracts, entity mapping, and reliable control

Define JSON Schema contracts before building module UIs. Reserve a platform namespace such as:

```text
originalhome/v1/{home_id}/{module}/events/{event_type}
originalhome/v1/{home_id}/{module}/state/{entity_id}
originalhome/v1/{home_id}/{module}/commands/{entity_id}
originalhome/v1/{home_id}/{module}/results/{command_id}
originalhome/v1/{home_id}/{module}/availability
```

An event includes schema version, event ID, home ID, source module, entity ID where applicable, observation time, receipt time, origin, and typed payload. Commands include command ID, actor, target, issue time, expiry, expected configuration version where relevant, and validated parameters. Preserve event IDs across synchronization and retries. Use UTC timestamps, track clock quality, and show stale data explicitly.

Use QoS 1 for important normalized events and commands, and deduplicate in consumers. Do not assume exactly-once physical effects. Retain current state and availability where appropriate; never retain action commands. Persist command acceptance and result status. For devices without idempotent commands, prefer setting a desired state over toggling, check reported state, and make retry policy device-specific. A timeout means unknown outcome until reconciled, rather than automatic failure or success.

Mosquitto persistence and bridge configuration are useful building blocks; configure queue limits and topic permissions deliberately. They do not replace an application event ledger or command authorization. [Mosquitto configuration reference](https://www.mosquitto.org/man/mosquitto-conf-5.html).

Onboarding workflow:

1. Enter broker connection and exact topic or a constrained topic filter. Capture bounded samples, with a timeout and payload-size limit.
2. Parse JSON and display field paths, observed types, and sample values. Do not infer a permanent schema from one message.
3. Select a virtual entity template and map fields using JSON Pointer paths. Configure units, scaling, range, missing-value behavior, availability, and stale timeout.
4. Preview normalized values and save a versioned mapping. Support several virtual entities from one physical device.
5. For actuators, separately configure command topic, payload template, reported-state mapping, valid range, and acknowledgement behavior. A sensor payload cannot reveal the device's command protocol reliably.
6. Publish a test only through an explicit onboarding control; retain mapping rollback and diagnostic sample capture with secrets redacted.

Templates cover temperature, humidity, CO2, NOx, motion, illuminance, and plug power/energy. Distinguish power in W from accumulated energy in Wh/kWh. NOx mappings must retain the actual measured quantity and unit; an index and a concentration are not interchangeable. Actuator capabilities cover switches, AC modes/setpoints, RGB bulbs, and strips, including supported ranges and optional features. Existing-product profiles should record tested firmware and sample payloads; generic MQTT support does not imply native Zigbee or proprietary radio support.

## 5. Storage and local/cloud ownership

Separate three concerns: essential operational configuration, the selected history destination, and a bounded delivery queue. Even in server-history mode the gateway needs configuration and spool storage so local control survives an internet outage.

| Mode | History behavior | Offline behavior |
| --- | --- | --- |
| Local | SQLite history; cloud disabled | Full local operation |
| Server | PostgreSQL history; gateway retains operational state and delivery spool | Local control continues; recent unsent history is bounded |
| Both | Local history plus replicated server history | Local history and control continue; catch-up on reconnect |

The gateway owns device configuration, effective home configuration, actuator state, and rule execution. The cloud holds a projection and submits authenticated requests to the gateway. Cloud requests cannot silently become independent automation writers. Apply configuration edits using gateway revisions; reject stale edits and present conflicts for resolution.

Implement transactional outbox/inbox patterns where a database update and publication must agree. Record normalized events before acknowledging durable ingestion, deliver at least once, and deduplicate by stable IDs. Upstream QoS 0 device loss cannot be repaired after the fact. Maintain per-stream sequence/checkpoint information, bounded replay batches, origin markers, and gap reporting. Separate event time from arrival time for late data.

Do not mirror every topic bidirectionally. Allowlist synchronized state/events and a separate command ingress. Validate authorization and expiry at the gateway; expired cloud commands never execute after reconnect. No automatic replay of stale physical actions.

Initial sizing assumption: 100 entities averaging one sample per 10 seconds produces 864,000 samples/day. At an illustrative 150 bytes/sample this is about 130 MB/day before indexes and overhead, or 3.9 GB over 30 days. Measure actual storage and write amplification. Start with configurable retention, for example seven days of local raw data, longer hourly aggregates, and a bounded spool. Report dropped ranges when capacity is exhausted; preserve operational configuration and critical audit records ahead of bulk telemetry. Video has an independent disk quota and retention policy.

## 6. Module delivery details

### OHM and house editor

Ship a conventional room list and dashboards first. Store stable home, floor, room, device, and entity IDs so later 3D placement does not change integrations. Store the house as structured geometry rather than only a rendered scene. Represent dimensions on a 0.5 m base grid; allow editing at either 0.5 m or 1 m, with explicit validation when changing resolution.

The first editor supports room footprints and height, walls, doors/windows as simple openings, multiple floors, a generated general roof, camera controls, undo/redo, save/load, and entity placement by room ID. Make the roof hideable for interior selection. Use instancing or merged meshes and lazy loading to keep the ordinary dashboard fast. Exclude photorealism, structural/CAD accuracy, and automatic floor-plan reconstruction from v1.

### OEMM: OpenEMS wrapper

Keep energy control inside OpenEMS Edge and expose normalized measurements, controller availability, and permitted strategy settings through the OEMM adapter. OpenEMS describes Java-based Edge/Backend components and local gateway deployment; its controllers own energy logic. This supports the wrapper approach rather than rebuilding optimization. [OpenEMS architecture](https://openems.github.io/openems.io/openems/latest/edge/architecture.html).

The current documented MQTT controller exposes channel data and control topics. In the spike, verify the exact pinned release, required writable channels, permissions, and target equipment. Use its MQTT interface where suitable; keep any native API translation within OEMM. Start with a simulator, read-only power flows, then one known inverter/meter/storage combination and one bounded strategy. [OpenEMS MQTT API](https://openems.github.io/openems.io/openems/latest/edge/controller.d/io.openems.edge.controller.api.mqtt.html).

Provide clear strategy controls and feedback on the effective strategy, stale readings, and rejected settings. Reuse the OpenEMS UI as a separately deployed initial interface if appropriate, then add focused platform controls. OpenEMS documents EPL-2.0 for Edge/Backend and AGPL-3.0 for UI; review the pinned components and intended distribution before deciding how to reuse or modify the UI. This plan does not determine resulting legal obligations. [OpenEMS introduction and licenses](https://openems.github.io/openems.io/openems/latest/).

OpenEMS remains the single energy setpoint writer. OHM and the assistant request bounded strategies; they do not compete with its control loop. Retain hardware limits, manual overrides, and safe behavior when the wrapper or internet connection fails. Validate writes on the actual equipment before enabling unattended operation.

### OCSM: cameras and alarms

Implement local ONVIF discovery with manual RTSP entry as fallback. Let users supply credentials, inspect capabilities, test streams, edit settings, and remove cameras. Discovery across VLANs is not guaranteed; document network boundaries. Prefer Profile T for newly qualified cameras; ONVIF has announced the end of Profile S support and recommends T. [ONVIF announcement](https://www.onvif.org/pressrelease/onvif-to-end-support-for-profile-s/).

Evaluate Frigate as the local person-detection engine and wrap it behind OCSM. Its MQTT events contain object IDs and repeated lifecycle updates; normalize these into detection events and deduplicate updates before counting alarm evidence. Pin and contract-test the upstream event format. [Frigate MQTT documentation](https://docs.frigate.video/integrations/mqtt/).

Use an explicit alarm state machine: disarmed, exit delay, armed, level 1, level 2, acknowledged/reset. Proposed configurable default: a confirmed moving person in a selected zone triggers level 1 lights; qualifying detections from two distinct cameras within 30 seconds trigger level 2. A one-camera home can explicitly choose a separate persistence rule for escalation. This is a proposed policy because the source scope does not define the exact thresholds. Repeated updates from one tracked object must not count as extra cameras. Support cooldown, entry delay where configured, manual disarm, output duration limits, and a dry-run mode. Camera failure must appear as degraded protection rather than absence of motion.

Benchmark stream decoding and inference separately. Frigate's hardware guidance distinguishes accelerators and platforms; do not promise a camera count from gateway CPU specifications alone. A separate local x86/accelerated host may be required while OHM remains on the gateway. Qualify the chosen board, decoder, model, resolution, frame rate, and camera count together. [Frigate hardware guidance](https://docs.frigate.video/frigate/hardware/).

### ODAM: analysis

Subscribe to versioned module events and store timestamped measurements, state transitions, command outcomes, energy data, and detection metadata. Use normalized tables for entities and measurements plus an event ledger; keep module-owned credentials and raw video outside ODAM. Index by home/entity/time and track schema/mapping revisions and quality flags. Respect history-destination and retention choices.

Deliver history, aggregates, exports, missing-data indicators, and trend dashboards before machine learning. Predictions then run in shadow mode with chronological train/validation splits and comparison against simple persistence or schedule baselines. Only expose useful predictions with freshness and confidence information. Automatic behavior changes require explicit opt-in, bounded actions, and rollback; a weak prediction must not become an actuator instruction.

### Intelligent assistant

Start with typed requests such as room temperature queries and creating draft scenarios. Route every action through a small allowlisted tool API with typed parameters and the same permissions as the UI. Add speech-to-text and text-to-speech as replaceable adapters. A cloud model is optional; provide a local path or constrained offline intents and clearly label any unavailable advanced capability.

Resolve phrases such as “make the room warmer” to a selected room and a bounded setpoint change, with clarification for ambiguous targets. The model cannot publish arbitrary MQTT topics or bypass energy limits. Require explicit user confirmation for alarm disarming and other sensitive actions; this is proposed product behavior. Store scenarios as deterministic rules, not continuously interpreted prompts. Test malformed tool arguments, prompt injection through device names, and repeated requests. Model training is not part of v1.

## 7. Hardware, deployment, and operational requirements

Use a Raspberry Pi 5 with 8 GB RAM and SSD as an initial test configuration, subject to measurements rather than a purchasing guarantee. Select one exact Olinuxino board, RAM size, CPU architecture, OS, and storage configuration in the first two weeks. A 32-bit or low-memory model may require native packages or a restricted core profile; do not silently treat another ARM board as equivalent. Failure to qualify the selected model is a release blocker for the promised Olinuxino support, or requires an explicit scope revision.

Core support means broker, OHM, UI, local rules, storage, and adapter connectivity. Heavy camera inference, large local language models, and possibly OpenEMS can run on a separate local host. Local-only means no required cloud dependency, not necessarily every workload on one board. Full co-location is an additional benchmarked profile, not an assumption.

Provide persistent volumes, resource limits, health/readiness endpoints, structured logs, and metrics for queue depth, sync lag, event loss, stale sensors, and command outcomes. Use authenticated LAN access, per-module broker credentials and topic ACLs, TLS for remote links, encrypted secret storage with keys kept out of source control, and cloud tenant isolation. Browser clients must not receive unrestricted broker credentials.

Support direct LAN and user-configured VPN access. VPN software can itself have external dependencies; core operation must work without it. The hosted cloud UI is optional and does not replace the gateway UI. Do not expose the gateway broker or administration ports directly to the internet by default.

Package all UI assets locally and document offline installation prerequisites, including images, detector models, and optional speech models. Provide backup/restore, migration preflight, pinned update bundles, and a tested recovery procedure; schema changes can require restoring a backup rather than merely downgrading a container. Keep camera recordings local by default and make any upload opt-in.

## 8. AI-led development workflow

Use AI as the main implementation tool within a human-owned delivery process:

1. Write a small issue with a concrete input/output example, contract, acceptance criteria, and affected modules.
2. Give the coding assistant only relevant documents, schemas, fixtures, and repository rules. Ask for a focused patch, migration notes, and verification.
3. Have the human review authorization, units, time handling, retries, and error paths. An AI review can supplement this but is not independent evidence of correctness.
4. Run contract, integration, and browser checks in CI; require real hardware results for device-facing changes.
5. Merge small changes after evidence is recorded. Update documentation and compatibility fixtures alongside implementation.

Good AI work includes CRUD screens, entity templates, schema validators, adapters against captured fixtures, simulator scenarios, migration drafts, and documentation. Human work includes choosing semantics, reproducing hardware faults, evaluating alarm false positives, controlling energy equipment, and deciding whether a release is fit for use. Do not budget an assumed 5x or 10x speedup. Re-estimate after the first four weeks using completed, accepted work and escaped defects.

Suggested repository structure:

```text
apps/web/
services/ohm/
services/oemm/
services/ocsm/
services/odam/
services/assistant/
services/sync/
contracts/                 # JSON Schema, topic catalog, API specifications
integrations/              # device profiles and captured, sanitized fixtures
deploy/gateway/
deploy/server/
tests/integration/
tests/hardware/
docs/decisions/
main_planning/
```

Keep secrets, private recordings, and personal household telemetry out of AI prompts and repository fixtures. Use reproducible synthetic or explicitly sanitized examples. Record dependency provenance and licenses as part of release preparation.

## 9. Work breakdown and realistic timeline

The baseline below is sequential for one experienced full-time engineer working approximately 35–40 hours/week with AI assistance and ready access to test hardware. Each range includes implementation, review, and normal testing for that phase. Later stabilization covers cross-module failures and field feedback rather than repeating every phase's tests.

| Phase | Duration | Cumulative working weeks | Deliverable and exit gate |
| --- | --- | --- | --- |
| 0. Feasibility and decisions | 2–3 weeks | 2–3 | Board/OS matrix; MQTT round trip on both boards; OpenEMS simulator read/write proof; camera stream/inference benchmark; pinned stack |
| 1. Platform foundation | 3–4 weeks | 5–7 | Broker ACLs, contracts, local identity, persistence, API/UI shell, CI, reproducible install |
| 2. OHM local MVP | 7–9 weeks | 12–16 | JSON mapping, basic entity catalog, room dashboard, actuator confirmation, history, rules, backup/restore, offline operation |
| 3. OEMM pilot | 4–5 weeks | 16–21 | OpenEMS integration, strategy UI, one validated equipment profile, bounded writes and override tests |
| 4. OCSM pilot | 5–6 weeks | 21–27 | Camera discovery/CRUD, person-event ingestion, two alarm levels, failure and duplicate-event tests |
| 5. Cloud and storage modes | 5–6 weeks | 26–33 | Server deployment/UI, local/server/both history, sync/replay, tenant isolation, stale command rejection |
| 6. 3D house editor | 4–5 weeks | 30–38 | Both grid sizes, rooms/floors/roof, placement, undo/save/load, browser performance checks |
| 7. ODAM predictions and assistant | 6–10 weeks | 36–48 | Basic predictive baseline, typed assistant, scenarios, local/offline intent path and voice adapters |
| 8. Field stabilization and v1 | 12–16 weeks | 48–64 | Pilot households, restore/update drills, load and outage tests, support matrix, installation docs, release fixes |

The full entity catalog and initial device profiles grow during phases 2–7; finishing them is part of the integrated pilot gate. Prototype hardware spikes do not count as production-ready modules.

Illustrative dates if full-time work starts on **9 November 2026**: local MVP around **February–March 2027**; integrated pilot around **July–October 2027**; hardened v1 around **November 2027–March 2028**, allowing for ordinary calendar interruptions. Working-week counts are the scheduling baseline; actual dates depend on holidays and hardware lead times.

Staffing alternatives:

| Available people | Local MVP | Hardened scoped v1 | Qualification |
| --- | --- | --- | --- |
| One experienced full-time engineer + AI | 12–16 working weeks | 48–64 working weeks | Baseline above |
| Two experienced full-time engineers + AI | 8–12 elapsed working weeks | 32–44 elapsed working weeks | Backend/integrations and UI/cloud can overlap after contracts stabilize |
| One experienced engineer at 15–20 hours/week + AI | Roughly 6–10 calendar months | Roughly 24–36 calendar months | Context switching and hardware sessions reduce linear scaling |

These estimates exclude broad commercial certification, custom electronics/firmware, unrestricted device support, mobile-native apps, billing, 24/7 operations, advanced custom ML, and a fully general voice assistant. Re-estimate at each milestone. A new energy protocol, difficult camera model, or unsupported board can add several weeks independently; no fixed contingency can absorb unlimited compatibility work.

## 10. Acceptance and release evidence

Use behavior-based gates, with thresholds agreed after the hardware spike:

- **MVP:** install on the reference Pi and selected Olinuxino core profile; map physical temperature/humidity and power telemetry; control a tested switch with reported-state feedback; persist mappings and rooms across restart; restore a backup to a clean installation.
- **Offline:** run 72 hours with WAN disconnected; local login, UI, rules, sensor ingestion, and actuator control continue. Required models/assets are already installed. No cloud identity refresh is necessary for local access.
- **Reliability:** inject duplicate/out-of-order events, broker restart, process crash, interrupted writes, disk-full conditions, and clock drift. Publish explicit data gaps; do not silently repeat physical actions. Test actual abrupt power loss on expendable test media.
- **Performance:** initial target is 100 entities at a 10-second average sample interval; additionally test 10x ingestion bursts and bounded recovery. Measure per-board CPU/RAM/disk use, command latency, and UI responsiveness; publish supported limits rather than inventing capacity claims.
- **Cloud:** exercise all three history modes, a prolonged outage, interrupted replay, duplicate delivery, stale configuration edits, cross-tenant access attempts, and command expiry. Restore consistent projections after reconnect without duplicate rule execution.
- **Energy:** verify simulator behavior, actual supported equipment, stale-data handling, manual override, and loss of OEMM connectivity. Confirm no competing setpoint writers.
- **Cameras:** qualify at least two selected models; demonstrate add/edit/remove, one- and two-camera policies, arm/disarm, cooldown, duplicate suppression, and visible degraded protection. Measure false positives in a real pilot before enabling sound outputs by default.
- **3D:** save/load both grid sizes, maintain room/entity relationships after edits, cover the building with a roof, and retain a usable non-3D dashboard on slower clients.
- **Assistant/analysis:** compare predictions against baselines; reject unauthorized or malformed tool calls; test ambiguous rooms and unavailable voice/model services; never report execution success before a module result arrives.
- **v1:** complete a multiweek pilot, backup/restore and upgrade recovery drills on both supported core boards, resolve release-blocking defects, and publish known limitations and the tested matrix.

## 11. Immediate backlog and decisions

The next implementation work should be a two-week feasibility milestone, not simultaneous construction of all modules:

1. Select the exact Olinuxino model, reference OS images, Pi storage, two camera models, and initial energy equipment; obtain or reserve the hardware.
2. Record architecture decisions for MQTT contracts, state ownership, history modes, and module permissions.
3. Build a disposable vertical slice: synthetic MQTT JSON -> field mapping -> normalized entity -> local storage -> browser value -> validated switch command/result.
4. Prove OpenEMS simulator integration and one allowed write; benchmark camera decoding/detection on the proposed local host.
5. Record measured resource use, dependency/image architecture support, license inventory, and revised estimates.
6. Turn phase 1 and phase 2 into small issues with acceptance examples and fixtures; implement the local OHM MVP before expanding the integration matrix.

Owner decisions still needed during that milestone are the precise board/device matrix, intended distribution model, required pilot camera count, default alarm escalation policy, cloud hosting ownership, and voice language/offline quality expectations. The assumptions above allow planning to proceed; they do not conceal those scope choices.

This planning deliverable completes the tasks currently listed in `copilot_tasks.md`. Application implementation remains future work and has not been performed by writing this strategy.
