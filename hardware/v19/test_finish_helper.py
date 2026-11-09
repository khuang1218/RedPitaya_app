"""Execute the actual finalization Tcl with mocked Vivado APIs, never Vivado."""
from pathlib import Path
import tempfile
import tkinter

root = Path(__file__).resolve().parent
out = root.parents[1] / 'build/tdc-v19-review'
cases = ['valid', 'setup', 'hold', 'no_paths', 'drc', 'structure', 'audit',
         'running', 'route_missing', 'route_error', 'checkpoint_missing', 'postopt_incomplete']
for mode in cases:
    with tempfile.TemporaryDirectory(prefix='finish_test_', dir=out) as directory:
        work = Path(directory)
        impl = work / 'impl_1'
        impl.mkdir()
        if mode != 'route_missing':
            (impl / '.route_design.end.rst').touch()
        if mode == 'route_error':
            (impl / '.route_design.error.rst').touch()
        if mode != 'checkpoint_missing':
            (impl / 'red_pitaya_top_routed.dcp').touch()
        t = tkinter.Tcl()
        events = []
        def prop(key, obj):
            if key == 'DIRECTORY':
                return (impl if obj == 'impl_1' else work).as_posix()
            if key == 'STATUS':
                return {'running': 'Running route_design',
                        'postopt_incomplete': 'route_design Complete'}.get(mode, 'phys_opt_design (Post-Route) Complete')
            if key == 'STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED':
                return '1'
            if key == 'SLACK':
                return '-0.001' if mode == obj else ('0.017' if obj == 'setup' else '0.006')
            raise RuntimeError((key, obj))
        t.createcommand('get_property', prop)
        t.createcommand('current_project', lambda *a: 'project')
        t.createcommand('current_design', lambda *a: 'design')
        t.createcommand('get_runs', lambda *a: 'impl_1')
        t.createcommand('list_property', lambda *a: ('STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED',))
        def event(name):
            def record(*a):
                events.append((name, a))
                return ''
            return record
        for name in ['close_design', 'open_run', 'report_timing_summary', 'report_drc',
                     'report_utilization', 'set_property', 'write_bitstream']:
            t.createcommand(name, event(name))
        t.createcommand('get_timing_paths', lambda *a: '' if mode == 'no_paths' else
                        ('setup' if a[a.index('-delay_type') + 1] == 'max' else 'hold'))
        t.createcommand('get_drc_violations', lambda *a: 'error1' if mode == 'drc' else '')
        t.setvar('test_mode', mode)
        t.eval('''
            rename source real_source
            proc source {args} {
                set filename [lindex $args end]
                set name [file tail $filename]
                if {$name eq "check_v19_constraints.tcl"} {
                    if {$::test_mode eq "structure"} {error "Structural check failed"}
                    return
                }
                if {$name eq "audit_v19_sampler_layout.tcl"} {
                    if {$::test_mode eq "audit"} {error "Physical audit failed"}
                    return
                }
                real_source {*}$args
            }
            proc puts {args} {}
        ''')
        try:
            t.call('source', (root / 'prj/v0.94/scripts/finish_tdc_v19.tcl').as_posix())
            passed = True
        except tkinter.TclError:
            passed = False
        assert passed == (mode == 'valid'), (mode, t.eval('set errorInfo') if not passed else events)
        writes = [a for name, a in events if name == 'write_bitstream']
        assert len(writes) == (1 if mode == 'valid' else 0), (mode, writes)
        if passed:
            assert writes[0] == ('-force', '-bin_file', (impl / 'red_pitaya_v19.bit').as_posix())
            assert [name for name, _ in events].index('open_run') < [name for name, _ in events].index('write_bitstream')
print('PASS: actual finish Tcl writes exact v19 filename; 11 failure fixtures block output; no rebuild APIs used')
