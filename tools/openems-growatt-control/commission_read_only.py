"""Temporary native serial read qualification. Always restore the old reader.

Run on the gateway. Refuses any armed policy or existing native bridge/driver.
Creates no write request and never changes qualification flags.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request

HOME=Path.home()
FOLDER=HOME/'.config/originalhome'
BASE=os.getenv('FELIX_URL','http://127.0.0.1:8081')
HEADERS={'Authorization':'Basic '+base64.b64encode((os.getenv('FELIX_USER','admin')+':'+os.getenv('FELIX_PASSWORD','admin')).encode()).decode()}
PORT='/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CYBCb2A5414-if00-port0'


def get(path):
    with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=HEADERS),timeout=15) as r:return json.load(r)


def query_id(value):
    return get('/system/console/configMgr/'+urllib.parse.quote('(id='+value+')',safe='')+'.json')


def apply(pid,values,factory=None):
    data={**values,'apply':'true','propertylist':','.join(values)}
    if factory:data['factoryPid']=factory
    request=urllib.request.Request(BASE+'/system/console/configMgr/'+pid,
        data=urllib.parse.urlencode(data).encode(),headers=HEADERS)
    with urllib.request.urlopen(request,timeout=20) as response:response.read()


def delete_config(pid):
    request=urllib.request.Request(BASE+'/system/console/configMgr/'+pid,
        data=urllib.parse.urlencode({'apply':'true','delete':'true'}).encode(),headers=HEADERS)
    with urllib.request.urlopen(request,timeout=20) as response:response.read()


policy=json.loads((FOLDER/'growatt-control.json').read_text())
if policy.get('writes_enabled') is not False:raise SystemExit('Read test requires writes_enabled=false')
if not Path(PORT).exists():raise SystemExit('Commissioned adapter path is absent; do not guess a replacement')
if query_id('modbusGrowattNative0') or get('/system/console/configMgr/OriginalHome.Growatt.ControlDriver.json'):
    raise SystemExit('Native bridge/driver already configured; refusing to overwrite it')
if subprocess.run(['systemctl','--user','is-active','--quiet','originalhome-growatt-serial']).returncode:
    raise SystemExit('Existing collector is not active; refusing to change ownership')
controllers=[component for component in get('/system/console/components.json').get('data',[])
             if component.get('name')=='OriginalHome.Growatt.Strategy']
if len(controllers)!=1 or controllers[0].get('stateRaw')!=8:
    raise SystemExit('Exactly one active native shadow controller is required')

result={'read_only':True,'writes_enabled':False,'restored_original_collector':False}
created_bridge=False
created_driver=False
try:
    subprocess.run(['systemctl','--user','stop','originalhome-growatt-serial'],check=True)
    created_bridge=True
    apply('Bridge.Modbus.Serial.originalhome-read-qualification',{
        'id':'modbusGrowattNative0','alias':'Temporary OriginalHome read qualification','enabled':'true',
        'portName':PORT,'baudRate':'9600','databits':'8','stopbits':'ONE','parity':'NONE',
        'logVerbosity':'NONE','invalidateElementsAfterReadErrors':'1'},'Bridge.Modbus.Serial')
    created_driver=True
    apply('OriginalHome.Growatt.ControlDriver',{'id':'growattControl0','enabled':'true'})
    print('Native read-only handoff started; physical write gate remains closed.',flush=True)
    received=[]
    for _ in range(30):
        current=json.loads((FOLDER/'growatt-control.json').read_text())
        if current.get('writes_enabled') is not False:raise RuntimeError('Policy changed during the read-only test')
        sample=json.loads((HOME/'OriginalHomeIOT/data/growatt-live/sample.json').read_text())
        status=json.loads((FOLDER/'growatt-control-status.json').read_text())
        now=int(time.time()*1000)
        if status.get('native_transport_bound') and sample.get('available') and 0<=now-sample['ts']<15000:
            if not received or received[-1]['ts']!=sample['ts']:received.append(sample)
            if len(received)>=3:break
        time.sleep(2)
    if len(received)<3:raise RuntimeError('Native read path did not produce three advancing valid samples')
    result.update(native_serial_read_verified=True,samples=len(received),latest=received[-1],
                  native_status=status.get('status'),native_writes_enabled=status.get('writes_enabled'))
finally:
    bridge_removed=not created_bridge
    try:
        if created_driver:delete_config('OriginalHome.Growatt.ControlDriver')
    finally:
        try:
            # Identify only the temporary configuration by its unique component ID.
            if created_bridge:
                for row in query_id('modbusGrowattNative0'):delete_config(row['pid'])
                bridge_removed=not query_id('modbusGrowattNative0')
        finally:
            time.sleep(2)
            if bridge_removed:
                subprocess.run(['systemctl','--user','start','originalhome-growatt-serial'],check=True)
                result['restored_original_collector']=True
            else:
                result['cleanup_error']='Native bridge removal was not confirmed; old collector left stopped to prevent two serial masters'
            out=HOME/'OriginalHomeIOT/data/commissioning/native-control-read-test-2026-11-17.json'
            out.write_text(json.dumps(result,indent=2)+'\n')
            if not bridge_removed:raise RuntimeError(result['cleanup_error'])
print(json.dumps(result,indent=2))
