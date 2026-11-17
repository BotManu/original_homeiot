"""Bounded real SPH commissioning. Only native OpenEMS writes the inverter.

Requires disarmed general control and idle schedule. Restores settings and
serial ownership in finally; retains full observations for review.
"""
import base64,json,os,subprocess,time,urllib.parse,urllib.request,sys
from pathlib import Path
HOME=Path.home(); ROOT=HOME/'OriginalHomeIOT'; FOLDER=HOME/'.config/originalhome'
PORT='/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CYBCb2A5414-if00-port0'
BASE='http://127.0.0.1:8081'
HEADERS={'Authorization':'Basic '+base64.b64encode(b'admin:admin').decode()}
def get(path):
 with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=HEADERS),timeout=15) as r:return json.load(r)
def apply(pid,values,factory=None):
 d={**values,'apply':'true','propertylist':','.join(values)}
 if factory:d['factoryPid']=factory
 with urllib.request.urlopen(urllib.request.Request(BASE+'/system/console/configMgr/'+pid,data=urllib.parse.urlencode(d).encode(),headers=HEADERS),timeout=20) as r:r.read()
def delete(pid):
 with urllib.request.urlopen(urllib.request.Request(BASE+'/system/console/configMgr/'+pid,data=urllib.parse.urlencode({'apply':'true','delete':'true'}).encode(),headers=HEADERS),timeout=20) as r:r.read()
def bridges():return get('/system/console/configMgr/'+urllib.parse.quote('(id=modbusGrowattNative0)',safe='')+'.json')
def atomic(path,data):
 temp=path.with_suffix('.new');temp.write_text(json.dumps(data)+'\n');temp.chmod(0o600);os.replace(temp,path)
def phase(name,duration=120):
 until=int(time.time()*1000)+duration*1000
 atomic(FOLDER/'growatt-commission.json',{'phase':name,'until_ms':until})
 print('Native commissioning phase: '+name,flush=True)
 return until
result={'hardware_writes_authorized':True,'general_control_enabled':False,'observations':[],'original_settings_restored':False}
policy_path=FOLDER/'growatt-control.json';policy=json.loads(policy_path.read_text())
assert policy['writes_enabled'] is False and not policy.get('commissioning_enabled')
assert not bridges() and not get('/system/console/configMgr/OriginalHome.Growatt.ControlDriver.json')
assert Path(PORT).exists()
assert subprocess.run(['systemctl','--user','is-active','--quiet','originalhome-growatt-serial']).returncode==0
created=False;baseline=None;armed=False
out=ROOT/'data/commissioning'/('native-schedule-test-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
print('Evidence: '+str(out),flush=True)
def current():
 p=FOLDER/'growatt-commission-status.json'
 if not p.exists():return None
 d=json.loads(p.read_text());now=int(time.time()*1000)
 if not 0<=now-d.get('updated_ms',0)<15000:return None
 if not result['observations'] or result['observations'][-1]['updated_ms']!=d['updated_ms']:
  result['observations'].append(d);atomic(out,result)
 return d
def wait_for(predicate,seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  d=current()
  if d and predicate(d):return d
  time.sleep(2)
 raise RuntimeError('Timed out awaiting native commissioning state')
try:
 subprocess.run(['systemctl','--user','stop','originalhome-growatt-serial'],check=True)
 created=True
 apply('Bridge.Modbus.Serial.originalhome-schedule-commission',{'id':'modbusGrowattNative0','alias':'Bounded native schedule commissioning','enabled':'true','portName':PORT,'baudRate':'9600','databits':'8','stopbits':'ONE','parity':'NONE','logVerbosity':'NONE','invalidateElementsAfterReadErrors':'1'},'Bridge.Modbus.Serial')
 apply('OriginalHome.Growatt.ControlDriver',{'id':'growattControl0','enabled':'true'})
 # Read baseline through the normal native status, before enabling commissioning.
 deadline=time.monotonic()+60
 while time.monotonic()<deadline:
  d=json.loads((FOLDER/'growatt-control-status.json').read_text())
  r=d.get('register_readback',{})
  if d.get('native_transport_bound') and r.get('charge') is not None and r.get('second') is not None:
   baseline=r;break
  time.sleep(2)
 if baseline is None:raise RuntimeError('No complete native readback')
 assert baseline['priority']==0 and baseline['ac']==0
 assert all(baseline.get(k)==0 for k in ['start','end','enable','start2','end2','enable2','start3','end3','enable3','gEnable1','gEnable2','gEnable3'])
 assert 0<=baseline['charge']<=100
 result['baseline']=baseline;atomic(out,result)
 if '--require-solar' in sys.argv:
  sample=json.loads((ROOT/'data/growatt-live/sample.json').read_text())
  values=sample.get('values',{})
  if (not sample.get('available') or time.time()*1000-sample.get('ts',0)>15000
      or values.get('solar_w',0)-values.get('load_w',0)<1500 or values.get('battery_soc',100)>=95):
   raise RuntimeError('Daylight preflight requires fresh PV surplus >=1500 W and SoC <95%; no write was enabled')
 # No write request exists before saving the durable baseline.
 policy['commissioning_enabled']=True;atomic(policy_path,policy);armed=True
 phase('CAP')
 cap=wait_for(lambda d:d['status']=='cap_readback_confirmed' and d['readback'].get('charge')==10,60)
 result['cap_write_readback_verified']=True;print('1090 charge cap read back at 10%',flush=True)
 phase('SLOT',180)
 active=wait_for(lambda d:d['status']=='strategy_readback_confirmed' and d['readback'].get('priority')==1,65)
 result['timed_strategy_readback_verified']=True
 print('Battery-first priority read back active',flush=True)
 measured=[];end=time.monotonic()+180
 while time.monotonic()<end:
  d=current()
  if d:
   r=d['readback'];t=d.get('telemetry',{});v=t.get('values',{})
   if t.get('available') and r.get('priority')==1:
    if not measured or measured[-1]['ts']!=t['ts']:measured.append(t)
    if v.get('battery_w',0)<-2990:raise RuntimeError('Measured charging exceeds owner ceiling')
   end_min=(r.get('end',0)>>8)*60+(r.get('end',0)&255)
   now_min=r.get('hour',0)*60+r.get('minute',0)
   if r.get('enable')==1 and now_min>end_min and r.get('priority')==0:
    result['inverter_timed_expiry_verified']=True;print('Inverter returned to load-first at scheduled end',flush=True);break
  time.sleep(3)
 else:raise RuntimeError('Hardware schedule expiry was not observed')
 result['active_samples']=measured
 # Require sustained charging response with enough PV to avoid attributing
 # a passing cloud or unavailable battery to the charge-power command.
 useful=[s for s in measured if s['values']['solar_w']-s['values']['load_w']>1500 and -750<=s['values']['battery_w']<=-100]
 result['bounded_physical_response_verified']=len(useful)>=3
 result['outcome']='completed' if result['bounded_physical_response_verified'] else 'readback_verified_physical_response_inconclusive'
except Exception as error:
 result['outcome']='failed';result['error']=str(error)
 raise
finally:
 try:
  if armed:
   phase('RESTORE',90)
   restored=wait_for(lambda d:d['status']=='restoration_readback_confirmed' and d['readback'].get('charge')==baseline['charge'] and all(d['readback'].get(k)==0 for k in ['start','end','enable','priority']),80)
   result['original_settings_restored']=True
   print('Original charge cap and disabled schedule restored by readback',flush=True)
 except Exception as error:
  result['restoration_error']=str(error)
  # The previously programmed inverter end time remains a bounded fallback.
  print('Restoration needs attention: '+str(error),flush=True)
 finally:
  policy['commissioning_enabled']=False;atomic(policy_path,policy)
  (FOLDER/'growatt-commission.json').unlink(missing_ok=True)
  removed=not created
  try:
   if created:
    delete('OriginalHome.Growatt.ControlDriver')
    for row in bridges():delete(row['pid'])
    removed=not bridges()
  finally:
   time.sleep(2)
   if removed:
    subprocess.run(['systemctl','--user','start','originalhome-growatt-serial'],check=True)
    result['collector_restored']=True
   else:result['collector_restored']=False
   atomic(out,result)
print(json.dumps({k:v for k,v in result.items() if k not in ('observations','active_samples')},indent=2),flush=True)
if not result['original_settings_restored']:raise SystemExit('Restoration not confirmed')
