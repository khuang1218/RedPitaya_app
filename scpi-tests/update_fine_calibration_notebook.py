"""One-time notebook migration; use tdc_external_square_test.ipynb for calibration."""

import json
import shutil
import uuid
from pathlib import Path

from local_data import local_data_root

root = Path(__file__).resolve().parents[1]
path = root / 'scpi-tests/tdc_external_square_test.ipynb'
notebook = json.loads(path.read_text(encoding='utf-8'))
if notebook.get('metadata', {}).get('fine_calibration_revision') == '2026-10-19-v8-provisional':
    raise SystemExit('Notebook already updated. Open tdc_external_square_test.ipynb to calibrate.')
if len(notebook['cells']) != 22 or notebook['cells'][7]['cell_type'] != 'markdown':
    raise SystemExit('Notebook layout differs from the original migration input; no changes made.')
backup = local_data_root() / 'build/tdc-calibration-backup/tdc_external_square_before_20261019.ipynb'
backup.parent.mkdir(parents=True, exist_ok=True)
if not backup.exists():
    shutil.copy2(path, backup)

def source(index):
    return ''.join(notebook['cells'][index]['source']).replace('\r\n', '\n')

def put(index, text):
    notebook['cells'][index]['source'] = text.splitlines(keepends=True)

intro = source(0)
intro = intro.replace(
    'Uses the **installed PWB v1 `TDC:WIDTH:*` commands**. No API, SCPI server, or HDL rebuild is needed.',
    'Uses the installed **PWB v1 `TDC:WIDTH:*` commands**; no rebuild is required to run this notebook.\n'
    'Newer servers expose `VERSION?` and `DATA:RAW?`; older servers use `DATA?` with the same host integrity checks.\n\n'
    '**Current image: October 19 BNET-disabled build, reported WNS -1.143 ns.**\n'
    'Measurements and LUTs from this run are **provisional** while implementation timing fails.\n'
    'Code-density calibration cannot repair capture/control timing violations. A later bitstream needs new LUTs.\n'
    'Historical notebook outputs were backed up under `build/tdc-calibration-backup/` in the app workspace; start with a fresh kernel.'
)
intro += '\n\nFor this run, manually set the independent AWG to **997 kHz, 50%, 3.3 Vpp, +1.65 V offset**.\n'
intro += 'Confirm 0–3.3 V at pin 7 using the scope. Expected HIGH is about **501.505 ns**.\n'
intro += 'Do not lock the AWG to the FPGA reference. The FPGA creates 1000 ns capture windows;\n'
intro += 'about half the windows should contain one complete pulse. Fine-code validity is a separate metric.\n'
intro += 'Run sections 1–4 first. Inspect baseline integrity and both edge histograms before section 5.\n'
put(0, intro)

config = source(2).replace('FREQUENCY_HZ = 100_003.0', 'FREQUENCY_HZ = 997_000.0')
config = config.replace('CAL_BATCHES = 12', 'CAL_BATCHES = 24')
config = config.replace('MIN_EDGE_SAMPLES = 20_000', 'MIN_EDGE_SAMPLES = 50_000')
config += '\n# Manual image identity: VERSION? identifies the interface, not a unique placed bitstream.\n'
config += 'BITSTREAM_LABEL = "2026-10-19 BNET disabled, routed WNS -1.143 ns"\n'
config += 'IMPLEMENTATION_WNS_NS = -1.143\n'
put(2, config)

helpers = source(3)
audit = '''def audit_records(records, taps, tick_ps=4000):
    counts = Counter()
    examples = []
    bad_count = 0
    frame_errors = sum(1 << bit for bit in (1, 2, 3, 4, 5, 10, 11, 12))
    for expected_id, row in enumerate(records, 1):
        frame_id, flags, coarse, rise, fall, width = map(int, row)
        errors = []
        if frame_id != expected_id: errors.append("frame_id")
        if rise >= taps or fall >= taps: errors.append("raw_index_range")
        if flags & 1:
            if flags & frame_errors: errors.append("VALID_with_frame_errors")
            mode = flags & (256 | 512)
            if mode not in (256, 512): errors.append("missing_or_conflicting_width_mode")
            both_fine_valid = bool((flags >> 16) & 1) and bool((flags >> 24) & 1)
            if bool(flags & 128) != (not both_fine_valid): errors.append("FINE_INVALID_mismatch")
            for shift in (16, 24):
                status = (flags >> shift) & 255
                if status & 1 and status & 0x1e: errors.append("fine_status_conflict")
            coarse_ps = coarse * tick_ps
            if coarse_ps > 0xffffffff: errors.append("coarse_width_overflow")
            if mode == 256 and width != coarse_ps: errors.append("coarse_width_mismatch")
            if mode == 512 and (not both_fine_valid or abs(width - coarse_ps) > 65535):
                errors.append("fine_width_mismatch")
        elif width != 0:
            errors.append("invalid_frame_has_nonzero_width")
        if errors:
            bad_count += 1
            counts.update(errors)
            if len(examples) < 8: examples.append(dict(row=list(map(int, row)), errors=errors))
    return dict(ok=bad_count == 0, bad_record_count=bad_count,
                violation_counts=dict(counts), examples=examples)


def require_capture_integrity(capture):
    audit = audit_records(capture["records"], capture["taps"], capture["tick_ps"])
    if not audit["ok"]:
        raise RuntimeError(f"Calibration blocked: {audit['bad_record_count']} inconsistent raw records; "
                           f"{audit['violation_counts']}. Inspect saved CSV and implementation timing.")
    return audit


def edge_quality(capture):
    rows = complete_rows(capture)
    result = {}
    for edge, shift in (("RISE", 16), ("FALL", 24)):
        statuses = (rows[:, 1] >> shift) & 255
        valid = int(np.count_nonzero(statuses & 1))
        result[edge] = dict(complete_pulses=len(rows), valid_edges=valid,
                           valid_fraction=valid / max(1, len(rows)),
                           status_counts=dict(Counter(f"0x{int(s):02x}" for s in statuses)))
    return result


'''
helpers = helpers.replace('def summarize(capture, correction_ns=0.0):', audit + 'def summarize(capture, correction_ns=0.0):')
helpers = helpers.replace('    rows = complete_rows(capture)\n    if not len(rows):',
                          '    require_capture_integrity(capture)\n    rows = complete_rows(capture)\n    if not len(rows):')
helpers = helpers.replace('    problems=[]\n', '    require_capture_integrity(capture)\n    problems=[]\n')
helpers += '''

def verify_fine_correction(capture, candidate):
    require_capture_integrity(capture)
    rows = complete_rows(capture)
    used = rows[(rows[:, 1] & 512) != 0]
    if not len(used): raise RuntimeError("No records used the uploaded fine LUTs")
    mismatch = []
    for row in used:
        frame_id, flags, coarse, rise, fall, width = map(int, row)
        expected = coarse * capture["tick_ps"] + candidate["tables"]["RISE"][rise] - candidate["tables"]["FALL"][fall]
        if width != expected and len(mismatch) < 8:
            mismatch.append(dict(frame_id=frame_id, reported_ps=width, expected_ps=expected))
    if mismatch: raise RuntimeError("Fine readout does not match the uploaded tables: " + str(mismatch))
    return dict(ok=True, checked_records=len(used), provisional=True)


def compare_fine_precision(coarse_capture, fine_capture):
    result = {}
    for label, capture in (("coarse", coarse_capture), ("fine", fine_capture)):
        require_capture_integrity(capture)
        rows = complete_rows(capture)
        # Compare the same eligibility rule in both fresh captures. Never
        # choose records by their closeness to the reference duration.
        both = ((rows[:, 1] >> 16) & 1) & ((rows[:, 1] >> 24) & 1)
        rows = rows[both != 0]
        if len(rows) < 100: raise RuntimeError("Too few fine-eligible records for precision comparison")
        values = rows[:, 5].astype(float) / 1000
        result[label] = dict(samples=len(rows), mean_ns=float(values.mean()),
                             std_ns=float(values.std(ddof=1)),
                             mean_error_ns=float(values.mean() - capture["plan"]["reference_high_ns"]))
    result["coarse_std_divided_by_fine_std"] = (
        result["coarse"]["std_ns"] / result["fine"]["std_ns"] if result["fine"]["std_ns"] > 0 else None)
    result["provisional"] = True
    result["note"] = "Fresh captures; no host offset applied. AWG/scope uncertainty and failed timing remain."
    print(json.dumps(result, indent=2))
    return result
'''
put(3, helpers)

transport = source(6)
transport = transport.replace('                 fine_requested=fine,cleanup_errors=[],acquisition_ok=False)',
    '                 fine_requested=fine,cleanup_errors=[],acquisition_ok=False,\n'
    '                 image=dict(PREFLIGHT),provisional=IMPLEMENTATION_WNS_NS < 0)')
transport = transport.replace('            text=client.ask(f"TDC:WIDTH:DATA? {start},{size}")',
    '            data_command = "TDC:WIDTH:DATA:RAW?" if PREFLIGHT["width_version"] is not None and PREFLIGHT["width_version"] >= 8 else "TDC:WIDTH:DATA?"\n'
    '            capture["data_command"] = data_command\n'
    '            text=client.ask(f"{data_command} {start},{size}")')
transport = transport.replace('        if any(row[0]!=i+1 for i,row in enumerate(capture["records"])):\n'
    '            raise RuntimeError("Missing/reordered acquisition frame IDs")\n',
    '        capture["record_integrity"]=audit_records(capture["records"],capture["taps"],capture["tick_ps"])\n'
    '        require_capture_integrity(capture)\n'
    '        capture["edge_quality"]=edge_quality(capture)\n')
transport += '''

def preflight_board(client_factory=SCPI):
    # Isolate an optional command probe: an old server may not reply to an
    # unsupported query. Discard that connection after a timeout.
    version = None
    probe_error = None
    client = client_factory(RP_IP, SCPI_PORT)
    try:
        client.send("*CLS")
        client.sock.settimeout(3)
        version = int(client.ask("TDC:WIDTH:VERSION?"))
    except (OSError, RuntimeError, ValueError) as exc:
        probe_error = str(exc)
    finally:
        client.close()
    client = client_factory(RP_IP, SCPI_PORT)
    try:
        client.send("*CLS")
        client.write("PULSE:OUTPUT OFF")
        client.write("TDC:WIDTH:ABORT")
        wait_idle(client, 5)
        client.write("TDC:ENABLE OFF")
        client.write("TDC:TEST:INTERNAL OFF")
        client.write("TDC:MMCM:ENABLE OFF")
        client.write("TDC:INPUT SINGLE")
        client.write("TDC:WIDTH:CALIBRATION:ACTIVATE OFF")
        info = dict(bitstream_label=BITSTREAM_LABEL, implementation_wns_ns=IMPLEMENTATION_WNS_NS,
                    provisional=IMPLEMENTATION_WNS_NS < 0, width_version=version,
                    version_probe_error=probe_error,
                    capacity=int(client.ask("TDC:WIDTH:CAPACITY?")),
                    tick_ps=int(client.ask("TDC:WIDTH:TICK?")),
                    taps=int(client.ask("TDC:TAPS?")), input=client.ask("TDC:INPUT?"))
        if info["tick_ps"] != 4000 or info["taps"] != 512:
            raise RuntimeError("Unexpected image: this run expects the 512-tap, 250 MHz width path")
        if FRAME_COUNT > info["capacity"]: raise RuntimeError("FRAME_COUNT exceeds hardware capacity")
        if client.ask("PULSE:OUTPUT?") not in ("0", "OFF"): raise RuntimeError("Pulse OFF not confirmed")
    finally:
        client.close()
    save_json(RUN_DIR / "00_board_preflight.json", info)
    print(json.dumps(info, indent=2))
    if version is None:
        print("Version/raw query unavailable: using installed DATA? with host integrity checks.")
    if info["provisional"]:
        print("PROVISIONAL CALIBRATION: this image still fails implementation timing.")
    print("AWG must be running independently at the settings entered above; E1 pin 5 stays disconnected.")
    return info
'''
put(6, transport)

baseline = source(8).replace('print("Frame flags:",baseline["flag_counts"])',
    'print("Frame flags:",baseline["flag_counts"])\n'
    'print("Raw record integrity:",baseline["record_integrity"])\n'
    'print("Fine edge validity:",json.dumps(baseline["edge_quality"],indent=2))')
put(8, baseline)

collection = source(12).replace('calibration_captures=[]',
    'guard_reference_capture(baseline,baseline_summary)\ncalibration_captures=[]')
collection = collection.replace('    calibration_captures.append(captured)',
    '    calibration_captures.append(captured)\n'
    '    print("Edge valid fractions:", {edge: round(q["valid_fraction"], 4) for edge,q in captured["edge_quality"].items()})')
put(12, collection)

candidate = source(13).replace('    taps=captures[0]["taps"];tick=captures[0]["tick_ps"]',
    '    for capture in captures: require_capture_integrity(capture)\n'
    '    taps=captures[0]["taps"];tick=captures[0]["tick_ps"]')
candidate = candidate.replace('c["plan"]!=reference_plan for c in captures',
    'c["plan"]!=reference_plan or c.get("image")!=captures[0].get("image") for c in captures')
candidate = candidate.replace('    return dict(taps=taps,tick_ps=tick,plan=dict(reference_plan),input="SINGLE",tables=tables,',
    '    return dict(taps=taps,tick_ps=tick,plan=dict(reference_plan),input="SINGLE",tables=tables,\n'
    '                image=dict(captures[0]["image"]),provisional=IMPLEMENTATION_WNS_NS < 0,\n'
    '                calibration_state="provisional; implementation timing has not closed",')
put(13, candidate)

put(15, source(15) + '\n\nFor this image, passing histogram gates permits **provisional** LUT use only.\n'
    'Do not lower the 99% per-edge validity gate, hide missing-code regions or apply an offset\n'
    'to make a failing fine calibration pass. Upload both tables only after inspecting section 4.\n')

upload = source(16).replace('    if not candidate["ready"] or candidate["plan"]!=plan:',
    '    if not candidate["ready"] or candidate["plan"]!=plan or candidate.get("image") != PREFLIGHT:')
upload = upload.replace('    client=client_factory(RP_IP,SCPI_PORT);backup=None;changed=False',
    '    for values in candidate["tables"].values():\n'
    '        if any(a > b for a,b in zip(values, values[1:])) or max(values) > candidate["tick_ps"]:\n'
    '            raise ValueError("Fine LUT must be monotonic and remain within one sampler tick")\n'
    '    client=client_factory(RP_IP,SCPI_PORT);backup=None;changed=False')
upload = upload.replace('        print("Both width LUTs uploaded, read back and activated.")',
    '        save_json(RUN_DIR/"04_uploaded_luts.json",dict(candidate=candidate,uploaded_utc=datetime.now(timezone.utc).isoformat()))\n'
    '        print("Both width LUTs uploaded, read back and activated. PROVISIONAL while timing fails.")')
put(16, upload)

validation = source(17).replace('upload_candidate(candidate)\n',
    'upload_candidate(candidate)\n'
    'fresh_coarse=capture_burst("05a_fresh_coarse_comparison",fine=False)\n')
validation += '\nfine_readback_check=verify_fine_correction(fine_fit_capture,candidate)\n'
validation += 'save_json(RUN_DIR/"05_fine_readback_check.json",fine_readback_check)\n'
validation += 'precision_comparison=compare_fine_precision(fresh_coarse,fine_fit_capture)\n'
validation += 'save_json(RUN_DIR/"05_precision_comparison.json",precision_comparison)\n'
put(17, validation)

reference = source(19).replace('reference_calibration=dict(plan=dict(plan),input="SINGLE",source="05_fine_reference_fit",',
    'reference_calibration=dict(plan=dict(plan),input="SINGLE",source="05_fine_reference_fit",\n'
    '                           provisional=IMPLEMENTATION_WNS_NS < 0,image=dict(PREFLIGHT),')
reference = reference.replace('validation_raw=summarize(validation)',
    'verify_fine_correction(validation,candidate)\nvalidation_raw=summarize(validation)')
reference += '\nprint("These results remain provisional until capture timing closes and this procedure is repeated for that image.")\n'
put(19, reference)

# Introduce preflight immediately after the transport definitions; subsequent
# sections retain their existing headings and execution order.
notebook['cells'].insert(7, dict(cell_type='code', execution_count=None, metadata={},
    outputs=[], source=['PREFLIGHT = preflight_board()\n']))
for cell in notebook['cells']:
    cell.setdefault('id', uuid.uuid4().hex[:8])
    if cell['cell_type'] == 'code':
        cell['execution_count'] = None
        cell['outputs'] = []
notebook.setdefault('metadata', {})['fine_calibration_revision'] = '2026-10-19-v8-provisional'
path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
print('Updated', path)
print('Historical notebook backup:', backup)
