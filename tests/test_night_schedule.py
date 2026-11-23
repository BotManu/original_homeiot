import json,tempfile,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from gateway.night_schedule import tick,config,DEFAULT
from gateway.energy_control import atomic_private_write
class NightScheduleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
  self.plan={**DEFAULT,'enabled':True};atomic_private_write(self.folder/'growatt-night-schedule.json',self.plan)
 def now(self,h,m=0):return datetime(2026,11,18,h,m,tzinfo=ZoneInfo('Europe/Bucharest'))
 def test_window_and_qualification(self):
  with patch('gateway.night_schedule.status',return_value={'battery_soc':50}),patch('gateway.night_schedule.submit',side_effect=PermissionError) as submit:
   self.assertEqual(tick(self.folder,self.now(1,59)),'outside_window');submit.assert_not_called()
   self.assertEqual(tick(self.folder,self.now(2)),'waiting_for_controller_qualification')
   self.assertEqual(tick(self.folder,self.now(5)),'outside_window')
 def test_stop_at_window_end_and_target(self):
  for hour,soc in [(5,50),(3,90)]:
   atomic_private_write(self.folder/'growatt-command.json',{'source':'night_schedule','mode':'GRID_CHARGE'})
   with patch('gateway.night_schedule.status',return_value={'battery_soc':soc}):tick(self.folder,self.now(hour))
   self.assertEqual(json.loads((self.folder/'growatt-command.json').read_text())['mode'],'MONITOR')
 def test_manual_override_and_late_window(self):
  now=self.now(3);atomic_private_write(self.folder/'growatt-command.json',{'mode':'MONITOR','expires_ms':int(now.timestamp()*1000)+180000})
  with patch('gateway.night_schedule.status',return_value={'battery_soc':50}),patch('gateway.night_schedule.submit') as submit:
   self.assertEqual(tick(self.folder,now),'manual_override');submit.assert_not_called()
   (self.folder/'growatt-command.json').unlink()
   self.assertEqual(tick(self.folder,self.now(4,59)),'window_ending');submit.assert_not_called()
 def test_invalid_and_disabled_schedule(self):
  atomic_private_write(self.folder/'growatt-night-schedule.json',{**self.plan,'enabled':False})
  with patch('gateway.night_schedule.status',return_value={}):self.assertEqual(tick(self.folder,self.now(3)),'disabled')
  atomic_private_write(self.folder/'growatt-night-schedule.json',{**self.plan,'start':'25:00'})
  with self.assertRaises(ValueError):config(self.folder)

 def test_submit_uses_requested_target_and_bounded_lease(self):
  with patch('gateway.night_schedule.status',return_value={'battery_soc':50}),patch('gateway.night_schedule.submit',return_value={'command_id':'test'}) as submit:
   self.assertEqual(tick(self.folder,self.now(3)),'submitted')
   submit.assert_called_once_with('GRID_CHARGE',1000,180,folder=self.folder,target_soc=90,source='night_schedule')
