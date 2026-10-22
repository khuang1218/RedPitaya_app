"""Rigol DG5502 Pro + v15 WIDTH acquisition, calibration and saved diagnostics.

Importing this module does not contact instruments. The notebook is the entry
point. AWG and FPGA are programmed to one common period on the FPGA timing grid.
Equal nominal periods do not establish clock/phase synchronization. All records,
including rejected frames, are retained for alignment and delay investigation.
"""
import csv
import json
import math
import socket
import time
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from tdc_sine_tools import audit_width_records


FIELDS = ("frame_id", "flags", "coarse_ticks", "rise_raw", "fall_raw", "width_ps")
FLAGS = {0: "VALID", 1: "NO_RISE", 2: "NO_FALL", 3: "HIGH_START",
         4: "EXTRA_EDGES", 5: "TRIGGER_TIMEOUT", 7: "FINE_INVALID",
         8: "COARSE_ONLY", 9: "CALIBRATED", 10: "BOUNDARY",
         11: "SATURATED", 12: "OUT_OF_RANGE", 13: "LATENCY_OVERFLOW",
         14: "CROSS_FRAME", 15: "RETURN_LATE"}
MANUAL = ("https://www.rigol.com/dam/global/downloads/brochures/en/"
          "program-guide/waveform-generators/DG5000Pro_ProgrammingGuide_EN.pdf"
          "?t=1761022282157")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _pulse_setting_quantum_ns(value_ns):
    """DG5000 Pro width resolution: 100 ps or five significant digits.

    The saved hardware log also shows a 100 ps-quantized pulse-period reply.
    Use one setting quantum as the bound, allowing rounding or truncation.
    This describes setting/readback granularity, not physical timing accuracy.
    """
    return max(0.1, 10.0**(math.floor(math.log10(abs(value_ns)))-4))


def validate_pulse_timing(settings, frequency_hz, width_ns):
    """Accept bounded setting quantization; retain readbacks as references.

    Compare periods rather than applying a fixed frequency tolerance: a 100 ps
    period step near 1 us is approximately a 100 Hz frequency step.
    """
    requested_period = 1e9/float(frequency_hz)
    requested_width = float(width_ns)
    actual_period = float(settings["period_ns"])
    actual_width = float(settings["width_ns"])
    if (not all(math.isfinite(x) for x in (actual_period, actual_width))
            or not 0 < actual_width < actual_period):
        raise RuntimeError("Invalid Rigol pulse period/width readback")
    width_limit = _pulse_setting_quantum_ns(requested_width)
    period_limit = _pulse_setting_quantum_ns(requested_period)
    width_delta = actual_width-requested_width
    period_delta = actual_period-requested_period
    # Small numerical margin prevents rejecting an exactly-on-limit difference.
    if abs(width_delta) > width_limit + 1e-9:
        raise RuntimeError(f"Rigol changed requested width {requested_width} ns to {actual_width} ns; "
                           f"difference exceeds one {width_limit:g} ns setting quantum")
    if abs(period_delta) > period_limit + 1e-9:
        raise RuntimeError(f"Rigol changed requested period {requested_period} ns to {actual_period} ns; "
                           f"difference exceeds one {period_limit:g} ns readback quantum")
    # Keep both FREQ? and pulse PER? replies. Some firmware reports these with
    # different decimal precision; do not pretend they are exact reciprocals.
    frequency_query = settings.get("frequency_query_hz")
    if frequency_query is not None:
        if not math.isfinite(frequency_query) or frequency_query <= 0:
            raise RuntimeError("Invalid Rigol frequency readback")
        if (abs(1e9/frequency_query-requested_period) > period_limit+1e-9
                or abs(1e9/frequency_query-actual_period) > period_limit+1e-9):
            raise RuntimeError("Rigol frequency and pulse-period readbacks disagree beyond setting resolution")
    return dict(requested_period_ns=requested_period, width_delta_ns=width_delta,
                period_delta_ns=period_delta, width_tolerance_ns=width_limit,
                period_tolerance_ns=period_limit,
                note="Bounded setting/readback quantization; analysis uses returned pulse width and period, not the requests.")


def plan_matched_period(frequency_hz, minimum_period_ns=500, frame_period_ns=None):
    """One nominal period for AWG pulses and FPGA launch/acquisition frames.

    The present FPGA uses a 4 ns frame grid. Snap the requested source period
    once, then program the AWG to that same value. Never shorten the frame as
    a function of HIGH/LOW width or add a phase-walking frequency offset.
    This is a settings plan, not verification of either physical clock.
    """
    frequency = float(frequency_hz)
    if not math.isfinite(frequency) or frequency <= 0:
        raise ValueError("Requested common frequency must be finite and positive")
    requested_period = 1e9/frequency
    if requested_period < minimum_period_ns-1e-9:
        raise ValueError(f"Common period {requested_period:g} ns is below the current "
                         f"FPGA minimum {minimum_period_ns:g} ns. No mismatched overspeed frames are allowed.")
    period = 4*math.floor(requested_period/4+0.5)
    if period < minimum_period_ns or period > 8_589_934_588:
        raise ValueError("Common period is outside the FPGA frame range")
    if frame_period_ns is not None:
        override = float(frame_period_ns)
        if not math.isfinite(override) or override != period:
            raise ValueError(f"Separate frame period {frame_period_ns} ns is not allowed; "
                             f"the common period selected from this frequency is {period} ns")
    return dict(policy="matched_period_v1", requested_frequency_hz=frequency,
                requested_period_ns=requested_period, common_period_ns=period,
                common_frequency_hz=1e9/period, grid_ns=4,
                period_rounding_ns=period-requested_period,
                phase_lock_verified=False,
                note="Both instruments receive the same nominal period. Relative phase, clock drift and launch-to-return delay are not established by equal settings.")


def verify_dc_readback(function, application_reply, level_v, arbitrary_type=None):
    """Verify DC using specific waveform identity, allowing a generic ARB reply.

    Offset 0 V alone cannot establish that an arbitrary waveform is constant.
    APPLy? reports the selected waveform as its first field. Older firmware can
    instead expose DC as the selected built-in arbitrary waveform.
    """
    function = function.strip().strip('"').upper()
    application = application_reply.strip().strip('"')
    application_fields = next(csv.reader([application]))
    application_type = application_fields[0].strip().upper() if application_fields else ""
    arb_type = arbitrary_type.strip().strip('"').upper() if arbitrary_type is not None else None
    specific_dc = (application_type in ("DC", "ARB") and
                   (function == "DC" or (function == "ARB" and
                                         (application_type == "DC" or arb_type == "DC"))))
    application_offset = None
    if application_type == "DC":
        if len(application_fields) != 5:
            raise RuntimeError("Malformed Rigol APPLy? DC response: " + application_reply)
        application_offset = float(application_fields[3])
    zero_offsets = (math.isfinite(level_v) and abs(level_v) <= 0.01
                    and (application_offset is None or
                         (math.isfinite(application_offset) and abs(application_offset) <= 0.01)))
    if not specific_dc or not zero_offsets:
        raise RuntimeError("Rigol DC LOW was not verified: "
                           f"FUNC?={function!r}, APPL?={application_reply!r}, "
                           f"FUNC:ARB?={arb_type!r}, offset={level_v!r} V. "
                           "Output remains OFF; an arbitrary waveform at zero offset is not sufficient.")
    return dict(function_readback=function, application_reply=application_reply,
                application_type=application_type, arbitrary_type=arb_type,
                application_offset_v=application_offset, dc_level_v=level_v,
                verified_waveform="DC", dc_verified=True)


def save_json(path, value):
    def convert(item):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, Path):
            return str(item)
        raise TypeError(type(item).__name__)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, default=convert,
                                    allow_nan=False), encoding="utf-8")


class RP:
    def __init__(self, host, port, timeout):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.reader = self.sock.makefile("rb")

    def send(self, command):
        self.sock.sendall((command + "\r\n").encode("ascii"))

    def query(self, command):
        self.send(command)
        line = self.reader.readline(65536)
        if not line or not line.endswith(b"\n"):
            raise RuntimeError("Incomplete FPGA SCPI response: " + command)
        return line.decode("ascii").strip()

    def check(self, command):
        error = self.query("SYST:ERR:NEXT?")
        if int(error.split(",", 1)[0]) != 0:
            raise RuntimeError(f"FPGA {command}: {error}")

    def ask(self, command):
        value = self.query(command)
        self.check(command)
        return value

    def write(self, command):
        self.send(command)
        self.check(command)

    def idle(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            status = int(self.ask("TDC:WIDTH:STATUS?"))
            if not status & 1:
                return status
            if time.monotonic() >= deadline:
                raise TimeoutError("FPGA remained BUSY")
            time.sleep(0.01)

    def close(self):
        try:
            self.reader.close()
        finally:
            self.sock.close()


class Rigol:
    """Selected-output commands; the internal reference-clock selection is global."""
    def __init__(self, config):
        import pyvisa
        self.rm = pyvisa.ResourceManager(config.get("visa_backend", ""))
        self.inst = None
        self.channel = int(config["awg_channel"])
        if self.channel not in (1, 2):
            self.rm.close()
            raise ValueError("DG5502 Pro channel must be 1 or 2")
        self.source = f":SOURce{self.channel}"
        self.output = f":OUTPut{self.channel}"
        self.log = []
        self.last_settings = None
        self._last_io = 0.0
        self.startup_errors = []
        try:
            self.command_delay_s = float(config.get("awg_command_delay_s", 0.02))
            if not math.isfinite(self.command_delay_s) or not 0 <= self.command_delay_s <= 1:
                raise ValueError("AWG command delay must be between zero and one second")
            self.inst = self.rm.open_resource(config["visa_resource"])
            self.inst.timeout = int(config.get("visa_timeout_ms", 10000))
            self.inst.write_termination = self.inst.read_termination = "\n"
            self.identity = self._raw_query("*IDN?")
            fields = self.identity.split(",")
            if (len(fields) < 3 or "RIGOL" not in fields[0].upper()
                    or fields[1].replace(" ", "").upper() != "DG5502PRO"
                    or fields[2].strip() != config["awg_serial"]):
                raise RuntimeError("Unexpected AWG identity: " + self.identity)
            # Retain pre-existing errors before configuring this session. Reading
            # the queue clears its entries; no *CLS hides newly generated errors.
            self.startup_errors = self.read_error_queue("session startup")
            if self.startup_errors:
                warnings.warn("Pre-existing Rigol errors recorded and drained: "
                              + "; ".join(self.startup_errors))
        except BaseException:
            self.close()
            raise

    def _pace(self):
        remaining = (getattr(self, "command_delay_s", 0.02)
                     - (time.monotonic()-getattr(self, "_last_io", 0.0)))
        if remaining > 0:
            time.sleep(remaining)

    def _raw_query(self, command, context=None):
        self._pace()
        value = self.inst.query(command).strip()
        self._last_io = time.monotonic()
        entry = dict(utc=utc_now(), command=command, reply=value)
        if context is not None:
            entry["context"] = context
        self.log.append(entry)
        return value

    def read_error_queue(self, context, limit=64):
        """Bounded drain, logging every reply including the final zero entry."""
        errors = []
        for _ in range(limit):
            # Rigol uses SYST:ERR?, whereas the FPGA uses SYST:ERR:NEXT?.
            error = self._raw_query(":SYSTem:ERRor?", context=context)
            if int(error.split(",", 1)[0]) == 0:
                return errors
            errors.append(error)
        raise RuntimeError("Rigol error queue did not empty after " + str(limit)
                           + " reads: " + "; ".join(errors))

    def check(self, command):
        errors = self.read_error_queue("after " + command)
        if errors:
            raise RuntimeError(f"Rigol errors reported after {command}: " + "; ".join(errors))

    def write(self, command):
        self._pace()
        self.log.append(dict(utc=utc_now(), command=command))
        self.inst.write(command)
        self._last_io = time.monotonic()
        self.check(command)

    def ask(self, command):
        value = self._raw_query(command)
        self.check(command)
        return value

    def off(self):
        self.write(self.output + " OFF")
        if self.ask(self.output + "?") not in ("0", "OFF"):
            raise RuntimeError("AWG OFF was not confirmed")

    def configure(self, frequency_hz, width_ns, config):
        f, w = float(frequency_hz), float(width_ns)
        low, high = float(config["low_v"]), float(config["high_v"])
        period_ns = 1e9 / f if f > 0 else 0
        if not all(math.isfinite(x) for x in (f, w, low, high)):
            raise ValueError("AWG settings must be finite")
        if not 0 < f <= 120e6 or not 0 <= low < high <= 3.3:
            raise ValueError("Use pulse frequency <=120 MHz and 0..3.3 V levels")
        if min(w, period_ns - w) < 4.2 - 1e-9:
            raise ValueError("DG5000 Pro pulse mode needs HIGH and LOW >=4.2 ns")
        self.off()
        # HighZ is the amplitude/load convention for a direct FPGA input.
        self.write(self.output + ":LOAD INFinity")
        self.write(self.output + ":POLarity NORMal")
        self.write(":SYSTem:ROSCillator:SOURce INTernal")
        for parameter in ("FREQuency", "VOLTage", "PHASe"):
            self.write(self.source + f":{parameter}:COUPle:STATe OFF")
        self.write(self.source + ":VOLTage:UNIT VPP")
        # APPLy explicitly selects continuous mode (no inherited burst/sweep).
        self.write(self.source + f":APPLy:PULSe {f:.15g},{high-low:.12g},{(high+low)/2:.12g},0")
        self.off()
        self.write(self.source + ":FUNCtion:PULSe:TRANsition:LEADing MINimum")
        self.write(self.source + ":FUNCtion:PULSe:TRANsition:TRAiling MINimum")
        self.write(self.source + f":FUNCtion:PULSe:WIDTh {w*1e-9:.15g}")
        if self.ask("*OPC?") != "1":
            raise RuntimeError("Rigol configuration did not complete")
        settings = self.readback()
        settings.update(requested_frequency_hz=f, requested_width_ns=w,
                        requested_low_v=low, requested_high_v=high)
        self.last_settings = settings
        settings["setting_quantization"] = validate_pulse_timing(settings, f, w)
        for key, expected in (("low_v", low), ("high_v", high)):
            if abs(settings[key] - expected) > 0.01:
                raise RuntimeError("Rigol voltage readback differs from request")
        if settings["load_ohm"] < 1e6 or settings["polarity"] != "NORM":
            raise RuntimeError("Expected HighZ amplitude convention and normal polarity")
        if settings["clock_source"] != "INT" or not settings["function"].startswith("PULS"):
            raise RuntimeError("Expected independent internal clock and PULSE waveform")
        return settings

    def readback(self):
        ask = self.ask
        period = float(ask(self.source + ":FUNCtion:PULSe:PERiod?"))
        width = float(ask(self.source + ":FUNCtion:PULSe:WIDTh?"))
        return dict(identity=self.identity, channel=self.channel,
                    period_ns=period*1e9, frequency_hz=1/period,
                    frequency_query_hz=float(ask(self.source + ":FREQuency?")),
                    width_ns=width*1e9, low_gap_ns=(period-width)*1e9,
                    duty_percent=100*width/period,
                    low_v=float(ask(self.source + ":VOLTage:LOW?")),
                    high_v=float(ask(self.source + ":VOLTage:HIGH?")),
                    leading_ns=float(ask(self.source + ":FUNCtion:PULSe:TRANsition:LEADing?"))*1e9,
                    trailing_ns=float(ask(self.source + ":FUNCtion:PULSe:TRANsition:TRAiling?"))*1e9,
                    minimum_width_ns=float(ask(self.source + ":FUNCtion:PULSe:WIDTh? MINimum"))*1e9,
                    load_ohm=float(ask(self.output + ":LOAD?")),
                    polarity=ask(self.output + ":POLarity?").upper(),
                    function=ask(self.source + ":FUNCtion?").upper(),
                    clock_source=ask(":SYSTem:ROSCillator:SOURce?").upper())

    def on(self):
        self.write(self.output + " ON")
        if self.ask(self.output + "?") not in ("1", "ON"):
            raise RuntimeError("AWG ON was not confirmed")

    def dc_low(self):
        """Drive a defined 0 V for a negative control instead of floating OFF."""
        self.off()
        # APPLy:DC requires placeholders for the unused frequency/amplitude/phase.
        self.write(self.source + ":APPLy:DC DEFault,DEFault,0,DEFault")
        self.off()
        # Firmware 00.01.00 reports DC as generic ARB. The redundant FUNCtion DC
        # selector was followed by -350 Queue overflow on this instrument.
        # APPLy:DC already selects the waveform and offset; verify its readbacks.
        if self.ask("*OPC?") != "1":
            raise RuntimeError("Rigol DC configuration did not complete")
        function = self.ask(self.source + ":FUNCtion?").upper()
        level = float(self.ask(self.source + ":VOLTage:OFFSet?"))
        application = self.ask(self.source + ":APPLy?")
        application_type = application.strip().strip('"').split(",", 1)[0].upper()
        arbitrary_type = None
        if function == "ARB" and application_type != "DC":
            arbitrary_type = self.ask(self.source + ":FUNCtion:ARBitrary?")
        info = dict(identity=self.identity, channel=self.channel, function=function,
                    application_reply=application, arbitrary_type=arbitrary_type,
                    dc_level_v=level, dc_verified=False,
                    reference="Defined LOW, no expected pulses")
        self.last_settings = info
        info.update(verify_dc_readback(function, application, level, arbitrary_type))
        return info

    def close(self):
        try:
            if self.inst is not None:
                self.inst.close()
        finally:
            self.rm.close()


def rows(capture, both_fine=False, calibrated=False):
    data = np.asarray(capture["records"], dtype=np.uint64).reshape(-1, 6)
    select = (data[:, 1] & 1) != 0
    if both_fine:
        select &= ((data[:, 1] >> 16) & 1) != 0
        select &= ((data[:, 1] >> 24) & 1) != 0
    if calibrated:
        select &= (data[:, 1] & 512) != 0
    return data[select]


def expected_complete_fraction(period, high, window):
    """One full HIGH, LOW at frame start, no second RISE; uniform frame phase.

    Historical uniform-phase geometry only. Do not use this as the expected
    yield for matched-period operation with unknown or calibrated phase.
    """
    low = period - high
    return max(0., min(low, window-high)-max(0., window-period)) / period


def width_distribution(values):
    """Full-distribution and chronological diagnostics; never trims samples."""
    values = np.asarray(values, dtype=float)
    if not len(values):
        return dict(n=0, median_ns=None, min_ns=None, max_ns=None, range_ns=None,
                    p01_ns=None, p99_ns=None, beyond_1ns_from_median=0,
                    block_means_ns=[], block_mean_span_ns=None)
    median = float(np.median(values))
    blocks = [float(b.mean()) for b in np.array_split(values, min(8, len(values)))]
    return dict(n=len(values), median_ns=median, min_ns=float(values.min()), range_ns=float(np.ptp(values)),
                max_ns=float(values.max()), p01_ns=float(np.percentile(values, 1)),
                p99_ns=float(np.percentile(values, 99)),
                beyond_1ns_from_median=int(np.count_nonzero(np.abs(values-median) > 1)),
                block_means_ns=blocks, block_mean_span_ns=float(np.ptp(blocks)))


def summarize(capture):
    complete = rows(capture)
    eligible = rows(capture, both_fine=True)
    fine = rows(capture, calibrated=True)
    count = len(capture["records"])
    result = dict(label=capture["label"], total_frames=count, complete_pulses=len(complete),
                  complete_fraction=len(complete)/max(1, count),
                  expected_complete_fraction=capture.get("expected_complete_fraction"),
                  target_complete_fraction=capture.get("target_complete_fraction"),
                  timing_policy=capture.get("timing", {}).get("policy", "historical_unmatched"),
                  synchronization_qualified=False,
                  both_fine_valid_pulses=len(eligible), calibrated_pulses=len(fine),
                  flag_counts=dict(Counter(name for r in capture["records"]
                                           for b, name in FLAGS.items() if r[1] & (1 << b))),
                  fine_edge_quality={})
    for edge, shift in (("RISE", 16), ("FALL", 24)):
        statuses = (complete[:, 1] >> shift) & 255
        result["fine_edge_quality"][edge] = dict(
            valid_fraction=float(np.count_nonzero(statuses & 1)/len(complete)) if len(complete) else None,
            status_counts=dict(Counter(f"0x{int(s):02x}" for s in statuses)))
    # Separate hardware fine results from coarse fallback. Never select by
    # closeness to the reference, which would artificially improve precision.
    for name, selected in (("all_complete", complete), ("fine_eligible", eligible),
                           ("calibrated_only", fine)):
        values = selected[:, 5].astype(float)/1000
        result[name] = dict(n=len(values),
                            mean_ns=float(values.mean()) if len(values) else None,
                            std_ns=float(values.std(ddof=1)) if len(values) > 1 else None,
                            error_ns=float(values.mean()-capture["reference_ns"])
                            if len(values) and capture["reference_ns"] is not None else None)
        result[name]["distribution"] = width_distribution(values)
    delays = np.asarray([delay*4 for r, delay in
                         zip(capture["records"], capture.get("latency_ticks", []))
                         if r[1] & 1 and delay != 65535], dtype=float)
    result["launch_to_rise_ns"] = dict(
        n=len(delays), minimum=float(delays.min()) if len(delays) else None,
        maximum=float(delays.max()) if len(delays) else None,
        mean=float(delays.mean()) if len(delays) else None,
        std=float(delays.std(ddof=1)) if len(delays)>1 else None,
        resolution_ns=4, reference="Internal launch marker; coarse only, no pin-offset calibration")
    observed = np.asarray([delay*4 for r, delay in
                           zip(capture["records"], capture.get("latency_ticks", []))
                           if not (r[1] & 2) and delay != 65535], dtype=float)
    result["observed_rise_latency_ns"] = dict(
        n=len(observed), minimum=float(observed.min()) if len(observed) else None,
        maximum=float(observed.max()) if len(observed) else None,
        mean=float(observed.mean()) if len(observed) else None,
        includes_invalid_width_records=True, resolution_ns=4)
    return result


def edge_timestamp_diagnostics(records, samples, stride, period_ns, tick_ps=4000, tables=None):
    """Audit V16 sparse timestamps and retain chronological edge drift (no trimming).

    Edge phases are relative to the first valid diagnostic frame. They include
    source/clock/path motion and cannot establish an independent pin reference.
    """
    expected_ids = list(range(1, len(records)+1, stride))
    if [s[0] for s in samples] != expected_ids:
        raise RuntimeError("Sparse diagnostic frame IDs/count do not match width records")
    pairs = []
    valid_coarse_pairs = 0
    for frame, rise, fall in samples:
        r = records[frame-1]
        if r[0] != frame:
            raise RuntimeError("Sparse diagnostic record sequence mismatch")
        if r[1] & 1:
            if ((fall-rise) & 0xffffffff) != r[2]:
                raise RuntimeError("Sparse edge timestamps disagree with coarse width")
            valid_coarse_pairs += 1
            # A coarse fallback does not have qualified fine edge timing.
            # Keep its raw pair and full-width record, but do not apply a LUT
            # to invalid codes in the per-edge phase diagnostic.
            if tables is not None and not r[1] & 512:
                continue
            pairs.append((r, rise, fall))
    result = dict(stride=stride, sampled=len(samples), valid_pairs=len(pairs),
                  valid_coarse_pairs=valid_coarse_pairs,
                  fine_ineligible_pairs=valid_coarse_pairs-len(pairs),
                  units="ns", calibrated_edges=tables is not None,
                  frame_ids=[], rise_phase_ns=[], fall_phase_ns=[])
    for edge, column, tick_column in (("RISE", 3, 1), ("FALL", 4, 2)):
        last_tick = None
        unwrapped = 0
        phase = []
        for r, rise, fall in pairs:
            tick = (rise, fall)[tick_column-1]
            if last_tick is not None:
                unwrapped += ((tick-last_tick+(1 << 31)) & 0xffffffff)-(1 << 31)
            last_tick = tick
            correction = tables[edge][r[column]] if tables is not None else 0
            phase.append(unwrapped*tick_ps-correction
                         -(r[0]-pairs[0][0][0])*period_ns*1000)
        relative = (np.asarray(phase)-phase[0])/1000 if phase else np.asarray([])
        result[edge.lower()+"_phase_ns"] = relative.tolist()
        result[edge.lower()+"_drift"] = width_distribution(relative)
    result["frame_ids"] = [p[0][0] for p in pairs]
    differential = np.asarray(result["fall_phase_ns"])-np.asarray(result["rise_phase_ns"])
    result["width_change_ns"] = differential.tolist()
    result["width_change_distribution"] = width_distribution(differential)
    return result


class Bench:
    def __init__(self, config, directory):
        self.config = dict(config)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.image = None
        self.candidate = None
        self.sequence = 0
        save_json(self.directory / "settings.json", dict(config=self.config, manual=MANUAL,
                                                       created_utc=utc_now()))

    def _rp(self):
        return RP(self.config["rp_ip"], int(self.config["scpi_port"]),
                  float(self.config.get("socket_timeout_s", 10)))

    def _image(self, rp):
        info = dict(width_version=int(rp.ask("TDC:WIDTH:VERSION?")),
                    tick_ps=int(rp.ask("TDC:WIDTH:TICK?")),
                    taps=int(rp.ask("TDC:TAPS?")),
                    capacity=int(rp.ask("TDC:WIDTH:CAPACITY?")),
                    bitstream_label=self.config["bitstream_label"],
                    implementation_wns_ns=self.config.get("implementation_wns_ns"))
        expected_version = int(self.config.get("expected_width_version", 16))
        if info["width_version"] != expected_version or info["tick_ps"] != 4000 or info["taps"] != 512:
            raise RuntimeError(f"Load the matching bitstream: expected VERSION={expected_version}, "
                               "TICK=4000, TAPS=512; " + str(info))
        if info["width_version"] == 13:
            info["association_policy"] = "launch_window_spill_v13"
            # Also establishes that the updated API/server commands are deployed.
            try:
                bounds = tuple(map(int, rp.ask("TDC:WIDTH:DELAY?").split(",")))
            except Exception as exc:
                raise RuntimeError("HDL V13 detected, but return-window readback failed. Deploy matching librp and SCPI server, then restart the server. Original error: " + str(exc)) from exc
            if len(bounds) != 2:
                raise RuntimeError("V13 return-window interface is unavailable; deploy matching API/server")
        if info["width_version"] >= 14:
            info["association_policy"] = "shifted_single_frame_v14"
            try:
                offset = int(rp.ask("TDC:WIDTH:OFFSET?"))
            except Exception as exc:
                raise RuntimeError("V14+ requires matching API/SCPI with TDC:WIDTH:OFFSET: " + str(exc)) from exc
            if not 0 <= offset <= 262140 or offset % 4:
                raise RuntimeError("Invalid frame-offset readback")
        info["minimum_period_ns"] = 500 if info["width_version"] >= 10 else 1000
        if info["width_version"] >= 16:
            try:
                minimum = int(rp.ask("TDC:WIDTH:MINIMUM:PERIOD?"))
                stride, capacity = map(int, rp.ask("TDC:WIDTH:DIAGNOSTIC:CONFIG?").split(","))
            except Exception as exc:
                raise RuntimeError("V16 needs the updated API and SCPI server (MINIMUM:PERIOD and DIAGNOSTIC commands): " + str(exc)) from exc
            if minimum < 200 or minimum % 4 or stride != 64 or capacity != (info["capacity"]+stride-1)//stride:
                raise RuntimeError("Invalid V16 minimum period or diagnostic configuration")
            info.update(minimum_period_ns=minimum, diagnostic_stride=stride,
                        diagnostic_capacity=capacity)
        if rp.ask("PULSE:PIN?") != "DIO1_P":
            raise RuntimeError("Unexpected FPGA window output pin")
        return info

    def preflight(self):
        awg, rp = None, None
        try:
            awg = Rigol(self.config)
            awg.off()
            rp = self._rp()
            rp.write("PULSE:OUTPUT OFF")
            rp.write("TDC:WIDTH:ABORT")
            rp.idle(5)
            self.image = self._image(rp)
            for cmd in ("TDC:ENABLE OFF", "TDC:TEST:INTERNAL OFF", "TDC:MMCM:ENABLE OFF",
                        "TDC:INPUT SINGLE", "TDC:WIDTH:CALIBRATION:ACTIVATE OFF"):
                rp.write(cmd)
            result = dict(image=self.image, awg_identity=awg.identity,
                          original_awg_settings=awg.ask(awg.source + ":APPLy?"),
                          original_clock_source=awg.ask(":SYSTem:ROSCillator:SOURce?"))
            save_json(self.directory / "preflight.json", result)
            return result
        finally:
            self._cleanup(rp, awg)

    def _cleanup(self, rp, awg):
        errors = []
        # Attempt every action even if another link has failed.
        if awg is not None:
            try:
                awg.off()
            except Exception as exc:
                errors.append("AWG OFF: " + str(exc))
        if rp is not None:
            for command in ("PULSE:OUTPUT OFF", "TDC:WIDTH:ABORT"):
                try:
                    rp.write(command)
                except Exception as exc:
                    errors.append(command + ": " + str(exc))
            try:
                rp.idle(5)
                if rp.ask("PULSE:OUTPUT?") not in ("0", "OFF"):
                    raise RuntimeError("FPGA OFF not confirmed")
            except Exception as exc:
                errors.append(str(exc))
        for obj in (rp, awg):
            if obj is not None:
                try:
                    obj.close()
                except Exception as exc:
                    errors.append("close: " + str(exc))
        if errors:
            warnings.warn("Cleanup incomplete; run STOP cell and check outputs: " + "; ".join(errors))
        return errors

    def stop(self):
        """Reconnect independently so losing either link does not block the other."""
        awg, rp, errors = None, None, []
        try:
            awg = Rigol(self.config)
        except Exception as exc:
            errors.append("AWG reconnect: " + str(exc))
        try:
            rp = self._rp()
        except Exception as exc:
            errors.append("FPGA reconnect: " + str(exc))
        errors += self._cleanup(rp, awg)
        if errors:
            raise RuntimeError("Stop could not be fully confirmed: " + "; ".join(errors))
        return "AWG selected output OFF; FPGA pulse output OFF; width capture idle."

    def acquire(self, label, frequency_hz, width_ns, frames=None, fine=False,
                reference_ns=None, window_ns=None, stimulus="pulse"):
        """Optionally restart incomplete pulse bursts, retaining every attempt.

        Enable phase_retries in notebook config. Acceptance uses completeness
        only, never width error, fine validity or a desired LUT distribution.
        DC is acquired once: retrying a false-positive control could hide a fault.
        """
        if not self.config.get("phase_retries", False) or stimulus != "pulse":
            return self._acquire_once(label, frequency_hz, width_ns, frames, fine,
                                      reference_ns, window_ns, stimulus)
        limit = self.config.get("phase_retry_max_attempts", 50)
        delay = float(self.config.get("phase_retry_delay_s", 0.2))
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("phase_retry_max_attempts must be an integer in 1..1000")
        if not math.isfinite(delay) or not 0 <= delay <= 10:
            raise ValueError("phase_retry_delay_s must be in 0..10 seconds")
        ledger_path = self.directory / f"{self.sequence+1:04d}_{label}_retries.json"
        ledger = dict(label=label, started_utc=utc_now(), policy="restart_until_complete_v1",
                      max_attempts=limit, attempts=[], accepted_attempt=None,
                      total_frames=0, total_complete_pulses=0,
                      phase_lock_verified=False,
                      note="Measurements are conditioned on complete-frame bursts. Rejected attempts remain saved; accepted-burst yield is not unconditional capture efficiency or synchronization.")
        for number in range(1, limit+1):
            context = dict(policy=ledger["policy"], attempt=number, max_attempts=limit,
                           ledger_path=str(ledger_path), conditioned_on_complete_burst=True)
            print(f"{label}: source-start attempt {number}/{limit}", flush=True)
            try:
                capture = self._acquire_once(label, frequency_hz, width_ns, frames, fine,
                                             reference_ns, window_ns, stimulus, context)
                if not capture["acquisition_ok"] or capture["cleanup_errors"]:
                    raise RuntimeError("Retry stopped: acquisition integrity or output cleanup failed")
                s = capture["summary"]
                accepted = s["complete_pulses"] == capture["frames_requested"]
                ledger["total_frames"] += s["total_frames"]
                ledger["total_complete_pulses"] += s["complete_pulses"]
                ledger["attempts"].append(dict(attempt=number, accepted=accepted,
                    capture_files=capture["capture_files"], complete=s["complete_pulses"],
                    frames=s["total_frames"], flag_counts=s["flag_counts"]))
                ledger["complete_fraction_all_attempts"] = (
                    ledger["total_complete_pulses"]/max(1, ledger["total_frames"]))
                print(f"  {s['complete_pulses']}/{capture['frames_requested']} complete; "
                      + ("accepted" if accepted else "saved; " +
                         ("restarting sources" if number < limit else "attempt limit reached")), flush=True)
                if accepted:
                    ledger["accepted_attempt"] = number
                    ledger["finished_utc"] = utc_now()
                    capture["phase_retry"].update(accepted=True,
                        complete_fraction_all_attempts=ledger["complete_fraction_all_attempts"],
                        total_frames_all_attempts=ledger["total_frames"])
                    self.save_capture(Path(capture["capture_files"]["json"]).with_suffix(""), capture)
                    save_json(ledger_path, ledger)
                    return capture
                save_json(ledger_path, ledger)
            except BaseException as exc:
                ledger["failure"] = f"{type(exc).__name__}: {exc}"
                ledger["failed_attempt"] = number
                ledger["finished_utc"] = utc_now()
                save_json(ledger_path, ledger)
                raise
            if number < limit:
                time.sleep(delay)
        ledger["finished_utc"] = utc_now()
        ledger["failure"] = "No fully complete pulse burst within attempt limit"
        save_json(ledger_path, ledger)
        raise RuntimeError(f"{label}: no {capture['frames_requested']}/{capture['frames_requested']} "
                           f"complete burst after {limit} source starts. All attempts saved: {ledger_path}. "
                           "Increase PHASE_RETRY_MAX_ATTEMPTS or investigate alignment/drift; periods were unchanged.")

    def _acquire_once(self, label, frequency_hz, width_ns, frames=None, fine=False,
                      reference_ns=None, window_ns=None, stimulus="pulse", retry_context=None):
        if self.image is None:
            raise RuntimeError("Run preflight after loading the bitstream")
        if stimulus not in ("pulse", "dc_low") or (stimulus == "dc_low" and fine):
            raise ValueError("Stimulus must be pulse or an uncalibrated dc_low control")
        count = self.config["frame_count"] if frames is None else frames
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= self.image["capacity"]:
            raise ValueError("Frames must be an integer within hardware capacity")
        self.sequence += 1
        stem = self.directory / f"{self.sequence:04d}_{label}"
        if retry_context is not None:
            stem = stem.with_name(stem.name + f"_attempt_{retry_context['attempt']:02d}")
        capture = dict(label=label, started_utc=utc_now(), records=[], image=dict(self.image),
                       stimulus=stimulus,
                       fine_requested=bool(fine), acquisition_ok=False, cleanup_errors=[],
                       reference_ns=None, reference_source="AWG readback (nominal, not traceable)")
        capture["capture_files"] = {ext: str(stem.with_suffix("."+ext)) for ext in ("csv", "json")}
        if retry_context is not None:
            capture["phase_retry"] = dict(retry_context, accepted=False)
        awg, rp = None, None
        try:
            minimum_period = self.image["minimum_period_ns"]
            plan = plan_matched_period(frequency_hz, minimum_period, window_ns)
            capture["timing"] = plan
            capture["return_window_ns"] = None
            capture["latency_ticks"] = []
            if self.image["width_version"] == 13:
                lo = self.config.get("return_delay_min_ns", 0)
                hi = self.config.get("return_delay_max_ns")
                if hi is None:
                    hi = lo + plan["common_period_ns"]
                if (isinstance(lo, bool) or isinstance(hi, bool)
                        or not isinstance(lo, int) or not isinstance(hi, int)
                        or lo < 0 or hi <= lo or hi > 262136 or lo % 4 or hi % 4
                        or hi-lo > plan["common_period_ns"]):
                    raise ValueError("Return RISE bounds must be integer multiples of 4 ns, 0<=min<max<=262136 ns, with span<=common period")
                capture["return_window_ns"] = dict(minimum=lo, maximum_exclusive=hi,
                                                   fall_grace_periods=1)
                capture["latency_ticks"] = []
            offset = self.config.get("frame_offset_ns", 0)
            overrides = self.config.get("frame_offsets_by_period_ns", {})
            if not isinstance(overrides, dict):
                raise ValueError("frame_offsets_by_period_ns must map common period in ns to offset in ns")
            offset = overrides.get(plan["common_period_ns"],
                         overrides.get(str(plan["common_period_ns"]), offset))
            if (isinstance(offset, bool) or not isinstance(offset, int) or offset % 4
                    or not 0 <= offset <= 262140 or offset >= plan["common_period_ns"]):
                raise ValueError("Frame offset must be a 4 ns multiple, 0..262140 ns and smaller than the common period")
            if offset and self.image["width_version"] < 14:
                raise RuntimeError("Frame offset requires V14 hardware/API/SCPI")
            capture["frame_offset_ns"] = offset
            plan["frame_offset_ns"] = offset
            capture["measured_return_delay_ns"] = self.config.get("measured_return_delay_ns")
            awg = Rigol(self.config)
            settings = awg.configure(plan["common_frequency_hz"], width_ns, self.config)
            capture["awg"] = settings
            reference = settings["width_ns"] if reference_ns is None else float(reference_ns)
            if not math.isfinite(reference) or not 0 < reference < settings["period_ns"]:
                raise ValueError("Reference HIGH must be finite and between zero and period")
            capture["reference_ns"] = reference
            if reference_ns is not None:
                capture["reference_source"] = "User independent scope reference"
            window = plan["common_period_ns"]
            period_error = settings["period_ns"]-window
            if abs(period_error) > _pulse_setting_quantum_ns(window)+1e-9:
                raise RuntimeError("AWG period readback does not match the FPGA common period")
            plan.update(awg_period_readback_ns=settings["period_ns"],
                        awg_frequency_query_hz=settings["frequency_query_hz"],
                        period_readback_error_ns=period_error,
                        period_readback_tolerance_ns=_pulse_setting_quantum_ns(window),
                        settings_match_within_readback_resolution=True)
            capture.update(window_ns=window, frames_requested=count,
                           expected_complete_fraction=None,
                           target_complete_fraction=1.0,
                           overspeed_input=False)
            settling = {"awg_s": float(self.config.get("settle_s", 0.05)),
                        "launch_s": float(self.config.get("launch_settle_s", 0.0))}
            if any(not math.isfinite(v) or not 0 <= v <= 10 for v in settling.values()):
                raise ValueError("AWG and launch settling times must be finite, between 0 and 10 seconds")
            capture["settling"] = settling
            if stimulus == "dc_low":
                capture["awg_pulse_setup_before_dc"] = settings
                capture["awg"] = awg.dc_low()
                capture["reference_ns"] = None
                capture["reference_source"] = "DC LOW negative control; no pulse reference"
                capture["expected_complete_fraction"] = 0.0
                capture["target_complete_fraction"] = 0.0
            rp = self._rp()
            rp.write("PULSE:OUTPUT OFF")
            rp.write("TDC:WIDTH:ABORT")
            rp.idle(5)
            if self._image(rp) != self.image:
                raise RuntimeError("Image interface changed; restart this run and recalibrate")
            if fine and (self.candidate is None or not self.candidate["ready"]):
                raise RuntimeError("Upload a qualified candidate before requesting fine capture")
            if fine and rp.ask("TDC:INPUT?").upper() != "SINGLE":
                raise RuntimeError("Input changed since LUT upload; recalibrate")
            for command in ("TDC:ENABLE OFF", "TDC:TEST:INTERNAL OFF", "TDC:MMCM:ENABLE OFF",
                            "TDC:INPUT SINGLE", "TDC:WIDTH:CALIBRATION:ACTIVATE " + ("ON" if fine else "OFF"),
                            f"PULSE:TIMING {window},{window//2}"):
                rp.write(command)
            if tuple(map(int, rp.ask("PULSE:TIMING?").split(","))) != (window, window//2):
                raise RuntimeError("FPGA launch/frame period does not match the common AWG period")
            plan["fpga_period_readback_ns"] = window
            if self.image["width_version"] == 13:
                rp.write(f"TDC:WIDTH:DELAY {lo},{hi}")
                if tuple(map(int, rp.ask("TDC:WIDTH:DELAY?").split(","))) != (lo, hi):
                    raise RuntimeError("Return-window readback mismatch")
            if self.image["width_version"] >= 14:
                rp.write(f"TDC:WIDTH:OFFSET {offset}")
                if int(rp.ask("TDC:WIDTH:OFFSET?")) != offset:
                    raise RuntimeError("Frame-offset readback mismatch")
            if rp.ask("TDC:INPUT?").upper() != "SINGLE":
                raise RuntimeError("FPGA input readback mismatch")
            if fine and rp.ask("TDC:WIDTH:CALIBRATION:ACTIVATE?") not in ("1", "ON"):
                raise RuntimeError("Fine correction did not activate")
            awg.on()
            awg_on_time = time.monotonic()
            time.sleep(settling["awg_s"])
            rp.write("PULSE:OUTPUT ON")
            launch_on_time = time.monotonic()
            time.sleep(settling["launch_s"])
            capture["settling"].update(
                awg_on_to_arm_s=time.monotonic()-awg_on_time,
                launch_on_to_arm_s=time.monotonic()-launch_on_time)
            rp.write(f"TDC:WIDTH:ARM {count}")
            capture["status"] = rp.idle(float(self.config.get("host_timeout_s", 30)))
            rp.write("PULSE:OUTPUT OFF")
            awg.off()
            available = int(rp.ask("TDC:WIDTH:COUNT?"))
            if not 0 <= available <= self.image["capacity"]:
                raise RuntimeError("FPGA returned an invalid record count")
            capture["reported_count"] = available
            for start in range(0, available, 128):
                size = min(128, available-start)
                response = rp.ask(f"TDC:WIDTH:DATA:RAW? {start},{size}")
                batch = [tuple(map(int, r.split(","))) for r in response.split(";")]
                if (len(batch) != size or any(len(r) != 6 or
                        any(x < 0 or x > 0xffffffff for x in r) for r in batch)):
                    raise RuntimeError("Malformed raw record response")
                capture["records"].extend(batch)
                if self.image["width_version"] == 13:
                    latencies = list(map(int, rp.ask(f"TDC:WIDTH:LATENCY? {start},{size}").split(",")))
                    if len(latencies) != size or any(not 0 <= x <= 65535 for x in latencies):
                        raise RuntimeError("Malformed launch-to-RISE latency response")
                    if any(((r[1] & 2) and (delay != 65535 or (r[1] & (1 << 13)))) or
                           (not (r[1] & 2) and bool(r[1] & (1 << 13)) != (delay == 65535)) or
                           (delay != 65535 and not lo//4 <= delay < hi//4)
                           for r, delay in zip(batch, latencies)):
                        raise RuntimeError("Launch latency flags/data integrity mismatch")
                    capture["latency_ticks"].extend(latencies)
            if self.image["width_version"] >= 16:
                stride = self.image["diagnostic_stride"]
                samples = capture["edge_tick_samples"] = []
                diagnostic_count = (available+stride-1)//stride
                for start in range(0, diagnostic_count, 128):
                    size = min(128, diagnostic_count-start)
                    response = rp.ask(f"TDC:WIDTH:DIAGNOSTIC:EDGE? {start},{size}")
                    batch = [tuple(map(int, row.split(","))) for row in response.split(";")]
                    if len(batch) != size or any(len(s) != 3 or any(x < 0 or x > 0xffffffff for x in s) for s in batch):
                        raise RuntimeError("Malformed sparse edge diagnostic response")
                    samples.extend(batch)
                capture["edge_diagnostics"] = edge_timestamp_diagnostics(
                    capture["records"], samples, stride, window, self.image["tick_ps"],
                    self.candidate["tables"] if fine else None)
            audit = audit_width_records(capture["records"], self.image["tick_ps"])
            raw_ok = all(r[3] < self.image["taps"] and r[4] < self.image["taps"]
                         for r in capture["records"])
            statuses_ok = all(not (((r[1] >> shift) & 1) and ((r[1] >> shift) & 0x1e))
                              for r in capture["records"] if r[1] & 1 for shift in (16, 24))
            capture["record_integrity"] = dict(audit, raw_indices_in_range=raw_ok,
                                               fine_statuses_consistent=statuses_ok)
            capture["acquisition_ok"] = (capture["status"] == 8 and available == count
                                         and audit["ok"] and raw_ok and statuses_ok)
            capture["summary"] = summarize(capture)
            if not capture["acquisition_ok"]:
                detail = (f"status={capture['status']} (expected 8), "
                          f"count={available}/{count}, violations={audit['violation_counts']}")
                hint = (" Negative fine deltas reported +131072 ps too large indicate the "
                        "known signed-correction HDL readout bug; rebuild/load the sign-extension fix."
                        if audit["violation_counts"].get("invalid_fine_correction") else "")
                raise RuntimeError("Burst status/count/record integrity failed: " + detail
                                   + ". Inspect saved raw records." + hint)
            if fine:
                mismatches = []
                used = rows(capture, calibrated=True)
                for r in used:
                    expected = (int(r[2])*self.image["tick_ps"]
                                + self.candidate["tables"]["RISE"][int(r[3])]
                                - self.candidate["tables"]["FALL"][int(r[4])])
                    if int(r[5]) != expected:
                        mismatches.append(int(r[0]))
                capture["fine_arithmetic_check"] = dict(checked=len(used),
                                                         mismatch_frames=mismatches[:20])
                if mismatches:
                    raise RuntimeError("Hardware fine arithmetic differs from uploaded LUTs")
                capture["previously_unseen_codes"] = {
                    edge: int(np.count_nonzero(np.asarray(self.candidate["histograms"][edge])[
                        used[:, col].astype(int)] == 0))
                    for edge, col in (("RISE", 3), ("FALL", 4))}
            return capture
        except BaseException as exc:
            capture["failure"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if awg is not None and awg.last_settings is not None:
                capture.setdefault("awg", awg.last_settings)
                if "failure" in capture:
                    capture["awg_failure_readback"] = awg.last_settings
            capture["awg_scpi_log"] = awg.log if awg is not None else []
            capture["cleanup_errors"] = self._cleanup(rp, awg)
            if "phase_retry" in capture:
                capture["phase_retry"]["accepted"] = bool(
                    capture["acquisition_ok"] and not capture["cleanup_errors"] and "failure" not in capture
                    and capture.get("summary", {}).get("complete_pulses") == capture.get("frames_requested"))
            capture["finished_utc"] = utc_now()
            self.save_capture(stem, capture)

    def save_capture(self, stem, capture):
        with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow((*FIELDS, "decoded_flags", "rise_status_hex", "fall_status_hex",
                             "launch_to_rise_ticks", "launch_to_rise_ns",
                             "diagnostic_rise_ticks", "diagnostic_fall_ticks"))
            latency = capture.get("latency_ticks", [])
            edge_ticks = {s[0]: s[1:] for s in capture.get("edge_tick_samples", [])}
            for index, r in enumerate(capture["records"]):
                delay = latency[index] if index < len(latency) else None
                writer.writerow((*r, "|".join(name for b, name in FLAGS.items() if r[1] & (1 << b)),
                                 f"0x{(r[1] >> 16) & 255:02x}", f"0x{(r[1] >> 24) & 255:02x}",
                                 delay, delay*4 if delay is not None and delay != 65535 else None,
                                 *edge_ticks.get(r[0], (None, None))))
        save_json(stem.with_suffix(".json"), {k: v for k, v in capture.items()
                                             if k not in ("records", "latency_ticks")})

    def _table(self, rp, edge, values=None):
        result = []
        for start in range(0, self.image["taps"], 64):
            count = min(64, self.image["taps"]-start)
            if values is not None:
                text = ",".join(str(int(v)) for v in values[start:start+count])
                rp.write(f"TDC:WIDTH:CALIBRATION:LUT:WRITE {edge},{start},{text}")
            response = rp.ask(f"TDC:WIDTH:CALIBRATION:LUT:READ? {edge},{start},{count}")
            part = list(map(int, response.split(",")))
            if len(part) != count or any(not 0 <= v <= 65535 for v in part):
                raise RuntimeError("Malformed LUT readback")
            result.extend(part)
        if values is not None and result != list(values):
            raise RuntimeError(edge + " LUT readback mismatch")
        return result

    def upload(self, candidate):
        if candidate["image"] != self.image:
            raise ValueError("Candidate belongs to another image; collect calibration for the current build")
        if not candidate["ready"]:
            reasons = [edge + ": " + error for edge, quality in candidate["quality"].items()
                       for error in quality["errors"]]
            raise ValueError("LUT upload blocked by calibration quality: "
                             + "; ".join(reasons or ["candidate is not qualified"]))
        for edge in ("RISE", "FALL"):
            values = candidate["tables"][edge]
            if (len(values) != self.image["taps"] or any(not 0 <= int(v) <= self.image["tick_ps"] for v in values)
                    or any(a > b for a, b in zip(values, values[1:]))):
                raise ValueError("Invalid LUT shape/range/order")
        rp, backup, changed = self._rp(), None, False
        try:
            rp.write("PULSE:OUTPUT OFF")
            rp.write("TDC:WIDTH:ABORT")
            rp.idle(5)
            if self._image(rp) != self.image or rp.ask("TDC:INPUT?").upper() != "SINGLE":
                raise RuntimeError("Image/input changed since calibration")
            backup = dict(active=rp.ask("TDC:WIDTH:CALIBRATION:ACTIVATE?") in ("1", "ON"),
                          tables={e: self._table(rp, e) for e in ("RISE", "FALL")})
            save_json(self.directory / "previous_luts.json", backup)
            changed = True
            rp.write("TDC:WIDTH:CALIBRATION:ACTIVATE OFF")
            for edge in ("RISE", "FALL"):
                self._table(rp, edge, candidate["tables"][edge])
            rp.write("TDC:WIDTH:CALIBRATION:ACTIVATE ON")
            if rp.ask("TDC:WIDTH:CALIBRATION:ACTIVATE?") not in ("1", "ON"):
                raise RuntimeError("LUT activation not confirmed")
            save_json(self.directory / "uploaded_luts.json", dict(candidate=candidate, utc=utc_now()))
            self.candidate = candidate
        except BaseException:
            if changed and backup is not None:
                try:
                    rp.write("TDC:WIDTH:CALIBRATION:ACTIVATE OFF")
                    for edge in ("RISE", "FALL"):
                        self._table(rp, edge, backup["tables"][edge])
                    rp.write("TDC:WIDTH:CALIBRATION:ACTIVATE " + ("ON" if backup["active"] else "OFF"))
                except Exception as exc:
                    warnings.warn("Previous LUT restoration not confirmed: " + str(exc))
            raise
        finally:
            rp.close()


def quality_guard(capture, minimum=100):
    s = capture["summary"]
    if capture.get("image", {}).get("width_version", 0) == 13 and s["complete_fraction"] < 1.0:
        raise RuntimeError("V13 launch/return qualification needs one complete pulse per requested launch: "
                           + capture["label"] + "; inspect return bounds and raw flags. No frames were discarded or retried.")
    historical_prediction = s.get("expected_complete_fraction")
    reasons = []
    if not capture["acquisition_ok"]:
        reasons.append("acquisition/status/record integrity failed")
    if capture["cleanup_errors"]:
        reasons.append("cleanup errors: " + str(capture["cleanup_errors"]))
    if s["complete_pulses"] < minimum:
        reasons.append(f"{s['complete_pulses']}/{s['total_frames']} complete pulses; need at least {minimum}")
    if (historical_prediction is not None
            and s["complete_fraction"] < 0.5*historical_prediction):
        reasons.append("complete fraction below the saved prediction threshold")
    if reasons:
        version = capture.get("image", {}).get("width_version", 0)
        hint = ("V12 has no return-delay bounds and rejects pulses crossing a frame boundary. "
                "This helper restarts both sources for each capture, so a passing alignment survey "
                "does not preserve phase for baseline. Check DIO1_P launch and DIO2_P input together "
                "on the scope and establish repeatable relative phase/startup at the same period. "
                if version == 12 else
                (f"V14 frame offset is {capture.get('frame_offset_ns')} ns. Check that the shifted boundary "
                 "lies in LOW with margin for the widest pulse. The helper restarts both sources; "
                 "an independent AWG can change phase, so fixed compensation needs stable relative phase. "
                 if version >= 14 else
                 "Inspect missing/extra edges, source synchronization and supported return-delay bounds. "))
        raise RuntimeError("Insufficient clean complete pulses for calibration: " + capture["label"]
                           + "; " + "; ".join(reasons)
                           + "; flags=" + str(s.get("flag_counts", {})) + ". "
                           + hint + "Do not detune or shorten acquisition frames to force a pass.")
    error = s["all_complete"]["error_ns"]
    if error is None or abs(error) > max(8., 0.05*capture["reference_ns"]):
        raise RuntimeError("Mean width disagrees with source; inspect wiring and scope before calibrating")


def alignment_survey(bench, frequency_hz, width_ns, repeats=4, frames=1024):
    """Same-rate screening across software restarts, not a controlled phase scan.

    Zero/partial yield is retained as a synchronization diagnostic. V12
    rejects boundary-cut pulses and has no programmable return delay or
    launch-to-RISE timestamp. This survey does not certify AWG phase lock.
    """
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("Alignment survey needs a positive integer repeat count")
    captures, points = [], []
    for index in range(repeats):
        c = bench.acquire(f"alignment_restart_{index:02d}", frequency_hz, width_ns,
                          frames=frames, fine=False)
        captures.append(c)
        s = c["summary"]
        points.append(dict(label=c["label"], common_period_ns=c["timing"]["common_period_ns"],
                           complete=s["complete_pulses"], frames=s["total_frames"],
                           complete_fraction=s["complete_fraction"], flag_counts=s["flag_counts"],
                           mean_width_ns=s["all_complete"]["mean_ns"],
                           frame_offset_ns=c.get("frame_offset_ns", 0),
                           phase_retry=c.get("phase_retry"),
                           return_window_ns=c["return_window_ns"],
                           launch_to_rise_ns=s["launch_to_rise_ns"]))
    result = dict(timing_policy="matched_period_v1", points=points,
                  target_complete_fraction=1.0, phase_lock_verified=False,
                  measured_return_delay_ns=bench.config.get("measured_return_delay_ns"),
                  hardware_delay_adjustment_available=bench.image["width_version"] >= 13,
                  association_policy=("shifted_single_frame_v14" if bench.image["width_version"] >= 14 else
                                      "launch_window_spill_v13" if bench.image["width_version"] == 13
                                      else "single_frame_v12"),
                  phase_retries=bool(bench.config.get("phase_retries", False)),
                  note="Software restarts do not command a known phase. When phase retries are enabled, each point is the first fully complete burst and its retry ledger retains every rejected start. Accepted yields are conditioned on startup/frame fit, not proof of clock lock or unconditional capture efficiency. No frequency detuning is applied.")
    save_json(bench.directory / "alignment_survey.json", result)
    return result, captures


def signal_identity_check(bench, frequency_hz=997003., frames=4096):
    """Change AWG width at one common AWG/FPGA period; retain alignment failures."""
    captures, points, errors = [], [], []
    common_period = plan_matched_period(frequency_hz)["common_period_ns"]
    control = bench.acquire("identity_dc_low", frequency_hz, common_period/2, frames=frames,
                            stimulus="dc_low")
    captures.append(control)
    dc_count = control["summary"]["complete_pulses"]
    if dc_count or control["cleanup_errors"]:
        errors.append(f"DC LOW produced {dc_count} complete pulses or cleanup was not confirmed")
    print(f"DC 0 V: {dc_count}/{frames} complete pulses (expected zero)")
    # Continue the diagnostic even if the control fails, retaining all evidence.
    for width in (100.2, 300.2, 700.2):
        capture = bench.acquire(f"identity_width_{width:g}", frequency_hz, width, frames=frames)
        captures.append(capture)
        summary = capture["summary"]
        measured = summary["all_complete"]["mean_ns"]
        point = dict(requested_ns=width, readback_ns=capture["awg"]["width_ns"],
                     measured_ns=measured, complete_pulses=summary["complete_pulses"],
                     complete_fraction=summary["complete_fraction"],
                     expected_complete_fraction=summary["expected_complete_fraction"],
                     phase_retry=capture.get("phase_retry"))
        points.append(point)
        try:
            quality_guard(capture)
        except RuntimeError as exc:
            errors.append(str(exc))
        print("AWG width identity:", point)
    result = dict(passed=not errors, dc_complete_pulses=dc_count, points=points, errors=errors,
                  frame_period_ns=common_period, internal_window_high_ns=common_period//2,
                  timing_policy="matched_period_v1", phase_lock_verified=False,
                  labels=[c["label"] for c in captures],
                  note="Passing supports correct stimulus identity. Equal programmed periods do not establish phase lock, return-delay calibration, fine accuracy or timing closure.")
    save_json(bench.directory / "signal_identity.json", result)
    return result, captures


def zero_runs(hist):
    occupied = np.flatnonzero(hist)
    if len(occupied) < 2:
        return []
    result, start = [], None
    for i in range(int(occupied[0]), int(occupied[-1])+1):
        if hist[i] == 0 and start is None:
            start = i
        if hist[i] != 0 and start is not None:
            result.append([start, i-1])
            start = None
    return result


def build_candidate(captures, minimum_samples=50000, minimum_bins=32, known_dead_zones=(),
                    *, provisional_missing_code_ranges=None):
    # An explicit, edge-specific experimental exception. This acknowledges the
    # missing codes without asserting that they represent harmless dead bins.
    provisional = provisional_missing_code_ranges or {}
    if any(edge not in ("RISE", "FALL") for edge in provisional):
        raise ValueError("Provisional missing-code exceptions must specify RISE or FALL")
    if len(captures) < 4:
        raise ValueError("Collect at least four bursts at multiple common AWG/FPGA frequency settings")
    for c in captures:
        quality_guard(c)
    image = captures[0]["image"]
    provisional = {edge: [list(r) for r in ranges] for edge, ranges in provisional.items()}
    for ranges in provisional.values():
        for r in ranges:
            if (len(r) != 2 or any(not isinstance(v, int) for v in r)
                    or not 0 <= r[0] <= r[1] < image["taps"]):
                raise ValueError("Invalid provisional inclusive raw-code range")
    if any(c["image"] != image for c in captures):
        raise ValueError("Calibration combines different images")
    timing_policies = {c.get("timing", {}).get("policy", "historical_unmatched") for c in captures}
    if len(timing_policies) != 1:
        raise ValueError("Do not combine historical unequal-period captures with matched-period calibration")
    signature = lambda c: tuple(c["awg"][k] for k in ("identity", "channel", "low_v", "high_v", "leading_ns", "trailing_ns"))
    if any(signature(c) != signature(captures[0]) for c in captures):
        raise ValueError("AWG identity, levels or transitions changed during calibration")
    frequencies = sorted({round(c["awg"]["frequency_hz"], 3) for c in captures})
    if len(frequencies) < 2 or any(c["overspeed_input"] for c in captures):
        raise ValueError("Use multiple distinct common AWG/FPGA rates within the image's acquisition limit for calibration")
    candidate = dict(image=image, input="SINGLE", created_utc=utc_now(), tables={},
                     histograms={}, quality={}, ready=False, frequencies_hz=frequencies,
                     source_labels=[c["label"] for c in captures],
                     provisional=bool(provisional),
                     provisional_missing_code_ranges=provisional,
                     limitations=(["Unresolved missing codes and adjacent rejected phases; LUT describes accepted edges and may have phase-dependent bias. Fresh validation required."]
                                  if provisional else []),
                     status="candidate; requires fresh validation",
                     assumption="Uniform asynchronous phase over 4000 ps. Frame selection may bias density; cross-frequency agreement is necessary, not proof.")
    candidate["timing_policy"] = next(iter(timing_policies))
    candidate["phase_retry"] = [dict(label=c["label"], **c["phase_retry"])
                                for c in captures if c.get("phase_retry")]
    if candidate["phase_retry"]:
        candidate["limitations"].append("Source starts were repeated until a complete-frame burst was obtained. LUT and precision results describe selected bursts; all rejected starts are retained in retry ledgers. This does not establish unconditional efficiency or synchronization and may bias fine-phase coverage.")
    if candidate["timing_policy"] == "matched_period_v1":
        candidate["limitations"].append("AWG/frame periods match nominally. Equal periods do not prove uniform fine-clock phase coverage or phase lock; frame-selection bias must be assessed independently.")
        candidate["assumption"] = ("Code density still requires uniform edge phase over 4000 ps. "
                                   "Keep AWG and FPGA periods equal at each setting; establish coverage through controlled phase/delay or measured independent-clock drift, not period detuning.")
    for edge, col, shift in (("RISE", 3, 16), ("FALL", 4, 24)):
        groups, ncomplete = [], 0
        by_frequency = {}
        for c in captures:
            complete = rows(c)
            ncomplete += len(complete)
            selected = complete[((complete[:, 1] >> shift) & 1) != 0, col].astype(int)
            groups.append(selected)
            key = round(c["awg"]["frequency_hz"], 3)
            by_frequency.setdefault(key, []).append(selected)
        hist = np.bincount(np.concatenate(groups), minlength=image["taps"])
        total, active = int(hist.sum()), int(np.count_nonzero(hist))
        errors = []
        fraction = total/max(1, ncomplete)
        if total < minimum_samples:
            errors.append(f"{total} edges; need {minimum_samples}")
        if active < minimum_bins:
            errors.append(f"{active} populated bins; need {minimum_bins}")
        if fraction < 0.99:
            errors.append(f"Only {fraction:.3%} valid {edge} codes; rejected phases can bias LUT")
        if hist.max(initial=0) > 0.15*max(1, total):
            errors.append("One bin contains >15% of observations; suspect poor phase coverage")
        missing = zero_runs(hist)
        acknowledged = [r for r in missing if r[1]-r[0]+1 > 2
                        and any(a <= r[0] and r[1] <= b
                                for a, b in provisional.get(edge, []))]
        unexpected = [r for r in missing if r[1]-r[0]+1 > 2
                      and not any(a <= r[0] and r[1] <= b for a, b in known_dead_zones)
                      and r not in acknowledged]
        if unexpected:
            errors.append("Uncharacterized missing-code ranges: " + str(unexpected))
        distributions = [np.concatenate(groups[:len(groups)//2]),
                         np.concatenate(groups[len(groups)//2:])]
        distributions += [np.concatenate(v) for v in by_frequency.values()]
        cdfs = [np.cumsum(np.bincount(g, minlength=image["taps"]))/max(1, len(g)) for g in distributions]
        drift = max(float(np.max(np.abs(a-b))) for i, a in enumerate(cdfs) for b in cdfs[i+1:])
        limit = max(0.03, 4*math.sqrt(2/max(1, min(map(len, distributions)))))
        if drift > limit:
            errors.append(f"Time/frequency CDF disagreement {drift:.4f} > {limit:.4f}")
        # Bin-centre propagation times, with independent rise/fall transfer maps.
        centres = image["tick_ps"]*(np.cumsum(hist)-hist/2)/max(1, total)
        candidate["tables"][edge] = np.rint(centres).astype(int).tolist()
        candidate["histograms"][edge] = hist.tolist()
        candidate["quality"][edge] = dict(samples=total, populated_bins=active,
                                           valid_edge_fraction=fraction, cdf_drift=drift,
                                           cdf_limit=limit, missing_code_runs=missing,
                                           provisionally_acknowledged_missing_code_runs=acknowledged,
                                           minimum_occupied_count=int(hist[hist > 0].min()) if active else 0,
                                           errors=errors)
    candidate["ready"] = all(not q["errors"] for q in candidate["quality"].values())
    if provisional:
        candidate["status"] = "provisional experimental candidate; unresolved missing codes; requires fresh validation"
    return candidate


def precision_comparison(coarse, fine):
    for c in (coarse, fine):
        quality_guard(c)
    for key in ("frequency_hz", "width_ns", "low_v", "high_v"):
        if not math.isclose(coarse["awg"][key], fine["awg"][key], rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("Coarse/fine source conditions differ")
    result = {}
    for name, c in (("coarse", coarse), ("fine", fine)):
        chosen = rows(c, both_fine=True, calibrated=(name == "fine"))
        if len(chosen) < 100:
            raise RuntimeError("Too few fine-eligible records for precision comparison")
        values = chosen[:, 5].astype(float)/1000
        result[name] = dict(n=len(values), mean_ns=float(values.mean()),
                            std_ns=float(values.std(ddof=1)),
                            error_ns=float(values.mean()-c["reference_ns"]))
    result["coarse_std_over_fine_std"] = (result["coarse"]["std_ns"]/result["fine"]["std_ns"]
                                           if result["fine"]["std_ns"] else None)
    result["note"] = "Same fine-valid eligibility, separate fresh bursts, no host correction. Includes source and input-path noise."
    return result


def fit_width_reference(captures, model="offset", minimum_reference_ns=100.,
                        maximum_std_ns=0.15, maximum_block_span_ns=0.25):
    """Host-only bias correction from stable full captures, with explicit exclusions.

    A fixed offset does not infer a clock scale from width-dependent bias or
    drifting captures. Affine fitting is opt-in and requires three stable widths.
    Limits apply to complete captures, not selected samples or reference errors.
    Neither model corrects narrow-pulse nonlinearity or qualifies absolute accuracy.
    """
    if model not in ("offset", "affine"):
        raise ValueError("Width reference model must be offset or affine")
    if any(not math.isfinite(v) or v < 0 for v in
           (minimum_reference_ns, maximum_std_ns, maximum_block_span_ns)):
        raise ValueError("Width reference gates must be finite and nonnegative")
    captures = list(captures)
    means, reference, accepted, excluded = [], [], [], []
    for c in captures:
        if c.get("reference_ns") is None or not math.isfinite(c["reference_ns"]) or c["reference_ns"] <= 0:
            raise ValueError("Width reference must be finite and positive")
        quality_guard(c)
        selected = rows(c, calibrated=True)
        if len(selected) < 100 or len(selected)/len(rows(c)) < 0.99:
            raise RuntimeError("Width reference fit needs >=99% calibrated complete pulses")
        if any(c.get("previously_unseen_codes", {}).values()):
            raise RuntimeError("Validation observed previously uncalibrated fine codes")
        values = selected[:, 5].astype(float)/1000
        distribution = width_distribution(values)
        reasons = []
        if c["reference_ns"] < minimum_reference_ns:
            reasons.append("reference below minimum training width")
        if values.std(ddof=1) > maximum_std_ns:
            reasons.append("full-capture SD exceeds stability gate")
        if distribution["block_mean_span_ns"] > maximum_block_span_ns:
            reasons.append("chronological block-mean span exceeds stability gate")
        if reasons:
            excluded.append(dict(label=c["label"], reasons=reasons,
                                 std_ns=float(values.std(ddof=1)), distribution=distribution))
            continue
        means.append(float(values.mean()))
        reference.append(c["reference_ns"])
        accepted.append(c)
    if not means:
        raise ValueError("No stable training captures passed the width reference gates")
    if model == "affine":
        if len(set(reference)) < 3 or np.ptp(means) < 40:
            raise ValueError("Affine fit needs >=3 stable training widths spanning >=40 ns")
        scale, offset = np.linalg.lstsq(np.column_stack((means, np.ones(len(means)))), reference, rcond=None)[0]
    else:
        scale, offset = 1., float(np.mean(np.asarray(reference)-means))
    if not 0.9 <= scale <= 1.1:
        raise RuntimeError("Implausible width scale; diagnose capture before fitting")
    return dict(model="reference_ns = scale * measured_ns + offset_ns", model_kind=model,
                scale=float(scale),
                offset_ns=float(offset), training_means_ns=means, training_reference_ns=reference,
                training_span_ns=[min(means), max(means)],
                reference_sources=sorted({c["reference_source"] for c in accepted}),
                training_labels=[c["label"] for c in accepted],
                considered_training_labels=[c["label"] for c in captures],
                excluded_training_captures=excluded,
                gates=dict(minimum_reference_ns=minimum_reference_ns,
                           maximum_std_ns=maximum_std_ns,
                           maximum_block_span_ns=maximum_block_span_ns),
                note="Nominal AWG-reference transfer unless independent scope widths supplied. Not a traceable clock calibration.")


def validate_width_reference(model, captures):
    result = []
    for c in captures:
        if c["label"] in model.get("considered_training_labels", model["training_labels"]):
            raise ValueError("Width validation must use captures not used for fitting")
        quality_guard(c)
        selected = rows(c, calibrated=True)
        if len(selected) < 100 or len(selected)/len(rows(c)) < 0.99:
            raise RuntimeError("Validation needs >=99% calibrated complete pulses")
        values = selected[:, 5].astype(float)/1000
        corrected = model["scale"]*values + model["offset_ns"]
        result.append(dict(label=c["label"], reference_ns=c["reference_ns"], samples=len(values),
                           raw_error_ns=float(values.mean()-c["reference_ns"]),
                           corrected_error_ns=float(corrected.mean()-c["reference_ns"]),
                           corrected_std_ns=float(corrected.std(ddof=1)),
                           distribution=width_distribution(corrected),
                           extrapolation=not model["training_span_ns"][0] <= values.mean() <= model["training_span_ns"][1],
                           previously_unseen_codes=c.get("previously_unseen_codes", {})))
    return result


def plot_capture(capture):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.5))
    for name, selected in (("Complete", rows(capture)), ("Calibrated", rows(capture, calibrated=True))):
        if len(selected):
            values = selected[:, 5].astype(float)/1000
            axes[0].plot(selected[:, 0], values, ".", ms=2, label=name)
            axes[1].hist(values, bins=40, alpha=0.5, label=name)
    if capture["reference_ns"] is not None:
        axes[0].axhline(capture["reference_ns"], color="C3", label="Nominal/reference width")
    axes[0].set(xlabel="Frame (missing markers are rejected frames)", ylabel="Width (ns)")
    axes[1].set(xlabel="Width (ns)", ylabel="Count")
    axes[0].legend()
    fig.suptitle(capture["label"])
    fig.tight_layout()
    return fig


def plot_candidate(candidate):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 6))
    for i, edge in enumerate(("RISE", "FALL")):
        hist = np.asarray(candidate["histograms"][edge])
        bin_ps = candidate["image"]["tick_ps"]*hist/max(1, hist.sum())
        axes[i, 0].bar(np.arange(len(hist)), bin_ps, width=1)
        axes[i, 0].set(title=edge + " inferred bin widths", xlabel="Raw code", ylabel="Width (ps)")
        axes[i, 1].plot(candidate["tables"][edge])
        axes[i, 1].set(title=edge + " LUT", xlabel="Raw code", ylabel="Propagation time (ps)")
    fig.tight_layout()
    return fig


def plot_sweep(captures):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 3.5))
    for mode in (False, True):
        group = sorted((c for c in captures if c["fine_requested"] == mode), key=lambda c: c["awg"]["width_ns"])
        if not group:
            continue
        x = [c["awg"]["width_ns"] for c in group]
        label = "Fine" if mode else "Coarse"
        axes[0].plot(x, [c["summary"]["complete_fraction"] for c in group], ".-", label=label)
        metric = "calibrated_only" if mode else "fine_eligible"
        axes[1].plot(x, [np.nan if c["summary"][metric]["error_ns"] is None else c["summary"][metric]["error_ns"] for c in group], ".-", label=label)
        axes[2].plot(x, [np.nan if c["summary"][metric]["std_ns"] is None else c["summary"][metric]["std_ns"] for c in group], ".-", label=label)
    axes[0].set(ylabel="Complete frames / total frames")
    axes[1].set(ylabel="Mean minus reference (ns)")
    axes[2].set(ylabel="Measured RMS width variation (ns)")
    for ax in axes:
        ax.set_xlabel("AWG readback HIGH (ns)")
        ax.legend()
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def phase_residuals(capture, candidate, bins=8):
    """Width residual versus inferred RISE propagation time, not known AWG phase."""
    selected = rows(capture, both_fine=True, calibrated=capture["fine_requested"])
    times = np.asarray(candidate["tables"]["RISE"])[selected[:, 3].astype(int)]
    indices = np.minimum(bins-1, (times*bins/candidate["image"]["tick_ps"]).astype(int))
    result = []
    for i in range(bins):
        widths = selected[indices == i, 5].astype(float)/1000
        result.append(dict(phase_bin=i, samples=len(widths),
                           mean_error_ns=float(widths.mean()-capture["reference_ns"]) if len(widths) else None,
                           std_ns=float(widths.std(ddof=1)) if len(widths) > 1 else None))
    return result
