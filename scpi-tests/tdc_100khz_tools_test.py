"""Offline checks for the 100 kHz notebook; no VISA or socket sessions."""
import ast
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tdc_100khz_tools import restore_bundled_candidate, require_complete, screen_offsets
from tdc_rigol_tools import summarize

HERE=Path(__file__).parent
BUNDLE=HERE.parent/'100kHz_demo'


class HundredKhzTests(unittest.TestCase):
    def image(self):
        image=json.loads((BUNDLE/'v18_luts.json').read_text())['image']
        image.update(bitstream_label='v18_20261026_140711',implementation_wns_ns=.008)
        return image

    def test_restore_reconciles_metadata_and_preserves_provenance(self):
        original=(BUNDLE/'v18_luts.json').read_bytes()
        image=self.image()
        restored=restore_bundled_candidate(BUNDLE,image,image['bitstream_label'])
        self.assertEqual(restored['image'],image)
        self.assertIsNone(restored['restored_provenance']['original_image']['implementation_wns_ns'])
        self.assertEqual(restored['tables'],json.loads(original)['tables'])
        self.assertEqual((BUNDLE/'v18_luts.json').read_bytes(),original)

    def test_restore_rejects_wrong_route_or_interface(self):
        image=self.image()
        with self.assertRaises(ValueError):restore_bundled_candidate(BUNDLE,image,'different-route')
        image['taps']=256
        with self.assertRaises(ValueError):restore_bundled_candidate(BUNDLE,image,image['bitstream_label'])

    def test_restore_rejects_corrupted_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            for name in ('v18_calibration_manifest.json','v18_luts.json'):
                (folder/name).write_bytes((BUNDLE/name).read_bytes())
            with (folder/'v18_luts.json').open('ab') as f:f.write(b' ')
            image=self.image()
            with self.assertRaisesRegex(ValueError,'checksum'):
                restore_bundled_candidate(folder,image,image['bitstream_label'])

    def test_offset_screen_retains_failed_starts_and_restores_configuration(self):
        class Bench:
            def __init__(self,directory):
                self.directory=Path(directory);self.image={'minimum_period_ns':40}
                self.config={'phase_retries':True,'frame_offset_ns':12,'frame_offsets_by_period_ns':{40:8}}
            def acquire(self,label,frequency,width,frames,fine):
                self.last_retry=self.config['phase_retries']
                offset=self.config['frame_offsets_by_period_ns'][10000]
                return dict(summary=dict(complete_pulses=frames if offset==1000 else 0,
                    total_frames=frames,flag_counts={}),capture_files={},acquisition_ok=True,cleanup_errors=[])
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
            bench=Bench(directory);original=copy.deepcopy(bench.config)
            result=screen_offsets(bench,100000,500.2,[0,1000],frames=512,repeats=2)
            self.assertEqual(len(result['attempts']),4)
            self.assertEqual(result['ranking'][0]['offset_ns'],1000)
            self.assertFalse(bench.last_retry);self.assertEqual(bench.config,original)

    def test_offset_failure_restores_configuration(self):
        class Bench:
            image={'minimum_period_ns':40}
            config={'phase_retries':True}
            def acquire(self,*args,**kwargs):raise RuntimeError('injected')
        with tempfile.TemporaryDirectory() as directory:
            bench=Bench();bench.config=dict(bench.config);bench.directory=Path(directory)
            with self.assertRaises(RuntimeError):screen_offsets(bench,100000,500.2,[0],repeats=1)
            self.assertEqual(bench.config,{'phase_retries':True})
            self.assertIn('injected',json.loads((bench.directory/'100khz_offset_screen.json').read_text())['failure'])

    def test_notebook_unexecuted_and_100khz_plan(self):
        book=json.loads((HERE/'tdc_rigol_v18_100khz_characterisation.ipynb').read_text(encoding='utf-8'))
        settings={}
        for cell in book['cells']:
            if cell['cell_type']=='code':
                ast.parse(cell['source']);self.assertEqual(cell['outputs'],[])
                self.assertIsNone(cell['execution_count'])
                if cell['source'].startswith('# Single source of configuration'):exec(cell['source'],settings)
        self.assertEqual(settings['TARGET_HZ'],100000)
        self.assertEqual(settings['PERIOD_NS'],10000)
        self.assertEqual(settings['AWG_CHANNEL'],1)
        self.assertFalse(set(settings['TRAIN_WIDTHS_NS'])&set(settings['VALIDATE_WIDTHS_NS']))
        self.assertLess(max(settings['TRAIN_WIDTHS_NS']),settings['PERIOD_NS'])

    def test_complete_guard_rejects_partial_burst(self):
        capture=dict(label='partial',reference_ns=20,acquisition_ok=True,cleanup_errors=[],
            records=[(i+1,1|512|(1<<16)|(1<<24),5,0,0,20000) for i in range(128)])
        capture['summary']=summarize(capture)
        self.assertIs(require_complete(capture,fine=True),capture)
        capture['records'][0]=(1,6,0,0,0,0)
        capture['summary']=summarize(capture)
        with self.assertRaisesRegex(RuntimeError,'Incomplete burst'):require_complete(capture)

    def test_complete_guard_requires_every_fine_record(self):
        capture=dict(label='coarse fallback',reference_ns=20,acquisition_ok=True,cleanup_errors=[],
            records=[(i+1,1|512|(1<<16)|(1<<24),5,0,0,20000) for i in range(128)])
        capture['records'][0]=(1,1|256|(1<<16)|(1<<24),5,0,0,20000)
        capture['summary']=summarize(capture)
        with self.assertRaisesRegex(RuntimeError,'every frame'):require_complete(capture,fine=True)


if __name__=='__main__':unittest.main()
