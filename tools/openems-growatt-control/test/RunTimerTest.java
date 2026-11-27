package originalhome.growatt.control;
import static originalhome.growatt.control.ControlPolicy.*;
public final class RunTimerTest {
    private static void check(boolean b,String why) { if(!b) throw new AssertionError(why); }
    public static void main(String[] args) {
        String id="00000000-0000-4000-8000-000000000001";
        var request=new Request(id,Mode.GRID_CHARGE,1000,100000,325000,90,180);
        var timer=new RunTimer();timer.reset(id);
        check(!timer.expired(id,120000,1000000000L),"Submission does not start duration");
        timer.confirm(request,120000,1000000000L);
        check(timer.untilMs()==300000,"Full 180 seconds after confirmation");
        timer.confirm(request,130000,11000000000L);
        check(timer.untilMs()==300000,"Repeated readback cannot renew runtime");
        check(!timer.expired(id,299999,180999000000L),"Do not end runtime early");
        check(timer.expired(id,300000,181000000000L),"End at requested duration");
        check(timer.expired(id,110000,181000000000L),"Backward wall-clock adjustment cannot extend charging");
        var restarted=new RunTimer();
        check(!restarted.startedFor(id),"Runtime cannot survive restart and authorize replay");
        timer.reset("new");timer.confirm(request,120000,1000);
        check(timer.startedMs()==0,"Other command cannot start runtime");
        timer.reset(id);timer.confirm(new Request(id,Mode.GRID_CHARGE,1000,100000,280000,90,180),120000,1000);
        check(timer.untilMs()==280000,"Night window is a hard end even with startup delay");
        // Every 5 device seconds, refresh a valid short window. The old window
        // still covers the next refresh: no early hardware expiry while healthy.
        for(int second=0;second<60;second++) {
            var w=ScheduleWindow.heartbeat(12,30,second);
            int remaining=(((w.end()>>8)*60+(w.end()&255))-(12*60+30)+1)*60-second;
            check(remaining>=30 && remaining<=90,"Independent short fallback remains bounded");
            check(remaining>5,"Window survives healthy refresh interval");
        }
        System.out.println("Confirmed-runtime, monotonic expiry, hard deadline and rolling fallback checks passed.");
    }
}
