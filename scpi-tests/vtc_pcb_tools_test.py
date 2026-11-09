"""Offline VTC stimulus/protocol and notebook flow tests; no live instruments."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import matplotlib
matplotlib.use('Agg')
from vtc_pcb_tools import prepare_stimulus, configure_stimulus, capture_vtc

REPO=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO/'100kHz_demo'))
from test_demo_offline import FakeRP


class VtcRP(FakeRP):
    def write(self, command):
        if command.startswith('TDC:WIDTH:ARM '):
            if not self.pulse or any(self.outputs.values()):
                raise AssertionError('Need launch ON, analogue FPGA outputs OFF')
            self.trace.append(command)
            self.count=int(command.split()[-1])
        else:super().write(command)
    def close(self):self.closed=True


class FakeAWG:
    def __init__(self, config=None):
        self.channel=1;self.source=':SOURce1';self.output=':OUTPut1'
        self.trace=[];self.enabled=False;self.closed=False
        self.identity='RIGOL,DG5502 Pro,TEST,1';self.startup_errors=[]
        self.reply='DC,0,0,0.5,0';self.arb_file='';self.last_settings=None
    def write(self, command):
        self.trace.append(command)
        if ':APPLy:' in command:
            kind,values=command.split(':APPLy:')[1].split(' ',1)
            kinds={'DC':'DC','SINusoid':'SIN','SQUare':'SQU','RAMP':'RAMP','TRIangle':'TRI','ARBitrary':'ARB'}
            self.reply=kinds[kind]+','+values.replace('DEFault','0')
        if command.startswith(':MMEMory:LOAD:DATA '):self.arb_file=command.split(',')[1]
    def ask(self, command):
        self.trace.append(command)
        if command=='*OPC?':return '1'
        if command.endswith(':APPLy?'):return '"'+self.reply+'"'
        if command.endswith(':FUNCtion:ARBitrary?'):return self.arb_file
        raise AssertionError(command)
    def off(self):self.enabled=False;self.trace.append('OFF')
    def on(self):self.enabled=True;self.trace.append('ON')
    def close(self):self.closed=True


class VtcTests(unittest.TestCase):
    def test_all_standard_waveforms_off_after_configuration(self):
        for kind in ('DC','SINE','SQUARE','RAMP','TRIANGLE'):
            awg=FakeAWG()
            info=configure_stimulus(awg,dict(kind=kind,offset_v=.5,vpp=.2,frequency_hz=100),0,1)
            self.assertEqual(info['kind'],kind);self.assertFalse(awg.enabled)
            self.assertFalse(any('PULSE:' in x for x in awg.trace))

    def test_voltage_and_sample_validation_before_any_io(self):
        for spec in [dict(kind='SINE',offset_v=.9,vpp=.4,frequency_hz=100),
                     dict(kind='SINE',offset_v=.5,vpp=.2,frequency_hz=50000),
                     dict(kind='DC',offset_v=float('nan')),
                     dict(kind='ARB',offset_v=.5,vpp=.2,frequency_hz=100,samples=[2]*32)]:
            awg=FakeAWG()
            with self.assertRaises(ValueError):configure_stimulus(awg,spec,0,1)
            self.assertEqual(awg.trace,[])

    def test_arb_upload_roundtrip_and_chunk_flags(self):
        samples=np.linspace(-1,1,32).tolist()
        spec=dict(kind='ARB',offset_v=.5,vpp=.4,frequency_hz=100,samples=samples)
        info,expected=prepare_stimulus(spec,0,1)
        awg=FakeAWG();configure_stimulus(awg,spec,0,1)
        packets=[x for x in awg.trace if ':ARB:DATA:DAC ' in x]
        self.assertEqual(len(packets),16)
        self.assertIn(',HEADer,',packets[0]);self.assertIn(',END,',packets[-1])
        actual=[int(v) for packet in packets for v in packet.split(',',2)[2].split(',')]
        np.testing.assert_array_equal(actual,expected)
        self.assertEqual(len(actual),16384);self.assertEqual(info['source_points'],32)

    def test_readback_mismatch_rejected(self):
        class Bad(FakeAWG):
            def ask(self, command):
                return '"SIN,100,0.2,0.8,0"' if command.endswith(':APPLy?') else super().ask(command)
        with self.assertRaises(RuntimeError):
            configure_stimulus(Bad(),dict(kind='SINE',offset_v=.5,vpp=.2,frequency_hz=100),0,1)

    def run_notebook_acquisition(self, partial=False):
        book=json.loads((REPO/'scpi-tests'/'vtc_pcb_v18_100khz.ipynb').read_text())
        code=[''.join(c['source']) for c in book['cells'] if c['cell_type']=='code']
        scope={}
        with patch('socket.create_connection',side_effect=AssertionError('Live hardware')):
            exec(compile(code[0],'settings','exec'),scope)
            scope.update(FRAMES=4,RUN_DC_SWEEP=True,DC_LEVELS_V=[.3,.7])
            with contextlib.redirect_stdout(io.StringIO()):exec(code[1],scope)
        rp=VtcRP(partial=partial);awg=FakeAWG()
        scope['demo'].SCPI=lambda *args:rp
        scope['Rigol']=lambda config:awg
        with tempfile.TemporaryDirectory() as directory:
            scope['RESULTS_DIR']=Path(directory)
            with patch.object(scope['time'],'sleep'),contextlib.redirect_stdout(io.StringIO()):
                if partial:
                    with self.assertRaises(RuntimeError):exec(code[3],scope)
                else:exec(code[3],scope)
            run=scope['RUN_DIR']
            self.assertEqual(len(list(run.glob('*.csv'))),0 if partial else 3)
            session=json.loads((run/'session.json').read_text())
            self.assertEqual(session['attempts'],1 if partial else 3)
            self.assertEqual(bool(session['error']),partial)
        self.assertFalse(rp.pulse);self.assertFalse(any(rp.outputs.values()))
        self.assertTrue(rp.closed);self.assertFalse(awg.enabled);self.assertTrue(awg.closed)
        self.assertEqual(rp.trace.count('PULSE:TIMING 10000,5000'),1)
        self.assertEqual(sum(x.startswith('TDC:WIDTH:ARM ') for x in rp.trace),1 if partial else 3)
        self.assertEqual(sum(x.startswith('TDC:WIDTH:CALIBRATION:LUT:WRITE ') for x in rp.trace),16)
        self.assertEqual(sum(x.startswith('TDC:WIDTH:OFFSET ') for x in rp.trace),1)
        self.assertTrue(all(c['timing_topology']=='fpga_triggered_vtc_pcb' for c in scope['captures']))

    def test_complete_notebook_batch_and_dc_sweep(self):self.run_notebook_acquisition()
    def test_incomplete_stops_once_and_keeps_only_metadata(self):self.run_notebook_acquisition(partial=True)
    def test_reject_changed_fpga_frequency(self):
        rp=VtcRP();rp.period='20000,10000'
        with self.assertRaises(RuntimeError):capture_vtc(None,rp,4,{})
        self.assertFalse(any('ARM ' in x for x in rp.trace))


if __name__=='__main__':unittest.main()
