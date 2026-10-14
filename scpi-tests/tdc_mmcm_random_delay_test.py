#!/usr/bin/env python3
"""Closed-loop internal self-test for the LVDS CARRY4 TDC.

For each of several random target delays, command the dedicated MMCM
phase-sweep source to realize that delay (a random whole-clock-cycle coarse
part plus a random fine phase-step count), take several repeated single-shot
TDC measurements at that fixed commanded point, then move on to the next
random point. This exercises the full commanded-delay -> physical edge ->
coarse+fine digitization loop entirely inside the FPGA, with no E3 cable
needed, and reports both:

  - repeatability: how tightly repeated measurements at the SAME commanded
    point agree with each other (jitter), and
  - linearity/trend: how well the measured delay tracks the commanded delay
    across many DIFFERENT random points (correlation, linear fit).

This does not calibrate or certify absolute picoseconds -- the MMCM's
phase-step size is nominal (~17.86 ps, see tdc_registers.md) and the mapping
from raw tap index to time still depends on whatever LUT/diagnostic-average
mode is currently active on the device. It also does not exercise the E3
electrical path. See HANDOVER.md and TDC_IMPLEMENTATION_ANALYSIS.md.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import redpitaya_scpi as scpi

# CLKFBOUT_MULT_F=8 and the MMCME2_ADV fine phase-shift granularity of 1/56th
# of a VCO period together give exactly 8*56 = 448 nominal phase steps per
# adc_clk period, regardless of the nominal clock period value used below.
STEPS_PER_PERIOD = 448

MMCM_STATUS_LOCKED = 1 << 0
MMCM_STATUS_PS_BUSY = 1 << 1
MMCM_STATUS_PS_TIMEOUT = 1 << 2
RESULT_VALID = 1 << 0


def send(rp: scpi.scpi, command: str) -> None:
    rp.tx_txt(command)


def query_csv(rp: scpi.scpi, command: str) -> list[int]:
    text = rp.txrx_txt(command).strip().strip("{}")
    if not text:
        return []
    return [int(item.strip(), 0) for item in text.split(",")]


def query_int(rp: scpi.scpi, command: str) -> int:
    return int(rp.txrx_txt(command).strip(), 0)


def parse_known_dead_zone(text: str) -> tuple[int, int]:
    """Parse a '<start>-<end>' inclusive raw-tap-index range, e.g. '305-320'."""
    try:
        start_text, end_text = text.split("-", 1)
        start, end = int(start_text), int(end_text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected '<start>-<end>' raw tap indices, e.g. '305-320', got {!r}".format(text))
    if start > end:
        raise argparse.ArgumentTypeError(
            "start index must not exceed end index in {!r}".format(text))
    return start, end


def wait_for_mmcm_lock(rp: scpi.scpi, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if query_int(rp, "TDC:MMCM:STATus?") & MMCM_STATUS_LOCKED:
            return True
        time.sleep(0.05)
    return False


def move_phase_to(rp: scpi.scpi, target_steps: int, max_stalls: int = 5) -> int:
    """Ratchet the MMCM's absolute phase-step count to target_steps.

    The FPGA only supports relative increment/decrement requests, so this
    reads the hardware's own accumulated counter (rather than trusting a
    locally tracked value) and issues one step at a time, re-checking the
    counter after every request. A step that times out is not assumed to
    have happened -- the loop simply reads the counter again and keeps
    going, so a dropped step just costs a retry rather than corrupting the
    trial. Gives up (raising) only if the counter stops moving entirely.
    """
    current = query_int(rp, "TDC:MMCM:PHASe:COUNt?")
    stalled = 0
    while current != target_steps:
        direction = "INCREASE" if target_steps > current else "DECREASE"
        send(rp, "TDC:MMCM:STEP {}".format(direction))
        status = query_int(rp, "TDC:MMCM:STATus?")
        if status & MMCM_STATUS_PS_TIMEOUT:
            send(rp, "TDC:MMCM:TIMeout:CLEar")
        previous, current = current, query_int(rp, "TDC:MMCM:PHASe:COUNt?")
        stalled = 0 if current != previous else stalled + 1
        if stalled >= max_stalls:
            raise RuntimeError(
                "MMCM phase counter stopped moving at {} (target {}); "
                "check TDC:MMCM:STATus? for a persistent PS_TIMEOUT".format(
                    current, target_steps))
    return current


def measure_once(rp: scpi.scpi) -> list[int]:
    result = query_csv(rp, "TDC:MEASure?")
    if len(result) != 7:
        raise RuntimeError("unexpected TDC:MEASure? response: {}".format(result))
    return result


def run_trial(rp: scpi.scpi, clock_period_ps: int, nominal_step_ps: float,
             commanded_coarse: int, commanded_phase: int, repeats: int) -> dict:
    send(rp, "TDC:MMCM:COARse:DELay {}".format(commanded_coarse))
    actual_phase = move_phase_to(rp, commanded_phase)
    commanded_ps = commanded_coarse * clock_period_ps + commanded_phase * nominal_step_ps

    samples = []
    for _ in range(repeats):
        send(rp, "TDC:ENABle ON")
        sequence, status, coarse, fine_raw, fine_ps, total_ps, _ = measure_once(rp)
        send(rp, "TDC:ENABle OFF")
        samples.append({
            "sequence": sequence,
            "status": status,
            "valid": bool(status & RESULT_VALID),
            "coarse_cycles": coarse,
            "fine_raw_index": fine_raw,
            "fine_time_ps": fine_ps,
            "total_time_ps": total_ps,
        })

    valid_totals = [s["total_time_ps"] for s in samples if s["valid"]]
    measured_mean = statistics.fmean(valid_totals) if valid_totals else None
    # None (not 0.0) when fewer than two valid samples: there is no jitter
    # estimate to make, and a stray 0.0 would silently bias the aggregate
    # mean_repeat_jitter_ps low if it were averaged in as "no jitter".
    measured_stddev = statistics.pstdev(valid_totals) if len(valid_totals) > 1 else None

    return {
        "commanded_coarse_cycles": commanded_coarse,
        "commanded_phase_steps": commanded_phase,
        "commanded_total_ps": commanded_ps,
        "phase_verified": actual_phase == commanded_phase,
        "actual_phase_steps": actual_phase,
        "repeat_count": repeats,
        "valid_count": len(valid_totals),
        "measured_mean_ps": measured_mean,
        "measured_stddev_ps": measured_stddev,
        "error_ps": (measured_mean - commanded_ps) if measured_mean is not None else None,
        "samples": samples,
    }


def linear_fit(xs: list[float], ys: list[float]) -> dict:
    """Ordinary least-squares fit of measured (ys) vs commanded (xs) delay,
    plus the Pearson correlation coefficient and residual RMS. This is a
    self-consistency/trend check, not a calibration -- it says nothing about
    absolute picosecond accuracy on its own."""
    n = len(xs)
    if n < 2:
        return {"n": n, "slope": None, "intercept": None, "correlation": None,
                "residual_rms_ps": None}
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return {"n": n, "slope": None, "intercept": None, "correlation": None,
                "residual_rms_ps": None}
    slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x
    correlation = cov_xy / (var_x ** 0.5 * var_y ** 0.5)
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    residual_rms = (sum(r * r for r in residuals) / n) ** 0.5
    return {"n": n, "slope": slope, "intercept": intercept,
            "correlation": correlation, "residual_rms_ps": residual_rms}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host", help="Red Pitaya host name or IP address")
    parser.add_argument("--trials", type=int, default=40,
                        help="number of distinct random commanded delays")
    parser.add_argument("--repeats", type=int, default=5,
                        help="repeated measurements taken at each random delay, "
                             "to characterize repeatability/jitter at that point")
    parser.add_argument("--max-coarse-cycles", type=int, default=3,
                        help="random commanded coarse delay is drawn from "
                             "[0, this] whole clock cycles")
    parser.add_argument("--max-phase-steps", type=int, default=None,
                        help="random commanded phase is drawn from [0, this] "
                             "steps; defaults to one full period (%d steps)" %
                             (STEPS_PER_PERIOD - 1))
    parser.add_argument("--clock-period-ps", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed; omit for a fresh random seed, which is "
                             "still logged in the output for later reproduction")
    parser.add_argument("--known-dead-zone", type=parse_known_dead_zone, action="append",
                        default=[], metavar="START-END",
                        help="raw tap index range already characterized as an "
                             "expected clock-region-crossing dead zone (see "
                             "tdc_calibrate.py); measured samples landing there "
                             "are flagged informationally, not as failures")
    parser.add_argument("--lock-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.trials <= 0 or args.repeats <= 0 or args.clock_period_ps <= 0:
        parser.error("trials, repeats and clock period must be positive")
    max_phase = STEPS_PER_PERIOD - 1 if args.max_phase_steps is None else args.max_phase_steps
    if max_phase < 0 or args.max_coarse_cycles < 0:
        parser.error("max-phase-steps and max-coarse-cycles must be >= 0")

    seed = args.seed if args.seed is not None else random.SystemRandom().getrandbits(32)
    rng = random.Random(seed)
    nominal_step_ps = args.clock_period_ps / STEPS_PER_PERIOD

    targets = [{
        "trial_index": i,
        "commanded_coarse_cycles": rng.randint(0, args.max_coarse_cycles),
        "commanded_phase_steps": rng.randint(0, max_phase),
    } for i in range(args.trials)]

    # Visit ascending phase order so the whole run steps monotonically forward
    # through the phase range once, instead of potentially re-walking a large
    # chunk of it for every single trial in random order. Coarse delay is a
    # plain register write, free to reorder however phase order dictates.
    execution_order = sorted(targets, key=lambda t: t["commanded_phase_steps"])

    output = args.output or Path("tdc_mmcm_random_delay_test_{}.json".format(
        datetime.now().strftime("%Y%m%d_%H%M%S")))

    rp = scpi.scpi(args.host, timeout=10.0)
    results = []
    try:
        send(rp, "TDC:RESet")
        send(rp, "TDC:MMCM:ENABle ON")
        if not wait_for_mmcm_lock(rp, args.lock_timeout_seconds):
            raise RuntimeError("dedicated MMCM did not lock within {} s".format(
                args.lock_timeout_seconds))
        send(rp, "TDC:MMCM:PHASe:CLEar")
        send(rp, "TDC:MMCM:COARse:DELay 0")
        send(rp, "TDC:MODE SINGLE")
        lut_active = rp.txrx_txt("TDC:CALibration:LUT:ACTivate?").strip() in ("1", "ON", "true", "True")

        for done, target in enumerate(execution_order, start=1):
            outcome = run_trial(rp, args.clock_period_ps, nominal_step_ps,
                                target["commanded_coarse_cycles"],
                                target["commanded_phase_steps"], args.repeats)
            outcome["trial_index"] = target["trial_index"]
            results.append(outcome)
            print("\rtrial {}/{}  coarse={} phase={:4d}  {}/{} valid  "
                  "mean={} ps  jitter(RMS)={} ps".format(
                      done, len(execution_order), outcome["commanded_coarse_cycles"],
                      outcome["commanded_phase_steps"], outcome["valid_count"], args.repeats,
                      "n/a" if outcome["measured_mean_ps"] is None else "{:.1f}".format(outcome["measured_mean_ps"]),
                      "n/a" if outcome["measured_stddev_ps"] is None else "{:.2f}".format(outcome["measured_stddev_ps"])),
                  end="", flush=True)
        print()
    finally:
        send(rp, "TDC:ENABle OFF")
        send(rp, "TDC:MMCM:ENABle OFF")
        send(rp, "TDC:MMCM:COARse:DELay 0")
        rp.close()

    results.sort(key=lambda r: r["trial_index"])

    # Cross-check: did any measured sample land inside a documented dead
    # zone? Should essentially never happen by definition, so any hit here
    # is worth a second look, but it is reported informationally, not as a
    # failure -- see tdc_calibrate.py's find_internal_dead_zones().
    dead_zone_hits = [
        {"trial_index": r["trial_index"], "fine_raw_index": s["fine_raw_index"]}
        for r in results for s in r["samples"]
        if s["valid"] and any(start <= s["fine_raw_index"] <= end
                              for start, end in args.known_dead_zone)
    ]

    phase_mismatches = [r for r in results if not r["phase_verified"]]
    fully_invalid = [r for r in results if r["valid_count"] == 0]
    partially_invalid = [r for r in results if 0 < r["valid_count"] < args.repeats]

    fit_xs = [r["commanded_total_ps"] for r in results if r["measured_mean_ps"] is not None]
    fit_ys = [r["measured_mean_ps"] for r in results if r["measured_mean_ps"] is not None]
    fit = linear_fit(fit_xs, fit_ys)

    jitter_values = [r["measured_stddev_ps"] for r in results if r["measured_stddev_ps"] is not None]
    mean_jitter = statistics.fmean(jitter_values) if jitter_values else None
    max_jitter = max(jitter_values) if jitter_values else None

    total_samples = args.trials * args.repeats
    total_valid = sum(r["valid_count"] for r in results)

    summary = {
        "trials": args.trials,
        "repeats": args.repeats,
        "total_samples": total_samples,
        "total_valid": total_valid,
        "total_invalid": total_samples - total_valid,
        "phase_mismatch_count": len(phase_mismatches),
        "fully_invalid_trial_count": len(fully_invalid),
        "partially_invalid_trial_count": len(partially_invalid),
        "mean_repeat_jitter_ps": mean_jitter,
        "max_repeat_jitter_ps": max_jitter,
        "linear_fit": fit,
        "known_dead_zone_hits": dead_zone_hits,
        "calibration_lut_active": lut_active,
    }

    document = {
        "format": "red-pitaya-carry4-tdc-mmcm-random-delay-test-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "host": args.host,
        "seed": seed,
        "clock_period_ps": args.clock_period_ps,
        "nominal_phase_step_ps": nominal_step_ps,
        "max_coarse_cycles": args.max_coarse_cycles,
        "max_phase_steps": max_phase,
        "known_dead_zones": [list(zone) for zone in args.known_dead_zone],
        "summary": summary,
        "trials_detail": results,
    }
    output.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    print()
    print("=" * 72)
    print("TDC MMCM random-delay closed-loop test -- {}".format(output))
    print("=" * 72)
    print("seed              : {}  (pass --seed {} to reproduce)".format(seed, seed))
    print("calibration LUT   : {}".format("active" if lut_active else "inactive (diagnostic average fine time)"))
    print("samples           : {:,} total ({} trials x {} repeats), {:,} valid, {:,} invalid".format(
        total_samples, args.trials, args.repeats, total_valid, total_samples - total_valid))
    print("phase verification: {}".format(
        "all {} trials confirmed".format(args.trials) if not phase_mismatches else
        "!! {} of {} trials did NOT reach the commanded phase step -- see phase_mismatch_count !!".format(
            len(phase_mismatches), args.trials)))
    if fully_invalid or partially_invalid:
        print("invalid trials    : {} fully invalid, {} partially invalid (see trials_detail)".format(
            len(fully_invalid), len(partially_invalid)))
    print("-" * 72)
    print("repeatability (jitter at a fixed commanded point):")
    print("  mean RMS jitter : {} ps".format("n/a" if mean_jitter is None else "{:.2f}".format(mean_jitter)))
    print("  max  RMS jitter : {} ps".format("n/a" if max_jitter is None else "{:.2f}".format(max_jitter)))
    print("-" * 72)
    print("linearity/trend (measured vs. commanded across all {} random points):".format(args.trials))
    if fit["slope"] is None:
        print("  not enough valid trials to fit a trend")
    else:
        print("  slope           : {:.4f}  (1.0 would mean measured tracks commanded 1:1)".format(fit["slope"]))
        print("  intercept       : {:.1f} ps".format(fit["intercept"]))
        print("  correlation r   : {:.5f}".format(fit["correlation"]))
        print("  residual RMS    : {:.2f} ps".format(fit["residual_rms_ps"]))
    if dead_zone_hits:
        print("-" * 72)
        print("note: {} valid sample(s) landed inside a documented --known-dead-zone "
              "(unexpected but not itself a failure; see known_dead_zone_hits).".format(
                  len(dead_zone_hits)))
    print("=" * 72)
    print("Remember: this characterizes internal self-consistency and repeatability, "
          "not absolute picosecond accuracy, and does not exercise the E3 electrical path.")


if __name__ == "__main__":
    main()
