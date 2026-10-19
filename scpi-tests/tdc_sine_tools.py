"""Acquisition and analysis helpers for tdc_pcb_sine_test.ipynb.

Only acquire_width_burst/stop_output contact hardware. Analysis needs NumPy;
the generator's analogue settings are metadata, not a voltage calibration.
"""
import csv
import json
import math
import time
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from tdc_pulse_width_test import Client


FLAG_BITS = {
    0: "VALID", 1: "NO_RISE", 2: "NO_FALL", 3: "HIGH_AT_START",
    4: "EXTRA_EDGES", 5: "TRIGGER_TIMEOUT", 7: "FINE_INVALID",
    8: "COARSE_ONLY", 9: "CALIBRATED", 10: "BOUNDARY",
    11: "SATURATED", 12: "OUT_OF_RANGE",
}
STATUS_BITS = {
    0: "BUSY", 1: "CAPTURING", 2: "PROCESSING", 3: "DONE",
    4: "TRIGGER_TIMEOUT", 5: "RATE_ERROR", 6: "ABORTED", 7: "OVERFLOW",
}
FIELDS = ("cycle_id", "flags", "coarse_ticks", "rise_raw", "fall_raw", "width_ps")


def decode_bits(value, names=FLAG_BITS):
    return "|".join(name for bit, name in names.items() if int(value) & (1 << bit)) or "NONE"


def audit_width_records(records, tick_ps=4000):
    """Check hardware invariants without changing or dropping any raw record."""
    counts = Counter()
    examples = []
    bad_records = 0
    for expected_id, row in enumerate(records, 1):
        cycle, flags, coarse, rise, fall, width = map(int, row)
        reasons = []
        if cycle != expected_id:
            reasons.append("cycle_id")
        if flags & 1:
            if flags & (2 | 4 | 8 | 16 | 32 | 1024 | 2048 | 4096):
                reasons.append("valid_with_frame_error")
            mode = flags & (256 | 512)
            if mode not in (256, 512):
                reasons.append("missing_or_conflicting_width_mode")
            fine_valid = bool(flags & (1 << 16)) and bool(flags & (1 << 24))
            if bool(flags & 128) != (not fine_valid):
                reasons.append("fine_invalid_flag_mismatch")
            coarse_ps = coarse * int(tick_ps)
            if coarse_ps > 0xffffffff:
                reasons.append("valid_coarse_overflow")
            if mode == 256 and width != coarse_ps:
                reasons.append("coarse_width_mismatch")
            if mode == 512 and (not fine_valid or abs(width - coarse_ps) > 65535):
                reasons.append("invalid_fine_correction")
        elif width != 0:
            reasons.append("invalid_frame_nonzero_width")
        if reasons:
            bad_records += 1
            counts.update(reasons)
            if len(examples) < 8:
                examples.append({"cycle_id": cycle, "flags_hex": f"0x{flags:08x}",
                                 "reasons": reasons})
    return {"ok": bad_records == 0, "bad_record_count": bad_records,
            "violation_counts": dict(counts), "examples": examples}


def validate_config(config):
    """Return the quantized trigger plan; reject aliasing before contacting a board."""
    for key in ("fpga_frequency_hz", "sine_frequency_hz", "sine_vpp", "sine_offset_v"):
        if not math.isfinite(float(config[key])):
            raise ValueError(f"{key} must be finite")
    fpga_hz = float(config["fpga_frequency_hz"])
    sine_hz = float(config["sine_frequency_hz"])
    count = config["sample_count"]
    if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or not 1 <= count <= 16384:
        raise ValueError("sample_count must be an integer from 1 to 16384")
    if not 0 < fpga_hz <= 1_000_000:
        raise ValueError("This width build requires 0 < FPGA trigger frequency <= 1 MHz")
    # PULSE:TIMING uses ns. A multiple of 4 ns gives an exact 50% duty cycle
    # with the pulse generator's 2 ns timing grid.
    period_ns = int(round(1e9 / fpga_hz / 4)) * 4
    if not 1000 <= period_ns <= 8_589_934_588:
        raise ValueError("FPGA trigger period is outside the supported range")
    actual_hz = 1e9 / period_ns
    if not 0 < sine_hz < actual_hz / 2:
        raise ValueError("Sine frequency must be positive and below half the actual FPGA trigger frequency")
    if float(config["sine_vpp"]) <= 0:
        raise ValueError("sine_vpp must be positive, in volts peak-to-peak")
    if config.get("input_mode", "SINGLE") not in ("SINGLE", "LVDS"):
        raise ValueError("input_mode must be SINGLE or LVDS")
    for key in ("timeout_s", "settle_s"):
        value = float(config.get(key, 20.0 if key == "timeout_s" else 0.1))
        if not math.isfinite(value) or value < 0 or (key == "timeout_s" and value == 0):
            raise ValueError(f"{key} must be finite and {'positive' if key == 'timeout_s' else 'nonnegative'}")
    duration_s = count * period_ns * 1e-9
    if config.get("timeout_s", 20.0) <= duration_s + 0.1:
        raise ValueError("timeout_s must exceed the acquisition duration by at least 0.1 s")
    return {
        "period_ns": period_ns, "high_ns": period_ns // 2,
        "actual_fpga_hz": actual_hz, "duration_s": duration_s,
        "sine_cycles": duration_s * sine_hz,
        "samples_per_sine_cycle": actual_hz / sine_hz,
    }


def _query(client, command):
    response = client.query(command)
    client.check()
    return response


def _wait_idle(client, timeout_s):
    deadline = time.monotonic() + timeout_s
    while True:
        status = int(_query(client, "TDC:WIDTH:STATUS?"))
        if not status & 1:
            return status
        if time.monotonic() >= deadline:
            raise TimeoutError("TDC remained BUSY; output will be stopped in cleanup")
        time.sleep(0.01)


def stop_output(host, port=5000, client_factory=Client):
    """Separate stop cell for an interrupted notebook; verify OFF and request abort."""
    client = client_factory(host, port)
    try:
        client.write("PULSE:OUTPUT OFF")
        if _query(client, "PULSE:OUTPUT?") not in ("0", "OFF"):
            raise RuntimeError("Pulse output OFF was not confirmed")
        client.write("TDC:WIDTH:ABORT")
        _wait_idle(client, 5.0)
    finally:
        client.close()


def acquire_width_burst(config, client_factory=Client):
    """Capture every pulse in one finite burst; retain invalid records and frame times.

    Output is stopped before readout, and OFF/ABORT is attempted on every exit,
    including exceptions and KeyboardInterrupt. A lost network connection can
    prevent confirmation of OFF, in which case cleanup reports that explicitly.
    """
    return acquire_framed_width_burst(config, validate_config(config), client_factory)


def acquire_framed_width_burst(config, plan, client_factory=Client, fine_enabled=False):
    """Shared WIDTH protocol for validated PCB-trigger or external-window plans.

    fine_enabled preserves/activates an already uploaded width LUT. It requires
    the input selection to match before setup, avoiding silent LUT invalidation.
    The default remains uncalibrated for the original sine notebook.
    """
    client = client_factory(config["host"], int(config.get("port", 5000)))
    records = []
    capture = {
        "settings": dict(config), "plan": plan, "records": records,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "cleanup_errors": [],
        "fine_enabled_requested": bool(fine_enabled),
    }
    timeout = float(config.get("timeout_s", 20.0))
    try:
        client.send("*CLS")
        client.write("PULSE:OUTPUT OFF")
        client.write("TDC:WIDTH:ABORT")
        _wait_idle(client, timeout)
        capacity = int(_query(client, "TDC:WIDTH:CAPACITY?"))
        capture["capacity"] = capacity
        capture["tick_ps"] = int(_query(client, "TDC:WIDTH:TICK?"))
        if config["sample_count"] > capacity:
            raise RuntimeError(f"Image capacity is {capacity}; requested {config['sample_count']}. Check the loaded image")
        if _query(client, "PULSE:PIN?") != "DIO1_P":
            raise RuntimeError("Unexpected pulse output pin; check image and wiring")
        if fine_enabled and _query(client, "TDC:INPUT?").upper() != config.get("input_mode", "SINGLE"):
            raise RuntimeError("Select the correct input, then upload its LUT before requesting fine capture")
        for command in (
            "TDC:ENABLE OFF", "TDC:TEST:INTERNAL OFF", "TDC:MMCM:ENABLE OFF",
            *(() if fine_enabled else ("TDC:RESET",)),
            "TDC:INPUT " + config.get("input_mode", "SINGLE"),
            "TDC:WIDTH:CALIBRATION:ACTIVATE " + ("ON" if fine_enabled else "OFF"),
            f"PULSE:TIMING {plan['period_ns']},{plan['high_ns']}",
        ):
            client.write(command)
        readback = tuple(map(int, _query(client, "PULSE:TIMING?").split(",")))
        if readback != (plan["period_ns"], plan["high_ns"]):
            raise RuntimeError(f"Pulse timing readback mismatch: {readback}")
        if _query(client, "TDC:INPUT?").upper() != config.get("input_mode", "SINGLE"):
            raise RuntimeError("TDC input selection readback mismatch")
        if fine_enabled and _query(client, "TDC:WIDTH:CALIBRATION:ACTIVATE?") not in ("1", "ON"):
            raise RuntimeError("Width fine calibration is not enabled")
        # Keep the clock running before ARM, including PCB settling time. ARM's
        # short stopped-trigger watchdog must not span a network round trip.
        client.write("PULSE:OUTPUT ON")
        time.sleep(float(config.get("settle_s", 0.1)))
        client.write(f"TDC:WIDTH:ARM {config['sample_count']}")
        capture["status"] = _wait_idle(client, timeout)
        client.write("PULSE:OUTPUT OFF")
        if _query(client, "PULSE:OUTPUT?") not in ("0", "OFF"):
            raise RuntimeError("Pulse output OFF was not confirmed after acquisition")
        count = int(_query(client, "TDC:WIDTH:COUNT?"))
        if not 0 <= count <= capacity:
            raise RuntimeError(f"Invalid completed record count: {count}")
        capture["reported_count"] = count
        for start in range(0, count, 128):
            batch_count = min(128, count - start)
            text = _query(client, f"TDC:WIDTH:DATA? {start},{batch_count}")
            batch = [tuple(map(int, row.split(","))) for row in text.split(";")]
            if len(batch) != batch_count or any(len(row) != 6 or any(v < 0 or v > 0xffffffff for v in row) for row in batch):
                raise RuntimeError(f"Malformed record batch at index {start}")
            records.extend(batch)
        if any(row[0] != index + 1 for index, row in enumerate(records)):
            raise RuntimeError("Missing or reordered cycle IDs; cannot construct a uniform trigger timeline")
        capture["acquisition_ok"] = (
            bool(capture["status"] & 8) and not capture["status"] & 0xf7
            and count == config["sample_count"]
        )
        capture["record_integrity"] = audit_width_records(records, capture["tick_ps"])
        capture["acquisition_ok"] &= capture["record_integrity"]["ok"]
        capture["valid_count"] = sum(bool(row[1] & 1) for row in records)
        capture["flag_counts"] = dict(Counter(
            name for row in records for bit, name in FLAG_BITS.items() if row[1] & (1 << bit)
        ))
        return capture
    finally:
        for command in ("PULSE:OUTPUT OFF", "TDC:WIDTH:ABORT"):
            try:
                client.write(command)
            except Exception as exc:
                capture["cleanup_errors"].append(f"{command}: {exc}")
        try:
            client.close()
        except Exception as exc:
            capture["cleanup_errors"].append(f"close: {exc}")
        if capture["cleanup_errors"]:
            warnings.warn("Cleanup was not fully confirmed: " + "; ".join(capture["cleanup_errors"])
                          + ". Reconnect and run the stop cell; check the trigger with a scope.")


def save_capture(capture, directory):
    """Save raw records and entered settings before analysis, even for faulty bursts."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    stem = directory / ("tdc_pcb_sine_" + stamp)
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow((*FIELDS, "time_s", "width_ns", "valid", "decoded_flags"))
        for row in capture["records"]:
            writer.writerow((*row, (row[0] - 1) * capture["plan"]["period_ns"] * 1e-9,
                             row[5] / 1000, int(bool(row[1] & 1)), decode_bits(row[1])))
    metadata = {key: value for key, value in capture.items() if key != "records"}
    metadata["timing_caveat"] = "Current implementation has known timing violations; results are diagnostic."
    metadata["reference_caveat"] = "No PCB voltage calibration; generator Vpp/offset are entered settings, not measurements."
    stem.with_suffix(".json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    return stem


def fit_sine(time_s, values, frequency_hz):
    """Least squares at fixed frequency; phase, amplitude and DC are fitted."""
    omega_t = 2 * np.pi * frequency_hz * np.asarray(time_s)
    design = np.column_stack((np.ones_like(omega_t), np.sin(omega_t), np.cos(omega_t)))
    coeff, _, rank, _ = np.linalg.lstsq(design, values, rcond=None)
    if rank < 3:
        raise ValueError("Insufficient phase coverage for a sine fit")
    residual = np.asarray(values) - design @ coeff
    return {
        "frequency_hz": float(frequency_hz), "offset": float(coeff[0]),
        "amplitude": float(np.hypot(coeff[1], coeff[2])),
        "phase_rad": float(np.arctan2(coeff[2], coeff[1])),
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "sse": float(residual @ residual),
    }


def sine_values(time_s, fit):
    return fit["offset"] + fit["amplitude"] * np.sin(
        2 * np.pi * fit["frequency_hz"] * np.asarray(time_s) + fit["phase_rad"]
    )


def _dominant_frequency(time_s, widths_ns, valid, sample_rate_hz):
    # Zero-mask invalid slots for the candidate spectrum, preserving timing.
    # All subsequent fitting uses only genuine valid samples at their own times.
    centered = np.where(valid, widths_ns - np.mean(widths_ns[valid]), 0.0)
    spectrum = np.abs(np.fft.rfft(centered * np.hanning(len(centered))))
    frequencies = np.fft.rfftfreq(len(centered), 1 / sample_rate_hz)
    candidates = np.argsort(spectrum[1:-1])[-5:] + 1
    bin_hz = sample_rate_hz / len(centered)
    best = None
    # Several FFT candidates handle leakage; no configured sine frequency is
    # used here, so a wrong generator frequency can be detected independently.
    for index in candidates:
        low = max(bin_hz / 4, frequencies[index] - bin_hz)
        high = min(sample_rate_hz / 2 * (1 - 1e-9), frequencies[index] + bin_hz)
        grid = np.linspace(low, high, 25)
        fits = [fit_sine(time_s[valid], widths_ns[valid], frequency) for frequency in grid]
        winner = int(np.argmin([fit["sse"] for fit in fits]))
        left, right = grid[max(0, winner - 1)], grid[min(len(grid) - 1, winner + 1)]
        # Bounded refinement around the best grid point.
        ratio = (math.sqrt(5) - 1) / 2
        for _ in range(28):
            a, b = right - ratio * (right - left), left + ratio * (right - left)
            if fit_sine(time_s[valid], widths_ns[valid], a)["sse"] < fit_sine(time_s[valid], widths_ns[valid], b)["sse"]:
                right = b
            else:
                left = a
        candidate = fit_sine(time_s[valid], widths_ns[valid], (left + right) / 2)
        if best is None or candidate["sse"] < best["sse"]:
            best = candidate
    return best, frequencies, spectrum


def analyze_capture(capture):
    rows = np.asarray(capture["records"], dtype=np.uint64)
    if rows.ndim != 2 or rows.shape[1] != 6 or len(rows) < 32:
        raise ValueError("Need at least 32 records for sine analysis; inspect/save raw capture first")
    if not capture.get("acquisition_ok", False):
        raise ValueError("Incomplete/error burst: inspect status/flags and saved raw data before fitting")
    audit = audit_width_records(capture["records"], capture["tick_ps"])
    if not audit["ok"]:
        raise ValueError(f"Contradictory hardware records ({audit['bad_record_count']} rows): "
                         f"{audit['violation_counts']}. Inspect raw capture and implementation timing.")
    if not np.array_equal(rows[:, 0], np.arange(1, len(rows) + 1)):
        raise ValueError("Missing/reordered cycle IDs")
    time_s = (rows[:, 0].astype(float) - 1) * capture["plan"]["period_ns"] * 1e-9
    width_ns = rows[:, 5].astype(float) / 1000
    valid = (rows[:, 1] & 1) != 0
    if np.count_nonzero(valid) < 32:
        raise ValueError("Fewer than 32 valid pulses; inspect flags and PCB output")
    if np.ptp(width_ns[valid]) <= 1e-12:
        raise ValueError("No resolved width variation: check analogue drive, PCB response and TDC input")
    fixed = fit_sine(time_s[valid], width_ns[valid], capture["settings"]["sine_frequency_hz"])
    if fixed["amplitude"] <= 1e-12:
        raise ValueError("No sine component at the configured frequency")
    dominant, fft_hz, fft_magnitude = _dominant_frequency(time_s, width_ns, valid, capture["plan"]["actual_fpga_hz"])
    fixed_curve = sine_values(time_s, fixed)
    variance = float(np.sum((width_ns[valid] - np.mean(width_ns[valid])) ** 2))
    notes = []
    if capture["plan"]["sine_cycles"] < 5:
        notes.append("Fewer than five configured sine cycles: frequency/shape estimates may be unstable.")
    if capture["plan"]["samples_per_sine_cycle"] < 10:
        notes.append("Fewer than ten samples per sine period: increase trigger rate or reduce analogue frequency.")
    if not np.all(valid):
        notes.append("Invalid frames are excluded, but their time slots are retained; the spectrum is masked/diagnostic.")
    if np.mean(valid) < 0.8:
        notes.append("Over 20% invalid frames: do not trust the frequency estimate; repair acquisition first.")
    if fixed["amplitude"] < capture["tick_ps"] / 1000:
        notes.append("Fitted width amplitude is below one coarse tick; modulation is poorly resolved.")
    if np.any(width_ns[valid] >= capture["plan"]["period_ns"] - 8):
        notes.append("Some widths approach the trigger period: LOW gap may be too short or pulses may saturate.")
    if abs(dominant["frequency_hz"] - fixed["frequency_hz"]) > capture["plan"]["actual_fpga_hz"] / len(rows):
        notes.append("Dominant tone differs by more than one FFT bin: check entered frequency, distortion and generator settings.")
    return {
        "time_s": time_s, "width_ns": width_ns, "valid": valid,
        "fixed_fit": fixed, "fixed_curve_ns": fixed_curve,
        "normalized_width": np.where(valid, (width_ns - fixed["offset"]) / fixed["amplitude"], np.nan),
        "normalized_reference": (fixed_curve - fixed["offset"]) / fixed["amplitude"],
        "residual_ns": np.where(valid, width_ns - fixed_curve, np.nan),
        "dominant_fit": dominant, "fft_hz": fft_hz, "fft_magnitude": fft_magnitude,
        "r_squared": 1 - fixed["sse"] / variance,
        "normalized_rmse": fixed["rmse"] / fixed["amplitude"],
        "notes": notes,
    }
