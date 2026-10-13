"""Register/SCPI smoke test for the custom single-channel GPIO pulse generator.

Requires the matching custom bitstream and server. This does not measure the
electrical waveform. Default ON test is 1 MHz; smaller periods require --fast
and a receiving circuit already verified for that speed. Output finishes OFF
and claimed LOW, rather than returning the pin to a possibly HIGH GPIO state.
"""
import argparse
import math
import socket
import time


class Client:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=3)
        self.reader = self.sock.makefile("rb")

    def send(self, command):
        self.sock.sendall((command + "\r\n").encode("ascii"))

    def query(self, command):
        self.send(command)
        line = self.reader.readline(4096)
        if not line:
            raise RuntimeError("SCPI connection closed")
        return line.decode("ascii").strip()

    def close(self):
        self.reader.close()
        self.sock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--period-ns", type=int, default=1000)
    parser.add_argument("--high-ns", type=int, default=500)
    parser.add_argument("--fast", action="store_true", help="permit an ON test faster than 1 MHz")
    args = parser.parse_args()
    if not (4 <= args.period_ns <= 8589934588 and args.period_ns % 4 == 0
            and 2 <= args.high_ns < args.period_ns and args.high_ns % 2 == 0):
        parser.error("period must be 4 ns aligned; HIGH must be 2 ns aligned and smaller than period")
    if args.period_ns < 1000 and not args.fast:
        parser.error("fast electrical testing requires --fast")

    client = Client(args.host, args.port)
    try:
        pin = client.query("PULSE:PIN?")
        if pin != "DIO1_P":
            raise RuntimeError("Unexpected pulse pin: " + pin)
        client.send("PULSE:OUTPUT OFF")
        if client.query("PULSE:OUTPUT?") != "0":
            raise RuntimeError("Failed to disable output")

        # Exercise exact timing and duty preservation with output OFF.
        client.send("PULSE:TIMING 8,4")
        if client.query("PULSE:TIMING?") != "8,4":
            raise RuntimeError("8 ns timing readback failed")
        client.send("PULSE:PERIOD 24")
        if client.query("PULSE:TIMING?") != "24,12":
            raise RuntimeError("Period/duty preservation failed")
        client.send("PULSE:FREQUENCY 250000000")
        if client.query("PULSE:TIMING?") != "4,2":
            raise RuntimeError("DDR maximum timing readback failed")

        client.send(f"PULSE:TIMING {args.period_ns},{args.high_ns}")
        timing = tuple(int(x) for x in client.query("PULSE:TIMING?").split(","))
        if timing != (args.period_ns, args.high_ns):
            raise RuntimeError("Configured timing readback failed")
        frequency = float(client.query("PULSE:FREQUENCY?"))
        if not math.isclose(frequency, 1e9 / args.period_ns, rel_tol=1e-6):
            raise RuntimeError("Frequency query mismatch")
        client.send("PULSE:OUTPUT ON")
        if client.query("PULSE:OUTPUT?") != "1":
            raise RuntimeError("Failed to enable output")
        status = int(client.query("PULSE:STATUS?"))
        if status & 0x1f != 0x16:
            raise RuntimeError(f"Unexpected running status: 0x{status:x}")
        time.sleep(0.05)
        print(f"SCPI/register test passed: {pin}, period={timing[0]} ns, HIGH={timing[1]} ns")
        print("Verify amplitude, period, HIGH/LOW durations and ringing on an oscilloscope.")
    finally:
        try:
            client.send("PULSE:OUTPUT OFF")
            if client.query("PULSE:OUTPUT?") != "0":
                raise RuntimeError("Final OFF failed")
        finally:
            client.close()


if __name__ == "__main__":
    main()
