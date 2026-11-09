"""Offline protocol/control tests. No sockets or board commands are used.

Run from this folder or the repository: python -m unittest discover -s 100kHz_demo
Requires the notebook's NumPy/Matplotlib dependencies.
"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
import matplotlib
matplotlib.use('Agg')

NOTEBOOK=Path(__file__).with_name('100kHz_matrix_demo.ipynb')
book=json.loads(NOTEBOOK.read_text(encoding='utf-8'))
ns={}
# Every code cell must be safe to run offline: imports/settings/definitions.
# Any accidental connection introduced in a future edit fails this import.
with patch('socket.create_connection',side_effect=AssertionError('Hardware connection in helpers-only notebook')):
    for cell in book['cells']:
        if cell['cell_type']=='code':
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(''.join(cell['source']),str(NOTEBOOK),'exec'),ns)

class FakeRP:
    def __init__(self, *, partial=False, fail_arm=False, bad_width=False, version=18, bad_readback=False):
        self.outputs={1:False,2:False};self.pulse=False;self.trace=[]
        self.period='10000,5000';self.offset=0;self.fine=False;self.count=0
        self.channels={(ch,key):value for ch in (1,2) for key,value in
                       {'FUNC':'SINE','VOLT':'0.8','VOLT:OFFS':'0','FREQ:FIX':'1000'}.items()}
        self.partial=partial;self.fail_arm=fail_arm;self.bad_width=bad_width
        self.version=version;self.bad_readback=bad_readback;self.closed=False
        self.tables={edge:[0]*512 for edge in ('RISE','FALL')}
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def write(self,command):
        self.trace.append(command)
        if command.startswith('OUTPUT:STATE'):self.outputs={1:command.endswith('ON'),2:command.endswith('ON')}
        elif match:=re.match(r'OUTPUT([12]):STATE (ON|OFF)',command):self.outputs[int(match[1])]=match[2]=='ON'
        elif command.startswith('PULSE:OUTPUT '):self.pulse=command.endswith('ON')
        elif command.startswith('PULSE:TIMING '):self.period=command.split(' ',1)[1]
        elif command.startswith('TDC:WIDTH:OFFSET '):self.offset=int(command.split()[-1])
        elif command.startswith('TDC:WIDTH:CALIBRATION:ACTIVATE '):self.fine=command.endswith('ON')
        elif command.startswith('TDC:WIDTH:CALIBRATION:LUT:WRITE '):
            edge,start,*values=command.split(' ',1)[1].split(',');start=int(start)
            self.tables[edge][start:start+len(values)]=list(map(int,values))
        elif command.startswith('TDC:WIDTH:ARM '):
            if self.fail_arm:raise RuntimeError('injected arm failure')
            if not self.pulse or not all(self.outputs.values()):raise AssertionError('ARM before sources')
            self.count=int(command.split()[-1])
        elif match:=re.match(r'SOUR([12]):([^ ]+) (.+)',command):self.channels[int(match[1]),match[2]]=match[3]
    def ask(self,command):
        self.trace.append(command)
        basic={'TDC:WIDTH:VERSION?':str(self.version),'TDC:WIDTH:TICK?':'4000','TDC:TAPS?':'512',
            'TDC:WIDTH:CAPACITY?':'16384','TDC:WIDTH:MINIMUM:PERIOD?':'40',
            'PULSE:PIN?':'DIO1_P','TDC:INPUT?':'SINGLE','TDC:WIDTH:STATUS?':'8',
            'PULSE:TIMING?':self.period,'PULSE:PERIOD?':self.period.split(',')[0],'TDC:WIDTH:OFFSET?':str(self.offset),
            'TDC:WIDTH:COUNT?':str(self.count),'PULSE:OUTPUT?':str(int(self.pulse)),
            'TDC:WIDTH:CALIBRATION:ACTIVATE?':str(int(self.fine))}
        if command in basic:return basic[command]
        if match:=re.fullmatch(r'OUTPUT([12]):STATE\?',command):return str(int(self.outputs[int(match[1])]))
        if match:=re.fullmatch(r'SOUR([12]):(.+)\?',command):
            result=self.channels[int(match[1]),match[2]]
            return '0.7' if self.bad_readback and match[2]=='VOLT:OFFS' else result
        if command.startswith('TDC:WIDTH:CALIBRATION:LUT:READ? '):
            edge,start,count=command.split(' ',1)[1].split(',')
            return ','.join(map(str,self.tables[edge][int(start):int(start)+int(count)]))
        if command.startswith('TDC:WIDTH:DATA? '):
            start,count=map(int,command.split(' ',1)[1].split(','));rows=[]
            for i in range(start,start+count):
                valid=not(self.partial and i==self.count-1)
                flags=(1|(512 if self.fine else 256)|(1<<16)|(1<<24)) if valid else 6
                width=8000+(self.tables['RISE'][0]-self.tables['FALL'][0] if self.fine else 0)
                if self.bad_width:width+=1
                rows.append(f'{i+1},{flags},{2 if valid else 0},0,0,{width if valid else 0}')
            return ';'.join(rows)
        raise AssertionError('Unmocked query: '+command)

class DemoTests(unittest.TestCase):
    def test_fixed_pcb_return_window(self):
        check=ns['check_pcb_return_window']
        self.assertEqual(check(100,120,2000)['fall_margin_ns'],7880)
        self.assertEqual(check(100,120,2000,offset_ns=40)['rise_margin_ns'],60)
        # Both boundaries are strict: a guard alone is not spare margin.
        for args,kwargs in [((8,20,100),{}),((100,120,9872),{}),
                            ((100,120,100),{'offset_ns':100}),
                            ((120,100,100),{}),((100,float('nan'),100),{})]:
            with self.assertRaises(ValueError):check(*args,**kwargs)

    def calibration(self):
        return dict(image=dict(width_version=18,tick_ps=4000,taps=512),input='SINGLE',
            ready=True,provisional=False,quality={e:dict(errors=[]) for e in ('RISE','FALL')},
            tables={'RISE':[100]*512,'FALL':[300]*512})

    def prepare(self,rp):
        image=ns['prepare_tdc'](rp)
        ns['configure_launch'](rp,10000)
        ns['set_frame_offset'](rp,400)
        calibration=self.calibration()
        ns['upload_luts'](rp,calibration)
        self.assertFalse(rp.fine)  # upload and activation are deliberately separate
        ns['enable_fine_mode'](rp)
        ns['initialize_weights'](rp)
        ns['set_dc_weight'](rp,1,.2)
        ns['set_dc_weight'](rp,2,.4)
        ns['start_weights'](rp)
        ns['start_launch'](rp)
        return calibration

    def capture_then_stop(self,rp):
        calibration=self.prepare(rp)
        with rp:
            try:
                result=ns['capture_burst'](rp,130,calibration)
            finally:
                cleanup=ns['stop_outputs'](rp)
        result['cleanup_errors']=cleanup
        if cleanup:result['success']=False
        with tempfile.TemporaryDirectory() as directory:
            files=ns['save_capture'](result,directory)
            metadata=json.loads(Path(files['json']).read_text())
            csv_count=len(list(Path(directory).glob('*.csv')))
        self.assertFalse(rp.pulse);self.assertFalse(any(rp.outputs.values()))
        self.assertTrue(rp.closed)
        return result,metadata,csv_count

    def test_helpers_only_and_no_monolithic_runner(self):
        self.assertNotIn('run_demo',ns)
        for cell in book['cells']:
            if cell['cell_type']=='code':
                self.assertIsNone(cell['execution_count']);self.assertEqual(cell['outputs'],[])

    def test_fine_capture_and_chunked_readout(self):
        rp=FakeRP();result,metadata,count=self.capture_then_stop(rp)
        self.assertTrue(result['success']);self.assertEqual(count,1)
        self.assertEqual(result['summary']['valid'],130)
        self.assertAlmostEqual(result['summary']['mean_ns'],7.8)
        self.assertIn('TDC:WIDTH:DATA? 128,2',rp.trace)
        self.assertTrue(metadata['raw_records_saved']);self.assertNotIn('records',metadata)

    def test_repeated_captures_do_not_upload_or_reconfigure(self):
        rp=FakeRP();calibration=self.prepare(rp);rp.trace=[]
        for _ in range(2):self.assertTrue(ns['capture_burst'](rp,4,calibration)['success'])
        self.assertFalse(any(':LUT:' in cmd for cmd in rp.trace))
        self.assertFalse(any(cmd.startswith('TDC:WIDTH:OFFSET ') for cmd in rp.trace))
        self.assertFalse(any(cmd.startswith(('SOUR','PULSE:OUTPUT','PULSE:TIMING ')) for cmd in rp.trace))
        self.assertTrue(rp.pulse);self.assertTrue(all(rp.outputs.values()))
        self.assertTrue(rp.fine);self.assertEqual(rp.offset,400)
        self.assertEqual(ns['stop_outputs'](rp),[])
        self.assertTrue(rp.fine);self.assertEqual(rp.offset,400)

    def test_partial_saves_summary_only(self):
        result,metadata,count=self.capture_then_stop(FakeRP(partial=True))
        self.assertFalse(result['success']);self.assertEqual(count,0)
        self.assertEqual(metadata['summary']['valid'],129);self.assertEqual(len(result['records']),130)
        self.assertIsNone(metadata['capture_files']['csv'])

    def test_capture_failure_and_explicit_finally_cleanup(self):
        result,_,count=self.capture_then_stop(FakeRP(fail_arm=True))
        self.assertFalse(result['success']);self.assertEqual(count,0)
        self.assertTrue(any('injected arm' in e for e in result['errors']))

    def test_wrong_version_is_rejected(self):
        rp=FakeRP(version=17)
        with self.assertRaises(RuntimeError):ns['prepare_tdc'](rp)
        self.assertFalse(rp.pulse);self.assertFalse(any(rp.outputs.values()))

    def test_weight_readback_mismatch(self):
        with self.assertRaises(RuntimeError):ns['set_dc_weight'](FakeRP(bad_readback=True),1,.2)

    def test_bad_width_arithmetic_is_rejected(self):
        result,_,count=self.capture_then_stop(FakeRP(bad_width=True))
        self.assertFalse(result['success']);self.assertEqual(count,0)
        self.assertEqual(result['summary']['integrity_error_count'],130)

    def test_invalid_weight_voltage_sends_nothing(self):
        rp=FakeRP()
        with self.assertRaises(ValueError):ns['set_dc_weight'](rp,1,1.2)
        with self.assertRaises(ValueError):ns['set_dynamic_weight'](rp,1,'SINE',100,.5,.8)
        self.assertEqual(rp.trace,[])

    def test_dynamic_weight_programs_asg_only(self):
        rp=FakeRP();ns['set_dynamic_weight'](rp,1,'SINE',100,.1,.3)
        self.assertIn('SOUR1:FUNC SINE',rp.trace);self.assertIn('SOUR1:VOLT 0.1',rp.trace)
        self.assertFalse(any(rp.outputs.values()));self.assertFalse(rp.pulse)
        self.assertFalse(any(cmd.startswith('TDC:') for cmd in rp.trace))

    def test_read_qualified_file_and_upload_tables(self):
        candidate=self.calibration();rp=FakeRP()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'luts.json';path.write_text(json.dumps(dict(candidate=candidate)))
            calibration=ns['read_calibration'](path)
            ns['upload_luts'](rp,calibration)
        self.assertEqual(rp.tables,candidate['tables']);self.assertFalse(rp.fine)
        ns['enable_fine_mode'](rp);self.assertTrue(rp.fine)

    def test_no_capture_in_coarse_mode(self):
        rp=FakeRP()
        with self.assertRaises(RuntimeError):ns['capture_burst'](rp,4,self.calibration())
        self.assertFalse(any(cmd.startswith('TDC:WIDTH:ARM ') for cmd in rp.trace))

    def test_tcp_fragmentation_and_error_queue(self):
        class Socket:
            def __init__(self):self.fragments=iter([b'12',b'3\r',b'\n0,"No error"\r\n']);self.sent=[]
            def sendall(self,data):self.sent.append(data)
            def recv(self,n):return next(self.fragments)
            def close(self):pass
        client=ns['SCPI'].__new__(ns['SCPI']);client.sock=Socket();client.buffer=bytearray()
        self.assertEqual(client.ask('TDC:WIDTH:COUNT?'),'123')
        self.assertEqual(client.sock.sent[-1],b'SYST:ERR:NEXT?\r\n')

    def test_signed_fine_corrections(self):
        flags=1|512|(1<<16)|(1<<24)
        rows=[dict(cycle_id=1,flags=flags,coarse_ticks=2,rise_raw=0,fall_raw=0,width_ps=7800),
              dict(cycle_id=2,flags=flags,coarse_ticks=2,rise_raw=1,fall_raw=1,width_ps=8200)]
        tables={'RISE':[100,300],'FALL':[300,100]}
        self.assertTrue(ns['summarize_records'](rows,2,fine=True,tables=tables)['all_valid'])
        rows[0]['width_ps']+=131072
        self.assertFalse(ns['summarize_records'](rows,2,fine=True,tables=tables)['all_valid'])

    def test_documented_flow_with_fake_board(self):
        flow=next(c['source'] for c in book['cells'] if c['cell_type']=='markdown' and '### One explicit sequence' in c['source'])
        code=re.search(r'```python\n(.*?)\n```',flow,re.S)[1]
        rp=FakeRP()
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'candidate.json';file.write_text(json.dumps(self.calibration()))
            scope=dict(ns,SCPI=lambda *args:rp,CALIBRATION_FILE=file,FRAMES=4,
                       RESULTS_DIR=Path(directory)/'results',plot_capture=lambda result:None)
            with patch.object(ns['time'],'sleep'),contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code,'documented_flow','exec'),scope)
            self.assertTrue(scope['result']['success'])
            self.assertEqual(scope['result']['timing_topology'],'fpga_triggered_pcb')
            self.assertEqual(scope['result']['automatic_retries'],0)
            self.assertEqual(rp.trace.count('TDC:WIDTH:ARM 4'),1)
            self.assertEqual(scope['offset_ns'],0)
            self.assertEqual(len(list((Path(directory)/'results').glob('*.csv'))),1)
        self.assertTrue(rp.closed);self.assertFalse(rp.pulse);self.assertFalse(any(rp.outputs.values()))

    def test_bundled_files_and_offset_qualification(self):
        folder=NOTEBOOK.parent
        manifest=json.loads((folder/'v18_calibration_manifest.json').read_text())
        for name,digest in manifest['files_sha256'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),digest)
        self.assertEqual(manifest['original_lut_file_sha256'],manifest['files_sha256']['v18_luts.json'])
        offsets=json.loads((folder/'v18_frame_offsets.json').read_text())
        self.assertNotIn('10000',offsets['offsets_by_period_ns'])
        self.assertIsNone(offsets['width_bias_offset_ns'])
        self.assertEqual(ns['read_frame_offset'](folder/'v18_frame_offsets.json',68),12)
        with contextlib.redirect_stdout(io.StringIO()) as notice:
            self.assertEqual(ns['read_frame_offset'](folder/'v18_frame_offsets.json',10000),0)
        self.assertIn('UNVERIFIED',notice.getvalue())

    def test_bundle_copied_to_another_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);copied=root/'100kHz_demo';copied.mkdir()
            for name in ('v18_luts.json','v18_frame_offsets.json','v18_calibration_manifest.json'):
                shutil.copyfile(NOTEBOOK.parent/name,copied/name)
            original_cwd=Path.cwd()
            try:
                for cwd in (root,copied):
                    os.chdir(cwd);scope={}
                    with patch('socket.create_connection',side_effect=AssertionError('Unexpected connection')):
                        for cell in book['cells']:
                            if cell['cell_type']=='code':exec(compile(cell['source'],'copied_notebook','exec'),scope)
                    self.assertEqual(scope['CALIBRATION_FILE'].resolve(),copied/'v18_luts.json')
                    calibration=scope['read_calibration'](scope['CALIBRATION_FILE'])
                    rp=FakeRP();scope['upload_luts'](rp,calibration);scope['enable_fine_mode'](rp)
                    self.assertEqual(rp.tables,calibration['tables']);self.assertTrue(rp.fine)
                    self.assertEqual(scope['read_frame_offset'](scope['FRAME_OFFSETS_FILE'],68),12)
            finally:os.chdir(original_cwd)

if __name__=='__main__':unittest.main()
