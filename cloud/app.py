"""Authenticated single-owner engineering PoC, restricted to the VPN."""
import asyncio
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
import csv
import hashlib
import io
import os
from pathlib import Path
import secrets
import time
import base64
import json
from urllib.request import Request as UpstreamRequest, urlopen
from urllib.error import URLError

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session

from .models import Audit, Base, LoginSession, Membership, Sample, Site, User, now_ms, password_hash, verify_password
from . import telemetry
from gateway.day_ahead import demo_plan

STATIC = Path(__file__).parent / 'static'


def create_app(database_url=None, worker=True):
    engine = create_engine(database_url or os.environ['DATABASE_URL'], pool_pre_ping=True)
    attempts = defaultdict(deque)
    secure = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        with Session(engine) as db, db.begin():
            if not db.get(User, 'admin'):
                password = os.getenv('CLOUD_ADMIN_PASSWORD', '')
                if len(password) < 16:
                    raise RuntimeError('Set CLOUD_ADMIN_PASSWORD to at least 16 characters')
                db.add(User(id='admin', password=password_hash(password)))
                db.flush()
            if not db.get(Site, 'first-home'):
                db.add(Site(id='first-home', name='First home', edge_id='original-volt-gateway',
                            timezone='Europe/Bucharest', component='growatt0', origin='equipment'))
                db.flush()
                db.add(Membership(user_id='admin', site_id='first-home', role='owner'))
        task = asyncio.create_task(telemetry.run(engine)) if worker else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        engine.dispose()

    app = FastAPI(title='OriginalHome cloud PoC', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'same-origin', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    def session():
        with Session(engine) as db:
            yield db

    def current_user(request: Request, db=Depends(session)):
        token = request.cookies.get('originalhome_session', '')
        login = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest()) if token else None
        if not login or login.expires_ms <= now_ms():
            raise HTTPException(401, 'Sign in to continue')
        return login.user_id

    def allowed_site(site_id, user_id, db):
        member = db.get(Membership, (user_id, site_id))
        if not member:
            raise HTTPException(404, 'Site not found')
        return db.get(Site, site_id)

    def same_origin(request):
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'Origin rejected')
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, 'Origin rejected')

    class Login(BaseModel):
        username: str = Field(max_length=100)
        password: str = Field(max_length=1024)

    @app.get('/healthz')
    def health(db=Depends(session)):
        db.execute(text('SELECT 1'))
        return {'status': 'ok', 'release': 'poc-1'}

    @app.post('/api/login')
    def login(body: Login, request: Request, response: Response, db=Depends(session)):
        same_origin(request)
        host = request.client.host
        queue = attempts[host]
        while queue and queue[0] < time.monotonic() - 60:
            queue.popleft()
        if len(queue) >= 10:
            raise HTTPException(429, 'Too many attempts. Try again in a minute.')
        queue.append(time.monotonic())
        user = db.get(User, body.username)
        # Run the same expensive hash for unknown accounts.
        stored = user.password if user else '0' * 32 + ':' + '0' * 64
        if not verify_password(body.password, stored) or not user:
            db.add(Audit(user_id='anonymous', action='login_failed'))
            db.commit()
            raise HTTPException(401, 'Incorrect username or password')
        token = secrets.token_urlsafe(32)
        old = request.cookies.get('originalhome_session')
        if old:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == hashlib.sha256(old.encode()).hexdigest()))
        db.execute(delete(LoginSession).where(LoginSession.expires_ms < now_ms()))
        db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                            expires_ms=now_ms() + 8 * 3600_000))
        db.add(Audit(user_id=user.id, action='login'))
        db.commit()
        response.set_cookie('originalhome_session', token, httponly=True, secure=secure,
                            samesite='strict', max_age=8 * 3600, path='/')
        return {'username': user.id}

    @app.post('/api/logout')
    def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(session)):
        same_origin(request)
        digest = hashlib.sha256(request.cookies['originalhome_session'].encode()).hexdigest()
        db.execute(delete(LoginSession).where(LoginSession.token_hash == digest))
        db.add(Audit(user_id=user, action='logout'))
        db.commit()
        response.delete_cookie('originalhome_session', path='/')
        return {'ok': True}

    def sample_json(sample):
        return None if sample is None else {'id': sample.id, 'observed_ms': sample.observed_ms,
            'received_ms': sample.received_ms, 'values': sample.values}

    def site_json(site, db):
        latest = db.scalar(select(Sample).where(Sample.site_id == site.id).order_by(Sample.observed_ms.desc()).limit(1))
        age = max(0, now_ms() - latest.observed_ms) if latest else None
        live = age is not None and age <= 20000 and site.connection == 'connected'
        return {'id': site.id, 'name': site.name, 'edge_id': site.edge_id,
                'timezone': site.timezone, 'data_origin': site.origin,
                'connection': site.connection, 'status': 'live' if live else 'stale' if latest else 'awaiting_gateway',
                'observation_age_ms': age, 'latest': sample_json(latest), 'control_enabled': False,
                'qualification': 'Daylight power and battery signs pending; inverter serial mismatch unresolved.',
                'solar_basis': 'PV input (DC)', 'history_retention_days': 7}

    @app.get('/api/sites')
    def sites(user=Depends(current_user), db=Depends(session)):
        rows = db.scalars(select(Site).join(Membership).where(Membership.user_id == user).order_by(Site.name))
        return {'username': user, 'sites': [site_json(site, db) for site in rows]}

    @app.get('/api/sites/{site_id}')
    def site(site_id: str, user=Depends(current_user), db=Depends(session)):
        return site_json(allowed_site(site_id, user, db), db)

    @app.get('/api/sites/{site_id}/history')
    def history(site_id: str, hours: int = Query(1, ge=1, le=168),
                user=Depends(current_user), db=Depends(session)):
        allowed_site(site_id, user, db)
        rows = list(db.scalars(select(Sample).where(Sample.site_id == site_id,
            Sample.observed_ms >= now_ms() - hours * 3600_000).order_by(Sample.observed_ms.desc()).limit(2000)))
        ordered = list(reversed(rows))
        gaps = [{'after_ms': a.observed_ms, 'before_ms': b.observed_ms}
                for a, b in zip(ordered, ordered[1:]) if b.observed_ms - a.observed_ms > 20000]
        return {'samples': [sample_json(row) for row in ordered], 'gaps': gaps, 'limit': 2000,
                'truncated': len(rows) == 2000, 'gap_threshold_ms': 20000}

    @app.get('/api/sites/{site_id}/plan')
    def day_ahead_plan(site_id: str, user=Depends(current_user), db=Depends(session)):
        site = allowed_site(site_id, user, db)
        if site_id == os.getenv('LIVE_PLAN_SITE_ID', 'olinuxino-home'):
            url = os.getenv('LIVE_PLAN_GATEWAY_URL', '')
            password = os.getenv('LIVE_PLAN_GATEWAY_PASSWORD', '')
            if not url or not password:
                raise HTTPException(503, 'Live gateway plan connection is not configured')
            auth = base64.b64encode(('admin:'+password).encode()).decode()
            try:
                with urlopen(UpstreamRequest(url+'/api/energy/plan', headers={'Authorization':'Basic '+auth}), timeout=8) as response:
                    data = json.loads(response.read(250001))
                if data.get('mode') != 'live_grid_charging':
                    raise ValueError('No live plan')
                return data
            except (URLError, OSError, ValueError):
                raise HTTPException(503, 'Live gateway plan unavailable; no demo substitution')
        return demo_plan(site.timezone)

    @app.get('/api/sites/{site_id}/export.csv')
    def export(site_id: str, hours: int = Query(24, ge=1, le=168),
               user=Depends(current_user), db=Depends(session)):
        allowed_site(site_id, user, db)
        rows = list(db.scalars(select(Sample).where(Sample.site_id == site_id,
            Sample.observed_ms >= now_ms() - hours * 3600_000).order_by(Sample.observed_ms).limit(10001)))
        if len(rows) > 10000:
            raise HTTPException(422, 'Export exceeds 10,000 samples. Choose a shorter interval.')
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['sample_id', 'observed_utc_ms', 'received_utc_ms', *telemetry.CHANNELS])
        writer.writerows([[row.id, row.observed_ms, row.received_ms,
                           *[row.values[key] for key in telemetry.CHANNELS]] for row in rows])
        db.add(Audit(user_id=user, site_id=site_id, action='export_csv'))
        db.commit()
        return Response(output.getvalue(), media_type='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="originalhome-energy.csv"'})

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    @app.get('/app.js')
    def javascript():
        return FileResponse(STATIC / 'app.js', media_type='text/javascript')

    @app.get('/style.css')
    def css():
        return FileResponse(STATIC / 'style.css', media_type='text/css')

    return app
