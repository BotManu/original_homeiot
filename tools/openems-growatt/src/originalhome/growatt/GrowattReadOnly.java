package originalhome.growatt;

import java.nio.file.Files;
import java.nio.file.Path;
import com.google.gson.JsonParser;
import io.openems.common.channel.Level;
import io.openems.common.channel.Unit;
import org.osgi.service.component.ComponentContext;
import org.osgi.service.event.Event;
import org.osgi.service.event.EventHandler;
import io.openems.common.types.OpenemsType;
import io.openems.edge.common.channel.Doc;
import io.openems.edge.common.component.AbstractOpenemsComponent;
import io.openems.edge.common.component.OpenemsComponent;

/** Isolated telemetry channels: no managed ESS interface or writable channels. */
public final class GrowattReadOnly extends AbstractOpenemsComponent implements EventHandler {
    public enum ChannelId implements io.openems.edge.common.channel.ChannelId {
        PRODUCTION_ACTIVE_POWER(Doc.of(OpenemsType.INTEGER).unit(Unit.WATT)),
        CONSUMPTION_ACTIVE_POWER(Doc.of(OpenemsType.INTEGER).unit(Unit.WATT)),
        GRID_ACTIVE_POWER(Doc.of(OpenemsType.INTEGER).unit(Unit.WATT)),
        ESS_ACTIVE_POWER(Doc.of(OpenemsType.INTEGER).unit(Unit.WATT)),
        ESS_SOC(Doc.of(OpenemsType.INTEGER).unit(Unit.PERCENT)),
        LAST_SUCCESSFUL_READ(Doc.of(OpenemsType.LONG)),
        COMMUNICATION_FAILED(Doc.of(Level.FAULT).text("Growatt serial telemetry is unavailable or stale"));
        private final Doc doc;
        ChannelId(Doc doc) { this.doc = doc; }
        public Doc doc() { return this.doc; }
    }
    private Path sample;
    public GrowattReadOnly() {
        super(OpenemsComponent.ChannelId.values(), ChannelId.values());
    }
    protected void activate(ComponentContext context) {
        super.activate(context, "growatt0", "Growatt SPH6000 live read-only telemetry", true);
        sample = Path.of(context.getProperties().get("sample.path").toString());
    }
    @Override
    protected void deactivate() { super.deactivate(); }
    @Override
    public void handleEvent(Event event) {
        try {
            if (sample == null || Files.size(sample) > 8192) throw new IllegalStateException();
            var data = JsonParser.parseString(Files.readString(sample)).getAsJsonObject();
            long ts = data.get("ts").getAsLong();
            long age = System.currentTimeMillis() - ts;
            if (!data.get("available").getAsBoolean() || age < -2000 || age > 15000)
                throw new IllegalStateException();
            var values = data.getAsJsonObject("values");
            var keys = new String[]{"solar_w", "load_w", "grid_w", "battery_w", "battery_soc"};
            var channels = ChannelId.values();
            // Validate the entire sample before publishing any of its channels.
            int[] parsed = new int[keys.length];
            for (int i=0; i<keys.length; i++) {
                double value = values.get(keys[i]).getAsDouble();
                if (!Double.isFinite(value) || Math.abs(value)>30000 ||
                    (i==4 && (value<0 || value>100))) throw new IllegalStateException();
                parsed[i] = (int)Math.round(value);
            }
            for (int i=0; i<keys.length; i++) channel(channels[i]).setNextValue(parsed[i]);
            channel(ChannelId.LAST_SUCCESSFUL_READ).setNextValue(ts);
            channel(ChannelId.COMMUNICATION_FAILED).setNextValue(false);
        } catch (Exception unavailable) {
            for (var id: ChannelId.values()) {
                if (id != ChannelId.COMMUNICATION_FAILED) channel(id).setNextValue(null);
            }
            channel(ChannelId.COMMUNICATION_FAILED).setNextValue(true);
        }
    }
}
