"""Local requests for the native OpenEMS Growatt strategy controller.

This module has no Modbus write path. OpenEMS evaluates each short-lived
request against its independent qualification gates and readback state.
"""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
from threading import RLock
REQUEST_LOCK=RLock()

FOLDER=Path.home()/'.config/originalhome'
MODES=('MONITOR','SELF_CONSUMPTION','SOLAR_CHARGE','GRID_CHARGE')
ACTIVATION_ALLOWANCE_MS=45000


def build_request(mode, charge_w=0, duration_s=180, now_ms=None, target_soc=90):
    if mode not in MODES:
        raise ValueError('Unsupported strategy; forced discharge and export are not enabled')
    if type(charge_w) is not int or not 0 <= charge_w <= 2990:
        raise ValueError('Charge power must be an integer from 0 to 2990 W')
    if type(duration_s) is not int or not 1 <= duration_s <= 180:
        raise ValueError('Strategy runtime must be 1..180 seconds')
    if mode=='MONITOR' and charge_w:
        raise ValueError('Monitor mode does not request charging power')
    if type(target_soc) is not int or not 1 <= target_soc <= 100:
        raise ValueError('Charge target must be an integer from 1 to 100 percent')
    if mode=='GRID_CHARGE' and charge_w==0:
        raise ValueError('Grid charging requires positive charging power')
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    run_seconds=duration_s if mode!='MONITOR' else 0
    return {'schema_version':1,'command_id':str(uuid.uuid4()),'mode':mode,
            'charge_w':charge_w,'target_soc':target_soc,'duration_s':run_seconds,
            'issued_ms':now_ms,'expires_ms':now_ms+duration_s*1000+(ACTIVATION_ALLOWANCE_MS if run_seconds else 0)}


def atomic_private_write(path, body):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as output:
        os.fchmod(output.fileno(),0o600) if hasattr(os,'fchmod') else None
        json.dump(body,output,allow_nan=False);output.write('\n')
    temporary.replace(path)


def status(folder=FOLDER, now_ms=None):
    path=Path(folder)/'growatt-control-status.json'
    if not path.exists():
        return {'status':'not_installed','writes_enabled':False,'max_charge_w':2990,'min_discharge_soc':15,
                'reason':'Native OpenEMS strategy controller has not reported status'}
    if path.stat().st_size>16384:
        raise ValueError('Invalid controller status document')
    data=json.loads(path.read_text(encoding='utf-8'))
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    stamp=data.get('updated_ms')
    data['stale']=type(stamp) is not int or not -2000<=now_ms-stamp<=15000
    if data['stale']:
        data.update(status='unavailable',reason='Native strategy controller status is stale')
    return data


REQUIRED_GATES=('firmware_register_map_verified','identity_verified',
    'charge_percentage_reference_verified','single_serial_owner_verified',
    'inverter_discharge_reserve_verified','crash_and_communication_fallback_verified')


def controls_ready(current, now_ms=None):
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    observed=current.get('observed_ms')
    gates=current.get('qualification',{})
    return bool(not current.get('stale') and current.get('writes_enabled')
        and current.get('native_transport_bound') and type(observed) is int
        and -2000<=now_ms-observed<=15000
        and all(gates.get(key) is True for key in REQUIRED_GATES
            if key!='inverter_discharge_reserve_verified' or current.get('min_discharge_soc',15)>0))


def submit(mode, charge_w=0, duration_s=180, folder=FOLDER, target_soc=90, source='manual', not_after_ms=None):
    with REQUEST_LOCK:
        return _submit(mode,charge_w,duration_s,folder,target_soc,source,not_after_ms)

def _submit(mode,charge_w,duration_s,folder,target_soc,source,not_after_ms):
    request=build_request(mode,charge_w,duration_s,target_soc=target_soc)
    if not_after_ms is not None:
        if type(not_after_ms) is not int or not_after_ms<=request['issued_ms']:
            raise ValueError('Request deadline must be in the future')
        request['expires_ms']=min(request['expires_ms'],not_after_ms)
    current=status(folder)
    if mode!='MONITOR':
        ceiling=current.get('max_charge_w',2990)
        if type(ceiling) is not int or charge_w>ceiling:
            raise ValueError('Charge request exceeds the active operating limit')
        gates=current.get('qualification',{})
        if mode=='GRID_CHARGE' and gates.get('grid_charging_verified') is not True:
            raise PermissionError('Grid charging has not passed physical commissioning')
        if not controls_ready(current):
            raise PermissionError('Live writes blocked: inverter protection and control qualification incomplete')
    if source not in ('manual','night_schedule'):raise ValueError('Invalid command source')
    request['source']=source
    atomic_private_write(Path(folder)/'growatt-command.json',request)
    return {'command_id':request['command_id'],'status':'submitted_for_native_evaluation',
            'applied':False,'expires_ms':request['expires_ms']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=MODES)
    parser.add_argument('--charge-w',type=int,default=0)
    parser.add_argument('--target-soc',type=int,default=90)
    parser.add_argument('--duration',type=int,default=180)
    args=parser.parse_args()
    if args.mode:
        try:
            request=build_request(args.mode,args.charge_w,args.duration)
        except ValueError as error:
            parser.error(str(error))
        try:
            print(json.dumps(submit(args.mode,args.charge_w,args.duration,target_soc=args.target_soc)))
        except PermissionError as error:
            raise SystemExit(str(error))

    else:
        print(json.dumps(status(),indent=2))


if __name__=='__main__':
    main()
