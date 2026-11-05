"""Build the isolated telemetry bundle against the exact installed OpenEMS JAR.

Usage: python3 tools/openems-growatt/build.py ~/original/openems-edge.jar
Output: data/openems-build/originalhome-growatt-readonly.jar (not deployed).
Requires JDK 21. Does not change the installed runtime.
"""
from pathlib import Path
import subprocess
import re
import sys
import zipfile

root = Path(__file__).resolve().parent
build = root.parent.parent / 'data/openems-build'
lib, classes = build / 'lib', build / 'classes'
lib.mkdir(parents=True, exist_ok=True)
classes.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(Path(sys.argv[1]).expanduser()) as runtime:
    for name in runtime.namelist():
        if name.startswith('jar/') and name.endswith('.jar'):
            (lib / Path(name).name).write_bytes(runtime.read(name))
subprocess.run(['javac', '--release', '21', '-cp', str(lib / '*'), '-d', str(classes),
                str(root / 'src/originalhome/growatt/GrowattReadOnly.java')], check=True)
dependencies = subprocess.run(['jdeps', '--multi-release', '21', '--class-path',
                              str(lib / '*'), '-verbose:class', str(classes)],
                             check=True, capture_output=True, text=True).stdout
packages = set()
for target in re.findall(r'^\s+\S+\s+->\s+([\w.$]+)\s+', dependencies, re.M):
    package = target.rsplit('.', 1)[0]
    if not package.startswith(('java.', 'jdk.', 'originalhome.')):
        packages.add(package)
imports = ',\n '.join(sorted(packages))
manifest = '''Manifest-Version: 1.0
Bundle-ManifestVersion: 2
Bundle-SymbolicName: org.originalhome.growatt.readonly
Bundle-Version: 0.1.0
Bundle-Name: OriginalHome Growatt Read-only Telemetry
Import-Package: {imports}
Service-Component: OSGI-INF/component.xml

'''.format(imports=imports)
output = build / 'originalhome-growatt-readonly.jar'
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as bundle:
    bundle.writestr('META-INF/MANIFEST.MF', manifest)
    bundle.write(root / 'component.xml', 'OSGI-INF/component.xml')
    for path in sorted(classes.rglob('*.class')):
        bundle.write(path, str(path.relative_to(classes)).replace('\\', '/'))
print(output)
