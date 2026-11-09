"""Read saved Rigol captures without instrument access or editing original results.

Example: python tdc_rigol_review.py RUN_DIR --output REVIEW_DIR --probe-dir PROBE_DIR
The unwrapped phase diagnostic assumes slow phase walk; it is not a correction.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import numpy as np

from tdc_rigol_tools import (fit_width_reference, rows, save_json, summarize,
                             validate_width_reference)


def load_captures(directory):
    captures = []
    for path in sorted(Path(directory).glob("*.json")):
        if not path.name[0].isdigit() or path.name.endswith("_retries.json"):
            continue
        c = json.loads(path.read_text())
        if c.get("raw_records_saved") is False:
            continue  # Deliberately compacted failures still count in retry ledgers.
        raw = path.with_suffix(".csv")
        if not raw.exists() or "frames_requested" not in c:
            continue
        with raw.open(newline="") as stream:
            c["records"] = [tuple(int(r[k]) for k in
                            ("frame_id", "flags", "coarse_ticks", "rise_raw", "fall_raw", "width_ps"))
                            for r in csv.DictReader(stream)]
        c["summary"] = summarize(c)
        c["review_source"] = str(path)
        captures.append(c)
    return captures


def phase_walk(capture, tables):
    selected = rows(capture, calibrated=True)
    tick = capture["image"]["tick_ps"] / 1000
    result = {}
    if len(selected) < 100 or np.any(np.diff(selected[:, 0].astype(np.int64)) != 1):
        return {"unavailable": "Need contiguous calibrated samples; no gaps may be unwrapped"}
    for edge, column in (("RISE", 3), ("FALL", 4)):
        phase = np.asarray(tables[edge])[selected[:, column].astype(int)] / 1000
        unwrapped = np.unwrap(phase * 2*np.pi/tick) * tick/(2*np.pi)
        indices = np.arange(len(unwrapped))
        slope, offset = np.polyfit(indices, unwrapped, 1)
        residual = unwrapped - (slope*indices + offset)
        result[edge] = dict(slope_ps_per_frame=float(slope*1000),
                            linear_residual_std_ns=float(residual.std(ddof=1)),
                            linear_residual_span_ns=float(np.ptp(residual)))
    result["assumption"] = "Slow phase walk, no intersample phase jump >= half a tick; source and TDC effects are not separated"
    return result


def selected_fine(captures):
    return [c for c in captures if c.get("fine_requested") and c.get("acquisition_ok")
            and c["summary"]["complete_pulses"] == c["frames_requested"]]


def parse_timing_report(path):
    data = Path(path).read_bytes()
    text = data.decode("utf-8", errors="replace")
    match = re.search(r"WNS\(ns\)[^\n]*\n[^\n]*\n([^\n]+)", text)
    if not match:
        raise ValueError("Design timing summary row not found")
    values = match[1].split()
    paths = [dict(slack_ns=float(slack), source=source.strip(), destination=destination.strip())
             for slack, source, destination in re.findall(
                 r"Slack \(VIOLATED\)\s*:\s*(-[\d.]+)ns.*?Source:\s*([^\r\n]+).*?Destination:\s*([^\r\n]+)", text, re.S)]
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(),
                wns_ns=float(values[0]), tns_ns=float(values[1]),
                setup_failing_endpoints=int(values[2]), hold_failing_endpoints=int(values[6]),
                detailed_violating_paths=paths,
                association="Supplied report; loaded bitstream hash remains unknown. Detailed max_paths need not enumerate all failing endpoints.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--probe-dir", type=Path)
    parser.add_argument("--timing-report", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.output.resolve() in (args.run_dir.resolve(), args.probe_dir.resolve() if args.probe_dir else None):
        raise ValueError("Use a separate review output directory to preserve original evidence")
    captures = selected_fine(load_captures(args.run_dir))
    probes = selected_fine(load_captures(args.probe_dir)) if args.probe_dir else []
    candidate = json.loads((args.run_dir / "candidate_luts.json").read_text())
    training = [c for c in captures if c["label"].startswith("reference_train_")]
    heldout = [c for c in captures if c["label"].startswith("reference_holdout_")]
    model = fit_width_reference(training)
    validation = validate_width_reference(model, heldout)
    old_validation = json.loads((args.run_dir / "host_width_reference_validation.json").read_text())
    report = dict(baseline=str(args.run_dir), probe=str(args.probe_dir),
                  model=model, heldout_validation=validation,
                  historical_affine_validation=old_validation,
                  fresh_probe_validation=validate_width_reference(model, probes),
                  limitations=["Retrospective model choice; nominal AWG reference, not traceable absolute accuracy.",
                               "All capture samples retained. Training exclusions do not improve reported full-capture precision.",
                               "Selected complete bursts after retries; no unconditional efficiency or synchronization claim.",
                               "A host offset cannot remove within-burst drift or narrow-pulse nonlinearity."],
                  capture_diagnostics=[])
    if args.timing_report:
        report["supplied_timing_report"] = parse_timing_report(args.timing_report)
    for c in captures + probes:
        report["capture_diagnostics"].append(dict(label=c["label"], source=c["review_source"],
            summary=c["summary"], phase_walk=phase_walk(c, candidate["tables"]),
            sparse_edge_diagnostics=c.get("edge_diagnostics")))
    save_json(args.output / "width_review.json", report)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), constrained_layout=True)
    for ax, original_label, prefix in zip(axes[:2], ("step_w103.25_fine", "narrow_w900_fine"), ("w103_", "w900_")):
        chosen = [c for c in captures if c["label"] == original_label] + [c for c in probes if c["label"].startswith(prefix)]
        for c in chosen:
            data = rows(c, calibrated=True)
            ax.plot(data[:, 0], data[:, 5]/1000-c["reference_ns"], lw=.6, alpha=.8, label=c["label"])
        ax.set(xlabel="Original frame ID (no trimming)", ylabel="Width minus nominal AWG (ns)")
        ax.legend(fontsize=8, ncol=2)
        ax.grid(alpha=.25)
    x = [r["reference_ns"] for r in validation]
    axes[2].plot(x, [r["corrected_error_ns"]*1000 for r in old_validation], ".-", label="Historical affine fit")
    axes[2].plot(x, [r["corrected_error_ns"]*1000 for r in validation], ".-", label="Stable-capture offset (retrospective)")
    axes[2].axhline(0, color="gray", lw=.7)
    axes[2].set(xlabel="Held-out nominal AWG width (ns)", ylabel="Corrected mean error (ps)")
    axes[2].legend()
    axes[2].grid(alpha=.25)
    fig.savefig(args.output / "width_review.png", dpi=160)
    print("Offset ns:", model["offset_ns"], "training:", model["training_labels"])
    print("Held-out errors ps:", [round(r["corrected_error_ns"]*1000, 1) for r in validation])
    print("Review:", args.output / "width_review.json")


if __name__ == "__main__":
    main()
