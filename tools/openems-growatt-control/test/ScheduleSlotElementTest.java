package originalhome.growatt.control;
/** Verify an FC16 task consumes a full schedule triple in a single element. */
public final class ScheduleSlotElementTest {
    public static void main(String[] args) {
        var element=new ScheduleSlotElement();
        element.setNextWriteValue(ScheduleWindow.words(0,5947,1));
        var registers=element.getNextWriteValueAndReset();
        if(registers.length!=3 || registers[0].toUnsignedShort()!=0
                || registers[1].toUnsignedShort()!=5947 || registers[2].toUnsignedShort()!=1)
            throw new AssertionError("Schedule must encode exactly three contiguous registers");
        if(element.getNextWriteValueAndReset()!=null) throw new AssertionError("Do not replay consumed writes");
        element.setNextWriteValue(ScheduleWindow.words(0,0,0));
        element.setNextWriteValue(null);
        if(element.getNextWriteValueAndReset()!=null) throw new AssertionError("Cancellation clears full triple");
        System.out.println("Atomic FC16 schedule payload checks passed.");
    }
}
