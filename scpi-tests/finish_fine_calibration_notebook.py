"""Finish the one-time notebook migration; this is not a hardware test runner."""

import json
import uuid
from pathlib import Path

path = Path(__file__).resolve().parent / 'tdc_external_square_test.ipynb'
notebook = json.loads(path.read_text(encoding='utf-8'))
if 'FIT_HOST_REFERENCE_OFFSET' in ''.join(notebook['cells'][2]['source']):
    raise SystemExit('Notebook already finished. Open tdc_external_square_test.ipynb to calibrate.')
if (notebook.get('metadata', {}).get('fine_calibration_revision') != '2026-10-19-v8-provisional'
        or len(notebook['cells']) != 23):
    raise SystemExit('Apply update_fine_calibration_notebook.py to the original notebook first; no changes made.')

def source(i):
    return ''.join(notebook['cells'][i]['source'])

def put(i, text):
    notebook['cells'][i]['source'] = text.splitlines(keepends=True)

put(2, source(2) + 'FIT_HOST_REFERENCE_OFFSET = False  # Keep OFF while assessing fine-LUT improvement.\n')
put(10, source(10) + '\nOptional: disabled by default with `FIT_HOST_REFERENCE_OFFSET = False`.\n'
    'The fine-LUT workflow does not need a fitted mean offset.\n')
put(11, 'if FIT_HOST_REFERENCE_OFFSET:\n' + ''.join('    ' + line for line in (source(11).rstrip() + '\n').splitlines(keepends=True)) +
    'else:\n    print("Skipping optional coarse reference-offset fit; continue to fine code-density collection.")\n')
put(19, source(19) + '\nThe default run performs a fresh validation with **no host offset**.\n'
    'Set `FIT_HOST_REFERENCE_OFFSET = True` only for the separate optional one-point reference experiment.\n')
put(20, 'if FIT_HOST_REFERENCE_OFFSET:\n' + ''.join('    ' + line for line in (source(20).rstrip() + '\n').splitlines(keepends=True)) + '''else:
    validation=capture_burst("07_independent_validation",fine=True)
    verify_fine_correction(validation,candidate)
    validation_raw=show_capture(validation)
    guard_reference_capture(validation,validation_raw)
    if validation_raw["fine_pulses"] < 0.95*validation_raw["accepted_pulses"]:
        raise RuntimeError("Fresh validation has too many coarse fallbacks; inspect fine-code quality")
    save_json(RUN_DIR/"07_validation_summary.json",dict(raw=validation_raw,provisional=True,host_offset_applied=False))
    print("No fitted reference offset was applied. Results remain provisional while timing fails.")
    print("Saved calibration records, LUTs, readback checks and validation in",RUN_DIR)
''')
put(6, source(6).replace('info = dict(bitstream_label=BITSTREAM_LABEL,',
    'info = dict(host=RP_IP,port=SCPI_PORT,bitstream_label=BITSTREAM_LABEL,'))

notebook['cells'].insert(21, dict(cell_type='markdown', metadata={}, source=[
    '### Interpreting this run\n', '\n',
    '- Roughly 50% complete frames is expected at these settings. Compare RISE/FALL valid fractions **among complete pulses** separately.\n',
    '- Any inconsistent raw record stops calibration; the CSV and audit are retained.\n',
    '- Each edge needs at least 50,000 accepted codes and 99% encoding validity, plus histogram coverage/stability checks.\n',
    '- More batches help sample statistics; they do not repair phase-dependent invalid codes or a failed capture path.\n',
    '- A precision ratio above 1 means the fine-eligible coarse data had greater standard deviation than the fresh fine data.\n',
    '- Check fresh widths at several duties (for example 30%, 50%, 70%) and another detuned frequency before broader use. Change the actual AWG and settings together. Keep the uploaded LUTs and use `capture_burst(..., fine=True)`; do not rerun preflight, which disables fine correction.\n',
    '- A later placed bitstream needs new calibration. Keep the saved image label, raw captures, LUTs and generator/scope references together.\n',
    '- Further background on uniform-phase code density: [TDC calibration research](https://pmc.ncbi.nlm.nih.gov/articles/PMC5424742/). Histogram gates cannot independently prove uniform phase.\n'
]))
for cell in notebook['cells']:
    cell.setdefault('id', uuid.uuid4().hex[:8])
path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
print('Fine-LUT comparison now leaves reference-offset fitting OFF by default.')
