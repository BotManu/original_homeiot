package originalhome.growatt.control;
import java.nio.ByteBuffer;
import io.openems.common.types.OpenemsType;
import io.openems.edge.bridge.modbus.api.element.AbstractMultipleWordsElement;
/** One indivisible element: FC16 always receives all three schedule words. */
final class ScheduleSlotElement extends AbstractMultipleWordsElement<ScheduleSlotElement,Long> {
    ScheduleSlotElement() { super(OpenemsType.LONG,1100,3); }
    @Override protected ScheduleSlotElement self() { return this; }
    @Override protected Long byteBufferToValue(ByteBuffer b) {
        return ((long)Short.toUnsignedInt(b.getShort())<<32)
            | ((long)Short.toUnsignedInt(b.getShort())<<16) | Short.toUnsignedInt(b.getShort());
    }
    @Override protected void valueToByteBuffer(ByteBuffer b,Long value) {
        b.putShort((short)(value>>32)); b.putShort((short)(value>>16)); b.putShort((short)(long)value);
    }
}
