from pathlib import Path
import hashlib,json,zipfile
root=Path(__file__).resolve().parent
app=root.parents[1]
repo=app.parent/'fpgaprj/RedPitaya-FPGA'
out=app/'build/tdc-v19-review';out.mkdir(parents=True,exist_ok=True)
sources={p.relative_to(root).as_posix():p for directory in ['prj','tbn'] for p in (root/directory).rglob('*') if p.is_file()}
for p in (repo/'prj/v0.94/rtl').glob('tdc_*.sv'):sources.setdefault(p.relative_to(repo).as_posix(),p)
for relative in ['prj/v0.94/rtl/pulse_gen.sv','rtl/sys_bus_cdc.sv','rtl/classic/red_pitaya_asg_ch.sv',
                 'tbn/tb_tdc_top.sv','tbn/tb_tdc_pulse_width.sv','tbn/tb_pulse_gen.sv',
                 'tbn/tdc_carry_chain_logic_model.sv','tbn/tdc_carry_chain_timing_model.sv']:
    sources.setdefault(relative,repo/relative)
manifest=[dict(path='RedPitaya-FPGA/'+relative,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for relative,p in sorted(sources.items())]
bundle=out/'tdc-v19-source-bundle.zip'
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
    for relative,p in sorted(sources.items()):z.write(p,'RedPitaya-FPGA/'+relative)
    z.writestr('source_manifest.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(bundle) as z:
    for row in manifest:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
(out/'bundle_manifest.json').write_text(json.dumps(manifest,indent=2))
print(f'PASS: {len(manifest)} source files packaged and SHA256 verified: {bundle}')
