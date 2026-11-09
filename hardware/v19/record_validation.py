from pathlib import Path
import hashlib,json
app=Path(__file__).resolve().parents[2]
out=app/'build/tdc-v19-review'
logs=[*(f'spi_hold{i}.log' for i in (1,2,3)),*(f'dual_hold{i}.log' for i in (1,2,3)),
      'legacy_v19.log','fine25.log',*(f'pulse_hold{i}.log' for i in (1,2,3)),'legacy.log']
passed={}
for name in logs:
    p=out/name
    assert 'PASS' in p.read_text() and 'FATAL' not in p.read_text(),name
    passed[name]=hashlib.sha256(p.read_bytes()).hexdigest()
elab=(app/'build/v19_elaboration.log').read_text()
assert '0 errors, 17 warnings' in elab
manifest=json.loads((out/'bundle_manifest.json').read_text())
result=dict(version=19,source_installed=True,vivado_run=False,bitstream_generated=False,
            board_programmed=False,elaboration=dict(sources=141,errors=0,warnings=17,generated_PS_IP_external=True),
            passed_simulation_logs=passed,bundle_source_count=len(manifest),
            limitations=['Routed utilization, timing, CDC, DRC and actual sampler placement require external Vivado.',
                         'Logic models do not establish physical precision or calibration.',
                         'V19 full 16384-record depth not rerun; unchanged memory datapath retains prior v18 evidence.',
                         'SPI register sequencer has no autonomous waveform queue or measurement-trigger synchronization.',
                         'Software/API/SCPI changes and removal of the artificial 50% duty restriction remain deferred.'])
(out/'v19_validation.json').write_text(json.dumps(result,indent=2))
print(f'PASS: {len(passed)} simulation logs and 141-source elaboration recorded; external timing unverified')
