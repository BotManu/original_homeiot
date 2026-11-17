"""Install only a non-writing native controller; refuse an armed configuration.

Run on the gateway after build.py. No serial bridge/configuration is created.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import time
import urllib.parse
import urllib.request
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[2]
runtime=Path.home()/'original/openems-edge.jar'
bundle=ROOT/'data/growatt-control-build/originalhome-growatt-control.jar'
symbol='org.originalhome.growatt.control'
member='jar/'+symbol+'.jar'
folder=Path.home()/'.config/originalhome'
profile=folder/'growatt-control.json'
headers={'Authorization':'Basic '+base64.b64encode((os.getenv('FELIX_USER','admin')+':'+os.getenv('FELIX_PASSWORD','admin')).encode()).decode()}
base=os.getenv('FELIX_URL','http://127.0.0.1:8081')


def fetch(path):
    with urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=15) as r:
        return json.load(r)


if profile.exists():
    config=json.loads(profile.read_text())
    if config.get('writes_enabled') is not False:
        raise SystemExit('Shadow install refused: existing configuration is not explicitly disarmed')
else:
    folder.mkdir(parents=True,exist_ok=True)
    with profile.open('x') as output:
        os.chmod(profile,0o600)
        output.write((ROOT/'config/devices/growatt-control.json').read_text())
if fetch('/system/console/configMgr/OriginalHome.Growatt.ControlDriver.json'):
    raise SystemExit('Shadow install refused: native serial driver has configuration')
query=urllib.parse.quote('(id=modbusGrowattNative0)',safe='')
if fetch('/system/console/configMgr/'+query+'.json'):
    raise SystemExit('Shadow install refused: native serial bridge already exists')

backup=runtime.with_name('openems-edge.pre-strategy-shadow.jar')
if not backup.exists():shutil.copy2(runtime,backup)
boundary=uuid.uuid4().hex
body=b''
for name,value in [('action','install'),('bundlestart','start'),('refreshPackages','refresh')]:
    body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="bundlefile"; filename="originalhome-growatt-control.jar"\r\nContent-Type: application/java-archive\r\n\r\n').encode()
body+=bundle.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
request=urllib.request.Request(base+'/system/console/bundles',data=body,headers={**headers,'Content-Type':'multipart/form-data; boundary='+boundary})
with urllib.request.urlopen(request,timeout=30) as response:response.read()
for attempt in range(20):
    rows=fetch('/system/console/bundles.json')['data']
    matches=[r for r in rows if r.get('symbolicName')==symbol]
    if len(matches)==1 and matches[0]['stateRaw']==32:break
    time.sleep(1)
else:raise RuntimeError('Shadow bundle did not become active; boot JAR not changed')

for attempt in range(15):
    status=folder/'growatt-control-status.json'
    if status.exists():
        data=json.loads(status.read_text())
        if data.get('writes_enabled') is False and data.get('status')=='shadow':break
    time.sleep(1)
else:raise RuntimeError('Native shadow controller did not report disarmed status; boot JAR not changed')

temporary=runtime.with_suffix('.strategy-new')
with zipfile.ZipFile(runtime) as original, zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as updated:
    for entry in original.infolist():
        if entry.filename==member:continue
        data=original.read(entry)
        if entry.filename=='launcher.properties':
            text=data.decode()
            if member not in text:
                if 'launch.bundles=' not in text:raise RuntimeError('Missing launch bundle list')
                text=text.replace('launch.bundles=','launch.bundles='+member+',',1)
            data=text.encode()
        updated.writestr(entry,data)
    updated.writestr(member,bundle.read_bytes())
temporary.replace(runtime)
print('Native shadow controller active; no serial bridge and no physical writes enabled.')
print('Original boot JAR preserved as '+str(backup))
