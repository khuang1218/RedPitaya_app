import csv,json,tempfile,unittest
from pathlib import Path
from tdc_capture_cleanup import plan_cleanup,apply_cleanup

class CleanupTests(unittest.TestCase):
    def make(self,root,name,flags):
        p=root/'run'/f'{name}.json';p.parent.mkdir(exist_ok=True)
        raw=p.with_suffix('.csv')
        with raw.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['flags']);writer.writeheader()
            writer.writerows({'flags':v} for v in flags)
        c=dict(summary=dict(total_frames=len(flags),complete_pulses=sum(bool(v&1) for v in flags)),
               capture_files=dict(csv=str(raw),json=str(p)),awg_scpi_log=[{'large':'log'}])
        p.write_text(json.dumps(c));return p,raw
    def test_zero_only_preserves_partial_full_and_summary(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'results';root.mkdir()
            zero,raw=self.make(root,'0001',[6,6])
            partial,partial_raw=self.make(root,'0002',[1,6])
            full,full_raw=self.make(root,'0003',[1,1])
            before=[p.read_bytes() for p in (partial,partial_raw,full,full_raw)]
            plan=plan_cleanup(root);self.assertEqual(len(plan),1)
            result=apply_cleanup(root,plan,Path(d)/'audit')
            self.assertEqual(result['deleted_csv_files'],1);self.assertFalse(raw.exists())
            c=json.loads(zero.read_text());self.assertEqual(c['summary']['total_frames'],2)
            self.assertIsNone(c['capture_files']['csv']);self.assertNotIn('awg_scpi_log',c)
            self.assertEqual(before,[p.read_bytes() for p in (partial,partial_raw,full,full_raw)])
    def test_changed_file_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'results';root.mkdir()
            _,raw=self.make(root,'0001',[6]);plan=plan_cleanup(root)
            raw.write_text('flags\n1\n')
            with self.assertRaisesRegex(ValueError,'changed after inventory'):
                apply_cleanup(root,plan,Path(d)/'audit')
            self.assertTrue(raw.exists())
    def test_outside_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'results';root.mkdir()
            p,_=self.make(root,'0001',[6]);c=json.loads(p.read_text())
            outside=Path(d)/'outside.csv';outside.write_text('flags\n6\n')
            c['capture_files']['csv']=str(outside);p.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError,'escapes result root'):
                plan_cleanup(root)
            self.assertTrue(outside.exists())

if __name__=='__main__':unittest.main()
