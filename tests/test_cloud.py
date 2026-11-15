"""Cloud PoC authorization, source validation and restart/deduplication tests."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cloud.app import create_app
from cloud.models import Audit, Membership, Sample, Site, User, now_ms, password_hash
from cloud.telemetry import CHANNELS, normalize, save_sample, unwrap_current_data


class CloudTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'CLOUD_ADMIN_PASSWORD': 'test-only-long-password'})
        self.env.start()
        self.url = 'sqlite:///' + str(Path(self.temp.name) / 'cloud.sqlite3')
        self.app = create_app(self.url, worker=False)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def login(self, username='admin', password='test-only-long-password'):
        return self.client.post('/api/login', json={'username': username, 'password': password})

    def test_authentication_logout_and_origin(self):
        self.assertEqual(self.client.get('/api/sites').status_code, 401)
        self.assertEqual(self.login(password='wrong').status_code, 401)
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/sites').status_code, 200)
        self.assertEqual(self.client.post('/api/logout', headers={'origin':'https://evil.test'}).status_code,403)
        self.assertEqual(self.client.post('/api/logout').status_code,200)
        self.assertEqual(self.client.get('/api/sites').status_code,401)

    def test_site_isolation_and_export(self):
        with Session(self.app.state.engine) as db, db.begin():
            db.add(User(id='other', password=password_hash('another-long-password')))
            db.add(Site(id='other-home',name='Other',edge_id='other-edge'))
            db.flush()
            db.add(Membership(user_id='other',site_id='other-home',role='owner'))
        self.login()
        for path in ['/api/sites/other-home','/api/sites/other-home/history','/api/sites/other-home/export.csv']:
            self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(len(self.client.get('/api/sites').json()['sites']),1)
        result = self.client.get('/api/sites/first-home/export.csv?hours=1')
        self.assertEqual(result.status_code,200)
        self.assertIn('observed_utc_ms',result.text)
        self.assertEqual(self.client.get('/api/sites/first-home/history?hours=999').status_code,422)

    def test_empty_stale_fresh_and_no_control(self):
        self.login()
        site = self.client.get('/api/sites/first-home').json()
        self.assertEqual(site['status'],'awaiting_gateway')
        self.assertIsNone(site['latest'])
        self.assertFalse(site['control_enabled'])
        observed = now_ms()
        values = {key: 50 for key in CHANNELS}
        save_sample(self.app.state.engine,'first-home',observed,observed,values)
        # A fresh stored sample alone cannot claim that equipment is connected.
        self.assertEqual(self.client.get('/api/sites/first-home').json()['status'],'stale')
        with Session(self.app.state.engine) as db, db.begin():
            db.get(Site,'first-home').connection = 'connected'
        self.assertEqual(self.client.get('/api/sites/first-home').json()['status'],'live')
        self.assertIn(self.client.post('/api/sites/first-home/control',json={}).status_code,(404,405))

    def test_deduplication_and_retention(self):
        engine = self.app.state.engine
        observed = now_ms()
        values = {key: 50 for key in CHANNELS}
        one = save_sample(engine,'first-home',observed,observed,values)
        two = save_sample(engine,'first-home',observed,observed+1000,values)
        self.assertEqual(one,two)
        with Session(engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Sample)),1)
        save_sample(engine,'first-home',observed-8*86400_000,observed,values)
        with Session(engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Sample)),1)
        self.client.__exit__(None,None,None)
        self.app = create_app(self.url,worker=False)
        self.client = TestClient(self.app)
        self.client.__enter__()
        with Session(self.app.state.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Sample)),1)

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.login(password='wrong').status_code,401)
        self.assertEqual(self.login(password='wrong').status_code,429)

    def test_history_gaps_and_out_of_order_samples(self):
        self.login()
        current = now_ms()
        values = {key: 50 for key in CHANNELS}
        values['solar_w'] = 0
        save_sample(self.app.state.engine,'first-home',current,current,values)
        save_sample(self.app.state.engine,'first-home',current-60000,current+1000,values)
        result = self.client.get('/api/sites/first-home/history').json()
        self.assertEqual([row['observed_ms'] for row in result['samples']],[current-60000,current])
        self.assertEqual(result['gaps'],[{'after_ms':current-60000,'before_ms':current}])
        latest = self.client.get('/api/sites/first-home').json()['latest']
        self.assertEqual(latest['observed_ms'],current)
        self.assertEqual(latest['values']['solar_w'],0)

    def test_channel_contract(self):
        now = now_ms()
        channels = {'growatt0/'+name: 50 for name in CHANNELS.values()}
        channels['growatt0/LastSuccessfulRead'] = now
        self.assertEqual(normalize(channels,'growatt0',now)[0],now)
        self.assertEqual(normalize({**channels,'growatt0/ProductionActivePower':0},'growatt0',now)[1]['solar_w'],0)
        with self.assertRaises(ValueError):
            normalize({**channels,'growatt0/ProductionActivePower':None},'growatt0',now)
        for value in [None,True,float('nan'),now-16000,now+3000]:
            with self.assertRaises(ValueError):
                normalize({**channels,'growatt0/LastSuccessfulRead':value},'growatt0',now)
        for value in [None,True,float('inf'),101,-1]:
            with self.assertRaises(ValueError):
                normalize({**channels,'growatt0/EssSoc':value},'growatt0',now)
        self.assertIsNone(unwrap_current_data({'method':'edgeRpc','params':{'edgeId':'wrong','payload':{}}},'right'))


if __name__ == '__main__':
    unittest.main()
