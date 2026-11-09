from pathlib import Path
import tempfile,tkinter,re
root=Path(__file__).resolve().parent
out=root.parents[1]/'build/tdc-v19-review'
chains=['i_tdc0/i_width/i_carry','i_tdc0/i_width/i_fall_carry','i_tdc1/i_width/i_carry','i_tdc1/i_width/i_fall_carry']
for mode in ['valid','wrong_lane','gap','unplaced','missing']:
    with tempfile.TemporaryDirectory(prefix='audit_test_',dir=out) as directory:
        t=tkinter.Tcl()
        t.createcommand('current_design',lambda *args:'mock_design')
        t.createcommand('current_project',lambda *args:'mock_project')
        # Quiet successful 2048-row audits while retaining real Tcl file I/O.
        t.eval('rename puts audit_test_puts;proc puts {args} {if {[llength $args]>1} {audit_test_puts {*}$args}}')
        def cells(*args):
            f=args[-1];chain=next((c for c in chains if '*'+c+'/' in f),None)
            if chain is None:raise RuntimeError(f)
            if 'CARRY4' in f:
                return tuple(f'{chain}/gen_carry[{i}].gen_'+('first' if i==0 else 'next')+'.i_carry4' for i in range(128))
            n=511 if mode=='missing' and chain==chains[0] else 512
            return tuple(f'{chain}/gen_tap[{i}].i_tap_ff' for i in range(n))
        def prop(key,obj):
            if key=='DIRECTORY':return directory
            chain=next(c for c in chains if obj.startswith(c+'/'))
            i=int(re.search(r'\[(\d+)\]',obj)[1]);tap='gen_tap' in obj
            stage=i//4 if tap else i
            if key=='LOC':
                if mode=='unplaced' and chain==chains[0] and stage==0:return ''
                y=20+stage+(1 if mode=='gap' and chain==chains[0] and stage==50 else 0)
                return f'SLICE_X{10+chains.index(chain)}Y{y}'
            if key=='BEL':
                if mode=='wrong_lane' and chain==chains[0] and i==17:return 'DFF'
                return 'SLICEM.'+['AFF','BFF','CFF','DFF'][i%4]
            raise RuntimeError(key)
        t.createcommand('get_cells',cells);t.createcommand('get_property',prop)
        try:t.call('source',(root/'prj/v0.94/scripts/audit_v19_sampler_layout.tcl').as_posix());passed=True
        except tkinter.TclError:passed=False
        assert passed==(mode=='valid'),mode
        if passed:
            report=next(Path(directory).glob('tdc_sampler_layout_*/placement.tsv'))
            assert len(report.read_text().splitlines())==2049
print('PASS: clean Tcl source invokes v19 audit; all2048 samplers checked; bad lane/gap/unplaced/missing rejected')
