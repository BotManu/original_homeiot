import json
from pathlib import Path
import tempfile
import unittest
from gateway.energy_control import build_request, atomic_private_write, status, main
from gateway.growatt_probe import read_block
from gateway.growatt_serial import crc
from unittest.mock import MagicMock, patch
import struct


class EnergyControlTests(unittest.TestCase):
    def test_owner_ceiling_and_lease_are_not_silently_clamped(self):
        command=build_request('SOLAR_CHARGE',2990,60,now_ms=100000)
        self.assertEqual(command['duration_s'],60)
        self.assertEqual(command['expires_ms'],205000)
        self.assertEqual(command['charge_w'],2990)
        for watts in [-1,2991,True,2990.5]:
            with self.assertRaises(ValueError):build_request('SOLAR_CHARGE',watts)
        for seconds in [0,181,True,1.5]:
            with self.assertRaises(ValueError):build_request('SOLAR_CHARGE',1000,seconds)
        for mode in ['FORCED_DISCHARGE','GRID_EXPORT','unknown']:
            with self.assertRaises(ValueError):build_request(mode,1000)

    def test_grid_charge_target_and_bounds(self):
        command=build_request('GRID_CHARGE',500,180,target_soc=90)
        self.assertEqual(command['target_soc'],90)
        self.assertEqual(command['duration_s'],180)
        self.assertEqual(command['expires_ms']-command['issued_ms'],225000)
        with self.assertRaises(ValueError):build_request('GRID_CHARGE',0)
        for target in (0,101,True,90.5):
            with self.assertRaises(ValueError):build_request('GRID_CHARGE',500,target_soc=target)

    def test_active_operating_limit_is_checked_before_submission(self):
        from gateway.energy_control import submit
        with patch('gateway.energy_control.status',return_value={'max_charge_w':1000}):
            with self.assertRaises(ValueError):submit('GRID_CHARGE',1001)

    def test_night_deadline_cannot_extend_for_activation(self):
        from gateway.energy_control import submit,REQUIRED_GATES
        ready={'max_charge_w':1000,'writes_enabled':True,'native_transport_bound':True,
               'observed_ms':100000,'min_discharge_soc':0,'qualification':{k:True for k in REQUIRED_GATES}}
        ready['qualification']['grid_charging_verified']=True
        with tempfile.TemporaryDirectory() as directory,patch('gateway.energy_control.time.time',return_value=100),patch('gateway.energy_control.status',return_value=ready):
            submit('GRID_CHARGE',1000,180,folder=directory,source='night_schedule',not_after_ms=280000)
            command=json.loads((Path(directory)/'growatt-command.json').read_text())
            self.assertEqual(command['expires_ms'],280000)
            self.assertEqual(command['duration_s'],180)
            with self.assertRaises(ValueError):submit('GRID_CHARGE',1000,folder=directory,not_after_ms=100000)

    def test_ready_requires_fresh_equipment_and_current_qualifications(self):
        from gateway.energy_control import controls_ready,REQUIRED_GATES
        data={'writes_enabled':True,'native_transport_bound':True,'observed_ms':100000,
              'min_discharge_soc':0,'qualification':{k:True for k in REQUIRED_GATES}}
        data['qualification']['inverter_discharge_reserve_verified']=False
        self.assertTrue(controls_ready(data,now_ms=101000))
        self.assertFalse(controls_ready(data,now_ms=116000))
        data['qualification']['crash_and_communication_fallback_verified']=False
        self.assertFalse(controls_ready(data,now_ms=101000))

    def test_cancel_and_stale_status_do_not_claim_applied_control(self):
        with self.assertRaises(ValueError):build_request('MONITOR',1000)
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(status(directory)['writes_enabled'])
            path=Path(directory)/'growatt-control-status.json'
            atomic_private_write(path,{'updated_ms':100000,'status':'shadow','writes_enabled':False})
            self.assertFalse(status(directory,now_ms=101000)['stale'])
            self.assertEqual(status(directory,now_ms=116000)['status'],'unavailable')

    def test_probe_has_finite_read_blocks_and_handles_exception_frames(self):
        port=MagicMock()
        frame=bytes((1,3,2))+struct.pack('>H',305)
        # protocol_revision is an explicit seven-word read, never a write.
        values=[21057,16705,12600,12599,12339,0,305]
        frame=bytes((1,3,14))+struct.pack('>7H',*values)
        port.read.side_effect=[frame[:3],frame[3:]+crc(frame)]
        result=read_block(port,'protocol_revision')
        self.assertEqual(result['holding_registers']['88'],305)
        self.assertEqual(port.write.call_args.args[0][:2],bytes((1,3)))
        with self.assertRaises(KeyError):read_block(port,'arbitrary_write')
        error=bytes((1,0x83,2))
        port.read.side_effect=[error,crc(error)]
        self.assertEqual(read_block(port,'firmware')['exception_code'],2)

    def test_cli_cannot_queue_commands_with_missing_physical_qualification(self):
        unqualified={'writes_enabled':True,'native_transport_bound':True,'stale':False,'qualification':{}}
        with patch('gateway.energy_control.status',return_value=unqualified), \
                patch('gateway.energy_control.atomic_private_write') as write, \
                patch('sys.argv',['energy_control','--mode','SOLAR_CHARGE','--charge-w','2990']):
            with self.assertRaises(SystemExit):main()
            write.assert_not_called()


if __name__=='__main__':unittest.main()
