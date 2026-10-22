"""Offline regression for full-capture drift diagnostics and width-reference fitting."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tdc_rigol_tools import (Bench, fit_width_reference, summarize,
                             validate_width_reference, width_distribution,
                             edge_timestamp_diagnostics, plan_matched_period)


def capture(label, reference, measured):
    result = dict(label=label, reference_ns=reference, reference_source="synthetic",
                  acquisition_ok=True, cleanup_errors=[], records=[
                      (i+1, 1 | 512 | (1 << 16) | (1 << 24), 0, 0, 0,
                       int(round(value*1000))) for i, value in enumerate(measured)])
    result["summary"] = summarize(result)
    return result


class StabilityTests(unittest.TestCase):
    def test_v16_preflight_keeps_exact_version_and_interface_checks(self):
        class FakeRP:
            def __init__(self, version, tick=4000):
                self.values = {"TDC:WIDTH:VERSION?": str(version), "TDC:WIDTH:TICK?": str(tick),
                               "TDC:TAPS?": "512", "TDC:WIDTH:CAPACITY?": "16384",
                               "TDC:WIDTH:OFFSET?": "0", "PULSE:PIN?": "DIO1_P",
                               "TDC:WIDTH:MINIMUM:PERIOD?": "200",
                               "TDC:WIDTH:DIAGNOSTIC:CONFIG?": "64,256"}

            def ask(self, query):
                return self.values[query]

        bench = Bench.__new__(Bench)
        bench.config = {"bitstream_label": "synthetic"}
        image = bench._image(FakeRP(16))
        self.assertEqual(image["minimum_period_ns"], 200)
        self.assertEqual(image["diagnostic_stride"], 64)
        with self.assertRaisesRegex(RuntimeError, "expected VERSION=16"):
            bench._image(FakeRP(14))
        with self.assertRaisesRegex(RuntimeError, "TICK=4000"):
            bench._image(FakeRP(16, tick=8000))
        bench.config["expected_width_version"] = 14
        self.assertEqual(bench._image(FakeRP(14))["width_version"], 14)
        with self.assertRaisesRegex(RuntimeError, "expected VERSION=14"):
            bench._image(FakeRP(15))
        bench.config["expected_width_version"] = 15
        self.assertEqual(bench._image(FakeRP(15))["minimum_period_ns"], 500)
        bench.config["expected_width_version"] = 16
        stale_server = FakeRP(16)
        stale_server.values.pop("TDC:WIDTH:DIAGNOSTIC:CONFIG?")
        with self.assertRaisesRegex(RuntimeError, "updated API"):
            bench._image(stale_server)

    def test_five_mhz_common_period_and_overspeed_guard(self):
        plan = plan_matched_period(5e6, 200)
        self.assertEqual(plan["common_period_ns"], 200)
        self.assertEqual(plan["common_frequency_hz"], 5e6)
        self.assertEqual(plan_matched_period(3e6, 200)["common_period_ns"], 332)
        self.assertEqual(plan_matched_period(4e6, 200)["common_period_ns"], 252)
        for frequency, minimum in ((5e6, 500), (5_000_001, 200), (10e6, 200)):
            with self.assertRaises(ValueError):
                plan_matched_period(frequency, minimum)

    def test_sparse_timestamps_wrap_drift_and_association(self):
        records = [(i+1, 513, 25, 0, 0, 100000) for i in range(129)]
        origin = 0xfffffff0
        samples = [(i+1, (origin+i*50)&0xffffffff,
                    (origin+i*50+25)&0xffffffff) for i in (0, 64, 128)]
        tables = {"RISE": [100], "FALL": [200]}
        result = edge_timestamp_diagnostics(records, samples, 64, 200, tables=tables)
        self.assertEqual(result["valid_pairs"], 3)
        np.testing.assert_allclose(result["rise_phase_ns"], 0)
        np.testing.assert_allclose(result["fall_phase_ns"], 0)
        # Add one clock to both edges of the last sample: common drift remains
        # visible even though every width is still 25 ticks.
        samples[-1] = (129, (samples[-1][1]+1)&0xffffffff,
                       (samples[-1][2]+1)&0xffffffff)
        result = edge_timestamp_diagnostics(records, samples, 64, 200, tables=tables)
        np.testing.assert_allclose(result["rise_phase_ns"], [0, 0, 4])
        np.testing.assert_allclose(result["width_change_ns"], 0)
        with self.assertRaisesRegex(RuntimeError, "frame IDs/count"):
            edge_timestamp_diagnostics(records, samples[:-1], 64, 200)
        samples[-1] = (129, samples[-1][1], samples[-1][2]+1)
        with self.assertRaisesRegex(RuntimeError, "coarse width"):
            edge_timestamp_diagnostics(records, samples, 64, 200)

    def test_sparse_invalid_pairs_are_counted_without_invented_timestamps(self):
        records = [(1, 2, 0, 0, 0, 0)]
        result = edge_timestamp_diagnostics(records, [(1, 0, 0)], 64, 200)
        self.assertEqual(result["sampled"], 1)
        self.assertEqual(result["valid_pairs"], 0)
        self.assertEqual(result["rise_phase_ns"], [])
        fallback = [(1, 1 | 128 | 256, 25, 511, 511, 100000)]
        result = edge_timestamp_diagnostics(fallback, [(1, 100, 125)], 64, 200,
                                            tables={"RISE": [], "FALL": []})
        self.assertEqual(result["valid_coarse_pairs"], 1)
        self.assertEqual(result["fine_ineligible_pairs"], 1)
        self.assertEqual(result["valid_pairs"], 0)

    def test_v16_acquisition_protocol_and_sparse_csv_export_offline(self):
        # Exercise real acquisition/save code with both instrument constructors
        # replaced. Unexpected queries fail instead of contacting any device.
        class FakeRP:
            values = {"TDC:WIDTH:VERSION?": "16", "TDC:WIDTH:TICK?": "4000",
                      "TDC:TAPS?": "512", "TDC:WIDTH:CAPACITY?": "16384",
                      "TDC:WIDTH:OFFSET?": "0", "PULSE:PIN?": "DIO1_P",
                      "TDC:WIDTH:MINIMUM:PERIOD?": "200",
                      "TDC:WIDTH:DIAGNOSTIC:CONFIG?": "64,256",
                      "TDC:INPUT?": "SINGLE", "PULSE:TIMING?": "200,100",
                      "TDC:WIDTH:CALIBRATION:ACTIVATE?": "1",
                      "TDC:WIDTH:COUNT?": "129", "PULSE:OUTPUT?": "OFF"}
            def ask(self, query):
                if query.startswith("TDC:WIDTH:DATA:RAW? "):
                    start, count = map(int, query.split()[1].split(","))
                    return ";".join(f"{i+1},16843265,25,0,0,100000" for i in range(start, start+count))
                if query == "TDC:WIDTH:DIAGNOSTIC:EDGE? 0,3":
                    return ";".join(f"{i+1},{100+i*50},{125+i*50}" for i in (0, 64, 128))
                return self.values[query]
            def idle(self, timeout): return 8
            def write(self, command): pass
            def close(self): pass
        class FakeRigol:
            def __init__(self, config): self.log=[]; self.last_settings=None
            def configure(self, frequency, width, config):
                self.last_settings = dict(width_ns=100.0, period_ns=200.0,
                                          frequency_query_hz=5e6)
                return self.last_settings
            def on(self): pass
            def off(self): pass
            def close(self): pass
        with tempfile.TemporaryDirectory() as directory:
            bench = Bench(dict(bitstream_label="offline V16", frame_count=129,
                               settle_s=0, launch_settle_s=0), directory)
            rp = FakeRP()
            bench._rp = lambda: rp
            bench.image = bench._image(rp)
            bench.candidate = dict(ready=True, tables={e: [0]*512 for e in ("RISE", "FALL")},
                                   histograms={e: [1]*512 for e in ("RISE", "FALL")})
            with patch("tdc_rigol_tools.Rigol", FakeRigol):
                c = bench._acquire_once("offline_5MHz", 5e6, 100.0, fine=True)
            self.assertTrue(c["acquisition_ok"])
            self.assertEqual(c["fine_arithmetic_check"]["mismatch_frames"], [])
            self.assertEqual(c["edge_diagnostics"]["valid_pairs"], 3)
            self.assertEqual(c["cleanup_errors"], [])
            with Path(c["capture_files"]["csv"]).open(newline="") as stream:
                saved = list(csv.DictReader(stream))
            self.assertEqual(len(saved), 129)
            self.assertEqual(saved[0]["diagnostic_rise_ticks"], "100")
            self.assertEqual(saved[1]["diagnostic_rise_ticks"], "")
            self.assertEqual(saved[128]["diagnostic_fall_ticks"], "6525")
            metadata = json.loads(Path(c["capture_files"]["json"]).read_text())
            self.assertEqual(len(metadata["edge_tick_samples"]), 3)

    def test_drift_and_tails_keep_all_samples(self):
        values = np.repeat(np.arange(8, dtype=float), 100)
        result = width_distribution(values)
        self.assertEqual(result["n"], 800)
        self.assertEqual(result["block_means_ns"], list(range(8)))
        self.assertEqual(result["block_mean_span_ns"], 7)
        self.assertEqual(result["beyond_1ns_from_median"], 600)

    def test_coarse_fallback_is_reported_separately(self):
        c = capture("mixed", 100, [102.] * 100)
        c["records"].append((101, 1 | 256, 26, 0, 0, 104000))
        s = summarize(c)
        self.assertEqual(s["all_complete"]["distribution"]["max_ns"], 104)
        self.assertEqual(s["calibrated_only"]["distribution"]["max_ns"], 102)
        self.assertEqual(s["all_complete"]["n"], 101)

    def test_offset_excludes_nonlinearity_and_drift_without_trimming(self):
        training = [capture("short", 20, [26.] * 800),
                    capture("stable", 500, [502.] * 800),
                    capture("drift", 800, 802 + np.linspace(-1, 1, 800))]
        model = fit_width_reference(training)
        self.assertEqual(model["scale"], 1)
        self.assertEqual(model["offset_ns"], -2)
        self.assertEqual(model["training_labels"], ["stable"])
        self.assertEqual(len(model["excluded_training_captures"]), 2)
        heldout = capture("heldout", 350, [352.] * 800)
        self.assertAlmostEqual(validate_width_reference(model, [heldout])[0]["corrected_error_ns"], 0)
        self.assertEqual(len(training[2]["records"]), 800)

    def test_low_sd_slow_drift_fails_chronological_gate(self):
        c = capture("slow", 100, 102 + np.linspace(-.2, .2, 800))
        self.assertLess(c["summary"]["all_complete"]["std_ns"], .15)
        with self.assertRaisesRegex(ValueError, "No stable"):
            fit_width_reference([c])

    def test_rejected_training_is_not_a_holdout(self):
        short = capture("short", 20, [26.] * 800)
        model = fit_width_reference([short, capture("stable", 500, [502.] * 800)])
        with self.assertRaisesRegex(ValueError, "not used for fitting"):
            validate_width_reference(model, [short])

    def test_affine_needs_three_stable_widths(self):
        with self.assertRaisesRegex(ValueError, ">=3 stable"):
            fit_width_reference([capture("only", 500, [502.] * 800)], model="affine")
        model = fit_width_reference([capture(str(w), w, [w+2.] * 800)
                                     for w in (100, 300, 600)], model="affine")
        self.assertAlmostEqual(model["scale"], 1)
        self.assertAlmostEqual(model["offset_ns"], -2)

    def test_empty_distribution_and_invalid_gates(self):
        self.assertIsNone(width_distribution([])["block_mean_span_ns"])
        with self.assertRaises(ValueError):
            fit_width_reference([], maximum_std_ns=float("nan"))


if __name__ == "__main__":
    unittest.main()
