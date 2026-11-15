"""Patch the pinned upstream File metadata provider's missing ingress cache map.

Keeps the vendor image intact; produces a derived JAR with one added override.
Requires JDK 21, Python 3 and the exact pinned vendor Backend distribution.
"""
import hashlib
import io
from pathlib import Path
import subprocess
import re
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE / 'runtime/metadata-build'
LIB = WORK / 'lib'
LIB.mkdir(parents=True, exist_ok=True)
SOURCE_REF = '3eb006a1534d6bec562008e8f35083303baa98c2'
source_jar = WORK / 'vendor-backend.jar'
vendor_image = 'openems/backend@sha256:7dc614a93693f82e3836681a3d426475fd278c15b2addb6560ef7243dc96ec71'
container = subprocess.check_output(['docker', 'create', vendor_image], text=True).strip()
try:
    subprocess.run(['docker', 'cp', container + ':/opt/openems/openems-backend.jar',
                    str(source_jar)], check=True)
finally:
    subprocess.run(['docker', 'rm', container], check=True, capture_output=True)
with zipfile.ZipFile(source_jar) as vendor:
    for name in vendor.namelist():
        if name.startswith('jar/') and name.endswith('.jar'):
            (LIB / Path(name).name).write_bytes(vendor.read(name))

source = WORK / 'source/io/openems/backend/metadata/file'
source.mkdir(parents=True, exist_ok=True)
hashes = {}
for name in ['Config.java', 'MyEdge.java', 'MetadataFile.java']:
    url = f'https://raw.githubusercontent.com/OpenEMS/openems/{SOURCE_REF}/io.openems.backend.metadata.file/src/io/openems/backend/metadata/file/{name}'
    data = urllib.request.urlopen(url, timeout=30).read()
    hashes[name] = hashlib.sha256(data).hexdigest()
    if name == 'MetadataFile.java':
        if hashes[name] != 'c402b1ce2e9f3aa7f43aab439c56e134154f86d22df6b9ee58a3963e64f6594c':
            raise RuntimeError('Pinned source integrity check failed')
        text = data.decode()
        if 'generateUpdateMetadataCacheNotification' in text:
            raise RuntimeError('Upstream already supplies the override; review patch')
        text = text.rstrip()[:-1] + '''
    /** OriginalHome PoC compatibility: publish API-key -> Edge-ID to ingress. */
    @Override
    public synchronized io.openems.backend.common.edge.jsonrpc.UpdateMetadataCache.Notification
            generateUpdateMetadataCacheNotification() {
        var mapping = this.edges.values().stream().collect(java.util.stream.Collectors.toMap(
            edge -> edge.getApikey(), edge -> edge.getId()));
        return new io.openems.backend.common.edge.jsonrpc.UpdateMetadataCache.Notification(mapping);
    }
}
'''
        # Retain the vendor-generated OSGi descriptors. These build-time-only
        # annotations are not included in the runtime distribution classpath.
        text = text.replace('import org.osgi.service.event.propertytypes.EventTopics;', '')
        text = text.replace('import org.osgi.service.metatype.annotations.Designate;', '')
        text = re.sub(r'@Designate\([^\n]*\)', '', text)
        text = re.sub(r'@EventTopics\(\{.*?\}\)', '', text, flags=re.S)
        data = text.encode()
    (source / name).write_bytes(data)
classes = WORK / 'classes'
classes.mkdir(exist_ok=True)
subprocess.run(['javac', '--release', '21', '-cp', str(LIB / '*'), '-d', str(classes),
                '-sourcepath', str(WORK / 'no-source'), str(source / 'MetadataFile.java')], check=True)
bundle_path = 'jar/io.openems.backend.metadata.file.jar'
with zipfile.ZipFile(source_jar) as vendor:
    bundle_bytes = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(vendor.read(bundle_path))) as original, \
            zipfile.ZipFile(bundle_bytes, 'w', zipfile.ZIP_DEFLATED) as patched:
        for entry in original.infolist():
            replacement = classes / entry.filename
            content = replacement.read_bytes() if replacement.is_file() else original.read(entry)
            if entry.filename == 'META-INF/MANIFEST.MF':
                manifest = re.sub(r'\r?\n ', '', content.decode())
                manifest = manifest.replace('Import-Package: ',
                    'Import-Package: io.openems.backend.common.edge.jsonrpc,', 1)
                wrapped = []
                for line in manifest.splitlines():
                    while len(line.encode()) > 70:
                        wrapped.append(line[:70])
                        line = ' ' + line[70:]
                    wrapped.append(line)
                content = ('\r\n'.join(wrapped) + '\r\n\r\n').encode()
            patched.writestr(entry, content)
    output = HERE / 'runtime/openems-backend-file-cache-poc.jar'
    temporary = output.with_suffix('.new')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as patched:
        for entry in vendor.infolist():
            patched.writestr(entry, bundle_bytes.getvalue() if entry.filename == bundle_path else vendor.read(entry))
    temporary.replace(output)
import json
(HERE / 'metadata-patch.lock.json').write_text(json.dumps({
    'source_ref': SOURCE_REF, 'upstream_sources_sha256': hashes,
    'vendor_jar_sha256': hashlib.sha256(source_jar.read_bytes()).hexdigest(),
    'patched_jar_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
    'patch': 'File metadata API-key to Edge-ID cache notification override'
}, indent=2) + '\n')
print('Built pinned File metadata compatibility patch; credentials unchanged.')
