# OriginalHomeIOT implementation plan for 1 to 3 months

Updated 5 November 2026. Proposed delivery baseline following review of `More_Realistic_Approach.docx`, the original scope, and the earlier implementation strategy.

## Delivery decision

Build a focused IoT product on ThingsBoard rather than implementing a new IoT platform core. Target a demonstrable system in four weeks, an integrator pilot in six to eight weeks, and a supported initial release for a small, agreed deployment matrix in ten to twelve weeks. These are engineering estimates, conditional on the scope and staffing below, rather than a delivery guarantee.

The first release should onboard selected MQTT and Modbus devices, organize them by customer and site, display telemetry and energy measurements, raise basic alarms, and export data. Reuse existing dashboards and administration screens. Write custom code only where the pilot requires a workflow that the base platform cannot provide.

The previous year-scale estimate covered building the original home platform and all its named modules, including a 3D editor, camera security, energy control, synchronization, predictions, and voice. That scope no longer defines initial delivery. The shorter timeline comes from removing work and reusing infrastructure; AI assistance supports that approach but does not justify keeping the full scope.

## What the reviewed proposal changes

The Word proposal is a useful foundation: ThingsBoard CE for IoT infrastructure, its gateway for integrations, Docker Compose for deployment, and optional FastAPI and React extensions. Its six-week roadmap is credible as a narrow pilot with available hardware and an experienced full-time developer.

It also introduces a different customer and additional work. White-label integrators, energy communities, POD records, and allocation simulations are not requirements of the original home platform. Treat the integrator-oriented product as a proposed direction, and energy communities as a conditional extension. Do not add every feature in the new proposal merely because the older features have been removed.

For planning, assume one pilot integrator with an energy site and a general IoT site. Create a second isolated test tenant to verify separation. The initial customer-facing experience can use ThingsBoard dashboards; a complete custom portal is not a prerequisite for the pilot.

## Release scope

| Capability | Initial delivery | Boundary |
| --- | --- | --- |
| Integrators, customers and sites | Yes | Use ThingsBoard tenants, customers and assets first |
| Device onboarding | Yes | Generic MQTT plus one selected Modbus meter profile |
| Device profiles | Yes | Small tested catalog with units, field mappings and example payloads |
| Live values and history | Yes | ThingsBoard storage and dashboards |
| Energy monitoring | Yes | Available import/export, power and energy readings; no inferred measurements presented as metered facts |
| Alarms | Yes | Threshold and stale-device alarms using existing rules |
| CSV export | Yes | Verify base capability; add one bounded export endpoint only if necessary |
| Basic actuator command | Conditional | One tested noncritical relay with permissions and reported-state feedback |
| Branding | Limited | Portal logo/name if a portal is built; no CE frontend fork |
| Energy community simulation | Optional weeks 9 to 12 | Only if a pilot customer needs it and core acceptance has passed |
| Local-only installation | Alternative deployment | Same stack on a capable local Linux host; qualify this instead of hosted deployment if offline is mandatory |
| Local plus cloud synchronization | Deferred | No dual authoritative databases or bidirectional configuration sync |
| Full custom customer portal | Deferred | At most a few specific screens within the timebox |

Defer the 3D house editor, camera discovery and people detection, alarm escalation across cameras, OpenEMS integration and active dispatch, forecasting, machine learning, voice assistant, native mobile apps, broad protocol coverage, automated billing, official energy settlement, and commercial fleet operations. Retain those ideas in the original scope for later prioritization.

LoRaWAN/ChirpStack and vendor REST integrations are also deferred unless one replaces the selected Modbus path for the first customer's actual hardware. Two integration paths are enough to validate the product; four parallel paths would spend the schedule on compatibility work.

## Reuse and custom implementation

| Area | Reuse | Custom work allowed in the first release |
| --- | --- | --- |
| Devices and telemetry | ThingsBoard CE | Tested device profiles and normalization |
| Dashboard and rules | ThingsBoard CE | Dashboard templates and a few rule configurations |
| Protocol bridging | ThingsBoard IoT Gateway | Adapter only for an identified unsupported requirement |
| Identity and tenant separation | Existing platform accounts and permissions | Explicit authorization checks for any custom API |
| Business workflow | Existing customer and asset models initially | Thin FastAPI module if the pilot exceeds those models |
| Energy community simulation | None assumed | Optional domain module and auditable interval calculation |
| Deployment | Supported ThingsBoard installation pattern and Docker Compose | Configuration, backups, health checks and operator documentation |

Do not build another MQTT broker, time-series database, generic rule engine, device registry, identity provider, or dashboard framework. Do not duplicate all telemetry in an application database. Avoid Kubernetes, service-per-module deployment, and an early plugin marketplace.

ThingsBoard CE already has multi-tenancy. Native white-labeling and advanced RBAC are listed as PE capabilities in the vendor's edition comparison. Consequently, CE is the baseline when standard screens and roles suffice. Evaluate PE if native branding or finer permissions become a firm pilot requirement; buying those capabilities may be faster than recreating them. No license purchase is assumed or authorized by this plan. See [multi-tenancy](https://thingsboard.io/docs/concepts/multi-tenancy/) and the [vendor edition comparison](https://github.com/thingsboard/thingsboard.github.io/blob/master/ce-vs-pe-diff.md).

If a custom business backend becomes necessary, keep it as one FastAPI application. Its own PostgreSQL database owns business-only records, such as community membership and allocation versions, plus mappings to ThingsBoard IDs. ThingsBoard remains authoritative for devices and telemetry. The initial hierarchy can remain in ThingsBoard until a concrete business requirement justifies moving ownership; never keep two independently editable copies of the same relationship.

## Deployment and offline behavior

Baseline topology:

```text
MQTT sensors ----> existing LAN broker ----> ThingsBoard IoT Gateway
Modbus meter -----------------------------> ThingsBoard IoT Gateway
                                                    |
                                              authenticated link
                                                    |
                           ThingsBoard CE + its database and queue dependencies
                                                    |
                                      existing dashboards and administration
                                                    |
                               optional thin FastAPI API and focused portal
```

Use the pinned release's documented deployment dependencies rather than assuming that ThingsBoard and PostgreSQL alone always form a complete stack. Begin with the vendor installation configuration and simplify only where supported. See [Docker installation](https://thingsboard.io/docs/installation/docker/).

Choose one primary deployment in week 1. The planning default is a hosted Linux server with a gateway at the pilot site. In that profile, losing the WAN makes the server UI unavailable locally; verify the gateway's selected persistent buffer, capacity and replay behavior. Buffered ingestion is not equivalent to local dashboards or local automation.

If local-only home operation remains essential, use the same platform stack on a qualified local Linux server or mini PC and access its UI over the LAN or VPN. Replace hosted deployment qualification with this local profile within the same timebox. Avoid implementing both profiles and their synchronization at once. Download all required images and assets before offline tests and verify local authentication without WAN access.

Raspberry Pi and Olinuxino are gateway candidates, not a promise that every model can run the complete stack. Qualify one exact board, OS and storage combination first. The gateway documentation includes Raspberry Pi and other installation options, but the selected Olinuxino model still needs a practical check. See [gateway installation](https://thingsboard.io/docs/iot-gateway/installation/) and [connectors](https://thingsboard.io/docs/iot-gateway/connectors/).

## Schedule and exit gates

Assumptions: one experienced engineer working full time with AI assistance; an owner available for prompt scope decisions; a working Linux host; credentials, hardware and protocol documentation available in week 1; one pilot integrator; one selected gateway model; two device paths; no custom firmware or unknown vendor API dependency. A part-time schedule or unavailable equipment requires reducing scope or changing the dates.

| Week | Work | Required evidence |
| --- | --- | --- |
| 1 | Pin stack, select deployment and devices, install, establish accounts and hierarchy | Repeatable install, two isolated test tenants, one synthetic value on a dashboard |
| 2 | Connect physical MQTT sensor and selected Modbus meter; save reusable profiles | Both devices produce correctly timestamped values with documented units and mappings |
| 3 | Configure site dashboards, history, energy views and basic alarms | Usable energy and general IoT dashboards; stale device appears as stale |
| 4 | Finish onboarding instructions and bounded CSV export; add one relay only if required | End-to-end demonstration and a repeatable onboarding process for supported profiles |
| 5 to 6 | Pilot use, access checks, gateway restart and outage recovery, backups and restore | Pilot candidate with documented limits and verified recovery; no unresolved isolation defects |
| 7 to 8 | Resolve pilot failures and installation friction; improve the most-used workflow | Release candidate for the agreed small deployment matrix |
| 9 to 10 | If core gates passed, add one differentiator: community simulation or focused portal workflow | One complete reviewed workflow; otherwise spend this time fixing core defects |
| 11 to 12 | Pilot regression, upgrade and restore drills, operational documentation | Initial release accepted against the checks below |

One month buys a demonstration or narrow internal alpha. Six to eight weeks is the target for an integrator pilot. Two to three months is the target for a limited initial release with real pilot feedback. None of these milestones imply support for the original complete feature list or arbitrary hardware.

Weeks 9 to 12 provide room for measured pilot issues and one bounded extension, not a second product roadmap. At the end of weeks 2 and 4, update estimates from actual integration results. If a device is blocking progress, substitute an available supported device or remove that profile; do not create an open-ended driver project inside the MVP.

## Optional energy community extension

Add this only after the core product works and the pilot needs it. Limit it to community identity, member and POD records, effective-dated membership, interval data import, completeness flags, one agreed allocation method, and CSV results. Label every result as a simulation.

Persist the source dataset reference, time zone and interval boundaries, energy units, missing and duplicate interval policy, algorithm version, allocation parameters, calculation run ID, and results. Check that assigned energy does not exceed the eligible pool and that unallocated quantities are explicit. Distinguish cumulative meter counters from interval energy; handle resets and missing intervals rather than silently subtracting any two readings.

Official settlement, billing, regulatory submissions and live dispatch remain outside this release. The Romanian legal statements in the Word proposal have not been adopted as verified requirements here. If the product later performs regulated workflows, verify the applicable current rules and data exchange requirements as a separate work item before defining acceptance.

## Acceptance for the initial release

1. A clean qualified Linux host can be installed from documented, pinned configuration; required secrets are supplied separately.
2. Two tenant accounts cannot access each other's devices, history, dashboards or exports. Exercise direct API requests as well as UI navigation. Any custom API derives access from the authenticated user rather than trusting a submitted tenant ID.
3. A real MQTT sensor and the selected real Modbus meter can be onboarded using reusable profiles. Document supported models and capabilities rather than claiming universal support.
4. The pilot shows useful energy and non-energy telemetry, history, threshold alarms, stale readings, and a usable CSV export with units and timestamps.
5. Restart the gateway and platform, interrupt the network, and verify bounded recovery without misleading readings. Record the buffer limit and behavior when full. Never replay a stale actuator action after reconnect.
6. Restore configuration and retained history to a clean test instance. Record retention, resource use and known operating limits for the pilot load.
7. If a relay is included, test authorization, bounded command parameters, offline failure and actual reported state; sending a request must not be presented as confirmed actuation.
8. Test the chosen deployment profile. A hosted pilot clearly documents WAN dependency; a local-only pilot demonstrates local login, dashboard, ingestion and any promised rules with WAN disconnected.
9. If community simulation is included, reproduce results from the same versioned inputs, expose incomplete intervals, and keep simulated results separate from official settlement.

## AI development workflow and immediate backlog

Use AI primarily to configure dashboards and rule templates, draft captured-payload mappings, implement focused API screens, write deployment documentation, and construct meaningful integration checks. Review generated configuration and code before applying it to real devices. Validate protocol details against the exact installed release and actual device fixtures. Do not introduce extra infrastructure merely because an assistant can generate it quickly.

Start with these bounded tasks:

1. Record the primary deployment profile, exact gateway, pilot sensor and meter, and whether community simulation is needed for the first customer.
2. Create the smallest supported pinned deployment and document startup and credential setup.
3. Create two test tenants and the pilot customer/site structure using standard platform functionality.
4. Deliver the physical sensor-to-dashboard path, then the selected meter-to-energy-dashboard path.
5. Save profile and dashboard configuration in source control, with sanitized fixtures and no credentials.
6. Run the week 2 review before starting any custom portal or community module.

This plan supersedes the initial-delivery schedule in `implementation_strategy.md`. The original scope and Word proposal remain reference inputs. No application implementation is claimed by this planning update.
