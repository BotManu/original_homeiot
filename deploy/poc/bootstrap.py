"""Initialize fresh private PoC configuration with sudo; preserve existing state."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

HERE = Path(__file__).resolve().parent
os.chdir(HERE)


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


env_file = HERE / '.env'
if not env_file.exists():
    ip = run('tailscale', 'ip', '-4')
    with env_file.open('x') as output:
        os.chmod(env_file, 0o600)
        output.write(f'TAILSCALE_IP={ip}\nPOSTGRES_PASSWORD={secrets.token_hex(24)}\n'
                     f'CLOUD_ADMIN_PASSWORD={secrets.token_urlsafe(24)}\n')

runtime = HERE / 'runtime'
runtime.mkdir(exist_ok=True)
images = {
    'backend': 'openems/backend@sha256:7dc614a93693f82e3836681a3d426475fd278c15b2addb6560ef7243dc96ec71',
    'ingress': 'openems/backend-edge@sha256:905f740a0040e2f0e5128d7e6cfde2ee7cdde2ba53f2e0b215204c3701aaea8f',
}
for name, image in images.items():
    target = runtime / name
    if not target.exists():
        target.mkdir()
        container = run('docker', 'create', image)
        try:
            run('docker', 'cp', container + ':/var/lib/openems-default-config/.', str(target))
        finally:
            run('docker', 'rm', container)
        if name == 'ingress':
            path = target / 'Backend/Edge/App.config'
            path.write_text(path.read_text().replace('ws://localhost:8083', 'ws://openems-backend:8083'))

metadata = runtime / 'metadata.json'
if not metadata.exists():
    metadata.write_text(json.dumps({'edges': {'original-volt-gateway': {
        'comment': 'OriginalHome first equipment gateway', 'apikey': secrets.token_hex(32)}}}))
    os.chmod(metadata, 0o640)
    os.chown(metadata, 0, 1000)

lock = HERE / 'images.lock.json'
if not lock.exists():
    resolved = dict(images)
    for name, tag in [('postgres', 'postgres:17.7-alpine'), ('python', 'python:3.12-slim')]:
        run('docker', 'pull', tag)
        resolved[name] = run('docker', 'image', 'inspect', tag, '--format', '{{index .RepoDigests 0}}')
    lock.write_text(json.dumps(resolved, indent=2) + '\n')
else:
    resolved = json.loads(lock.read_text())
env = env_file.read_text()
if 'POSTGRES_IMAGE=' not in env:
    env_file.write_text(env + 'POSTGRES_IMAGE=' + resolved['postgres'] + '\n'
                        + 'PYTHON_IMAGE=' + resolved['python'] + '\n')
print('Initialized private PoC configuration; secrets were not printed.')

env_values = dict(line.split('=', 1) for line in env_file.read_text().splitlines() if '=' in line)
additions = {}
for key in ['BACKEND_READER_PASSWORD', 'BACKEND_CLIENT_SECRET']:
    if key not in env_values:
        additions[key] = secrets.token_hex(24)
if additions:
    with env_file.open('a') as output:
        output.write(''.join(f'{k}={v}\n' for k, v in additions.items()))
    env_values.update(additions)
identity = runtime / 'identity'
identity.mkdir(exist_ok=True)
realm = identity / 'originalhome-realm.json'
if not realm.exists():
    realm.write_text(json.dumps({
        'realm': 'originalhome', 'enabled': True, 'sslRequired': 'none',
        'registrationAllowed': False,
        'clients': [{'clientId': 'openems', 'enabled': True, 'protocol': 'openid-connect',
                     'publicClient': False, 'secret': env_values['BACKEND_CLIENT_SECRET'],
                     'standardFlowEnabled': False, 'directAccessGrantsEnabled': True,
                     'serviceAccountsEnabled': True}],
        'users': [{'username': 'cloud-reader', 'enabled': True, 'emailVerified': True,
                   'email': 'cloud-reader@originalhome.invalid', 'firstName': 'Cloud', 'lastName': 'Reader',
                   'credentials': [{'type': 'password', 'value': env_values['BACKEND_READER_PASSWORD'],
                                    'temporary': False}]}]
    }))
    os.chmod(realm, 0o640)
    os.chown(realm, 1000, 0)
auth_folder = runtime / 'backend/Authentication'
auth_folder.mkdir(exist_ok=True)
auth = auth_folder / 'OAuth.config'
if not auth.exists():
    issuer = 'http://identity:8080/realms/originalhome'
    auth.write_text('\n'.join([
        'realm="originalhome"', 'baseKeycloakUrl="http://identity:8080"',
        f'issuerUrl="{issuer}"', f'loginUrl="{issuer}/protocol/openid-connect/auth"',
        f'tokenUrl="{issuer}/protocol/openid-connect/token"',
        f'certsUrl="{issuer}/protocol/openid-connect/certs"',
        'service.pid="Authentication.OAuth"', '']))
client_folder = auth_folder / 'OAuth/ClientConfig'
client_folder.mkdir(parents=True, exist_ok=True)
client = client_folder / 'originalhome.config'
if not client.exists():
    client.write_text('\n'.join(['oem="openems"', 'clientId="openems"',
        'clientSecret=' + json.dumps(env_values['BACKEND_CLIENT_SECRET']),
        'redirectUri="http://identity:8080/"', 'serviceAccount=B"true"',
        'service.factoryPid="Authentication.OAuth.ClientConfig"',
        'service.pid="Authentication.OAuth.ClientConfig.originalhome"', '']))
    os.chmod(client, 0o640)
    os.chown(client, 0, 1000)
if 'keycloak' not in resolved:
    run('docker', 'pull', 'quay.io/keycloak/keycloak:26.4.0')
    resolved['keycloak'] = run('docker', 'image', 'inspect', 'quay.io/keycloak/keycloak:26.4.0',
                              '--format', '{{index .RepoDigests 0}}')
    lock.write_text(json.dumps(resolved, indent=2) + '\n')
if 'KEYCLOAK_IMAGE' not in env_values:
    with env_file.open('a') as output:
        output.write('KEYCLOAK_IMAGE=' + resolved['keycloak'] + '\n')
run('docker', 'compose', 'up', '-d', 'database')
exists = run('docker', 'compose', 'exec', '-T', 'database', 'psql', '-U', 'originalhome', '-d', 'originalhome',
             '-tAc', "SELECT 1 FROM pg_database WHERE datname='originalhome_identity'")
if exists != '1':
    run('docker', 'compose', 'exec', '-T', 'database', 'psql', '-U', 'originalhome', '-d', 'originalhome',
        '-c', 'CREATE DATABASE originalhome_identity OWNER originalhome')
print('Initialized private Backend OAuth provider.')
if not (runtime / 'openems-backend-file-cache-poc.jar').exists():
    subprocess.run([sys.executable, str(HERE / 'patch_metadata.py')], check=True)
