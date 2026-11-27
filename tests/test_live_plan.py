from datetime import date, datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from gateway.day_ahead import day_slots
from gateway.energy_control import atomic_private_write, REQUIRED_GATES
from gateway.live_plan import prices, rank, decision, record, NAME
from gateway.night_schedule import tick, DEFAULT


class LivePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.zone = ZoneInfo('Europe/Bucharest')
        self.now = datetime(2026,11,28,2,0,tzinfo=self.zone)
        self.night = dict(DEFAULT,enabled=True)
        atomic_private_write(self.folder/'growatt-night-schedule.json',self.night)
        self.current = dict(writes_enabled=True,native_transport_bound=True,
                            observed_ms=int(self.now.timestamp()*1000), battery_soc=50,
                            qualification={k:True for k in REQUIRED_GATES})
        self.plan = dict(enabled=True,date='2026-11-28',charge_w=1000,target_soc=90,
                         capacity_kwh=3,window_start='02:00',window_end='05:00',locked=False,
                         slots=[dict(start_ms=int(s.timestamp()*1000),local=s.astimezone(self.zone).isoformat(),
                                     spot_eur_kwh=.05 if s.astimezone(self.zone).hour==4 else .2)
                                for s in day_slots(date(2026,11,28),self.zone)])
        rank(self.plan,50)
        atomic_private_write(self.folder/NAME,self.plan)

    def test_cheapest_slots_and_no_outside_window(self):
        selected=[s for s in self.plan['slots'] if s['selected']]
        self.assertEqual(len(selected),6)
        self.assertTrue(all('02:00'<=s['local'][11:16]<'05:00' for s in selected))
        self.assertEqual(sum(s['spot_eur_kwh']==.05 for s in selected),4)

    def test_lock_actual_soc_and_cancel_expensive_slot(self):
        self.current['battery_soc']=80
        decision(self.folder,self.now,self.current,self.night)
        locked=json.loads((self.folder/NAME).read_text())
        self.assertEqual(locked['selected_intervals'],2)
        self.assertTrue(locked['locked'])
        atomic_private_write(self.folder/'growatt-command.json',dict(source='night_schedule',mode='GRID_CHARGE'))
        with patch('gateway.night_schedule.status',return_value=self.current),patch('gateway.night_schedule.submit') as submit:
            self.assertEqual(tick(self.folder,self.now),'live_plan_price_hold')
            submit.assert_not_called()
        self.assertEqual(json.loads((self.folder/'growatt-command.json').read_text())['mode'],'MONITOR')

    def test_selected_lease_deadline_and_manual_override(self):
        now=self.now.replace(hour=4)
        self.current['observed_ms']=int(now.timestamp()*1000)
        with patch('gateway.night_schedule.status',return_value=self.current),patch('gateway.night_schedule.submit') as submit:
            self.assertEqual(tick(self.folder,now),'submitted')
            self.assertEqual(submit.call_args.kwargs['not_after_ms'],int(now.replace(minute=15).timestamp()*1000))
            atomic_private_write(self.folder/'growatt-command.json',dict(source='manual',mode='SELF_CONSUMPTION',expires_ms=int(now.timestamp()*1000)+180000))
            self.assertEqual(tick(self.folder,now),'manual_override')

    def test_missing_stale_qualification_holds_and_other_day_unchanged(self):
        self.current['observed_ms']=0
        self.assertFalse(decision(self.folder,self.now,self.current,self.night)['charge'])
        self.assertIsNone(decision(self.folder,self.now.replace(day=29),self.current,self.night))

    def test_meter_price_boundary_and_gaps(self):
        slots=self.plan['slots']; boundary=slots[16]['start_ms']
        # Split ten seconds around the 04:00 price change, then reject a long gap.
        previous=dict(ts=boundary-5000,values={'grid_w':1000})
        sample=dict(ts=boundary+5000,values={'grid_w':-1000})
        record(self.folder,previous,sample)
        meter=json.loads((self.folder/'day-ahead-meter.json').read_text())
        self.assertAlmostEqual(meter['import_spot_eur'],1000*5/3600000*(.2+.05))
        self.assertEqual(meter['covered_seconds'],10)
        record(self.folder,sample,dict(sample,ts=boundary+65000))
        meter=json.loads((self.folder/'day-ahead-meter.json').read_text())
        self.assertEqual(meter['covered_seconds'],10)
        self.assertEqual(meter['skipped_gap_seconds'],60)

    def test_price_response_validates_full_day_and_units(self):
        expected=day_slots(date(2026,11,28),self.zone)
        payload=dict(unit='EUR / MWh',deprecated=False,
                     unix_seconds=[int(s.timestamp()) for s in expected],price=[-10]*96)
        with patch('gateway.live_plan.urlopen') as fetch:
            fetch.return_value.__enter__.return_value.read.side_effect=lambda _:json.dumps(payload).encode()
            result,_,_=prices(date(2026,11,28))
            self.assertEqual(result[0]['spot_eur_kwh'],-.01)
            payload['price'].pop(); payload['unix_seconds'].pop()
            with self.assertRaises(ValueError):prices(date(2026,11,28))
            payload['unit']='RON / MWh'
            with self.assertRaises(ValueError):prices(date(2026,11,28))


if __name__=='__main__': unittest.main()
