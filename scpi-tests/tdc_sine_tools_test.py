"""Offline numerical/protocol checks. Does not connect to hardware or run HDL."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tdc_sine_tools import (
    acquire_width_burst, analyze_capture, save_capture, stop_output, validate_config,
)


CONFIG = dict(host="mock", port=5000, fpga_frequency_hz=100_000.0,
              sample_count=2048, input_mode="SINGLE", sine_frequency_hz=1000.0,
              sine_vpp=1.0, sine_offset_v=0.5, settle_s=0, timeout_s=5)


def synthetic_capture(frequency=1003.7, invalid=False):
    config = dict(CONFIG)
    plan = validate_config(config)
    times = np.arange(config["sample_count"]) / plan["actual_fpga_hz"]
    widths = np.round((250 + 90 * np.sin(2*np.pi*frequency*times + 0.61)) / 4) * 4
    records = [(i+1, 0x01010101, int(width/4), 4, 8, int(width*1000))
               for i, width in enumerate(widths)]
    if invalid:
        for i in range(20, len(records), 37):
            records[i] = (i+1, 4 | 2048, 0, 0, 0, 0)
    return dict(settings=config, plan=plan, records=records, tick_ps=4000,
                acquisition_ok=True, status=8, capacity=16384)


class MockClient:
    def __init__(self, status=8, interrupt=False, malformed=False):
        self.commands = []
        self.status = 0
        self.final_status = status
        self.enabled = False
        self.count = 0
        self.input_mode = "LVDS"
        self.timing = "1000,500"
        self.closed = False
        self.interrupt = interrupt
        self.malformed = malformed

    def send(self, command):
        self.commands.append(command)

    def check(self):
        pass

    def write(self, command):
        self.commands.append(command)
        if command.startswith("PULSE:OUTPUT "):
            self.enabled = command.endswith("ON")
        elif command.startswith("PULSE:TIMING "):
            self.timing = command.split(" ")[1]
        elif command.startswith("TDC:INPUT "):
            self.input_mode = command.split(" ")[1]
        elif command.startswith("TDC:WIDTH:ARM "):
            if not self.enabled:
                raise AssertionError("ARM requires running pulse source")
            self.count = int(command.split(" ")[1])
            self.status = self.final_status
            if self.interrupt:
                raise KeyboardInterrupt()
        elif command == "TDC:WIDTH:ABORT":
            self.status = 0

    def query(self, command):
        self.commands.append(command)
        responses = {
            "TDC:WIDTH:CAPACITY?": "16384", "TDC:WIDTH:TICK?": "4000",
            "TDC:WIDTH:STATUS?": str(self.status), "TDC:WIDTH:COUNT?": str(self.count),
            "PULSE:PIN?": "DIO1_P", "PULSE:TIMING?": self.timing,
            "PULSE:OUTPUT?": str(int(self.enabled)), "TDC:INPUT?": self.input_mode,
        }
        if command.startswith("TDC:WIDTH:DATA? "):
            start, count = map(int, command.split(" ")[1].split(","))
            assert count <= 128
            if self.malformed:
                return "1,2,3"
            return ";".join(f"{i+1},{4 if i == 5 else 0x01010101},25,4,8,{0 if i == 5 else 100000}"
                            for i in range(start, start+count))
        return responses[command]

    def close(self):
        self.closed = True


class SineNotebookChecks(unittest.TestCase):
    def test_trigger_quantization_and_nyquist(self):
        config = dict(CONFIG, fpga_frequency_hz=123456)
        plan = validate_config(config)
        self.assertEqual(plan["period_ns"] % 4, 0)
        self.assertEqual(plan["high_ns"]*2, plan["period_ns"])
        for bad in (dict(CONFIG, fpga_frequency_hz=1_000_001),
                    dict(CONFIG, sine_frequency_hz=50_000),
                    dict(CONFIG, sample_count=16385), dict(CONFIG, sine_vpp=0),
                    dict(CONFIG, sine_offset_v=float("nan"))):
            with self.assertRaises(ValueError):
                validate_config(bad)

    def test_known_sine_and_independent_frequency(self):
        capture = synthetic_capture()
        result = analyze_capture(capture)
        self.assertAlmostEqual(result["dominant_fit"]["frequency_hz"], 1003.7, delta=0.08)
        self.assertEqual(result["fixed_fit"]["frequency_hz"], 1000.0)
        self.assertAlmostEqual(result["fixed_fit"]["offset"], 250, delta=0.4)
        self.assertAlmostEqual(result["fixed_fit"]["amplitude"], 90, delta=1)
        self.assertGreater(result["r_squared"], 0.97)
        self.assertLess(result["dominant_fit"]["rmse"], 1.3)

    def test_invalid_slots_are_not_compressed(self):
        result = analyze_capture(synthetic_capture(invalid=True))
        self.assertAlmostEqual(result["time_s"][100], 0.001)
        self.assertTrue(np.isnan(result["normalized_width"][20]))
        self.assertFalse(result["valid"][20])
        self.assertAlmostEqual(result["dominant_fit"]["frequency_hz"], 1003.7, delta=0.15)

    def test_flat_or_incomplete_signal_is_not_a_sine_pass(self):
        capture = synthetic_capture()
        capture["records"] = [(row[0], row[1], 25, 4, 8, 100000) for row in capture["records"]]
        with self.assertRaisesRegex(ValueError, "No resolved width"):
            analyze_capture(capture)
        capture["acquisition_ok"] = False
        with self.assertRaisesRegex(ValueError, "Incomplete/error"):
            analyze_capture(capture)

    def test_protocol_chunking_invalid_flags_and_cleanup(self):
        mock = MockClient()
        capture = acquire_width_burst(dict(CONFIG, sample_count=130), lambda *_: mock)
        self.assertTrue(capture["acquisition_ok"])
        self.assertEqual(capture["valid_count"], 129)
        self.assertEqual(capture["records"][5][0], 6)
        self.assertFalse(mock.enabled)
        self.assertTrue(mock.closed)
        self.assertLess(mock.commands.index("PULSE:OUTPUT ON"), mock.commands.index("TDC:WIDTH:ARM 130"))
        self.assertLess(mock.commands.index("PULSE:OUTPUT OFF", mock.commands.index("TDC:WIDTH:ARM 130")),
                        mock.commands.index("TDC:WIDTH:DATA? 0,128"))
        self.assertIn("TDC:WIDTH:DATA? 128,2", mock.commands)
        with tempfile.TemporaryDirectory() as directory:
            stem = save_capture(capture, directory)
            self.assertEqual(json.loads(stem.with_suffix(".json").read_text())["valid_count"], 129)
            self.assertIn("NO_FALL", stem.with_suffix(".csv").read_text())

    def test_error_status_retained_and_keyboard_interrupt_stops_output(self):
        mock = MockClient(status=8 | 128)
        capture = acquire_width_burst(dict(CONFIG, sample_count=32), lambda *_: mock)
        self.assertFalse(capture["acquisition_ok"])
        self.assertEqual(capture["status"], 136)
        mock = MockClient(interrupt=True)
        with self.assertRaises(KeyboardInterrupt):
            acquire_width_burst(dict(CONFIG, sample_count=32), lambda *_: mock)
        self.assertFalse(mock.enabled)
        self.assertTrue(mock.closed)
        mock = MockClient(malformed=True)
        with self.assertRaisesRegex(RuntimeError, "Malformed"):
            acquire_width_burst(dict(CONFIG, sample_count=32), lambda *_: mock)
        self.assertFalse(mock.enabled)
        self.assertTrue(mock.closed)

    def test_stop_cell(self):
        mock = MockClient()
        mock.enabled = True
        stop_output("mock", client_factory=lambda *_: mock)
        self.assertFalse(mock.enabled)
        self.assertTrue(mock.closed)

    def test_notebook_structure_and_cell_syntax(self):
        notebook = json.loads(Path(__file__).with_name("tdc_pcb_sine_test.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"], 4)
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])
                compile("".join(cell["source"]), f"notebook-cell-{index}", "exec")


if __name__ == "__main__":
    unittest.main(verbosity=2)
