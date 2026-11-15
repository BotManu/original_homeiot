"""Read-only OpenEMS UI websocket adapter. No generic RPC proxy or write path."""
import asyncio
import hashlib
import json
import logging
import math
import os
import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect

from .models import Site, Sample, now_ms

CHANNELS = {'solar_w': 'ProductionActivePower', 'load_w': 'ConsumptionActivePower',
            'grid_w': 'GridActivePower', 'battery_w': 'EssActivePower', 'battery_soc': 'EssSoc'}
log = logging.getLogger(__name__)


def normalize(channels, component, received_ms):
    observed = channels.get(component + '/LastSuccessfulRead')
    if (isinstance(observed, bool) or not isinstance(observed, (int, float))
            or not math.isfinite(observed) or not -2000 <= received_ms - observed <= 15000):
        raise ValueError('Missing or stale equipment observation time')
    values = {key: channels.get(component + '/' + channel) for key, channel in CHANNELS.items()}
    for value in values.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Incomplete channel set')
    if not 0 <= values['battery_soc'] <= 100:
        raise ValueError('Invalid state of charge')
    if any(abs(values[key]) > 100_000 for key in values if key != 'battery_soc'):
        raise ValueError('Outside engineering site power envelope')
    return int(observed), values


def save_sample(engine, site_id, observed_ms, received_ms, values):
    identity = hashlib.sha256(f'v1:{site_id}:{observed_ms}'.encode()).hexdigest()
    insert = pg_insert if engine.dialect.name == 'postgresql' else sqlite_insert
    with Session(engine) as db, db.begin():
        db.execute(insert(Sample).values(id=identity, site_id=site_id, observed_ms=observed_ms,
                   received_ms=received_ms, values=values).on_conflict_do_nothing())
        # Seven days of projection; native OpenEMS timedata remains the history/replay path.
        db.execute(delete(Sample).where(Sample.site_id == site_id,
                                       Sample.observed_ms < received_ms - 7 * 86400_000))
    return identity


def rpc(method, params):
    return {'jsonrpc': '2.0', 'id': str(uuid.uuid4()), 'method': method, 'params': params}


def unwrap_current_data(message, edge_id):
    if message.get('method') == 'edgeRpc':
        if message.get('params', {}).get('edgeId') != edge_id:
            return None
        message = message['params'].get('payload', {})
    if message.get('method') != 'currentData':
        return None
    return message.get('params', {})


async def follow_site(engine, site_id, edge_id, component):
    url = os.environ.get('OPENEMS_BACKEND_WS', 'ws://openems-backend:8082')
    def state(value):
        with Session(engine) as db, db.begin():
            site = db.get(Site, site_id)
            site.connection = value
            if value == 'connected':
                site.last_contact_ms = now_ms()
    while True:
        try:
            async with connect(url, open_timeout=10, max_size=1024 * 1024) as ws:
                auth = rpc('authenticateWithPassword', {'username': os.getenv('OPENEMS_BACKEND_USER', 'cloud-reader'), 'password':
                           os.environ.get('OPENEMS_BACKEND_PASSWORD', '')})
                await ws.send(json.dumps(auth))
                async with asyncio.timeout(15):
                    while True:
                        answer = json.loads(await ws.recv())
                        if answer.get('id') == auth['id']:
                            if 'error' in answer:
                                raise ValueError('Backend authentication rejected')
                            break
                channels = [component + '/' + name for name in [*CHANNELS.values(), 'LastSuccessfulRead']]
                edge_subscription = rpc('subscribeEdges', {'edges': [edge_id]})
                await ws.send(json.dumps(edge_subscription))
                subscription = rpc('edgeRpc', {'edgeId': edge_id,
                    'payload': rpc('subscribeChannels', {'count': 1, 'channels': channels})})
                await ws.send(json.dumps(subscription))
                cache = {}
                last_valid = asyncio.get_running_loop().time()
                state('waiting_for_equipment')
                while True:
                    message = json.loads(await asyncio.wait_for(ws.recv(), timeout=45))
                    # A Backend can accept subscriptions while an Edge is offline
                    # and then emit status messages without any channel data.
                    # Re-establish the subscription after recovery; transport
                    # heartbeats alone cannot keep an empty subscription alive.
                    if asyncio.get_running_loop().time() - last_valid > 30:
                        raise TimeoutError('No fresh equipment observations')
                    if message.get('id') in (subscription['id'], edge_subscription['id']) and 'error' in message:
                        raise ValueError('Edge subscription rejected')
                    data = unwrap_current_data(message, edge_id)
                    if data is None:
                        continue
                    cache.update(data)
                    received = now_ms()
                    try:
                        observed, values = normalize(cache, component, received)
                    except ValueError:
                        state('equipment_unavailable')
                        continue
                    save_sample(engine, site_id, observed, received, values)
                    last_valid = asyncio.get_running_loop().time()
                    state('connected')
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Never log frames, passwords, URLs or backend exception bodies.
            log.warning('Backend subscription unavailable for %s (%s)', site_id, type(exc).__name__)
            state('disconnected')
            await asyncio.sleep(5)


async def run(engine):
    with Session(engine) as db:
        sites = [(s.id, s.edge_id, s.component) for s in db.scalars(select(Site))]
    await asyncio.gather(*(follow_site(engine, *site) for site in sites))
