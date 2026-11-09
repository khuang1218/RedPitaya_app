"""PCB pulse-width burst test. Requires TDC v5+/PWB v1 and matching API/server.

Trigger: DIO1_P, E1 pin 5. Return: DIO2_P, E1 pin 7 (3.3 V), or
LVDS DIO18_P/N, E3 pins 31/33. Common ground required. Finishes output OFF.
No external E3 launch connection is used. Default: 1 MHz, 50%, 16 records.
TDC v6+ supports 16384 records; capacity is queried from the loaded image.
Uncalibrated widths use 4 ns ticks; raw carry codes are diagnostic.
"""
import argparse
import csv
import math
import socket
import time
from pathlib import Path

from local_data import results_directory


class Client:
    def __init__(self, host, port):
        self.socket = socket.create_connection((host, port), timeout=3)
        self.reader = self.socket.makefile("rb")

    def send(self, command):
        self.socket.sendall((command + "\r\n").encode("ascii"))

    def query(self, command):
        self.send(command)
        response = self.reader.readline(65536)
        if not response or not response.endswith(b"\n"):
            raise RuntimeError("Missing or incomplete SCPI reply: " + command)
        return response.decode("ascii").strip()

    def check(self):
        error = self.query("SYST:ERR:NEXT?")
        if int(error.split(",", 1)[0]) != 0:
            raise RuntimeError("SCPI: " + error)

    def write(self, command):
        self.send(command)
        self.check()

    def close(self):
        self.reader.close()
        self.socket.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--frequency", type=float, default=1_000_000)
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument("--input", choices=["SINGLE", "LVDS"], default="SINGLE")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--return-delay-min-ns", type=int, default=0, help="V13 earliest return RISE, 4 ns grid")
    parser.add_argument("--return-delay-max-ns", type=int, default=None, help="V13 exclusive RISE deadline; default MIN+period")
    parser.add_argument("--frame-offset-ns", type=int, default=0, help="V14 acquisition-frame shift; 4 ns grid, less than period")
    parser.add_argument("--csv", help="save all records; relative paths go under local tdc_width_results")
    parser.add_argument("--quiet", action="store_true", help="print a summary instead of every pulse")
    args = parser.parse_args()
    if not 0 < args.frequency <= 25_000_000 or args.count < 1:
        parser.error("requires 0 < frequency <= 25 MHz (V17 above 5 MHz) and a positive count")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    period = math.ceil(1e9 / args.frequency / 4-1e-9) * 4
    if period > 8_589_934_588:
        parser.error("period exceeds the pulse generator range")
    client = Client(args.host, args.port)
    records = []
    try:
        client.send("*CLS")
        version = int(client.query("TDC:WIDTH:VERSION?"))
        client.check()
        minimum = 500 if version >= 10 else 1000
        if version >= 16:
            minimum = int(client.query("TDC:WIDTH:MINIMUM:PERIOD?"))
            client.check()
            if minimum < (40 if version >= 17 else 200) or minimum % 4:
                raise RuntimeError("Invalid hardware minimum period")
        if 1e9/args.frequency < minimum-1e-9:
            raise RuntimeError(f"Requested rate exceeds this image's {minimum} ns minimum frame period")
        capacity = int(client.query("TDC:WIDTH:CAPACITY?"))
        client.check()
        if args.count > capacity:
            raise RuntimeError(f"Requested {args.count} records exceeds this image's capacity of {capacity}")
        client.write("PULSE:OUTPUT OFF")
        client.write("TDC:WIDTH:ABORT")
        deadline = time.monotonic() + args.timeout
        while int(client.query("TDC:WIDTH:STATUS?")) & 1:
            if time.monotonic() > deadline:
                raise TimeoutError("Previous acquisition did not abort")
            time.sleep(0.01)
        client.write("TDC:ENABLE OFF")
        client.write("TDC:TEST:INTERNAL OFF")
        client.write("TDC:MMCM:ENABLE OFF")
        client.write("TDC:RESET")
        client.write("TDC:INPUT " + args.input)
        client.write("TDC:WIDTH:CALIBRATION:ACTIVATE OFF")
        client.write(f"PULSE:TIMING {period},{period // 2}")
        actual = client.query("PULSE:TIMING?")
        if actual != f"{period},{period // 2}":
            raise RuntimeError("Unexpected output timing: " + actual)
        if version == 13:
            lo = args.return_delay_min_ns
            hi = args.return_delay_max_ns if args.return_delay_max_ns is not None else lo+period
            if lo < 0 or hi <= lo or hi > 262136 or lo % 4 or hi % 4 or hi-lo > period:
                raise ValueError("V13 bounds require 4 ns grid, 0<=min<max<=262136 ns, span<=period")
            client.write(f"TDC:WIDTH:DELAY {lo},{hi}")
            actual_bounds = tuple(map(int, client.query("TDC:WIDTH:DELAY?").split(",")))
            client.check()
            if actual_bounds != (lo, hi):
                raise RuntimeError("V13 return-window readback mismatch")
            print(f"Return RISE: [{lo}, {hi}) ns; FALL may cross into the next window")
        elif args.return_delay_min_ns or args.return_delay_max_ns is not None:
            raise RuntimeError("Return-delay configuration requires V13 hardware/API/server")
        offset = args.frame_offset_ns
        if offset < 0 or offset > 262140 or offset % 4 or offset >= period:
            raise ValueError("Frame offset requires 4 ns grid, 0..262140 ns and offset < period")
        if version >= 14:
            client.write(f"TDC:WIDTH:OFFSET {offset}")
            if int(client.query("TDC:WIDTH:OFFSET?")) != offset:
                raise RuntimeError("Frame-offset readback mismatch")
        elif offset:
            raise RuntimeError("Frame offset requires V14 hardware/API/SCPI")
        print(f"Acquisition frame offset: {offset} ns (full period retained)")
        print(f"Trigger: {1e9 / period:g} Hz, 50%; input: {args.input}")
        # Start the source first. ARM begins at the next complete output cycle;
        # its watchdog need not wait for a second SCPI command/network round trip.
        client.write("PULSE:OUTPUT ON")
        client.write(f"TDC:WIDTH:ARM {args.count}")
        deadline = time.monotonic() + args.timeout
        while True:
            status = int(client.query("TDC:WIDTH:STATUS?"))
            if not status & 1:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("Pulse-width burst timed out")
            time.sleep(0.01)
        client.write("PULSE:OUTPUT OFF")
        client.check()
        count = int(client.query("TDC:WIDTH:COUNT?"))
        for start in range(0, count, 128):
            text = client.query(f"TDC:WIDTH:DATA? {start},{min(128, count-start)}")
            client.check()
            for row in text.split(";"):
                values = tuple(map(int, row.split(",")))
                if len(values) != 6:
                    raise RuntimeError("Unexpected record: " + row)
                records.append(values)
        if not args.quiet:
            print("cycle flags       width_ns   rise_raw fall_raw")
            for cycle, flags, coarse, rise, fall, width in records:
                label = "coarse" if flags & 256 else "fine"
                if not flags & 1:
                    label = "INVALID"
                print(f"{cycle:5d} 0x{flags:08x} {width/1000:10.3f} {rise:8d} {fall:8d} {label}")
        print(f"Received {len(records)} records; invalid: {sum(not r[1] & 1 for r in records)}; status=0x{status:x}")
        if args.csv:
            csv_path = Path(args.csv).expanduser()
            if not csv_path.is_absolute():
                csv_root = results_directory("tdc_width_results").resolve()
                csv_path = (csv_root / csv_path).resolve()
                if csv_root not in csv_path.parents:
                    raise ValueError("Relative --csv path must stay within local tdc_width_results")
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with csv_path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.writer(output)
                writer.writerow(["cycle_id", "flags", "coarse_ticks", "rise_raw", "fall_raw", "width_ps"])
                writer.writerows(records)
            print("Saved raw records:", csv_path)
        if status & (16 | 32 | 64 | 128) or not status & 8 or count != args.count:
            raise RuntimeError(f"Incomplete/error burst: status=0x{status:x}, records={count}")
        if len(records) != count or any(r[0] != i+1 for i, r in enumerate(records)):
            raise RuntimeError("Missing or misordered records")
        if any(not r[1] & 1 for r in records):
            raise RuntimeError("Invalid pulse(s); inspect flags, wiring, width and LOW gap")
        print("Burst capture passed. Compare widths to the oscilloscope before accepting accuracy.")
    finally:
        for command in ("PULSE:OUTPUT OFF", "TDC:WIDTH:ABORT"):
            try:
                client.send(command)
            except OSError:
                pass
        try:
            client.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()
