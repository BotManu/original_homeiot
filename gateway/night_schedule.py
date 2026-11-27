"""Local night-window planner. Submits leases; never accesses the inverter bus."""
import json,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .energy_control import FOLDER,build_request,atomic_private_write,status,submit,REQUEST_LOCK
DEFAULT={'enabled':False,'timezone':'Europe/Bucharest','start':'02:00','end':'05:00','charge_w':1000,'target_soc':90}
def config(folder=FOLDER):
    path=Path(folder)/'growatt-night-schedule.json'
    if not path.exists():return dict(DEFAULT)
    if path.stat().st_size>4096:raise ValueError('Oversized night schedule')
    value=json.loads(path.read_text())
    if not isinstance(value,dict) or set(value)!=set(DEFAULT):raise ValueError('Invalid schedule fields')
    if type(value['enabled']) is not bool or value['timezone']!='Europe/Bucharest':raise ValueError('Invalid schedule timezone/enabled')
    for name in ('start','end'):
        stamp=value[name]
        if not isinstance(stamp,str) or len(stamp)!=5 or stamp[2]!=':':raise ValueError('Use HH:MM')
        hour,minute=map(int,stamp.split(':'))
        if not 0<=hour<24 or not 0<=minute<60:raise ValueError('Invalid schedule time')
    if value['start']>=value['end']:raise ValueError('Night window must end after start')
    build_request('GRID_CHARGE',value['charge_w'],180,target_soc=value['target_soc'])
    return value
def tick(folder=FOLDER,now=None):
    with REQUEST_LOCK:return _tick(folder,now)
def _tick(folder,now):
    folder=Path(folder);plan=config(folder)
    now=datetime.now(ZoneInfo(plan['timezone'])) if now is None else now.astimezone(ZoneInfo(plan['timezone']))
    stamp=now.strftime('%H:%M');inside=plan['enabled'] and plan['start']<=stamp<plan['end']
    path=folder/'growatt-command.json';command={}
    if path.exists():
        if path.stat().st_size>16384:raise ValueError('Oversized request')
        command=json.loads(path.read_text())
    now_ms=int(now.timestamp()*1000)
    owned=command.get('source')=='night_schedule'
    current=status(folder,now_ms=now_ms)
    soc=current.get('battery_soc')
    target_reached=type(soc) is int and soc>=plan['target_soc']
    if not inside or target_reached:
        if owned and command.get('mode')!='MONITOR':
            cancel=build_request('MONITOR',0,180,now_ms=now_ms)
            cancel['source']='night_schedule';atomic_private_write(path,cancel)
        return 'target_reached' if target_reached and inside else 'outside_window' if plan['enabled'] else 'disabled'
    if not owned and command.get('expires_ms',0)>now_ms:return 'manual_override'
    if owned and command.get('mode')=='GRID_CHARGE' and command.get('expires_ms',0)>now_ms+90000:return 'lease_active'
    end_hour,end_minute=map(int,plan['end'].split(':'))
    ends=now.replace(hour=end_hour,minute=end_minute,second=0,microsecond=0)
    duration=min(180,int(ends.timestamp()-now.timestamp()))
    if duration<120:return 'window_ending'
    # submit() enforces native qualification; the planner cannot arm hardware.
    try:
        submitted=submit('GRID_CHARGE',plan['charge_w'],duration,folder=folder,target_soc=plan['target_soc'],source='night_schedule',not_after_ms=int(ends.timestamp()*1000))
    except PermissionError:return 'waiting_for_controller_qualification'
    return 'submitted'
def run(stop,folder=FOLDER):
    while not stop.is_set():
        try:state=tick(folder)
        except (ValueError,OSError,KeyError,TypeError):state='schedule_unavailable'
        try:atomic_private_write(Path(folder)/'growatt-night-status.json',{'updated_ms':int(time.time()*1000),'state':state})
        except OSError:pass
        stop.wait(15)
