"""Hot-update only the read-only bundle and preserve the embedded boot copy.

Run on the gateway after build.py. Uses its loopback Felix console.
"""
import base64
import io
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.request
import uuid
import zipfile

runtime = Path(sys.argv[1]).expanduser().resolve()
bundle = Path(__file__).resolve().parents[2] / 'data/openems-build/originalhome-growatt-readonly.jar'
symbol = 'org.originalhome.growatt.readonly'
member = 'jar/org.originalhome.growatt.readonly.jar'
backup = runtime.with_name('openems-edge.pre-cloud-poc.jar')
headers = {'Authorization': 'Basic ' + base64.b64encode(
    (os.getenv('FELIX_USER', 'admin') + ':' + os.getenv('FELIX_PASSWORD', 'admin')).encode()).decode()}
base = os.getenv('FELIX_URL', 'http://127.0.0.1:8081')


def upload(data):
    boundary = uuid.uuid4().hex
    body = b''
    for key, value in [('action', 'install'), ('bundlestart', 'start'), ('refreshPackages', 'refresh')]:
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="bundlefile"; '
             'filename="originalhome-growatt-readonly.jar"\r\nContent-Type: application/java-archive\r\n\r\n').encode()
    body += data + f'\r\n--{boundary}--\r\n'.encode()
    request = urllib.request.Request(base + '/system/console/bundles', data=body,
        headers={**headers, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


with zipfile.ZipFile(runtime) as original:
    old_bundle = original.read(member)
if not backup.exists():
    shutil.copy2(runtime, backup)
upload(bundle.read_bytes())
try:
    for attempt in range(15):
        request = urllib.request.Request(base + '/system/console/bundles.json', headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            rows = json.load(response)['data']
        matches = [row for row in rows if row.get('symbolicName') == symbol]
        if len(matches) == 1 and matches[0]['version'] == '0.1.1' and matches[0]['stateRaw'] == 32:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Updated telemetry bundle did not become active')
    temporary = runtime.with_suffix('.cloud-poc-new')
    with zipfile.ZipFile(runtime) as original, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as updated:
        for entry in original.infolist():
            updated.writestr(entry, bundle.read_bytes() if entry.filename == member else original.read(entry))
    temporary.replace(runtime)
except Exception:
    upload(old_bundle)
    raise
print('Read-only telemetry bundle 0.1.1 active; boot JAR updated; pre-cloud-poc backup preserved.')
