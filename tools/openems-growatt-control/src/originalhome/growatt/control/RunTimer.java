package originalhome.growatt.control;

/** Runtime starts at confirmed inverter application, never at submission or after restart. */
public final class RunTimer {
    private String id="";
    private long startedMs, untilMs, untilNanos;
    public void reset(String id) { this.id=id; startedMs=untilMs=untilNanos=0; }
    public boolean startedFor(String id) { return this.id.equals(id) && startedMs>0; }
    public boolean expired(String id,long nowMs,long nowNanos) {
        return startedFor(id) && (nowMs>=untilMs || nowNanos>=untilNanos);
    }
    public void confirm(ControlPolicy.Request request,long nowMs,long nowNanos) {
        if(!id.equals(request.id()) || startedMs>0 || request.durationSeconds()<=0) return;
        startedMs=nowMs;
        untilMs=Math.min(request.expiresMs(),nowMs+request.durationSeconds()*1000L);
        untilNanos=nowNanos+Math.max(0,untilMs-nowMs)*1000000L;
    }
    public long startedMs() { return startedMs; }
    public long untilMs() { return untilMs; }
}
