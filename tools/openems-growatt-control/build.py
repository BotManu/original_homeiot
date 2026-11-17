"""Compile against the installed distribution and run native policy checks.

Usage: python3 tools/openems-growatt-control/build.py ~/original/openems-edge.jar
Requires JDK 21. Building never opens a serial port or changes the runtime.
"""
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
BUILD = ROOT.parents[1] / 'data/growatt-control-build'
LIB, CLASSES, TESTS = BUILD / 'lib', BUILD / 'classes', BUILD / 'tests'
for folder in (LIB, CLASSES, TESTS):
    folder.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(Path(sys.argv[1]).expanduser()) as distribution:
    for name in distribution.namelist():
        if name.startswith('jar/') and name.endswith('.jar'):
            (LIB / Path(name).name).write_bytes(distribution.read(name))
subprocess.run(['javac', '--release', '21', '-cp', str(LIB / '*'), '-d', str(CLASSES),
                *map(str, sorted((ROOT / 'src').rglob('*.java')))], check=True)
test_classpath=str(CLASSES)+':'+str(LIB/'*')
subprocess.run(['javac', '--release', '21', '-cp', test_classpath, '-d', str(TESTS),
                *map(str,sorted((ROOT/'test').glob('*.java')))],check=True)
for test in ('ControlPolicyTest','originalhome.growatt.control.ScheduleSlotElementTest'):
    subprocess.run(['java','-ea','-cp',test_classpath+':'+str(TESTS),test],check=True)

dependencies = subprocess.run(['jdeps', '--multi-release', '21', '--class-path', str(LIB / '*'),
                              '-verbose:class', str(CLASSES)], check=True, capture_output=True, text=True).stdout
packages=set()
for target in re.findall(r'^\s+\S+\s+->\s+([\w.$]+)\s+', dependencies, re.M):
    package=target.rsplit('.',1)[0]
    if not package.startswith(('java.','jdk.','originalhome.')):
        packages.add(package)
fields={
    'Manifest-Version':'1.0', 'Bundle-ManifestVersion':'2',
    'Bundle-SymbolicName':'org.originalhome.growatt.control', 'Bundle-Version':'0.1.0',
    'Bundle-Name':'OriginalHome bounded Growatt strategy commissioning',
    'Import-Package':','.join(sorted(packages)),
    'Service-Component':'OSGI-INF/driver.xml,OSGI-INF/controller.xml',
}
lines=[]
for key,value in fields.items():
    line=key+': '+value
    while len(line)>70:
        lines.append(line[:70]);line=' '+line[70:]
    lines.append(line)
manifest='\r\n'.join(lines)+'\r\n\r\n'
output=BUILD/'originalhome-growatt-control.jar'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as jar:
    jar.writestr('META-INF/MANIFEST.MF',manifest)
    for name in ('driver.xml','controller.xml'):
        jar.write(ROOT/name,'OSGI-INF/'+name)
    for path in sorted(CLASSES.rglob('*.class')):
        jar.write(path,path.relative_to(CLASSES).as_posix())
print(output)
