import originalhome.growatt.control.ControlPolicy;
import originalhome.growatt.control.ScheduleWindow;
import static originalhome.growatt.control.ControlPolicy.*;

/** Hardware-independent acceptance checks; run with assertions enabled. */
public final class ControlPolicyTest {
    private static final long NOW = 1794906000000L;
    private static final String ID = "00000000-0000-4000-8000-000000000001";
    private static Limits limits() { return new Limits(2990, 3000, 90, 15, true, true, true, true, true, true); }
    private static Snapshot sample() { return new Snapshot(NOW-1000, 61, -1000, 0, 100, 0, true, 15, 15); }
    private static Request request(int watts) { return new Request(ID, Mode.SOLAR_CHARGE, watts, NOW-1000, NOW+30000); }
    private static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    public static void main(String[] args) {
        for(int second=0;second<60;second++) for(int lease=1;lease<=180;lease++) {
            int minutes=(second+lease/2)/60-1;
            try {
                var window=ScheduleWindow.of(12,30,second,lease);
                check(minutes>=0 && window.start()==((12<<8)|29),"Packed start uses inverter clock");
                int duration=(((window.end()>>8)*60+(window.end()&255))-(12*60+30)+1)*60-second;
                check(duration>0 && duration<=lease/2,"Hardware expiry never extends command lease");
            } catch(IllegalArgumentException invalid) { check(minutes<0,"Only impossible short slots rejected"); }
        }
        try { ScheduleWindow.of(23,59,30,90); throw new AssertionError("Reject midnight rollover"); }
        catch(IllegalArgumentException expected) {}
        check(ScheduleWindow.words(0,5947,0)==((long)5947<<16),"FC16 triple encodes all words");
        check(ScheduleWindow.words(0,0,0)==0,"Original empty slot restoration");
        try { ScheduleWindow.words(5947,0,1); throw new AssertionError("Reject inverted active slot"); }
        catch(IllegalArgumentException expected) {}
        var normal = ControlPolicy.decide(limits(),request(2990),sample(),NOW,false);
        check(normal.writable() && normal.chargePercent()==99 && normal.effectiveChargeW()==2970,"Round down below owner ceiling");
        check(normal.priority()==1,"PV-first charging strategy");
        check(!ControlPolicy.decide(limits(),request(2991),sample(),NOW,false).writable(),"Reject oversized request");
        for (int reference : new int[]{1000, 3000, 4000, 6000, 9999}) {
            for (int watts=0;watts<=2990;watts+=17) {
                var result=ControlPolicy.decide(new Limits(2990,reference,90,15,true,true,true,true,true,true),request(watts),sample(),NOW,false);
                check(result.effectiveChargeW()<=watts && result.chargePercent()<=100,"Never round power upward");
            }
        }
        check(!ControlPolicy.decide(new Limits(2990,0,90,15,true,true,false,true,true,true),request(1000),sample(),NOW,false).writable(),"Unverified percent conversion cannot write");
        check(!ControlPolicy.decide(new Limits(2990,3000,90,15,true,true,true,true,true,false),request(1000),sample(),NOW,false).writable(),"Shadow mode cannot write");
        check(!ControlPolicy.decide(new Limits(2990,3000,90,15,true,true,true,false,true,true),request(1000),sample(),NOW,false).writable(),"Two serial owners forbidden");
        check(!ControlPolicy.decide(limits(),request(1000),new Snapshot(NOW-16000,61,-1000,0,100,0,true,15,15),NOW,false).writable(),"Reject stale equipment");
        check(!ControlPolicy.decide(limits(),request(1000),new Snapshot(NOW,61,-1000,0,100,1,true,15,15),NOW,false).writable(),"No grid-charge enablement");
        check(!ControlPolicy.decide(limits(),request(1000),new Snapshot(NOW,61,-1000,2,100,0,true,15,15),NOW,false).writable(),"No export strategy");
        check(!ControlPolicy.decide(limits(),request(1000),new Snapshot(NOW,61,-1000,0,100,0,false,15,15),NOW,false).writable(),"Reject wrong device");
        check(ControlPolicy.decide(limits(),request(1000),new Snapshot(NOW,90,-1000,0,100,0,true,15,15),NOW,false).fallback(),"Stop at SoC ceiling");
        check(ControlPolicy.decide(limits(),request(1000),new Snapshot(NOW,61,-2991,0,100,0,true,15,15),NOW,false).chargePercent()==0,"Stop on measured excess");
        for (Integer reserve : new Integer[]{null, 10, 14, 101}) {
            var unprotected=new Snapshot(NOW,61,-1000,0,100,0,true,reserve,15);
            check(!ControlPolicy.decide(limits(),request(1000),unprotected,NOW,false).writable(),"Reject invalid reserve");
            check(!ControlPolicy.decide(limits(),null,unprotected,NOW,true).writable(),"Fallback cannot bypass reserve");
        }
        check(!ControlPolicy.decide(limits(),request(1000),new Snapshot(NOW,15,100,0,100,0,true,15,15),NOW,false).writable(),"Detect discharge at reserve");
        var waived=new Limits(2990,3000,90,0,true,true,true,true,false,true);
        check(ControlPolicy.decide(waived,request(1000),new Snapshot(NOW,61,-1000,0,100,0,true,null,null),NOW,false).writable(),"Owner can withdraw optional reserve");
        check(!ControlPolicy.decide(new Limits(2990,0,90,0,true,true,false,true,false,true),request(1000),sample(),NOW,false).writable(),"Reserve waiver cannot bypass power qualification");
        var expired=new Request(ID,Mode.SOLAR_CHARGE,1000,NOW-2000,NOW-1);
        check(!ControlPolicy.decide(limits(),expired,sample(),NOW,false).writable(),"Do not replay expired commands on startup");
        check(ControlPolicy.decide(limits(),expired,sample(),NOW,true).fallback(),"Applied lease expires into fallback");
        check(ControlPolicy.decide(limits(),null,sample(),NOW,true).fallback(),"Cancellation fallback");
        check(!ControlPolicy.decide(limits(),new Request(ID,Mode.SOLAR_CHARGE,1000,NOW,NOW+180001),sample(),NOW,false).writable(),"Bound lease duration");
        System.out.println("Control policy acceptance checks passed (including 880 power-bound and 10800 schedule-expiry cases).");
    }
}
