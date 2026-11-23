package originalhome.growatt.control;

/** Bounded, device-specific strategy policy. Contains no transport or write API. */
public final class ControlPolicy {
    public enum Mode { MONITOR, SELF_CONSUMPTION, SOLAR_CHARGE, GRID_CHARGE }
    public record Limits(int maxChargeW, int chargePercentReferenceW, int maxSoc, int minSoc,
            boolean protocolQualified, boolean identityQualified, boolean powerMappingQualified,
            boolean singleSerialOwner, boolean inverterReserveQualified, boolean writesEnabled) {
        public Limits {
            if (maxChargeW < 1 || maxChargeW > 2990)
                throw new IllegalArgumentException("Owner charging ceiling is 2990 W");
            if (chargePercentReferenceW < 0 || chargePercentReferenceW > 30000)
                throw new IllegalArgumentException("Invalid percentage reference");
            if (maxSoc < 0 || maxSoc > 100) throw new IllegalArgumentException("Invalid SoC ceiling");
            if (minSoc < 0 || minSoc > 99 || (maxSoc > 0 && minSoc >= maxSoc))
                throw new IllegalArgumentException("Discharge reserve must be 0..99 and below the charging ceiling");
        }
    }
    public record Request(String id, Mode mode, int chargeW, long issuedMs, long expiresMs, int targetSoc) {
        public Request(String id,Mode mode,int chargeW,long issuedMs,long expiresMs) { this(id,mode,chargeW,issuedMs,expiresMs,0); }
    }
    public record Snapshot(long observedMs, Integer soc, Integer batteryW, Integer priority,
            Integer chargePercent, Integer acChargeEnabled, boolean identityMatches,
            Integer loadDischargeStopSoc, Integer gridDischargeStopSoc) {}
    public record Decision(boolean writable, String reason, Integer chargePercent, Integer priority,
            int effectiveChargeW, boolean fallback, boolean gridCharge) {
        public Decision(boolean writable,String reason,Integer percent,Integer priority,int watts,boolean fallback) {
            this(writable,reason,percent,priority,watts,fallback,false);
        }
    }

    private static Decision blocked(String reason) {
        return new Decision(false, reason, null, null, 0, false);
    }

    public static Decision decide(Limits limits, Request request, Snapshot sample, long nowMs,
            boolean leasePreviouslyApplied) {
        if (!limits.writesEnabled()) return blocked("writes_disabled");
        if (!limits.protocolQualified()) return blocked("firmware_register_map_unqualified");
        if (!limits.identityQualified()) return blocked("inverter_identity_unqualified");
        if (!limits.powerMappingQualified() || limits.chargePercentReferenceW() == 0)
            return blocked("charge_percentage_reference_unqualified");
        if (!limits.singleSerialOwner()) return blocked("serial_ownership_not_transferred");
        if (limits.minSoc()>0 && !limits.inverterReserveQualified()) return blocked("inverter_discharge_reserve_unqualified");
        if (limits.maxSoc() == 0) return blocked("maximum_soc_not_configured");
        if (sample == null || !sample.identityMatches()) return blocked("device_identity_mismatch");
        if (sample.observedMs() > nowMs + 2000 || nowMs - sample.observedMs() > 15000)
            return blocked("equipment_stale");
        if (sample.soc() == null || sample.soc() < 0 || sample.soc() > 100
                || sample.batteryW() == null || sample.priority() == null
                || sample.chargePercent() == null || sample.chargePercent() < 0 || sample.chargePercent() > 100
                || sample.acChargeEnabled() == null)
            return blocked("equipment_incomplete");
        if (sample.acChargeEnabled()<0 || sample.acChargeEnabled()>1) return blocked("invalid_grid_charge_readback");
        if (sample.priority() < 0 || sample.priority() > 1) return blocked("unsupported_existing_priority");
        // Require actual inverter-side protection before requesting a strategy
        // or a load-first fallback. A local if(soc<=15) check cannot protect the
        // battery while OpenEMS is stopped or serial communication is lost.
        if (limits.minSoc()>0 && (sample.loadDischargeStopSoc()==null || sample.gridDischargeStopSoc()==null
                || sample.loadDischargeStopSoc()<limits.minSoc() || sample.gridDischargeStopSoc()<limits.minSoc()
                || sample.loadDischargeStopSoc()>100 || sample.gridDischargeStopSoc()>100))
            return blocked("inverter_discharge_reserve_readback_mismatch");
        if (limits.minSoc()>0 && sample.soc()<=limits.minSoc() && sample.batteryW()>0)
            return blocked("discharge_at_or_below_reserve_detected");
        if (request == null || request.mode() == Mode.MONITOR) {
            return leasePreviouslyApplied || sample.acChargeEnabled()==1 ? fallback("cancelled") : blocked("monitoring_only");
        }
        if (request.id() == null || !request.id().matches("[a-f0-9-]{36}"))
            return blocked("invalid_command_id");
        if (request.issuedMs() > nowMs + 2000 || request.issuedMs() <= 0
                || request.expiresMs() <= request.issuedMs()
                || request.expiresMs() - request.issuedMs() > 180000)
            return blocked("invalid_command_lease");
        if (nowMs >= request.expiresMs())
            return leasePreviouslyApplied ? fallback("lease_expired") : blocked("command_expired");
        if (request.chargeW() < 0 || request.chargeW() > limits.maxChargeW())
            return blocked("requested_charge_exceeds_owner_limit");
        if(request.targetSoc()<0 || request.targetSoc()>100) return blocked("invalid_target_soc");
        if(request.mode()==Mode.GRID_CHARGE && request.chargeW()==0) return blocked("grid_charge_requires_positive_power");
        int stopSoc=request.targetSoc()==0 ? limits.maxSoc() : Math.min(limits.maxSoc(),request.targetSoc());
        if(request.mode()!=Mode.GRID_CHARGE && sample.acChargeEnabled()==1) return fallback("disable_grid_charging_before_mode_change");
        if (sample.soc() >= stopSoc) return fallback("maximum_soc_reached");
        if (sample.batteryW() < -limits.maxChargeW()) return fallback("measured_charge_exceeds_owner_limit");
        int percent = (int) Math.min(100,
                (long) request.chargeW() * 100 / limits.chargePercentReferenceW());
        int boundedWatts = (int) ((long) percent * limits.chargePercentReferenceW() / 100);
        int priority = request.mode() == Mode.SELF_CONSUMPTION ? 0 : 1;
        return new Decision(true, "ready", percent, priority, boundedWatts, false, request.mode()==Mode.GRID_CHARGE);
    }

    private static Decision fallback(String reason) {
        // Best effort while communication is healthy: stop charging and return
        // to the inverter's load-first mode. Never restore a captured 100% cap.
        return new Decision(true, reason, 0, 0, 0, true);
    }

    private ControlPolicy() {}
}
