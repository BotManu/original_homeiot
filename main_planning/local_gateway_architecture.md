# Local gateway implementation baseline

Owner clarifications, 5 November 2026:

- ThingsBoard is the platform foundation; OpenEMS is its integrated energy subsystem.
- The product has a local gateway UI and a cloud UI.
- Implement the local component first. The local UI covers the integrated platform, rather than requiring the owner to use the separate OpenEMS UI for ordinary energy tasks.
- OpenEMS remains the sole energy control writer. The local component must operate independently of WAN availability.

These decisions replace the earlier separate-interface pilot assumption. They do not require every ThingsBoard server dependency to run on every gateway model. Gateway hardware and the placement of ThingsBoard CE still require qualification.

## First code slice

`gateway/` implements a dependency-free Python development service and locally served browser UI. Its normalized energy contract contains five measurements, collection timestamps, stale state, source status, and delivery-buffer status. Live reads use OpenEMS REST in read-only mode. Optional ThingsBoard HTTP telemetry delivery is decoupled from collection and backed by a bounded SQLite spool. The simulator is explicitly labeled and isolated from external forwarding.

This is the local companion layer for ThingsBoard/OpenEMS, not a replacement platform or a completed ThingsBoard installation. General IoT onboarding, production authentication, equipment qualification, actual strategy controls, deployment services, and the cloud UI remain subsequent work. Hardware writes are disabled in this slice. The current UI can show last collected readings offline; it cannot infer live equipment health solely from the OpenEMS REST response.

## Next implementation milestone

Qualify the exact reference gateway and OpenEMS/Growatt setup; record a sanitized real response fixture and verify units, signs, freshness, and failure behavior. Connect the ThingsBoard device projection, demonstrate WAN-loss recovery, and then implement supported bounded strategy requests with expiry and observed feedback. Preserve the local API contract for the later cloud UI without creating a second energy-control loop.
