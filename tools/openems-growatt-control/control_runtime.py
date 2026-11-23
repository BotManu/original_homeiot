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
