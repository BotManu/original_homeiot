# OriginalHome cloud: private monitoring PoC

This is the first engineering slice of the release plan, running on the real
server with the first equipment gateway. It is not release-1 acceptance.

## Access

Connect your computer to the owner's Tailscale network, then open
http://100.122.80.43:8080. Sign in as `admin`. The generated owner password is
in the development computer's Git-ignored `local/poc_access.json` and in the
server's root-only `deploy/poc/.env`. Do not use the Linux login password.
HTTP and the gateway websocket are confined to Tailscale addresses; WireGuard
provides transport encryption. Do not publish these ports on the internet.

## Implemented

- FastAPI cloud application and locally served, responsive dashboard.
- Hashed owner password, opaque eight-hour sessions, HttpOnly/SameSite cookies,
  origin checks, login throttling and audit events for login/logout/export.
- PostgreSQL site/user/membership registry and seven-day monitoring projection.
- Backend OAuth authentication through a private Keycloak realm, stored in a
  separate database on the same PostgreSQL instance.
- Native Edge -> Backend.Edge.App -> central Backend connection using a unique
  gateway API key. Only the isolated `growatt0` component reaches the cloud UI.
- Source observation time from `LastSuccessfulRead`, separate receipt time,
  validation of units/numerics/SoC and a 100 kW engineering power envelope.
- Deduplication by site and observed timestamp, stale state, visible chart gaps,
  bounded history (2,000 samples) and CSV (10,000 rows, at most seven days).
- No equipment-control endpoints. Local collection and UI continue independently.

Sample identity is SHA-256 of `v1:<site-id>:<observed-utc-ms>`. W is power;
SoC is percent. Grid positive means import; battery positive means discharge.
Solar is inverter PV input/DC, not an exact AC energy-balance quantity.
Site time is Europe/Bucharest; stored timestamps are UTC milliseconds.

The UI reads a live websocket projection. It does **not** yet backfill offline
samples from native timedata. The native Backend still has Timedata.Dummy.
An outage appears as a history gap; it must not be represented as complete
cloud history. No integrated energy totals are calculated.

Observed native reconnect limitation: unchanged channels can lack a baseline
after relay restart until the connector's default full-snapshot interval
(five minutes). The app rejects incomplete samples and keeps the site stale
until a fresh, complete baseline arrives. Its subscription watchdog retries
empty/stale sessions, but does not invent missing zero values. Allow about
five minutes for complete monitoring recovery in this engineering PoC.

## Pinned compatibility spike

Vendor Backend/ingress are OpenEMS 2026.11.0. Exact vendor, Python, PostgreSQL
and Keycloak image digests are in `images.lock.json`; Python dependencies are
in `cloud/requirements.lock.txt`. `requirements.txt` lists direct dependencies.

The vendor File metadata provider omitted the ingress API-key cache mapping.
`patch_metadata.py` builds a single-method override against the exact vendor
JAR, preserving OSGi descriptors and adding its required package import. It
uses upstream source revision `3eb006a1534d6bec562008e8f35083303baa98c2` and verifies
the changed source's SHA-256. `metadata-patch.lock.json` records provenance.
The derived JAR is bind-mounted; the vendor image is retained unchanged.
File metadata is engineering-only: its shared ADMIN mapping is **not** a
production customer authorization model. All native engineering ports stay
on loopback/private container networking.

The installed gateway distribution before this work had SHA-256
`dd279d5fb3a399108fece08c2dea4610e66806fee0ebafb3b4ec028248a78e2a`.
Its OpenEMS Common bundle is `1.0.0.202610301329`; custom read-only bundle
0.1.1 marks six equipment channels HIGH for remote persistence so their
source timestamps advance in the live Backend cache. Local persistence
priority, serial polling and register access remain unchanged.

## Fresh deployment

Use Ubuntu 24.04, Docker Engine/Compose, Python 3 and JDK 21. The current
server uses Ubuntu Docker packages 29.1.3 / Compose 2.40.3. Copy the source to
`/home/original_home_srv/originalhome-poc` (no credentials or runtime databases).
On the server:

```sh
cd /home/original_home_srv/originalhome-poc
sudo python3 deploy/poc/bootstrap.py
sudo docker compose --project-directory deploy/poc build app
sudo docker compose --project-directory deploy/poc up -d
```

Bootstrap generates unique secrets only when absent and preserves existing
credentials/configuration. It prepares File metadata, the OAuth realm and
the derived compatibility JAR. Initialization needs registry/GitHub access.
Never replace the `.env` after the databases have initialized without a
deliberate credential rotation; bootstrap does not rotate existing accounts.
The owner password is read into the database only on first creation.

For a new gateway, configure `Controller.Api.Backend` through the local
Configuration Admin API with the API key in private `runtime/metadata.json`,
URI `ws://100.122.80.43:8081`, and ID `ctrlOriginalHomeBackend0`. Keep the key
private. The existing deployment uses factory PID
`Controller.Api.Backend.originalhome-poc`. The new gateway connector was
activated without restarting Edge.

For the telemetry bundle, use these commands **on the gateway**:

```sh
cd ~/OriginalHomeIOT
python3 tools/openems-growatt/build.py ~/original/openems-edge.jar
python3 tools/openems-growatt/deploy.py ~/original/openems-edge.jar
```

The deploy helper updates only the read-only bundle through the loopback
Felix console, verifies activation, persists its boot copy and preserves
`~/original/openems-edge.pre-cloud-poc.jar`. It uses the installation's
existing default console login unless FELIX_USER/FELIX_PASSWORD are supplied.

## Operations

```sh
cd /home/original_home_srv/originalhome-poc
sudo docker compose --project-directory deploy/poc ps
sudo docker compose --project-directory deploy/poc logs --tail 50 app
sudo docker compose --project-directory deploy/poc restart app
```

`originalhome-poc.service` orders startup after Docker/Tailscale and waits for
the configured VPN address. It is specific to this server's path and IP.
Container restart policies and bounded logs are configured. Health checks
verify the API/database; equipment freshness is reported separately.

For unit/API regression checks (development dependencies installed):

```sh
python -m unittest discover -s tests -v
```

Use `docker compose stop` to stop this PoC; do not use `down -v` unless you
intend to discard data. Preserve `.env`, runtime metadata/realm, image and
patch locks, and database volumes. Off-host backups/restore and actual host
reboot recovery remain release gates; restart policies alone do not prove them.

## Rollback

Stop the cloud stack with `sudo systemctl stop originalhome-poc`. Disable the
gateway's `ctrlOriginalHomeBackend0` through its Configuration Admin API.
Local services do not depend on this cloud connector. Preserve local history.

To revert telemetry priority, extract the old read-only bundle from
`~/original/openems-edge.pre-cloud-poc.jar`, update it through the loopback
Felix console, and restore that backup as `openems-edge.jar` for next boot.
This needs no serial collector change. To revert the Backend patch, stop the
cloud stack and remove the derived-JAR bind mount in Compose; the retained
vendor image is untouched. Its original File metadata will not initialize
the separate ingress cache, which is the documented reason for the patch.

## Next engineering gates

1. Qualify the native timedata store and bounded reconnect/history replay,
   including suitable local persistence for the custom channels.
   Resolve the native full-baseline reconnect delay before pilot acceptance.
2. Replace File metadata with the authoritative registry projection. Add
   one-time enrollment, credential rotation/revocation and gateway replacement.
3. Integrate customer/installer/operator OIDC, MFA, invitations and recovery;
   the current owner login and internal Keycloak are engineering scaffolding.
4. Add off-host backups, restore test, migration tooling, update/rollback and
   full server/gateway reboot tests. Configure HTTPS before public deployment.
5. Complete device identity/sign/daylight qualification and verified writable
   OpenEMS integration before implementing controls or VPP dispatch.
