"""Compact zero-yield WIDTH captures; dry-run by default, no instrument access."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within(path, root):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError(f"Capture path escapes result root or is a symlink: {path}")
    return resolved


def plan_cleanup(root):
    root = root.resolve()
    plan = []
    for meta in sorted(root.glob('*/*.json')):
        if not meta.name[0].isdigit() or meta.name.endswith('_retries.json'):
            continue
        c = json.loads(meta.read_text(encoding='utf-8'))
        if c.get('summary', {}).get('complete_pulses') != 0:
            continue
        raw_name = c.get('capture_files', {}).get('csv')
        if not raw_name:
            continue
        raw = within(Path(raw_name), root)
        if raw != within(meta.with_suffix('.csv'), root):
            raise ValueError(f"Capture metadata/CSV names disagree: {meta}")
        if not raw.is_file():
            continue
        # Do not delete a capture merely because its summary claims zero yield.
        with raw.open(newline='', encoding='utf-8') as f:
            records = list(csv.DictReader(f))
        if any(int(row['flags']) & 1 for row in records):
            raise ValueError(f"Raw VALID records contradict zero-yield summary: {raw}")
        if len(records) != c['summary']['total_frames']:
            raise ValueError(f"Raw record count contradicts summary: {raw}")
        plan.append(dict(json=str(meta.resolve()), csv=str(raw), records=len(records),
                         csv_bytes=raw.stat().st_size, json_sha256=digest(meta), csv_sha256=digest(raw)))
    return plan


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.cleanup.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


def apply_cleanup(root, plan, audit):
    root = root.resolve()
    audit.mkdir(parents=True, exist_ok=True)
    journal = audit/'cleanup_journal.jsonl'
    backup = audit/'original_capture_metadata.jsonl.gz'
    if journal.exists() or backup.exists():
        raise ValueError('Use a new audit directory; do not overwrite an earlier cleanup audit')
    deleted = set()
    result = dict(deleted_csv_files=0, removed_csv_bytes=0, metadata_pointer_updates=0)
    with gzip.open(backup, 'wt', encoding='utf-8') as originals, journal.open('w', encoding='utf-8') as log:
        for item in plan:
            meta, raw = within(Path(item['json']), root), within(Path(item['csv']), root)
            if digest(meta) != item['json_sha256'] or digest(raw) != item['csv_sha256']:
                raise ValueError(f"Capture changed after inventory; no deletion for {raw}")
            original = meta.read_text(encoding='utf-8')
            c = json.loads(original)
            originals.write(json.dumps(dict(path=str(meta), original_json=original))+'\n')
            originals.flush()
            for key in ('records','latency_ticks','edge_tick_samples','edge_diagnostics','awg_scpi_log'):
                c.pop(key, None)
            c['capture_files']['csv'] = None
            c['raw_records_saved'] = False
            c['retention'] = dict(policy='historical_zero_yield_cleanup', raw_omitted=True,
                records_acquired=item['records'], complete_pulses=0,
                omitted_csv=str(raw), csv_sha256=item['csv_sha256'],
                reason='User-requested removal of zero-complete raw captures; summary retained')
            atomic_json(meta, c)
            try:
                # Single verified file only; never recursive deletion or a wildcard.
                raw.unlink()
            except BaseException:
                meta.write_text(original, encoding='utf-8')
                raise
            deleted.add(str(raw))
            result['deleted_csv_files'] += 1
            result['removed_csv_bytes'] += item['csv_bytes']
            log.write(json.dumps(item)+'\n')
            log.flush()
    # Preserve retry/offset statistics and make their omitted-raw pointers explicit.
    def fix(value):
        changed = 0
        if isinstance(value, dict):
            if isinstance(value.get('csv'), str) and str(Path(value['csv']).resolve()) in deleted:
                value['csv'] = None
                value['raw_omitted'] = True
                changed += 1
            changed += sum(fix(v) for v in value.values())
        elif isinstance(value, list):
            changed += sum(fix(v) for v in value)
        return changed
    for p in sorted(root.glob('*/*.json')):
        within(p, root)
        value = json.loads(p.read_text(encoding='utf-8'))
        changed = fix(value)
        if changed:
            atomic_json(p, value)
            result['metadata_pointer_updates'] += changed
    atomic_json(audit/'cleanup_result.json', result)
    return result


def main():
    from local_data import results_directory
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = results_directory('tdc_rigol_results').resolve()
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_cleanup(root)
    atomic_json(args.audit_dir/'cleanup_plan.json', dict(root=str(root), files=plan))
    print(f"Verified zero-complete captures: {len(plan)}; raw CSV {sum(p['csv_bytes'] for p in plan)/2**20:.2f} MiB")
    if args.apply:
        print(json.dumps(apply_cleanup(root, plan, args.audit_dir), indent=2))
    else:
        print('Dry run only; no saved measurements changed. Add --apply to compact/delete these files.')


if __name__ == '__main__':
    main()
