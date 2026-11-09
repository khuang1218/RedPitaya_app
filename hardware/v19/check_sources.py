from pathlib import Path
import hashlib,json,tkinter,re
root=Path(__file__).resolve().parent
repo=root.parents[2]/'fpgaprj/RedPitaya-FPGA'
out=root.parents[1]/'build/tdc-v19-review';out.mkdir(parents=True,exist_ok=True)
tcl=tkinter.Tcl()
for p in [*root.rglob('*.tcl'),*root.rglob('*.xdc')]:
    if not int(tcl.call('info','complete',p.read_text())):raise RuntimeError(f'Incomplete Tcl: {p}')
# Evaluate flat XDC syntax with collection/property APIs mocked. This validates
# Tcl structure only; the external build checker validates actual netlist names.
for command in ['get_cells','get_pins','get_ports','get_clocks','current_design']:
    tcl.eval(f'proc {command} {{args}} {{return object}}')
for command in ['set_property','set_false_path','set_max_delay','create_clock','create_macro','update_macro']:
    tcl.eval(f'proc {command} {{args}} {{return {{}}}}')
for p in root.rglob('*.xdc'):tcl.call('source',p.as_posix())
text=(root/'prj/v0.94/rtl/red_pitaya_top_v19.sv').read_text()
assert text.count('.VERSION(8\'d19)')==2
assert all(f') i_tdc{i} (' in text for i in (0,1))
assert all(f' {name} ' not in text for name in ['i_scope','i_pid','i_ams','i_daisy','i_serlines_add','i_bnet_regs'])
assert '.I(spi_ldac_n)' in text and 'g==4) begin: dac_load' in text
assert 'i_dac_spi' in text and 'i_asg' in text and 'i_pulse_gen' in text
for i in range(2):
    layout=(root/'prj/v0.94/sdc/tdc_v19_sampler_layout.xdc').read_text()
    for edge in ['RISE','FALL']:assert f'create_macro TDC{i}_WIDTH_{edge}_SAMPLER' in layout
for name in ['tdc_pulse_width.sv','pulse_gen.sv','tdc_thermometer_encoder.sv','tdc_population_pipeline.sv']:
    assert not (root/'prj/v0.94/rtl'/name).exists(),'Datapath unexpectedly copied/modified'
files=[]
for p in sorted(root.rglob('*')):
    if p.is_file() and '__pycache__' not in str(p):
        files.append(dict(path=p.relative_to(root).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
retained=[]
for p in sorted((repo/'prj/v0.94/rtl').glob('tdc_*.sv')):
    if not (root/'prj/v0.94/rtl'/p.name).exists():
        retained.append(dict(path=p.relative_to(repo).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
for relative in ['prj/v0.94/rtl/pulse_gen.sv','rtl/classic/red_pitaya_asg_ch.sv']:
    p=repo/relative;retained.append(dict(path=relative,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(out/'source_manifest.json').write_text(json.dumps(dict(overlay=files,unchanged_datapaths=retained),indent=2))
print(f'PASS: Tcl structure/flat XDC syntax, v19 topology, four sampler macros; {len(retained)} unchanged datapath sources hashed')
