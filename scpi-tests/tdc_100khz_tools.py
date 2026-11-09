"""Small helpers for the 100 kHz Rigol/V18 notebook. Import is hardware-free."""
import copy
import hashlib
import json
from pathlib import Path

from tdc_rigol_tools import plan_matched_period, quality_guard, save_json


def restore_bundled_candidate(directory, image, bitstream_label):
    """Verify bundle/hash/interface, preserving provenance when fixing old metadata.

    The original V18 candidate recorded a placeholder build label and null WNS.
    The portable manifest records the implementation established by run history.
    This reconciles only those metadata fields; hardware identity must match.
    No board command or LUT change occurs here.
    """
    directory = Path(directory)
    manifest = json.loads((directory / 'v18_calibration_manifest.json').read_text())
    if manifest['bitstream_label'] != bitstream_label or image['bitstream_label'] != bitstream_label:
        raise ValueError('Bundle belongs to another routed implementation')
    data = (directory / manifest['calibration_file']).read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest['files_sha256'][manifest['calibration_file']]:
        raise ValueError('Bundled LUT checksum mismatch')
    candidate = json.loads(data)
    candidate = candidate.get('candidate', candidate)
    if not candidate.get('ready') or candidate.get('provisional') or candidate.get('input') != 'SINGLE':
        raise ValueError('Need qualified, nonprovisional SINGLE calibration')
    old_image = candidate['image']
    for key, value in image.items():
        if key not in ('bitstream_label', 'implementation_wns_ns') and old_image.get(key) != value:
            raise ValueError(f'Calibration hardware mismatch: {key}')
    for edge in ('RISE', 'FALL'):
        if candidate['quality'][edge]['errors']:
            raise ValueError(f'{edge} calibration quality errors')
        table = candidate['tables'][edge]
        if (len(table) != image['taps'] or
                any(type(v) != int or not 0 <= v <= image['tick_ps'] for v in table) or
                any(a > b for a, b in zip(table, table[1:]))):
            raise ValueError(f'Invalid {edge} LUT')
    result = copy.deepcopy(candidate)
    result['restored_provenance'] = dict(
        source_run=manifest['source_run'], source_sha256=hashlib.sha256(data).hexdigest(),
        original_image=old_image, reference_bitstream_sha256=manifest.get('reference_bitstream_sha256'),
        note='Only placeholder build/WNS metadata reconciled against the portable manifest; operator must load this exact implementation.')
    result['image'] = dict(image)
    return result


def require_complete(capture, fine=False):
    """Require the entire burst; never select only favourable records."""
    quality_guard(capture)
    summary = capture['summary']
    if summary['complete_pulses'] != summary['total_frames']:
        raise RuntimeError('Incomplete burst; inspect saved attempt/flags before continuing')
    if fine and summary['calibrated_pulses'] != summary['total_frames']:
        raise RuntimeError('Fine capture did not calibrate every frame')
    return capture


def screen_offsets(bench, frequency_hz, width_ns, offsets_ns, frames=512, repeats=3):
    """Small explicit offset screen, not all 2,500 offsets of a 10 us frame.

    Each start is retained and retries are disabled during the screen. Software
    restarts confound offset with independent AWG phase; rankings are candidates
    for fresh validation, not a deterministic pin-delay calibration.
    """
    period = plan_matched_period(frequency_hz, bench.image['minimum_period_ns'])['common_period_ns']
    offsets_ns = list(offsets_ns)
    if not offsets_ns or len(set(offsets_ns)) != len(offsets_ns):
        raise ValueError('Choose distinct offsets')
    if any(type(v) != int or v % 4 or not 0 <= v < period for v in offsets_ns):
        raise ValueError('Offsets must be 4 ns multiples inside the frame')
    if type(repeats) != int or not 1 <= repeats <= 10:
        raise ValueError('Use 1..10 repeats')
    saved = copy.deepcopy(bench.config)
    result = dict(period_ns=period, width_ns=width_ns, attempts=[], ranking=[],
                  phase_lock_verified=False,
                  note='Independent starts, no completeness retries. Offset and startup phase are confounded; validate a chosen offset on new bursts.')
    try:
        bench.config['phase_retries'] = False
        for offset in offsets_ns:
            bench.config['frame_offsets_by_period_ns'] = {period: offset}
            for repeat in range(repeats):
                capture = bench.acquire(f'100k_offset_{offset}_r{repeat}', frequency_hz,
                                        width_ns, frames=frames, fine=False)
                summary = capture['summary']
                result['attempts'].append(dict(offset_ns=offset, repeat=repeat,
                    complete=summary['complete_pulses'], frames=summary['total_frames'],
                    flag_counts=summary['flag_counts'], capture_files=capture['capture_files']))
                print(f"Offset {offset} ns, start {repeat+1}/{repeats}: "
                      f"{summary['complete_pulses']}/{summary['total_frames']} complete", flush=True)
                save_json(bench.directory / '100khz_offset_screen.json', result)
                if not capture['acquisition_ok'] or capture['cleanup_errors']:
                    raise RuntimeError('Offset screening acquisition/cleanup failed')
        for offset in offsets_ns:
            points = [p for p in result['attempts'] if p['offset_ns'] == offset]
            result['ranking'].append(dict(offset_ns=offset,
                complete_starts=sum(p['complete'] == p['frames'] for p in points),
                starts=len(points), complete_frames=sum(p['complete'] for p in points),
                total_frames=sum(p['frames'] for p in points)))
        result['ranking'].sort(key=lambda p: (-p['complete_starts'], -p['complete_frames'], p['offset_ns']))
        return result
    except BaseException as exc:
        result['failure'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        bench.config.clear()
        bench.config.update(saved)
        save_json(bench.directory / '100khz_offset_screen.json', result)


def compact_capture(capture):
    """Keep report links/statistics, without duplicating raw arrays in a report."""
    return {key: capture.get(key) for key in (
        'label', 'timing', 'frame_offset_ns', 'reference_ns', 'reference_source',
        'summary', 'acquisition_ok', 'cleanup_errors', 'phase_retry',
        'fine_arithmetic_check', 'previously_unseen_codes', 'capture_files')}
