package originalhome.growatt.control;
/** Inverter-clock schedule window. Treat end minute as inclusive; round down to respect the lease. */
public record ScheduleWindow(int start, int end) {
    /** Renew while healthy; a stopped controller leaves only 30–90 device seconds. */
    public static ScheduleWindow heartbeat(int hour,int minute,int second) {
        return of(hour,minute,second,180);
    }
    public static long words(int start,int end,int enable) {
        if(start<0 || end<0 || start>0xffff || end>0xffff || (enable!=0 && enable!=1)
                || (start>>8)>23 || (end>>8)>23 || (start&255)>59 || (end&255)>59
                || (enable==1 && start>=end)) throw new IllegalArgumentException("Invalid slot triple");
        return ((long)start<<32)|((long)end<<16)|enable;
    }
    public static ScheduleWindow of(int hour,int minute,int second,long remainingSeconds) {
        if(hour<0 || hour>23 || minute<0 || minute>59 || second<0 || second>59
                || remainingSeconds<1 || remainingSeconds>180) throw new IllegalArgumentException("Invalid schedule clock/lease");
        // The commissioned inverter clock advanced only ~0.8 device seconds
        // per wall second. Use half the lease for device time, and a start
        // in the prior minute so a whole-minute end fits without rounding up.
        int count=(int)((second+remainingSeconds/2)/60)-1, current=hour*60+minute;
        if(count<0 || current==0 || current+count+1>=1440) throw new IllegalArgumentException("No complete minute before lease/midnight");
        int end=current+count;
        int start=current-1;
        return new ScheduleWindow(((start/60)<<8)|(start%60),((end/60)<<8)|(end%60));
    }
}
