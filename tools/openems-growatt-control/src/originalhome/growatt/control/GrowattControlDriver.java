package originalhome.growatt.control;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.osgi.service.component.ComponentContext;
import io.openems.common.channel.PersistencePriority;
import io.openems.common.types.OpenemsType;
import io.openems.edge.bridge.modbus.api.AbstractOpenemsModbusComponent;
import io.openems.edge.bridge.modbus.api.BridgeModbus;
import io.openems.edge.bridge.modbus.api.ModbusComponent;
import io.openems.edge.bridge.modbus.api.ModbusProtocol;
import io.openems.edge.bridge.modbus.api.element.*;
import io.openems.edge.bridge.modbus.api.task.*;
import io.openems.edge.common.channel.Doc;
import io.openems.edge.common.component.OpenemsComponent;
import io.openems.edge.common.taskmanager.Priority;

/** Candidate Protocol-II driver. No public writable channels or arbitrary-register API.
 *
 * The serial bridge is intentionally absent from the shadow deployment. A
 * qualified activation must transfer serial ownership from the Python reader.
 */
public final class GrowattControlDriver extends AbstractOpenemsModbusComponent {
    public enum ChannelId implements io.openems.edge.common.channel.ChannelId {
        CHARGE_PERCENT(Doc.of(OpenemsType.INTEGER)), PRIORITY(Doc.of(OpenemsType.INTEGER)),
        AC_CHARGE_ENABLED(Doc.of(OpenemsType.INTEGER)),
        CANDIDATE_LOAD_DISCHARGE_STOP_SOC(Doc.of(OpenemsType.INTEGER)),
        CANDIDATE_GRID_DISCHARGE_STOP_SOC(Doc.of(OpenemsType.INTEGER)),
        NATIVE_TRANSPORT_BOUND(Doc.of(OpenemsType.BOOLEAN)),
        LAST_SUCCESSFUL_READ(Doc.of(OpenemsType.LONG).remotePersistencePriority(PersistencePriority.HIGH));
        private final Doc doc;
        ChannelId(Doc doc) { this.doc=doc; }
        public Doc doc() { return doc; }
    }
    private final Map<String, Number> raw = new ConcurrentHashMap<>();
    private volatile long identityAt, firmwareAt, protocolAt, settingsAt, telemetryAt, pvAt, reserveAt, priorityAt, clockAt, slotsAt;
    private final UnsignedWordElement chargeWrite = new UnsignedWordElement(1090);
    private final UnsignedWordElement acWrite=new UnsignedWordElement(1092);
    private final UnsignedWordElement socWrite=new UnsignedWordElement(1091);
    private Integer commissioningOriginalSoc;
    private final ScheduleSlotElement slotWrite = new ScheduleSlotElement();
    private Integer commissioningOriginalCap;
    private Integer plannedStart, plannedEnd;
    private long plannedUntil;

    public GrowattControlDriver() {
        super(OpenemsComponent.ChannelId.values(), ModbusComponent.ChannelId.values(), ChannelId.values());
    }
    protected void activate(ComponentContext context) {
        super.activate(context, "growattControl0", "Growatt candidate bounded charge interface", true, 1);
    }
    @Override protected void deactivate() { clearPendingWrites(); super.deactivate(); }
    protected void bindModbus(BridgeModbus bridge) {
        super.setModbus(bridge);
        // The base setter only stores the reference. If DS binds the bridge
        // after activate(), register the protocol here as well.
        if(getUnitId()!=null && isEnabled()) {
            bridge.addProtocol(id(),getModbusProtocol());
            bridge.retryModbusCommunication(id());
        }
    }
    protected void unbindModbus(BridgeModbus bridge) { clearPendingWrites(); super.unsetModbus(bridge); }

    private void put(String key, Number value) {
        if (value==null) raw.remove(key); else raw.put(key,value);
    }
    private UnsignedWordElement word(int address, String key) {
        return new UnsignedWordElement(address).onUpdateCallback(value -> put(key,value));
    }
    private UnsignedDoublewordElement doubleword(int address, String key) {
        return new UnsignedDoublewordElement(address).onUpdateCallback(value -> put(key,value));
    }
    private static long stamp(Object value) { return value==null ? 0 : System.currentTimeMillis(); }
    private Integer integer(String key) { var value=raw.get(key); return value==null ? null : value.intValue(); }

    @Override protected ModbusProtocol defineModbusProtocol() {
        return new ModbusProtocol(this,
            new FC3ReadRegistersTask(9, Priority.HIGH,
                word(9,"fw9"),word(10,"fw10"),word(11,"fw11"),
                word(12,"fw12"),word(13,"fw13"),word(14,"fw14").onUpdateCallback(v -> firmwareAt=stamp(v))),
            new FC3ReadRegistersTask(23, Priority.HIGH,
                word(23,"serial23"),word(24,"serial24"),word(25,"serial25"),word(26,"serial26"),word(27,"serial27"),
                word(28,"model28"),word(29,"model29").onUpdateCallback(v -> identityAt=stamp(v))),
            new FC3ReadRegistersTask(88, Priority.HIGH,
                word(88,"protocol").onUpdateCallback(v -> protocolAt=stamp(v))),
            // Diagnostics only: these candidate addresses are not a qualified
            // reserve write map. Newer firmware documents reserve them.
            new FC3ReadRegistersTask(1039, Priority.HIGH,
                m(ChannelId.CANDIDATE_LOAD_DISCHARGE_STOP_SOC,word(1039,"loadReserve")),
                m(ChannelId.CANDIDATE_GRID_DISCHARGE_STOP_SOC,word(1040,"gridReserve")).onUpdateCallback(v -> reserveAt=stamp(v))),
            new FC3ReadRegistersTask(1044, Priority.HIGH,
                m(ChannelId.PRIORITY,word(1044,"priority")).onUpdateCallback(v -> priorityAt=stamp(v))),
            new FC3ReadRegistersTask(1090, Priority.HIGH,
                m(ChannelId.CHARGE_PERCENT,word(1090,"charge")),word(1091,"stopSoc"),
                m(ChannelId.AC_CHARGE_ENABLED,word(1092,"ac")).onUpdateCallback(v -> settingsAt=stamp(v))),
            new FC3ReadRegistersTask(45, Priority.HIGH,
                word(45,"year"),word(46,"month"),word(47,"day"),word(48,"hour"),word(49,"minute"),
                word(50,"second").onUpdateCallback(v -> clockAt=stamp(v))),
            new FC3ReadRegistersTask(1080, Priority.HIGH,
                word(1080,"gStart1"),word(1081,"gEnd1"),word(1082,"gEnable1"),
                word(1083,"gStart2"),word(1084,"gEnd2"),word(1085,"gEnable2"),
                word(1086,"gStart3"),word(1087,"gEnd3"),word(1088,"gEnable3")),
            new FC3ReadRegistersTask(1100, Priority.HIGH,
                word(1100,"start"),word(1101,"end"),word(1102,"enable"),
                word(1103,"start2"),word(1104,"end2"),word(1105,"enable2"),
                word(1106,"start3"),word(1107,"end3"),word(1108,"enable3").onUpdateCallback(v -> slotsAt=stamp(v))),
            new FC4ReadInputRegistersTask(1, Priority.HIGH,
                doubleword(1,"pv").onUpdateCallback(v -> pvAt=stamp(v))),
            new FC4ReadInputRegistersTask(1009, Priority.HIGH,
                doubleword(1009,"discharge"), doubleword(1011,"chargePower"),
                word(1013,"voltage"),word(1014,"soc"),new DummyRegisterElement(1015,1020),
                doubleword(1021,"import"),new DummyRegisterElement(1023,1028),
                doubleword(1029,"export"),new DummyRegisterElement(1031,1036),
                doubleword(1037,"load").onUpdateCallback(v -> {
                    telemetryAt=stamp(v); channel(ChannelId.LAST_SUCCESSFUL_READ).setNextValue(telemetryAt);
                })),
            // Only documented battery-first charge and first-slot registers can be written.
            // No AC-charge gate, protection, battery chemistry, export or test registers.
            new FC6WriteRegisterTask(1090,chargeWrite), new FC6WriteRegisterTask(1091,socWrite),
            new FC6WriteRegisterTask(1092,acWrite), new FC16WriteRegistersTask(1100,slotWrite));
    }

    public boolean transportBound() { return getBridgeModbus()!=null; }
    private static boolean fresh(long at, long now) { return at>0 && at<=now+2000 && now-at<=15000; }
    public ControlPolicy.Snapshot snapshot(long now) {
        channel(ChannelId.NATIVE_TRANSPORT_BOUND).setNextValue(transportBound());
        boolean identity = fresh(identityAt,now) && fresh(firmwareAt,now) && fresh(protocolAt,now)
            && Integer.valueOf(0x1100).equals(integer("model28")) && Integer.valueOf(0xF25D).equals(integer("model29"))
            && Integer.valueOf(21057).equals(integer("fw9")) && Integer.valueOf(12590).equals(integer("fw10"))
            && Integer.valueOf(12320).equals(integer("fw11")) && Integer.valueOf(23107).equals(integer("fw12"))
            && Integer.valueOf(16961).equals(integer("fw13")) && Integer.valueOf(3).equals(integer("fw14"))
            && Integer.valueOf(305).equals(integer("protocol"))
            && Integer.valueOf(14648).equals(integer("serial23")) && Integer.valueOf(14134).equals(integer("serial24"))
            && Integer.valueOf(13620).equals(integer("serial25")) && Integer.valueOf(13106).equals(integer("serial26"))
            && Integer.valueOf(12592).equals(integer("serial27"));
        Integer battery = raw.containsKey("discharge") && raw.containsKey("chargePower")
            ? (int)Math.round((raw.get("discharge").doubleValue()-raw.get("chargePower").doubleValue())/10) : null;
        for(var key : new String[]{"discharge","chargePower"})
            if(raw.containsKey(key) && (raw.get(key).doubleValue()<0 || raw.get(key).doubleValue()>300000)) battery=null;
        long observed = fresh(settingsAt,now) && fresh(priorityAt,now) ? telemetryAt : 0;
        return new ControlPolicy.Snapshot(observed, integer("soc"), battery, integer("priority"),
            integer("charge"),integer("ac"),identity,
            fresh(reserveAt,now) ? integer("loadReserve") : null,
            fresh(reserveAt,now) ? integer("gridReserve") : null);
    }
    public Map<String,Object> telemetry(long now) {
        var sample=snapshot(now);
        if (!sample.identityMatches() || !fresh(telemetryAt,now) || !fresh(pvAt,now)) return Map.of("available",false,"ts",now);
        for (var key : new String[]{"pv","load","import","export","voltage","soc","chargePower","discharge"})
            if (!raw.containsKey(key)) return Map.of("available",false,"ts",now);
        if(sample.batteryW()==null || sample.soc()==null || sample.soc()<0 || sample.soc()>100
                || raw.get("voltage").doubleValue()<100 || raw.get("voltage").doubleValue()>1000)
            return Map.of("available",false,"ts",now);
        for(var key : new String[]{"pv","load","import","export","chargePower","discharge"})
            if(raw.get(key).doubleValue()<0 || raw.get(key).doubleValue()>300000)
                return Map.of("available",false,"ts",now);
        return Map.of("available",true,"ts",telemetryAt,"values",Map.of(
            "solar_w",raw.get("pv").doubleValue()/10,
            "load_w",raw.get("load").doubleValue()/10,
            "grid_w",(raw.get("import").doubleValue()-raw.get("export").doubleValue())/10,
            "battery_w",sample.batteryW(),"battery_soc",sample.soc()),
            "model_code","GT1100F25D","reported_serial","9876543210",
            "battery_voltage_v",raw.get("voltage").doubleValue()/10);
    }
    synchronized void clearPendingWrites() {
        chargeWrite.setNextWriteValue(null); acWrite.setNextWriteValue(null); socWrite.setNextWriteValue(null); slotWrite.setNextWriteValue(null);
    }
    public Map<String,Object> diagnostics() {
        var result=new java.util.LinkedHashMap<String,Object>();
        for(var key : new String[]{"charge","stopSoc","ac","priority","hour","minute","second",
                "start","end","enable","start2","end2","enable2","start3","end3","enable3",
                "gEnable1","gEnable2","gEnable3"}) result.put(key,integer(key));
        return result;
    }
    private boolean prerequisites(long now) {
        var sample=snapshot(now);
        if(!transportBound() || !sample.identityMatches() || !fresh(settingsAt,now)
                || !fresh(priorityAt,now) || !fresh(telemetryAt,now) || !fresh(clockAt,now)
                || !fresh(slotsAt,now) || integer("ac")==null || integer("ac")<0 || integer("ac")>1) return false;
        for(var key : new String[]{"enable2","enable3","gEnable1","gEnable2","gEnable3"})
            if(!Integer.valueOf(0).equals(integer(key))) return false;
        return true;
    }
    private String set(UnsignedWordElement element, String key, int value, String label) {
        if(!Integer.valueOf(value).equals(integer(key))) { element.setNextWriteValue(value); return label+"_requested"; }
        return null;
    }
    private String slot(int start,int end,int enable) {
        if(Integer.valueOf(start).equals(integer("start")) && Integer.valueOf(end).equals(integer("end"))
                && Integer.valueOf(enable).equals(integer("enable"))) return null;
        slotWrite.setNextWriteValue(ScheduleWindow.words(start,end,enable));
        return "atomic_slot_requested";
    }
    private String disableSlot() {
        if(Integer.valueOf(0).equals(integer("enable"))) return "readback_confirmed";
        String result=slot(integer("start"),integer("end"),0);
        return result==null ? "readback_confirmed" : result;
    }
    private String stopCharging() {
        String result=set(acWrite,"ac",0,"ac_disable");
        return result==null ? disableSlot() : result;
    }
    private String schedule(int cap,int targetSoc,boolean grid,long until,long now,boolean rolling) {
        String result;
        if(!rolling && (plannedStart==null || plannedUntil!=until) &&
                (!Integer.valueOf(0).equals(integer("enable")) || !Integer.valueOf(0).equals(integer("ac"))))
            return stopCharging();
        result=set(chargeWrite,"charge",cap,"charge_cap"); if(result!=null) return result;
        if(rolling || plannedStart==null || plannedUntil!=until) {
            try {
                var window=rolling ? ScheduleWindow.heartbeat(integer("hour"),integer("minute"),integer("second"))
                    : ScheduleWindow.of(integer("hour"),integer("minute"),integer("second"),(until-now)/1000);
                plannedStart=window.start(); plannedEnd=window.end(); plannedUntil=until;
            } catch(IllegalArgumentException invalid) { return rolling ? stopCharging() : "lease_too_short_for_hardware_schedule"; }
        }
        if(now>=until) return stopCharging();
        result=set(socWrite,"stopSoc",targetSoc,"target_soc"); if(result!=null) return result;
        result=set(acWrite,"ac",grid ? 1 : 0,"ac_charge"); if(result!=null) return result;
        result=slot(plannedStart,plannedEnd,1); if(result!=null) return result;
        return Integer.valueOf(1).equals(integer("priority")) ? "strategy_readback_confirmed" : "awaiting_priority_transition";
    }
    /** Explicit short commissioning session; grid-charge tests are explicit; export is never enabled. */
    synchronized String commission(String phase,long until,long now) {
        clearPendingWrites();
        if(!prerequisites(now)) return "commissioning_gate_closed";
        if(commissioningOriginalCap==null) {
            if(!Integer.valueOf(0).equals(integer("enable")) || !Integer.valueOf(0).equals(integer("priority")))
                return "commissioning_requires_idle_slot";
            commissioningOriginalCap=integer("charge"); commissioningOriginalSoc=integer("stopSoc");
            if(commissioningOriginalCap==null || commissioningOriginalCap<0 || commissioningOriginalCap>100)
                return "invalid_original_cap";
        }
        if(phase.equals("DISABLE") || now>=until) return stopCharging();
        if(phase.equals("RESTORE")) {
            String result=stopCharging(); if(!result.equals("readback_confirmed")) return result;
            if(!Integer.valueOf(0).equals(integer("priority"))) return "awaiting_load_first";
            result=slot(0,0,0); if(result!=null) return result;
            result=set(socWrite,"stopSoc",commissioningOriginalSoc,"restore_soc"); if(result!=null) return result;
            result=set(chargeWrite,"charge",commissioningOriginalCap,"restore_cap");
            return result==null ? "restoration_readback_confirmed" : result;
        }
        if(phase.equals("CAP")) {
            if(!Integer.valueOf(0).equals(integer("enable"))) return "disable_slot_before_cap_test";
            String result=set(chargeWrite,"charge",10,"commissioning_cap");
            return result==null ? "cap_readback_confirmed" : result;
        }
        if(phase.equals("SLOT")) return schedule(10,commissioningOriginalSoc,false,until,now,false);
        if(phase.equals("GRID_SLOT") || phase.equals("GRID_SLOT_33")) {
            if(integer("soc")==null || integer("soc")>=90) return stopCharging();
            return schedule(phase.equals("GRID_SLOT_33") ? 33 : 10,90,true,until,now,false);
        }
        return "unknown_commissioning_phase";
    }
    synchronized String apply(ControlPolicy.Decision decision, ControlPolicy.Limits limits, long until, int targetSoc, long now) {
        clearPendingWrites();
        if(!decision.writable() || !limits.writesEnabled() || !limits.protocolQualified()
                || !limits.identityQualified() || !limits.powerMappingQualified() || !limits.singleSerialOwner()
                || limits.minSoc()>0 || !prerequisites(now)) return "write_gate_closed";
        int cap=decision.chargePercent();
        if(cap<0 || cap>100 || (long)cap*limits.chargePercentReferenceW()>limits.maxChargeW()*100L)
            return "invalid_native_target";
        if(decision.priority()==0 || decision.fallback()) return stopCharging();
        return schedule(cap,targetSoc,decision.gridCharge(),until,now,true);
    }
}
