package originalhome.growatt.control;

import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import com.google.gson.*;
import org.osgi.service.component.ComponentContext;
import io.openems.common.types.OpenemsType;
import io.openems.edge.common.channel.Doc;
import io.openems.edge.common.component.AbstractOpenemsComponent;
import io.openems.edge.common.component.ComponentManager;
import io.openems.edge.common.component.OpenemsComponent;
import io.openems.edge.controller.api.Controller;
import io.openems.common.types.ChannelAddress;

/** Native scheduled OpenEMS controller, initially deployed in monitoring mode.
 * This supports discrete inverter priorities, not a ManagedSymmetricEss power
 * actuator. Do not attach the stock ESS balancing controller to this driver.
 */
public final class GrowattStrategyController extends AbstractOpenemsComponent implements Controller {
    public enum ChannelId implements io.openems.edge.common.channel.ChannelId {
        STATUS(Doc.of(OpenemsType.STRING)), BLOCK_REASON(Doc.of(OpenemsType.STRING)),
        WRITES_ENABLED(Doc.of(OpenemsType.BOOLEAN)), MAX_CHARGE_POWER(Doc.of(OpenemsType.INTEGER)),
        MIN_DISCHARGE_SOC(Doc.of(OpenemsType.INTEGER)),
        REQUESTED_CHARGE_POWER(Doc.of(OpenemsType.INTEGER)),
        TARGET_CHARGE_PERCENT(Doc.of(OpenemsType.INTEGER));
        private final Doc doc;
        ChannelId(Doc doc) { this.doc=doc; }
        public Doc doc() { return doc; }
    }
    private ComponentManager manager;
    private GrowattControlDriver driver;
    private final Path folder=Path.of(System.getProperty("user.home"),".config/originalhome");
    private final Path profilePath=folder.resolve("growatt-control.json");
    private final Path requestPath=folder.resolve("growatt-command.json");
    private final Path ledgerPath=folder.resolve("growatt-control-ledger.json");
    private final Path statusPath=folder.resolve("growatt-control-status.json");
    private String burnedId="", activeId="";
    private boolean previouslyApplied=false;
    private long lastAttemptMs=0, lastStatusMs=0;
    private long lastNativePublished=0;
    private String previousStatus="";
    public GrowattStrategyController() {
        super(OpenemsComponent.ChannelId.values(), Controller.ChannelId.values(), ChannelId.values());
    }
    protected void bindManager(ComponentManager value) { manager=value; }
    protected void bindDriver(GrowattControlDriver value) { driver=value; }
    protected void unbindDriver(GrowattControlDriver value) { if(driver==value) driver=null; }
    protected void activate(ComponentContext context) {
        super.activate(context,"ctrlGrowattStrategy0","OriginalHome bounded Growatt strategies",true);
        try {
            var ledger=read(ledgerPath);
            burnedId=string(ledger,"last_command_id","");
            previouslyApplied=bool(ledger,"fallback_required");
        } catch(Exception invalid) {
            // Corrupt durable state must never cause an old command to be replayed.
            burnedId="INVALID_LEDGER";
        }
    }
    @Override protected void deactivate() {
        if(driver!=null) driver.clearPendingWrites();
        // If power/communication/process is lost there is no guaranteed inverter
        // rollback. The durable marker requests fallback on healthy restart.
        super.deactivate();
    }
    private static JsonObject read(Path path) throws Exception {
        if(!Files.exists(path)) return new JsonObject();
        if(Files.size(path)>16384) throw new IllegalArgumentException("Oversized control document");
        return JsonParser.parseString(Files.readString(path)).getAsJsonObject();
    }
    private static boolean bool(JsonObject obj,String key) {
        return obj.has(key) && obj.get(key).isJsonPrimitive()
            && obj.getAsJsonPrimitive(key).isBoolean() && obj.get(key).getAsBoolean();
    }
    private static int integer(JsonObject obj,String key,int fallback) {
        if(!obj.has(key) || obj.get(key).isJsonNull()) return fallback;
        var value=obj.get(key).getAsBigDecimal(); return value.intValueExact();
    }
    private static String string(JsonObject obj,String key,String fallback) {
        return obj.has(key) ? obj.get(key).getAsString() : fallback;
    }
    private static void atomicWrite(Path path,Object value) throws Exception {
        Files.createDirectories(path.getParent());
        var temp=path.resolveSibling(path.getFileName()+".tmp");
        Files.writeString(temp,new Gson().toJson(value)+"\n",StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
        Files.setPosixFilePermissions(temp,PosixFilePermissions.fromString("rw-------"));
        Files.move(temp,path,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }
    private ControlPolicy.Snapshot shadowSnapshot(long now) {
        try {
            long ts=((Number)manager.getChannel(new ChannelAddress("growatt0","LastSuccessfulRead")).value().get()).longValue();
            int soc=((Number)manager.getChannel(new ChannelAddress("growatt0","EssSoc")).value().get()).intValue();
            int battery=((Number)manager.getChannel(new ChannelAddress("growatt0","EssActivePower")).value().get()).intValue();
            // Shadow telemetry is useful for decisions but supplies no current
            // holding-register readback or independent control identity proof.
            return new ControlPolicy.Snapshot(ts,soc,battery,null,null,null,false,null,null);
        } catch(Exception unavailable) { return null; }
    }
    private void remember(boolean required) throws Exception {
        atomicWrite(ledgerPath,Map.of("last_command_id",burnedId,"fallback_required",required));
    }
    @Override public void run() {
        long now=System.currentTimeMillis();
        String state="monitoring", reason="writes_disabled";
        Integer target=null;
        int requestedW=0, maxW=2990, minSoc=15;
        boolean enabled=false;
        ControlPolicy.Snapshot sample=null;
        try {
            var profile=read(profilePath);
            maxW=integer(profile,"max_charge_w",2990);
            minSoc=integer(profile,"min_discharge_soc",15);
            var qualification=profile.has("qualification") ? profile.getAsJsonObject("qualification") : new JsonObject();
            enabled=bool(profile,"writes_enabled");
            var limits=new ControlPolicy.Limits(maxW,integer(profile,"charge_percent_reference_w",0),
                integer(profile,"max_soc",0),minSoc,bool(qualification,"firmware_register_map_verified"),
                bool(qualification,"identity_verified"),bool(qualification,"charge_percentage_reference_verified"),
                bool(qualification,"single_serial_owner_verified"),bool(qualification,"inverter_discharge_reserve_verified"),enabled);
            var body=read(requestPath);
            ControlPolicy.Request request=null;
            if(body.has("command_id")) {
                request=new ControlPolicy.Request(body.get("command_id").getAsString(),
                    ControlPolicy.Mode.valueOf(body.get("mode").getAsString()),
                    integer(body,"charge_w",0),body.get("issued_ms").getAsBigDecimal().longValueExact(),
                    body.get("expires_ms").getAsBigDecimal().longValueExact(),integer(body,"target_soc",90));
                requestedW=request.chargeW();
                if(burnedId.equals(request.id()) && !activeId.equals(request.id())) {
                    request=null; reason="command_not_replayed_after_restart";
                }
            }
            sample=driver!=null && driver.transportBound() ? driver.snapshot(now) : shadowSnapshot(now);
            if(driver!=null && driver.transportBound() && now-lastNativePublished>=1000) {
                atomicWrite(Path.of(System.getProperty("user.home"),"OriginalHomeIOT/data/growatt-live/sample.json"),driver.telemetry(now));
                lastNativePublished=now;
            }
            var commissioning=read(folder.resolve("growatt-commission.json"));
            long commissionUntil=commissioning.has("until_ms") ? commissioning.get("until_ms").getAsLong() : 0;
            if(bool(profile,"commissioning_enabled") && !enabled && commissionUntil>now && commissionUntil-now<=180000
                    && driver!=null && driver.transportBound()) {
                if(now-lastAttemptMs>=3000) {
                    state=driver.commission(string(commissioning,"phase","DISABLE"),commissionUntil,now);
                    lastAttemptMs=now;
                } else state="awaiting_commissioning_readback";
                var diagnostic=new LinkedHashMap<String,Object>();
                diagnostic.put("updated_ms",now); diagnostic.put("status",state);
                diagnostic.put("readback",driver.diagnostics()); diagnostic.put("telemetry",driver.telemetry(now));
                atomicWrite(folder.resolve("growatt-commission-status.json"),diagnostic);
                return;
            }
            long recoveryUntil=profile.has("recovery_test_until_ms") ? profile.get("recovery_test_until_ms").getAsBigDecimal().longValueExact() : 0;
            boolean recoveryTest=recoveryUntil>now && recoveryUntil-now<=180000;
            var decision=ControlPolicy.decide(limits,request,sample,now,previouslyApplied);
            if(!decision.writable()) {
                if(driver!=null) driver.clearPendingWrites();
                reason=decision.reason(); state=enabled ? "blocked" : "shadow";
            } else if(driver==null || !driver.transportBound()) {
                reason="native_serial_bridge_not_bound"; state="blocked";
            } else if(decision.gridCharge() && !bool(qualification,"grid_charging_verified")) {
                reason="grid_charging_not_qualified";state="blocked";driver.clearPendingWrites();
            } else if(!bool(qualification,"crash_and_communication_fallback_verified")
                    && !recoveryTest && !(decision.fallback() && previouslyApplied)) {
                reason="inverter_fallback_not_qualified"; state="blocked"; driver.clearPendingWrites();
            } else {
                if(request!=null && !request.id().equals(activeId) && !decision.fallback()) {
                    if(burnedId.equals("INVALID_LEDGER")) throw new IllegalStateException("Invalid control ledger");
                    burnedId=request.id(); activeId=request.id();
                    // Commit intent before queueing a register write. On crash,
                    // request fallback instead of replaying a stale strategy.
                    remember(true); previouslyApplied=true;
                }
                target=decision.chargePercent();
                if(now-lastAttemptMs>=5000) {
                    state=driver.apply(decision,limits,request==null ? now : request.expiresMs(),request==null || request.targetSoc()==0 ? limits.maxSoc() : Math.min(limits.maxSoc(),request.targetSoc()),now); lastAttemptMs=now;
                } else state="awaiting_readback";
                reason=decision.reason();
                if(decision.fallback() && state.equals("readback_confirmed")) {
                    remember(false); previouslyApplied=false; activeId="";
                }
            }
            var info=new LinkedHashMap<String,Object>();
            info.put("schema_version",1); info.put("updated_ms",now);
            info.put("status",state);info.put("reason",reason);info.put("writes_enabled",enabled);
            info.put("max_charge_w",maxW);info.put("requested_charge_w",requestedW);
            info.put("min_discharge_soc",minSoc);
            info.put("inverter_limits_applied",false);
            info.put("target_charge_percent",target);info.put("native_transport_bound",driver!=null && driver.transportBound());
            info.put("physical_effect_verified",false);
            if(driver!=null) info.put("register_readback",driver.diagnostics());
            info.put("supported_modes",List.of("MONITOR","SELF_CONSUMPTION","SOLAR_CHARGE","GRID_CHARGE"));
            info.put("unsupported_modes",List.of("FORCED_DISCHARGE","GRID_EXPORT","TARIFF_OPTIMIZATION"));
            info.put("qualification",qualification);
            if(sample!=null) {
                info.put("observed_ms",sample.observedMs()); info.put("battery_soc",sample.soc());
                info.put("battery_w",sample.batteryW());
                info.put("candidate_load_discharge_stop_soc",sample.loadDischargeStopSoc());
                info.put("candidate_grid_discharge_stop_soc",sample.gridDischargeStopSoc());
            }
            // Write-on-change or every five seconds; do not churn flash every cycle.
            String signature=state+reason+requestedW+target;
            if(!signature.equals(previousStatus) || now-lastStatusMs>=5000) {
                atomicWrite(statusPath,info);previousStatus=signature;lastStatusMs=now;
            }
        } catch(Exception invalid) {
            if(driver!=null) driver.clearPendingWrites();
            state="blocked";reason="invalid_or_unavailable_control_configuration";
        }
        channel(ChannelId.STATUS).setNextValue(state);channel(ChannelId.BLOCK_REASON).setNextValue(reason);
        channel(ChannelId.WRITES_ENABLED).setNextValue(enabled);channel(ChannelId.MAX_CHARGE_POWER).setNextValue(maxW);
        channel(ChannelId.MIN_DISCHARGE_SOC).setNextValue(minSoc);
        channel(ChannelId.REQUESTED_CHARGE_POWER).setNextValue(requestedW);channel(ChannelId.TARGET_CHARGE_PERCENT).setNextValue(target);
    }
}
