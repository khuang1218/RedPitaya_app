"""VTC PCB stimulus helpers. Importing this module never opens instruments."""
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def load_demo_helpers(repo):
    """Load definitions from our hardware-free helper reference, not its examples."""
    path = Path(repo) / '100kHz_demo' / '100kHz_matrix_demo.ipynb'
    namespace = {'__name__': 'vtc_demo_helpers'}
    for cell in json.loads(path.read_text(encoding='utf-8'))['cells']:
        if cell['cell_type'] == 'code':
            exec(compile(''.join(cell['source']), str(path), 'exec'), namespace)
    return SimpleNamespace(**namespace)


def prepare_stimulus(spec, min_v, max_v):
    """Validate everything before touching the AWG; amplitudes are Vpp, not peak."""
    kind = str(spec['kind']).upper()
    if kind not in ('DC', 'SINE', 'SQUARE', 'RAMP', 'TRIANGLE', 'ARB'):
        raise ValueError('Use DC, SINE, SQUARE, RAMP, TRIANGLE or ARB')
    if not all(math.isfinite(x) for x in (min_v, max_v)) or min_v >= max_v:
        raise ValueError('Set the PCB voltage limits explicitly')
    offset = float(spec['offset_v'])
    vpp = 0.0 if kind == 'DC' else float(spec['vpp'])
    frequency = 0.0 if kind == 'DC' else float(spec['frequency_hz'])
    if (not all(math.isfinite(x) for x in (offset, vpp, frequency)) or
            vpp < 0 or not min_v <= offset-vpp/2 <= offset+vpp/2 <= max_v):
        raise ValueError('Stimulus extrema exceed configured PCB voltage limits')
    if kind != 'DC' and (vpp <= 0 or not 0 < frequency < 50_000):
        raise ValueError('Use positive Vpp and frequency below the 100 kHz sampling Nyquist limit')
    info = dict(kind=kind, offset_v=offset, vpp=vpp, frequency_hz=frequency,
                voltage_limits_v=[min_v, max_v], load='INF')
    points = None
    if kind == 'ARB':
        values = np.asarray(spec['samples'], dtype=float)
        if (values.ndim != 1 or not 32 <= len(values) <= 16384 or
                not np.isfinite(values).all() or np.max(np.abs(values)) > 1):
            raise ValueError('ARB needs 32..16384 finite normalized samples in [-1,1]')
        # Basic-mode stored ARB on the DG5000 Pro requires exactly 16384 points.
        # Periodic linear interpolation preserves the user's scale (no normalization).
        values = np.interp(np.arange(16384)/16384, np.arange(len(values))/len(values),
                           values, period=1.0)
        points = np.rint(values*32767).astype(np.int16)
        info.update(points=16384, source_points=len(spec['samples']),
                    samples_sha256=hashlib.sha256(points.astype('<i2').tobytes()).hexdigest(),
                    interpolation='periodic linear to 16384 samples')
    return info, points


def configure_stimulus(awg, spec, min_v, max_v, arb_file=r'INT:\vtc_pcb_test.arb'):
    """Configure selected Rigol output while OFF; never changes the FPGA trigger.

    ARB overwrites only the named test file in AWG internal memory. Uses the
    DG5000 Pro basic-mode 16384-point stored waveform path.
    """
    info, points = prepare_stimulus(spec, min_v, max_v)
    if not arb_file.startswith('INT:\\') or any(c in arb_file for c in ',;"\r\n') or not arb_file.endswith('.arb'):
        raise ValueError('Use a simple INT:\\...arb test filename')
    s = awg.source
    awg.off()
    awg.write(awg.output + ':LOAD INFinity')
    awg.write(awg.output + ':POLarity NORMal')
    for parameter in ('FREQuency', 'VOLTage', 'PHASe'):
        awg.write(s + f':{parameter}:COUPle:STATe OFF')
    awg.write(s + ':FUNCtion:ADVance:STATe OFF')
    if info['kind'] == 'DC':
        awg.write(s + f":APPLy:DC DEFault,DEFault,{info['offset_v']:.12g},DEFault")
    else:
        command = dict(SINE='SINusoid', SQUARE='SQUare', RAMP='RAMP',
                       TRIANGLE='TRIangle', ARB='ARBitrary')[info['kind']]
        awg.write(s + f":APPLy:{command} {info['frequency_hz']:.12g},{info['vpp']:.12g},{info['offset_v']:.12g},0")
        if info['kind'] == 'SQUARE':
            awg.write(s + ':FUNCtion:SQUare:DCYCle 50')
        if info['kind'] == 'RAMP':
            awg.write(s + ':FUNCtion:RAMP:SYMMetry 50')
        if points is not None:
            for start in range(0, len(points), 1024):
                flag = 'HEADer' if start == 0 else ('END' if start+1024 == len(points) else 'CONTinue')
                data = ','.join(map(str, points[start:start+1024]))
                awg.write(f':MMEMory:TRACe:ARB:DATA:DAC {arb_file},{flag},{data}')
            awg.write(f':MMEMory:LOAD:DATA {awg.channel},{arb_file}')
            awg.write(s + f":FREQuency {info['frequency_hz']:.12g}")
            info['arb_file'] = arb_file
    awg.off()
    if awg.ask('*OPC?') != '1':
        raise RuntimeError('AWG configuration did not complete')
    reply = awg.ask(s + ':APPLy?').strip().strip('"').split(',')
    expected = dict(DC=('DC', 'ARB'), SINE=('SIN',), SQUARE=('SQU',),
                    RAMP=('RAMP',), TRIANGLE=('TRI',), ARB=('ARB',))[info['kind']]
    if len(reply) != 5 or reply[0].upper() not in expected:
        raise RuntimeError('Unexpected AWG waveform readback: ' + ','.join(reply))
    for actual, expected_value in [(float(reply[3]), info['offset_v'])] + (
            [] if info['kind'] == 'DC' else [(float(reply[1]), info['frequency_hz']),
                                           (float(reply[2]), info['vpp'])]):
        if not math.isclose(actual, expected_value, rel_tol=1e-6, abs_tol=1e-6):
            raise RuntimeError('AWG parameter readback mismatch: ' + ','.join(reply))
    info['application_readback'] = ','.join(reply)
    if points is not None:
        info['arb_readback'] = awg.ask(s + ':FUNCtion:ARBitrary?')
        if Path(info['arb_readback'].strip('"').replace('\\', '/')).name.lower() != Path(arb_file.replace('\\', '/')).name.lower():
            raise RuntimeError('Stored ARB selection readback mismatch')
    awg.last_settings = info
    return info


def stop_vtc(demo, rp, awg):
    """Attempt every OFF even if one instrument fails; return cleanup errors."""
    errors = demo.stop_outputs(rp) if rp is not None else []
    if awg is not None:
        try:
            awg.off()
        except Exception as exc:
            errors.append(f'AWG OFF: {exc}')
    return errors


def capture_vtc(demo, rp, frames, calibration, timeout_s=30):
    """One attempt only. The FPGA period is always 10000 ns for this test."""
    if rp.ask('PULSE:TIMING?') != '10000,5000':
        raise RuntimeError('Expected fixed 100 kHz / 50% FPGA launch')
    result = demo.capture_burst(rp, frames, calibration, timeout_s=timeout_s)
    result.update(timing_topology='fpga_triggered_vtc_pcb', automatic_retries=0)
    return result
