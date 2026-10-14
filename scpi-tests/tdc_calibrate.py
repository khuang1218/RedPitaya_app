#!/usr/bin/env python3
"""Collect, calculate, upload, verify and save a CARRY4 TDC calibration."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import redpitaya_scpi as scpi


CALIBRATION_COMPLETE = 1 << 17
RESULT_VALID = 1 << 0


def query_csv(rp: scpi.scpi, command: str) -> list[int]:
    text = rp.txrx_txt(command).strip().strip("{}")
    if not text:
        return []
    return [int(item.strip(), 0) for item in text.split(",")]


def send(rp: scpi.scpi, command: str) -> None:
    rp.tx_txt(command)


def collect_histogram(rp: scpi.scpi, target: int, wait_seconds: float,
                      poll_seconds: float, chunk: int) -> tuple[int, list[int]]:
    send(rp, "TDC:CALibration:STARt {}".format(target))
    deadline = time.monotonic() + wait_seconds
    status = 0
    events = 0
    while time.monotonic() < deadline:
        status, events = query_csv(rp, "TDC:CALibration:STATus?")
        print("\rvalid calibration events: {:,}/{:,}".format(events, target),
              end="", flush=True)
        if status & CALIBRATION_COMPLETE:
            break
        time.sleep(poll_seconds)
    print()
    send(rp, "TDC:CALibration:STOP")
    if not (status & CALIBRATION_COMPLETE):
        raise TimeoutError(
            "calibration did not reach {} events within {} seconds (got {})".format(
                target, wait_seconds, events))

    taps = int(rp.txrx_txt("TDC:TAPs?"))
    histogram: list[int] = []
    for start in range(0, taps, chunk):
        count = min(chunk, taps - start)
        histogram.extend(query_csv(
            rp, "TDC:CALibration:HISTogram? {},{}".format(start, count)))
    if len(histogram) != taps:
        raise RuntimeError("expected {} histogram bins, received {}".format(
            taps, len(histogram)))
    return events, histogram


def find_internal_dead_zones(histogram: list[int], max_benign_run: int,
                             taps_per_carry4: int = 4) -> list[dict]:
    """Flag contiguous runs of zero-count bins that sit strictly inside the
    populated range of the chain.

    Two kinds of zero run are expected and benign, so they are not reported:
    the leading/trailing edges (before the first / after the last populated
    bin -- the chain start/saturation region and the deliberately-longer-
    than-one-period tail, see HANDOVER section 16.3), and short 1-2 bin dips
    that land on a CARRY4-to-CARRY4 cascade seam (index a multiple of
    ``taps_per_carry4``), a normal artifact of that connection using a
    different route than the four intra-cell taps.

    A run longer than ``max_benign_run`` bins that is *not* at a cascade seam
    and *not* at the edge of the populated range indicates something more
    structural. On this project's first hardware build, one such run (raw
    taps 305-320, CARRY4 cells 76-80) was confirmed by querying
    ``CLOCK_REGION`` in Vivado to be a clock-region boundary crossing between
    ``gen_carry[77]`` and ``gen_carry[78]``: the dedicated CARRY4 CO->CIN
    cascade wire only exists within one clock region, so the connection
    crossing to the next region detours through general routing and settles
    several downstream taps together instead of progressively, producing
    missing codes rather than one wide bin. Clock regions on this device are
    roughly 50 rows tall, so a single 128-CARRY4 vertical column crosses at
    least one such boundary *no matter which* SLICE_X/Y0 it is placed at --
    this is not fixable by re-placement, and is expected to reappear (not
    necessarily at the same tap index) on any similarly long single-column
    build. Use ``--known-dead-zone`` to record ranges already characterized
    this way so re-runs only warn about genuinely new/unexpected ones.
    """
    populated = [index for index, count in enumerate(histogram) if count != 0]
    if not populated:
        return []
    first_populated, last_populated = populated[0], populated[-1]

    zones = []
    run_start = None
    for index in range(first_populated, last_populated + 2):
        is_dead = index > last_populated or histogram[index] == 0
        if is_dead and run_start is None:
            run_start = index
        elif not is_dead and run_start is not None:
            run_length = index - run_start
            on_cascade_seam = run_length <= 2 and run_start % taps_per_carry4 == 0
            if run_length > max_benign_run and not on_cascade_seam:
                zones.append({
                    "start_index": run_start,
                    "end_index": run_start + run_length - 1,
                    "length": run_length,
                    "first_carry4_cell": run_start // taps_per_carry4,
                    "last_carry4_cell": (run_start + run_length - 1) // taps_per_carry4,
                })
            run_start = None
    return zones


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


def classify_dead_zones(zones: list[dict],
                        known_ranges: list[tuple[int, int]]) -> tuple[list[dict], list[dict]]:
    """Split detected dead zones into ones fully covered by a previously
    documented/accepted range and genuinely new/unexpected ones."""
    documented, new = [], []
    for zone in zones:
        covered = any(known_start <= zone["start_index"] and zone["end_index"] <= known_end
                      for known_start, known_end in known_ranges)
        (documented if covered else new).append(zone)
    return documented, new


def calculate_lut(histogram: list[int], period_ps: int,
                  minimum_useful_bins: int,
                  max_benign_dead_run: int = 2,
                  known_dead_zones: list[tuple[int, int]] | None = None) -> tuple[list[int], dict]:
    total = sum(histogram)
    if total == 0:
        raise ValueError("histogram is empty; check the asynchronous phase source")

    ideal_preview = period_ps / max(1, sum(1 for count in histogram if count != 0))
    large_dead_zones = find_internal_dead_zones(histogram, max_benign_dead_run)
    documented_zones, new_zones = classify_dead_zones(
        large_dead_zones, known_dead_zones or [])

    for zone in documented_zones:
        zone_ps = zone["length"] * ideal_preview
        print("dead zone at taps {}-{} ({} bins, ~{:.1f} ps, CARRY4 cells {}-{}): "
              "matches a documented --known-dead-zone, treating as expected.".format(
                  zone["start_index"], zone["end_index"], zone["length"], zone_ps,
                  zone["first_carry4_cell"], zone["last_carry4_cell"]))
    if new_zones:
        print("WARNING: {} NEW/unexpected large internal dead zone(s) detected -- "
              "not covered by any --known-dead-zone:".format(len(new_zones)))
        for zone in new_zones:
            zone_ps = zone["length"] * ideal_preview
            print("  taps {}-{} ({} bins, ~{:.1f} ps, CARRY4 cells {}-{})".format(
                zone["start_index"], zone["end_index"], zone["length"], zone_ps,
                zone["first_carry4_cell"], zone["last_carry4_cell"]))
        print("  Likely cause: a clock-region boundary crossing in the carry column "
              "(see find_internal_dead_zones() docstring). Confirm with "
              "get_property CLOCK_REGION [get_sites -of <cell>] on the CARRY4 cells "
              "spanning this range in Vivado's Device view; if confirmed, add "
              "--known-dead-zone {}-{} to accept it on future runs.".format(
                  new_zones[0]["start_index"], new_zones[0]["end_index"]))

    widths = [period_ps * count / total for count in histogram]
    lut: list[int] = []
    cumulative = 0.0
    for width in widths:
        center = round(cumulative + width / 2.0)
        lut.append(max(lut[-1] if lut else 0, min(65535, center)))
        cumulative += width

    useful = [width for width, count in zip(widths, histogram) if count != 0]
    if len(useful) < minimum_useful_bins:
        raise ValueError(
            "only {} populated bins; the calibration source does not provide "
            "enough phase coverage (minimum requested is {})".format(
                len(useful), minimum_useful_bins))
    ideal = period_ps / len(useful)
    dnl = [(width / ideal - 1.0) if count else None
           for width, count in zip(widths, histogram)]
    inl: list[float | None] = []
    observed_rank = 0
    observed_cumulative = 0.0
    for width, count in zip(widths, histogram):
        if count:
            inl.append(observed_cumulative / ideal - observed_rank)
            observed_cumulative += width
            observed_rank += 1
        else:
            inl.append(None)

    metrics = {
        "total_events": total,
        "useful_bins": len(useful),
        "dead_bins": len(histogram) - len(useful),
        "calibrated_interval_ps": sum(widths),
        "ideal_bin_width_ps": ideal,
        "minimum_bin_width_ps": min(useful),
        "maximum_bin_width_ps": max(useful),
        "peak_abs_dnl_lsb": max(abs(value) for value in dnl if value is not None),
        "peak_abs_inl_lsb": max(abs(value) for value in inl if value is not None),
        "large_dead_zones": large_dead_zones,
        "documented_dead_zones": documented_zones,
        "new_dead_zones": new_zones,
        "width_ps": widths,
        "dnl_lsb": dnl,
        "inl_lsb": inl,
    }
    return lut, metrics


def upload_and_verify(rp: scpi.scpi, lut: list[int], chunk: int) -> None:
    for start in range(0, len(lut), chunk):
        values = lut[start:start + chunk]
        send(rp, "TDC:CALibration:LUT:WRITe {},{}".format(
            start, ",".join(str(value) for value in values)))

    readback: list[int] = []
    for start in range(0, len(lut), chunk):
        count = min(chunk, len(lut) - start)
        readback.extend(query_csv(
            rp, "TDC:CALibration:LUT:READ? {},{}".format(start, count)))
    if readback != lut:
        mismatches = [index for index, values in enumerate(zip(lut, readback))
                      if values[0] != values[1]]
        raise RuntimeError("LUT readback failed at bins {}".format(mismatches[:10]))
    send(rp, "TDC:CALibration:LUT:ACTivate ON")


def precision_test(rp: scpi.scpi, samples: int) -> dict | None:
    if samples == 0:
        return None
    send(rp, "TDC:MODE SINGLE")
    send(rp, "TDC:ENABle ON")
    measured: list[int] = []
    invalid = 0
    for index in range(samples):
        result = query_csv(rp, "TDC:MEASure?")
        if len(result) != 7:
            raise RuntimeError("unexpected TDC:MEASure? response: {}".format(result))
        if result[1] & RESULT_VALID:
            measured.append(result[5])
        else:
            invalid += 1
        print("\rprecision samples: {}/{}".format(index + 1, samples),
              end="", flush=True)
    print()
    send(rp, "TDC:ENABle OFF")
    if not measured:
        return {"requested": samples, "valid": 0, "invalid": invalid}
    mean = statistics.fmean(measured)
    stddev = statistics.pstdev(measured)
    outliers = sum(abs(value - mean) > 3.0 * stddev for value in measured) if stddev else 0
    return {
        "requested": samples,
        "valid": len(measured),
        "invalid": invalid,
        "mean_ps": mean,
        "rms_precision_ps": stddev,
        "peak_to_peak_ps": max(measured) - min(measured),
        "three_sigma_outliers": outliers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Red Pitaya host name or IP address")
    parser.add_argument("--events", type=int, default=1_000_000)
    parser.add_argument("--clock-period-ps", type=int, default=8000)
    parser.add_argument("--chunk", type=int, default=64,
                        help="SCPI histogram/LUT values per transaction")
    parser.add_argument("--wait-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--precision-samples", type=int, default=0)
    parser.add_argument("--minimum-useful-bins", type=int, default=64)
    parser.add_argument("--max-benign-dead-run", type=int, default=2,
                        help="longest zero-count run tolerated as a normal CARRY4 "
                             "cascade-seam artifact before it is flagged as a likely "
                             "placement/routing discontinuity")
    parser.add_argument("--known-dead-zone", type=parse_known_dead_zone, action="append",
                        default=[], metavar="START-END",
                        help="raw tap index range (inclusive, e.g. 305-320) already "
                             "characterized as an expected clock-region-crossing dead "
                             "zone on this bitstream/placement. Repeatable. Zones "
                             "matching a documented range are reported informationally "
                             "instead of as a warning; anything else is flagged as new.")
    parser.add_argument("--internal", action="store_true",
                        help="use the FPGA's asynchronous internal self-test source")
    parser.add_argument("--collect-only", action="store_true",
                        help="calculate/save metrics without uploading or activating the LUT")
    parser.add_argument("--board-serial", default="unknown")
    parser.add_argument("--bitstream-id", required=True,
                        help="Git hash or unique identifier for the placed bitstream")
    parser.add_argument("--temperature-c", type=float)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.events <= 0 or args.clock_period_ps <= 0 or args.chunk <= 0:
        parser.error("events, clock period and chunk must be positive")

    output = args.output or Path("tdc_calibration_{}.json".format(
        datetime.now().strftime("%Y%m%d_%H%M%S")))
    rp = scpi.scpi(args.host, timeout=max(10.0, args.poll_seconds * 4.0))
    try:
        send(rp, "TDC:TEST:INTernal {}".format("ON" if args.internal else "OFF"))
        events, histogram = collect_histogram(
            rp, args.events, args.wait_seconds, args.poll_seconds, args.chunk)
        lut, metrics = calculate_lut(
            histogram, args.clock_period_ps, args.minimum_useful_bins,
            args.max_benign_dead_run, args.known_dead_zone)
        if not args.collect_only:
            upload_and_verify(rp, lut, args.chunk)
        precision = precision_test(rp, args.precision_samples)
    finally:
        rp.close()

    document = {
        "format": "red-pitaya-carry4-tdc-calibration-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "board_serial": args.board_serial,
        "bitstream_id": args.bitstream_id,
        "temperature_c": args.temperature_c,
        "stimulus_source": "internal_ps_fclk_divider" if args.internal else "external_e3_return",
        "lut_uploaded_and_activated": not args.collect_only,
        "num_taps": len(histogram),
        "clock_period_ps": args.clock_period_ps,
        "events_collected": events,
        "histogram": histogram,
        "lut_bin_center_ps": lut,
        "metrics": metrics,
        "precision_test": precision,
    }
    output.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")

    dead_zone_ps = sum(zone["length"] for zone in metrics["large_dead_zones"]) * metrics["ideal_bin_width_ps"]
    coverage_pct = 100.0 * metrics["useful_bins"] / len(histogram)

    print()
    print("=" * 72)
    print("TDC calibration summary -- {}".format(output))
    print("=" * 72)
    print("source            : {}".format(document["stimulus_source"]))
    print("bitstream         : {}".format(args.bitstream_id))
    print("events collected  : {:,} / {:,} requested".format(events, args.events))
    print("taps              : {} total, {} useful ({:.1f}% of range), {} dead".format(
        len(histogram), metrics["useful_bins"], coverage_pct, metrics["dead_bins"]))
    print("bin width (ps)    : min {:.2f} / ideal {:.2f} / max {:.2f}".format(
        metrics["minimum_bin_width_ps"], metrics["ideal_bin_width_ps"],
        metrics["maximum_bin_width_ps"]))
    print("chain coverage    : {:.1f} ps calibrated over an {} ps clock period".format(
        metrics["calibrated_interval_ps"], args.clock_period_ps))
    print("linearity         : peak |DNL| {:.3f} LSB, peak |INL| {:.3f} LSB".format(
        metrics["peak_abs_dnl_lsb"], metrics["peak_abs_inl_lsb"]))
    print("LUT               : {}".format(
        "uploaded and activated" if not args.collect_only else "computed only (--collect-only)"))

    if metrics["documented_dead_zones"]:
        print("-" * 72)
        print("documented dead zones (matched --known-dead-zone, expected):")
        for zone in metrics["documented_dead_zones"]:
            print("  taps {:>3}-{:<3} | {:>2} bins | ~{:5.1f} ps | CARRY4 cells {}-{}".format(
                zone["start_index"], zone["end_index"], zone["length"],
                zone["length"] * metrics["ideal_bin_width_ps"],
                zone["first_carry4_cell"], zone["last_carry4_cell"]))

    if metrics["new_dead_zones"]:
        print("-" * 72)
        print("!! {} NEW/unexpected dead zone(s) -- not covered by --known-dead-zone !!".format(
            len(metrics["new_dead_zones"])))
        for zone in metrics["new_dead_zones"]:
            print("  taps {:>3}-{:<3} | {:>2} bins | ~{:5.1f} ps | CARRY4 cells {}-{}".format(
                zone["start_index"], zone["end_index"], zone["length"],
                zone["length"] * metrics["ideal_bin_width_ps"],
                zone["first_carry4_cell"], zone["last_carry4_cell"]))
        print("  Check CLOCK_REGION on these CARRY4 cells in Vivado before trusting")
        print("  this LUT range; once characterized, re-run with --known-dead-zone.")
    elif metrics["large_dead_zones"]:
        print("-" * 72)
        print("All {} large dead zone(s) match a documented --known-dead-zone -- "
              "no new anomalies this run (~{:.0f} ps, {:.1f}% of the range affected).".format(
                  len(metrics["large_dead_zones"]), dead_zone_ps, dead_zone_ps / args.clock_period_ps * 100.0))
    else:
        print("-" * 72)
        print("No large internal dead zones detected (only ordinary CARRY4-seam "
              "ripple and the expected end-of-chain tail).")

    if precision:
        print("-" * 72)
        print("precision test    : {} / {} valid".format(precision["valid"], precision["requested"]))
        if precision["valid"]:
            print("  mean {:.1f} ps, RMS {:.2f} ps, p-p {:.1f} ps, {} outliers > 3 sigma".format(
                precision["mean_ps"], precision["rms_precision_ps"],
                precision["peak_to_peak_ps"], precision["three_sigma_outliers"]))
    print("=" * 72)


if __name__ == "__main__":
    main()
