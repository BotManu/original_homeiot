"""Arm bounded controls only after rate evidence and a real OpenEMS restart test."""
import hashlib,uuid
from control_runtime import HOME,ROOT,FOLDER,PORT,get,apply,delete,bridges,atomic
import json,time,subprocess
out=ROOT/'data/commissioning/arming-verification.json'
if out.exists():
 archive=out.with_name('arming-attempt-'+time.strftime('%Y%m%d-%H%M%S')+'.json');archive.write_bytes(out.read_bytes())
state={'phase':'preflight','armed':False}
def report(**values):
 state.update(values);atomic(out,state);print(json.dumps(values),flush=True)
def read(path):return json.loads(path.read_text())
def pid():return subprocess.check_output(['systemctl','show','--value','-p','MainPID','original-edge.service'],text=True).strip()
def current():
 try:
  d=read(FOLDER/'growatt-control-status.json')
  return d if 0<=time.time()*1000-d['updated_ms']<15000 else {}
 except (OSError,ValueError,KeyError):return {}
def wait_for(predicate,seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  d=current()
  if d and predicate(d):return d
  time.sleep(2)
 raise RuntimeError('Timed out awaiting '+state['phase'])
policy_path=FOLDER/'growatt-control.json';plan_path=FOLDER/'growatt-night-schedule.json'
policy=read(policy_path);plan=read(plan_path)
assert policy['writes_enabled'] is False and not policy.get('commissioning_enabled')
assert not bridges() and not get('/system/console/configMgr/OriginalHome.Growatt.ControlDriver.json')
assert plan['timezone']=='Europe/Bucharest' and plan['start']=='02:00' and plan['end']=='05:00'
files=list((ROOT/'data/commissioning').glob('native-grid-test*.json'))
evidence=None
for p in sorted(files,key=lambda p:p.stat().st_mtime,reverse=True):
 d=read(p)
 if d.get('operating_rate_test') and d.get('bounded_physical_response_verified') and d.get('original_settings_restored'):
  evidence=(p,d);break
if evidence is None:raise SystemExit('Missing successful operating-rate evidence; controls remain disarmed')
p,d=evidence
samples=[-s['values']['battery_w'] for s in d['active_samples'] if s['values']['battery_w']<-400]
assert len(samples)>=3 and max(samples)<=1000
assert all(s['values']['solar_w']<50 for s in d['active_samples'])
report(rate_evidence=str(p),rate_evidence_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),measured_charge_range_w=[min(samples),max(samples)])
backup=ROOT/'data/commissioning/pre-arm-policy.json'
if not backup.exists():atomic(backup,policy)
plan['enabled']=False;atomic(plan_path,plan)
configured=False;scope=False
try:
 subprocess.run(['systemctl','--user','disable','--now','originalhome-growatt-serial'],check=True,capture_output=True)
 assert subprocess.run(['systemctl','--user','is-active','--quiet','originalhome-growatt-serial']).returncode!=0
 configured=True
 apply('Bridge.Modbus.Serial.originalhome-live-control',{'id':'modbusGrowattNative0','alias':'OriginalHome native sole inverter writer','enabled':'true','portName':PORT,'baudRate':'9600','databits':'8','stopbits':'ONE','parity':'NONE','logVerbosity':'NONE','invalidateElementsAfterReadErrors':'1'},'Bridge.Modbus.Serial')
 apply('OriginalHome.Growatt.ControlDriver',{'id':'growattControl0','enabled':'true'})
 report(phase='native_read_preflight')
 before=wait_for(lambda d:d.get('native_transport_bound') and d.get('register_readback',{}).get('ac')==0 and d.get('register_readback',{}).get('enable')==0 and d.get('register_readback',{}).get('priority')==0,60)
 assert before['battery_soc']<90
 policy.update(writes_enabled=True,max_charge_w=1000,charge_percent_reference_w=3000,min_discharge_soc=0,
   charge_reference_is_conservative_bound=True,owner_max_charge_w=2990,recovery_test_until_ms=int(time.time()*1000)+180000)
 gates=policy['qualification'];gates.update(identity_verified=True,firmware_register_map_verified=True,
   charge_percentage_reference_verified=True,single_serial_owner_verified=True,grid_charging_verified=True,
   crash_and_communication_fallback_verified=False)
 policy['identity_qualification_basis']='Owner identified wired inverter; stable USB path, model and exact Modbus firmware fingerprint. Placeholder reported serial retained; no serial rewritten.'
 atomic(policy_path,policy);scope=True
 now=int(time.time()*1000);command_id=str(uuid.uuid4())
 atomic(FOLDER/'growatt-command.json',{'schema_version':1,'command_id':command_id,'mode':'GRID_CHARGE','charge_w':1000,'target_soc':90,'issued_ms':now,'expires_ms':now+180000,'source':'recovery_qualification'})
 report(phase='bounded_recovery_activation')
 active=wait_for(lambda d:d.get('register_readback',{}).get('ac')==1 and d.get('register_readback',{}).get('enable')==1 and -1000<=d.get('battery_w',0)<-400,65)
 old_pid=pid();report(phase='awaiting_service_restart',old_pid=old_pid,active_status=active)
 # The owner-authorized privileged restart is issued by the SSH operator.
 deadline=time.monotonic()+120
 while time.monotonic()<deadline and pid()==old_pid:time.sleep(2)
 if pid()==old_pid:raise RuntimeError('OpenEMS restart did not occur')
 new_pid=pid();restart_observed_ms=int(time.time()*1000)
 report(phase='verifying_restart_cleanup',new_pid=new_pid)
 recovered=wait_for(lambda d:d.get('updated_ms',0)>restart_observed_ms and d.get('native_transport_bound')
   and d.get('register_readback',{}).get('ac')==0 and d.get('register_readback',{}).get('enable')==0
   and read(FOLDER/'growatt-control-ledger.json').get('fallback_required') is False,100)
 assert read(FOLDER/'growatt-control-ledger.json')['last_command_id']==command_id
 time.sleep(8)
 assert current()['register_readback']['ac']==0 and current()['register_readback']['enable']==0
 report(restart_cleanup_verified=True,stale_command_not_replayed=True,recovered_status=recovered)
 policy.pop('recovery_test_until_ms',None)
 policy['qualification']['crash_and_communication_fallback_verified']=True
 policy['arming_verification']='OriginalHomeIOT/data/commissioning/arming-verification.json'
 atomic(policy_path,policy)
 now=int(time.time()*1000)
 atomic(FOLDER/'growatt-command.json',{'schema_version':1,'command_id':str(uuid.uuid4()),'mode':'MONITOR','charge_w':0,'target_soc':90,'issued_ms':now,'expires_ms':now+1000,'source':'manual'})
 plan.update(enabled=True,charge_w=1000,target_soc=90);atomic(plan_path,plan)
 report(phase='armed',armed=True,max_charge_w=1000,owner_ceiling_w=2990,night_plan=plan)
except Exception as error:
 report(phase='failed',error=str(error))
 plan['enabled']=False;atomic(plan_path,plan)
 safe=not scope
 if scope:
  now=int(time.time()*1000)
  atomic(FOLDER/'growatt-command.json',{'schema_version':1,'command_id':str(uuid.uuid4()),'mode':'MONITOR','charge_w':0,'target_soc':90,'issued_ms':now,'expires_ms':now+180000,'source':'manual'})
  try:
   wait_for(lambda d:d.get('register_readback',{}).get('ac')==0 and d.get('register_readback',{}).get('enable')==0,60);safe=True
  except Exception:pass
 policy.update(writes_enabled=False,commissioning_enabled=False);policy.pop('recovery_test_until_ms',None);atomic(policy_path,policy)
 if safe:
  if configured:
   delete('OriginalHome.Growatt.ControlDriver')
   for row in bridges():delete(row['pid'])
  if not bridges():subprocess.run(['systemctl','--user','enable','--now','originalhome-growatt-serial'],check=True,capture_output=True)
 report(cleanup_confirmed=safe)
 raise
