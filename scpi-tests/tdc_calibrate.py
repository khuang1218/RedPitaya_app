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


def calculate_lut(histogram: list[int], period_ps: int,
                  minimum_useful_bins: int) -> tuple[list[int], dict]:
    total = sum(histogram)
    if total == 0:
        raise ValueError("histogram is empty; check the asynchronous phase source")

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
            histogram, args.clock_period_ps, args.minimum_useful_bins)
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
    print("saved {}".format(output))
    print("useful bins: {}, min/mean/max width: {:.2f}/{:.2f}/{:.2f} ps".format(
        metrics["useful_bins"], metrics["minimum_bin_width_ps"],
        metrics["ideal_bin_width_ps"], metrics["maximum_bin_width_ps"]))
    print("peak |DNL|: {:.3f} LSB, peak |INL|: {:.3f} LSB".format(
        metrics["peak_abs_dnl_lsb"], metrics["peak_abs_inl_lsb"]))


if __name__ == "__main__":
    main()
