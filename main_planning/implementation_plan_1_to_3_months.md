# OriginalHomeIOT implementation plan for 1 to 3 months

Updated 5 November 2026. Proposed delivery baseline following review of `More_Realistic_Approach.docx`, the original scope, and the earlier implementation strategy.

## Delivery decision

Build an energy-first IoT product using **OpenEMS Edge for energy devices and local real-time control**, and **ThingsBoard CE for general IoT, dashboards, history and site organization**. Energy monitoring and physical control are mandatory from the first deployment. First target inverter: **Growatt SPH6000**, exact variant and firmware to be confirmed.

Target an engineering demonstration with physical energy control in four weeks, a supervised pilot in six to eight weeks, and a limited initial release in ten to twelve weeks. These estimates depend on early Growatt read/write qualification, available equipment and one chosen strategy. A telemetry-only deployment or simulator demonstration does not satisfy first-deployment acceptance.

The first release must monitor energy flows, run one useful automatic local strategy, expose supported manual controls and limits, and demonstrate actual equipment response. Use OpenEMS UI for energy controls and ThingsBoard dashboards for general IoT and mirrored energy history. Reusing two interfaces initially keeps a complete custom portal out of the critical path.

The previous year-scale estimate covered the original full platform. The shorter timeline comes from reusing infrastructure and deferring secondary features while preserving energy control as the differentiator. If time becomes tight, remove portal polish, reports and integration breadth before removing energy functionality.

## What the reviewed proposal changes

The Word proposal provides a useful ThingsBoard foundation but defers OpenEMS. The owner's clarified requirement overrides that choice: OpenEMS is part of the first deployment. The six-week pilot estimate now depends on proving local energy control early, rather than completing a monitoring-only product first.

It also introduces a different customer and additional work. White-label integrators, energy communities, POD records, and allocation simulations are not requirements of the original home platform. Treat the integrator-oriented product as a proposed direction, and energy communities as a conditional extension. Do not add every feature in the new proposal merely because the older features have been removed.

For planning, assume one pilot integrator with an energy site and a general IoT site. Create a second isolated test tenant to verify separation. The initial customer-facing experience can use ThingsBoard dashboards; a complete custom portal is not a prerequisite for the pilot.

## Release scope

| Capability | Initial delivery | Boundary |
| --- | --- | --- |
| Integrators, customers and sites | Yes | Use ThingsBoard tenants, customers and assets first |
| Device onboarding | Yes | Generic MQTT in ThingsBoard; selected energy equipment in OpenEMS |
| Device profiles | Yes | Small tested catalog with units, field mappings and example payloads |
| Live values and history | Yes | ThingsBoard storage and dashboards |
| Energy monitoring | Mandatory | OpenEMS measurements for available PV, grid, battery, SoC and consumption; calculated values labeled and validated |
| Real-time energy control | Mandatory | OpenEMS on site, one selected strategy and bounded manual controls on actual equipment |
| Local energy UI and offline control | Mandatory | OpenEMS UI and local controller continue without WAN or ThingsBoard |
| Alarms | Yes | Threshold and stale-device alarms using existing rules |
| CSV export | Yes | Verify base capability; add one bounded export endpoint only if necessary |
| Basic actuator command | Conditional | One tested noncritical relay with permissions and reported-state feedback |
| Branding | Limited | Portal logo/name if a portal is built; no CE frontend fork |
| Energy community simulation | Deferred | Energy equipment control and pilot reliability take priority |
| Local-only installation | Alternative deployment | Same stack on a capable local Linux host; qualify this instead of hosted deployment if offline is mandatory |
| Local plus cloud synchronization | Deferred | No dual authoritative databases or bidirectional configuration sync |
| Full custom customer portal | Deferred | At most a few specific screens within the timebox |

Defer the 3D house editor, camera security, forecasting, machine learning, voice, native mobile apps, broad protocol coverage, energy communities, VPP aggregation, automated billing, official settlement and commercial fleet operations. OpenEMS and local energy dispatch are explicitly included. Start with one automatic strategy; solar self-consumption is a provisional choice until the owner selects the behavior and the device capability is verified.

LoRaWAN/ChirpStack and vendor REST integrations are also deferred unless one replaces the selected Modbus path for the first customer's actual hardware. Two integration paths are enough to validate the product; four parallel paths would spend the schedule on compatibility work.

## Reuse and custom implementation

| Area | Reuse | Custom work allowed in the first release |
| --- | --- | --- |
| Energy devices and local control | OpenEMS Edge | Qualify the Growatt path; implement a narrow driver only if necessary |
| Energy UI | OpenEMS UI | Supported strategy controls and status, minimal customization |
| General IoT and history | ThingsBoard CE | Tested profiles and normalization; mirror selected energy channels |
| Dashboard and rules | ThingsBoard CE | Dashboard templates and a few rule configurations |
| Protocol bridging | ThingsBoard IoT Gateway for general IoT; OpenEMS bridges for energy | Small energy adapter between native OpenEMS and ThingsBoard interfaces |
| Identity and tenant separation | Existing platform accounts and permissions | Explicit authorization checks for any custom API |
| Business workflow | Existing customer and asset models initially | Thin FastAPI module if the pilot exceeds those models |
| Energy community simulation | None assumed | Optional domain module and auditable interval calculation |
| Deployment | Supported ThingsBoard installation pattern and Docker Compose | Configuration, backups, health checks and operator documentation |

Reuse an established local MQTT broker such as Mosquitto. Do not build a broker, time-series engine, generic rules engine, identity provider or dashboard framework. Do not duplicate all telemetry in an application database. Avoid Kubernetes and service-per-module deployment.

OpenEMS is the sole application writer to controlled energy equipment. ThingsBoard must not run a competing Modbus writer or energy feedback loop. A supervisory request from ThingsBoard passes through an allowlisted adapter to OpenEMS. A general IoT load participating in an energy strategy also needs one explicit control owner and override policy.

OpenEMS uses a local input/process/output cycle whose practical timing depends on device communication. Treat real-time here as measured operational responsiveness, not hard real-time protection. Inverter and BMS protections remain in the equipment. See [OpenEMS architecture](https://openems.github.io/openems.io/openems/latest/edge/architecture.html).

## Growatt SPH6000 qualification and control contract

The owner selected Growatt SPH6000. Confirm the full nameplate designation, firmware, battery/BMS, installed grid meter and local communications accessory. Growatt documents RS485 Modbus for specific SPH families, including SPH 3000–6000TL BL-UP, but this does not establish all required writable capabilities for the owner's installation. See [Growatt local integration](https://en.growatt.com/media/blogs/how-to-maximize-the-benefits-of-vpp-with-energy-storage-solutions).

Native OpenEMS support for this exact configuration has not been verified. Inspect the pinned release and component source; do not infer compatibility from generic Modbus, SunSpec or a read-only PV driver. Obtain protocol documentation matching the actual variant before choosing registers. Do not guess addresses from another SPH model.

In week 1, establish real reads, write access and one bounded write with readback and observed physical response under supervision. Check scaling, signs, supported modes, command timeout/watchdog behavior, and interaction with native inverter operation and vendor software. Distinguish OpenEMS-owned decisions from merely displaying or selecting an inverter-native mode.

If a driver is required, implement the narrow device integration within OpenEMS so existing controllers can use it; do not create another energy controller in FastAPI. Re-estimate at weeks 1 and 2 from this evidence. Significant new driver work threatens the twelve-week estimate, but monitoring alone does not become an acceptable substitute for mandatory control.

Use OpenEMS MQTT for selected energy measurements where supported, normalizing them to ThingsBoard's device/gateway ingestion format. The MQTT interfaces are not assumed to be directly compatible. Map site, Edge, component and ThingsBoard entity IDs; filter configuration and credentials from customer telemetry. Verify command semantics against the pinned release; use a supported native API through the adapter if MQTT cannot express the required operation. See [MQTT API](https://openems.github.io/openems.io/openems/latest/edge/controller.d/io.openems.edge.controller.api.mqtt.html) and [configuration APIs](https://openems.github.io/openems.io/openems/latest/edge/configuration.html). Persistent configuration changes are not a per-cycle setpoint transport.

Every custom control request needs authenticated site scope, a unique ID, expiry, an allowed operation and bounded parameters. Reject unauthorized, duplicate or expired requests; never retain physical actions for replay after reconnect. Track requested, accepted/rejected and observed outcomes separately. Temporary overrides also need a duration/lease and defined fallback; request-delivery expiry alone does not undo an applied override.

Configure power and SoC limits, controller priority, manual override, stale-measurement handling, communications-loss fallback and restart behavior. Verify whether the actual device holds its last target, times out or returns to native operation when communication stops. Measure physical response within agreed tolerances and observation windows.

Set sampling, local cycle, display and supervisory-request latency criteria during the hardware spike. Investigate roughly one-second samples and a local display within a few seconds as planning targets, not Growatt specifications. Record measured latency distributions and physical response time independently of cloud refresh.

ThingsBoard CE already has multi-tenancy. Native white-labeling and advanced RBAC are listed as PE capabilities in the vendor's edition comparison. Consequently, CE is the baseline when standard screens and roles suffice. Evaluate PE if native branding or finer permissions become a firm pilot requirement; buying those capabilities may be faster than recreating them. No license purchase is assumed or authorized by this plan. See [multi-tenancy](https://thingsboard.io/docs/concepts/multi-tenancy/) and the [vendor edition comparison](https://github.com/thingsboard/thingsboard.github.io/blob/master/ce-vs-pe-diff.md).

If a custom business backend becomes necessary, keep it as one FastAPI application. Its database owns business-only records and ID mappings. OpenEMS owns energy device configuration and control state; ThingsBoard owns the general IoT registry and its historical telemetry projection. Mirrored energy values are not an independent source of live control truth. Keep the initial customer/site hierarchy in ThingsBoard until a concrete requirement justifies moving ownership; never keep two independently editable copies of the same relationship.

## Deployment and offline behavior

Baseline topology:

```text
Growatt inverter + battery + energy meter
                  |
         local supported protocol
                  |
             OpenEMS Edge <----> local OpenEMS UI
                  |
             local MQTT broker
                  |
             energy adapter <---- bounded supervisory requests
                  |
         ThingsBoard CE + database/dependencies
                  |
          IoT and energy dashboards
                  ^
       ThingsBoard IoT Gateway
                  ^
          general MQTT sensors
```

Use the pinned release's documented deployment dependencies rather than assuming that ThingsBoard and PostgreSQL alone always form a complete stack. Begin with the vendor installation configuration and simplify only where supported. See [Docker installation](https://thingsboard.io/docs/installation/docker/).

OpenEMS Edge and its energy UI run locally from the first deployment. ThingsBoard may run on a hosted Linux server. WAN loss affects the hosted dashboard and mirrored history, while local energy control and the energy UI remain available. Verify bounded telemetry buffering and replay, with explicit history gaps when capacity is exceeded.

For complete local-only operation, run ThingsBoard on a qualified local Linux server or mini PC too. No bidirectional local/cloud database synchronization is required. Download necessary assets before offline tests and verify local authentication. Initially use separate authenticated OpenEMS and ThingsBoard interfaces. ThingsBoard tenancy does not automatically authorize OpenEMS access: restrict Edge to the site's LAN/VPN and enforce site ownership in every custom control API.

Raspberry Pi and Olinuxino are gateway candidates, not a promise that every model can run the complete stack. Qualify one exact board, OS and storage combination first. The gateway documentation includes Raspberry Pi and other installation options, but the selected Olinuxino model still needs a practical check. See [gateway installation](https://thingsboard.io/docs/iot-gateway/installation/) and [connectors](https://thingsboard.io/docs/iot-gateway/connectors/).

## Schedule and exit gates

Assumptions: one experienced engineer working full time with AI assistance; owner availability for equipment decisions; access to the Growatt installation and matching protocol documentation in week 1; one battery/meter configuration; one automatic strategy; one generic MQTT sensor; one reference gateway. Growatt driver readiness is unverified and is the first schedule gate.

| Week | Work | Required evidence |
| --- | --- | --- |
| 1 | Qualify Growatt/OpenEMS read and write path; select strategy; pin stack | Exact equipment matrix, driver assessment and bounded physical-write feasibility |
| 2 | Complete minimum driver/control path and energy telemetry adapter | Repeatable real actuation and feedback; selected energy values in ThingsBoard |
| 3 | Configure local automatic strategy, limits, override and OpenEMS UI | Useful automatic behavior on real equipment with documented fallback |
| 4 | Integrate general MQTT sensor; verify access boundaries and WAN independence | Engineering deployment contains physical energy monitoring and control |
| 5 to 6 | Supervised pilot; stale data, communications loss, expiry and restart tests | Pilot candidate with measured timing and observed device behavior |
| 7 to 8 | Fix pilot issues; installation, history, isolation and restore | Accepted energy-first pilot for the qualified configuration |
| 9 to 10 | Longer operation and recovery tests; second strategy only if core gates pass | Operational evidence before further scope expansion |
| 11 to 12 | Regression, upgrade/restore drills, documentation and release fixes | Limited initial release with energy acceptance passed |

One month buys a demonstration or narrow internal alpha. Six to eight weeks is the target for an integrator pilot. Two to three months is the target for a limited initial release with real pilot feedback. None of these milestones imply support for the original complete feature list or arbitrary hardware.

Weeks 9 to 12 prioritize energy integration and reliability. Re-estimate Growatt work at weeks 1 and 2; simulator success alone cannot close a hardware gate. Reducing scope must preserve the owner's mandatory energy monitoring and control outcome. Any hardware substitution needs an explicit owner decision.

## Optional energy community extension

This is future scope beyond the initial energy-control release. If prioritized later, limit it to community identity, member and POD records, effective-dated membership, interval import, completeness flags, one agreed allocation method and CSV results. Label every result as a simulation.

Persist the source dataset reference, time zone and interval boundaries, energy units, missing and duplicate interval policy, algorithm version, allocation parameters, calculation run ID, and results. Check that assigned energy does not exceed the eligible pool and that unallocated quantities are explicit. Distinguish cumulative meter counters from interval energy; handle resets and missing intervals rather than silently subtracting any two readings.

Official settlement, billing, regulatory submissions and VPP aggregation remain outside this release. Local equipment dispatch through OpenEMS is included. The Romanian legal statements in the Word proposal have not been adopted as verified requirements here. Verify applicable rules separately before defining regulated workflows.

## Acceptance for the initial release

1. A clean qualified Linux host can be installed from documented, pinned configuration; required secrets are supplied separately.
2. Two tenant accounts cannot access each other's devices, history, dashboards or exports. Exercise direct API requests as well as UI navigation. Any custom API derives access from the authenticated user rather than trusting a submitted tenant ID.
3. Qualify the exact Growatt model, firmware, battery, meter and OpenEMS release. Show real measurements with validated units, signs and freshness. Onboard one generic MQTT sensor in ThingsBoard.
4. The pilot shows useful energy and non-energy telemetry, history, threshold alarms, stale readings, and a usable CSV export with units and timestamps.
5. Restart the gateway and platform, interrupt the network, and verify bounded recovery without misleading readings. Record the buffer limit and behavior when full. Never replay a stale actuator action after reconnect.
6. Restore configuration and retained history to a clean test instance. Record retention, resource use and known operating limits for the pilot load.
7. If a relay is included, test authorization, bounded command parameters, offline failure and actual reported state; sending a request must not be presented as confirmed actuation.
8. From the first deployment, demonstrate one manual energy control change and one useful automatic OpenEMS strategy on the actual Growatt installation. Verify readback and observed physical response within agreed tolerances; sending a request is not confirmed actuation.
9. Disconnect WAN and independently stop ThingsBoard and the adapter. The local energy UI remains usable and the strategy continues or enters its documented fallback. Cloud loss must not disable local control.
10. Before unattended release, test stale grid data, energy-device communication loss, OpenEMS restart, power/SoC limits, conflicting requests, duplicate/expired commands, temporary-override expiry and manual override. Verify one writer per controlled device and document safe fallback and recovery.

## AI development workflow and immediate backlog

Use AI primarily to configure dashboards and rule templates, draft captured-payload mappings, implement focused API screens, write deployment documentation, and construct meaningful integration checks. Review generated configuration and code before applying it to real devices. Validate protocol details against the exact installed release and actual device fixtures. Do not introduce extra infrastructure merely because an assistant can generate it quickly.

Start with these bounded tasks:

1. Confirm full SPH6000 variant, firmware, battery, installed meter and local communications hardware; obtain matching protocol documentation.
2. Prove the OpenEMS read/write path and agree the first automatic strategy before portal work.
3. Deploy OpenEMS UI locally and the smallest supported ThingsBoard stack; create isolated test tenants.
4. Deliver real energy actuation and feedback, then selected energy telemetry and the generic sensor dashboard in ThingsBoard.
5. Save sanitized mappings, fixtures and configuration without credentials; record physical control results.
6. Re-estimate at weeks 1 and 2. Prioritize energy reliability over community modules or a complete custom portal.

This plan supersedes the initial-delivery schedule in `implementation_strategy.md`. The original scope and Word proposal remain reference inputs. No application implementation is claimed by this planning update.
