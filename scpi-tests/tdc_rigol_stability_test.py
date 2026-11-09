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
                             edge_timestamp_diagnostics, plan_matched_period,
                             input_path_diagnostic, verify_dc_readback,
                             gpio_pulse_diagnostic, frame_offset_survey)


def capture(label, reference, measured):
    result = dict(label=label, reference_ns=reference, reference_source="synthetic",
                  acquisition_ok=True, cleanup_errors=[], records=[
                      (i+1, 1 | 512 | (1 << 16) | (1 << 24), 0, 0, 0,
                       int(round(value*1000))) for i, value in enumerate(measured)])
    result["summary"] = summarize(result)
    return result


class StabilityTests(unittest.TestCase):
    def test_capture_retention_keeps_only_complete_bursts_by_default(self):
        for policy in ('complete_only','nonzero','all'):
            for valid in (0,2,4):
                with self.subTest(policy=policy,valid=valid), tempfile.TemporaryDirectory() as directory:
                    bench=Bench({'capture_retention':policy},directory)
                    c=capture('retention',20.,[20.]*valid)
                    c['records'] += [(i+1,6,0,0,0,0) for i in range(valid,4)]
                    c.update(frames_requested=4,capture_files={},edge_tick_samples=[[1,0,0]],
                             awg_scpi_log=[{'command':':SYST:ERR?','reply':'0,"No error"'}])
                    c['summary']=summarize(c)
                    original=list(c['records'])
                    bench.save_capture(Path(directory)/'attempt',c)
                    expected=policy=='all' or valid==4 or (policy=='nonzero' and valid>0)
                    metadata=json.loads(Path(c['capture_files']['json']).read_text())
                    self.assertEqual(metadata['raw_records_saved'],expected)
                    self.assertEqual((Path(directory)/'attempt.csv').exists(),expected)
                    self.assertEqual(c['records'],original)
                    self.assertEqual(metadata['summary']['complete_pulses'],valid)
                    if not expected:
                        self.assertIsNone(metadata['capture_files']['csv'])
                        self.assertNotIn('edge_tick_samples',metadata)
                        self.assertNotIn('awg_scpi_log',metadata)

    def test_reloaded_input_blocks_fine_before_arm_and_explains_lut_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            writes=[]
            class FakeRP:
                def write(self,command): writes.append(command)
                def idle(self,timeout): return 8
                def ask(self,command):
                    return {'TDC:INPUT?':'LVDS','PULSE:OUTPUT?':'OFF'}[command]
                def close(self): pass
            class FakeRigol:
                last_settings=None
                def __init__(self,config): self.log=[]
                def configure(self,frequency,width,config):
                    self.last_settings=dict(period_ns=40.,width_ns=20.2,frequency_query_hz=25e6)
                    return self.last_settings
                def off(self): pass
                def close(self): pass
            bench=Bench({'frame_count':4},directory)
            bench.image=dict(width_version=17,minimum_period_ns=40,capacity=16384,taps=512)
            bench.candidate={'ready':True}
            bench._rp=FakeRP
            bench._image=lambda rp:bench.image
            with patch('tdc_rigol_tools.Rigol',FakeRigol):
                with self.assertRaisesRegex(RuntimeError,'bench.preflight.*bench.upload'):
                    bench._acquire_once('after_reload',25e6,20.2,fine=True)
            self.assertFalse(any(c.startswith('TDC:WIDTH:ARM') for c in writes))
            self.assertNotIn('TDC:INPUT SINGLE',writes)
            saved=json.loads(next(Path(directory).glob('0*.json')).read_text())
            self.assertEqual(saved['cleanup_errors'],[])
            self.assertEqual(saved['records'] if 'records' in saved else [],[])

    def test_offset_survey_scans_every_offset_without_retries_and_restores_config(self):
        with tempfile.TemporaryDirectory() as directory:
            prior = {40: 8}
            bench = Bench(dict(frame_offsets_by_period_ns=prior, phase_retries=True), directory)
            bench.image = dict(width_version=17, minimum_period_ns=40, capacity=16384)
            calls = []
            def once(label, frequency, width, frames, fine):
                offset = bench.config['frame_offsets_by_period_ns'][40]
                calls.append(offset)
                self.assertEqual(frequency,25e6)
                self.assertEqual(width,20.2)
                self.assertFalse(fine)
                # One stable full candidate, one intermittent candidate, and
                # partial/missing frames retained at every other offset.
                complete = offset == 12 or (offset == 20 and len(calls) <= 10)
                c = capture(label,width,[24.] * frames if complete else [])
                if not complete:
                    c['records'] = [(i+1,6,0,0,0,0) for i in range(frames)]
                    c['summary'] = summarize(c)
                c['capture_files'] = {'json':label+'.json'}
                return c
            with patch.object(bench,'_acquire_once',side_effect=once):
                result=frame_offset_survey(bench,points=[(25e6,20.2)],frames=4,repeats=2)
            self.assertEqual(calls,list(range(0,40,4))*2)
            self.assertIs(bench.config['frame_offsets_by_period_ns'],prior)
            self.assertEqual(len(result['attempts']),20)
            self.assertEqual(result['suggested_offsets_by_period_ns'],{'40':12})
            intermittent=next(p for p in result['offset_summary'] if p['offset_ns']==20)
            self.assertEqual(intermittent['complete_starts'],1)
            saved=json.loads(Path(result['ledger_path']).read_text())
            self.assertEqual(saved['attempts'][0]['flag_counts'],{'NO_RISE':4,'NO_FALL':4})

    def test_offset_survey_failure_retains_progress_and_restores_config(self):
        with tempfile.TemporaryDirectory() as directory:
            bench=Bench({},directory)
            bench.image=dict(width_version=17,minimum_period_ns=40,capacity=16384)
            c=capture('good',20.2,[24.]*4)
            c['capture_files']={'json':'good.json'}
            with patch.object(bench,'_acquire_once',side_effect=[c,RuntimeError('synthetic disconnect')]):
                with self.assertRaisesRegex(RuntimeError,'synthetic disconnect'):
                    frame_offset_survey(bench,points=[(25e6,20.2)],frames=4)
            self.assertNotIn('frame_offsets_by_period_ns',bench.config)
            saved=json.loads(next(Path(directory).glob('frame_offset_survey_*.json')).read_text())
            self.assertEqual(len(saved['attempts']),1)
            self.assertIn('synthetic disconnect',saved['failure'])

    def test_gpio_pulse_diagnostic_has_no_arm_and_stops_on_read_failure(self):
        # Exercise the actual GPIO-only protocol and exception cleanup, with
        # no real constructors, sockets, USB sessions or sleep delays.
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                shared = dict(width=0., awg_on=False, launch=False, reads=0, writes=[])
                class FakeRP:
                    def write(self, command):
                        shared['writes'].append(command)
                        if command.startswith('PULSE:OUTPUT '):
                            shared['launch'] = command.endswith(' ON')
                    def ask(self, command):
                        if command == 'PULSE:TIMING?': return '1000,500'
                        if command == 'PULSE:OUTPUT?': return str(int(shared['launch']))
                        if command == 'DIG:PIN? DIO2_P':
                            self_test.assertTrue(shared['awg_on'])
                            shared['reads'] += 1
                            if fail and shared['reads'] == 5:
                                raise RuntimeError('synthetic GPIO read failure')
                            return str(shared['reads'] % 2)
                        raise AssertionError('unexpected command: '+command)
                    def idle(self, timeout): return 8
                    def close(self): pass
                class FakeRigol:
                    source = ':SOURce1'
                    last_settings = None
                    def __init__(self, config): self.log = []
                    def configure(self, frequency, width, config):
                        shared['width'] = width
                        return self.readback()
                    def readback(self):
                        return dict(width_ns=shared['width'], period_ns=1000.,
                                    frequency_query_hz=1e6)
                    def ask(self, command):
                        self_test.assertEqual(command, ':SOURce1:FUNCtion:PULSe:DCYCle?')
                        return str(shared['width']/10.)
                    def on(self): shared['awg_on'] = True
                    def off(self): shared['awg_on'] = False
                    def close(self): pass
                self_test = self
                bench = Bench({}, directory)
                bench.image = {'synthetic': True}
                bench._image = lambda rp: bench.image
                bench._rp = FakeRP
                with patch('tdc_rigol_tools.Rigol', FakeRigol), patch('tdc_rigol_tools.time.sleep'):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, 'synthetic GPIO read failure'):
                            gpio_pulse_diagnostic(bench, samples=32)
                    else:
                        result = gpio_pulse_diagnostic(bench, samples=32)
                        self.assertEqual(len(result['points']), 8)
                        self.assertEqual([p['launch_enabled'] for p in result['points']], [False,True]*4)
                        self.assertTrue(all(len(p['samples']) == 32 for p in result['points']))
                        self.assertTrue(all(p['active_awg']['width_duty_consistent'] for p in result['points']))
                self.assertFalse(shared['awg_on'])
                self.assertFalse(shared['launch'])
                self.assertFalse(any('TDC:WIDTH:ARM' in c for c in shared['writes']))
                saved = json.loads((Path(directory)/'gpio_pulse_diagnostic.json').read_text())
                self.assertEqual(saved['cleanup_errors'], [])
                if fail:
                    self.assertIn('synthetic GPIO read failure', saved['failure'])
                    self.assertEqual(len(saved['points'][0]['samples']), 4)

    def test_dc_high_requires_dc_identity_and_both_offset_readbacks(self):
        verified = verify_dc_readback('ARB', 'DC,DEF,DEF,3.3,DEF', 3.3,
                                      expected_level_v=3.3)
        self.assertTrue(verified['dc_verified'])
        self.assertTrue(verify_dc_readback('ARB', 'DC,DEF,DEF,0,DEF', 0)['dc_verified'])
        for function, reply, level in (('ARB', 'ARB,1,1,3.3,0', 3.3),
                                      ('DC', 'DC,DEF,DEF,0,DEF', 3.3),
                                      ('DC', 'DC,DEF,DEF,3.3,DEF', 0)):
            with self.assertRaises(RuntimeError):
                verify_dc_readback(function, reply, level, expected_level_v=3.3)

    def test_no_edges_stops_retries_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            bench = Bench(dict(phase_retries=True, phase_retry_max_attempts=50,
                               phase_retry_delay_s=0), directory)
            missing = capture('missing', 20.2, [])
            missing.update(frames_requested=512,
                           records=[(i+1,6,0,0,0,0) for i in range(512)],
                           capture_files={'json': str(Path(directory)/'attempt.json')})
            missing['summary'] = summarize(missing)
            with patch.object(bench, '_acquire_once', return_value=missing) as acquire:
                with self.assertRaisesRegex(RuntimeError, 'No rising or falling edges'):
                    bench.acquire('missing', 25e6, 20.2, frames=512)
            self.assertEqual(acquire.call_count, 1)
            ledger = json.loads(next(Path(directory).glob('*retries.json')).read_text())
            self.assertEqual(ledger['total_frames'], 512)
            self.assertEqual(ledger['attempts'][0]['flag_counts'], {'NO_RISE':512, 'NO_FALL':512})
            self.assertEqual(ledger['failed_attempt'], 1)

    def test_boundary_cut_pulses_still_retry_for_completeness(self):
        with tempfile.TemporaryDirectory() as directory:
            bench = Bench(dict(phase_retries=True, phase_retry_max_attempts=2,
                               phase_retry_delay_s=0), directory)
            partial = capture('partial', 100, [])
            partial.update(records=[(1, 2,0,0,0,0)], frames_requested=1,
                           capture_files={'json':str(Path(directory)/'partial.json')})
            partial['summary'] = summarize(partial)
            complete = capture('complete', 100, [100])
            complete.update(frames_requested=1, phase_retry={},
                            capture_files={'json':str(Path(directory)/'complete.json')})
            with patch.object(bench, '_acquire_once', side_effect=[partial, complete]) as acquire:
                self.assertIs(bench.acquire('boundary', 1e6, 100), complete)
            self.assertEqual(acquire.call_count, 2)

    def test_input_diagnostic_distinguishes_gpio_sampler_and_rate_failures(self):
        for failure in (None, 'gpio', 'sampler', 'rate'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                bench = Bench({}, directory)
                bench.image = dict(minimum_period_ns=40)
                def once(label, frequency, width, frames, fine=False, stimulus='pulse'):
                    self.assertFalse(fine)
                    high = stimulus == 'dc_high'
                    flags = (2062 if high and failure != 'sampler' else 6) if stimulus != 'pulse' else 257
                    if failure == 'rate' and frequency == 25e6:
                        flags = 6
                    c = capture(label, width, [])
                    c.update(records=[(i+1,flags,0,0,0,0) for i in range(frames)],
                             input_gpio=dict(matched=failure != 'gpio'),
                             capture_files={'json':label+'.json'},
                             timing=plan_matched_period(frequency,40), awg=dict(width_ns=width))
                    c['summary'] = summarize(c)
                    return c
                with patch.object(bench, '_acquire_once', side_effect=once) as acquire:
                    result, captures = input_path_diagnostic(bench, frames=4)
                self.assertEqual(acquire.call_count, 10)
                self.assertEqual(len(captures), 10)
                self.assertEqual(result['ready_for_alignment'], failure is None)
                self.assertEqual(result['gpio_dc_pass'], failure != 'gpio')
                self.assertEqual(result['width_dc_pass'], failure != 'sampler')
                self.assertEqual(result['points'][-1]['period_ns'], 40)
                self.assertTrue((Path(directory)/'input_path_diagnostic.json').is_file())

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
        bench.config["expected_width_version"] = 17
        v17 = FakeRP(17)
        v17.values["TDC:WIDTH:MINIMUM:PERIOD?"] = "40"
        self.assertEqual(bench._image(v17)["minimum_period_ns"], 40)
        with self.assertRaisesRegex(RuntimeError, "expected VERSION=17"):
            bench._image(FakeRP(16))
        v17.values["TDC:WIDTH:MINIMUM:PERIOD?"] = "36"
        with self.assertRaisesRegex(RuntimeError, "Invalid hardware minimum"):
            bench._image(v17)
        bench.config["expected_width_version"] = 18
        v18 = FakeRP(18)
        v18.values["TDC:WIDTH:MINIMUM:PERIOD?"] = "40"
        self.assertEqual(bench._image(v18)["width_version"],18)
        with self.assertRaisesRegex(RuntimeError,"expected VERSION=18"):
            bench._image(FakeRP(17))
        # A V16-labelled image must not acquire a V17-only minimum silently.
        bench.config["expected_width_version"] = 16
        invalid_v16 = FakeRP(16)
        invalid_v16.values["TDC:WIDTH:MINIMUM:PERIOD?"] = "40"
        with self.assertRaisesRegex(RuntimeError, "Invalid hardware minimum"):
            bench._image(invalid_v16)

    def test_five_mhz_common_period_and_overspeed_guard(self):
        plan = plan_matched_period(5e6, 200)
        self.assertEqual(plan["common_period_ns"], 200)
        self.assertEqual(plan["common_frequency_hz"], 5e6)
        self.assertEqual(plan_matched_period(3e6, 200)["common_period_ns"], 332)
        self.assertEqual(plan_matched_period(4e6, 200)["common_period_ns"], 252)
        for frequency, minimum in ((5e6, 500), (5_000_001, 200), (10e6, 200)):
            with self.assertRaises(ValueError):
                plan_matched_period(frequency, minimum)

    def test_25mhz_planning_preserves_legacy_rate_guards(self):
        self.assertEqual(plan_matched_period(25e6, 40)["common_period_ns"], 40)
        for frequency in (25_000_001., 30e6, 50e6):
            with self.assertRaises(ValueError):
                plan_matched_period(frequency, 40)
        with self.assertRaises(ValueError):
            plan_matched_period(25e6, 200)
        with self.assertRaises(ValueError):
            plan_matched_period(25e6, 40, frame_period_ns=80)

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
            dc = None
            values = {"TDC:WIDTH:VERSION?": "16", "TDC:WIDTH:TICK?": "4000",
                      "TDC:TAPS?": "512", "TDC:WIDTH:CAPACITY?": "16384",
                      "TDC:WIDTH:OFFSET?": "0", "PULSE:PIN?": "DIO1_P",
                      "TDC:WIDTH:MINIMUM:PERIOD?": "200",
                      "TDC:WIDTH:DIAGNOSTIC:CONFIG?": "64,256",
                      "TDC:INPUT?": "SINGLE", "PULSE:TIMING?": "200,100",
                      "TDC:WIDTH:CALIBRATION:ACTIVATE?": "1",
                      "TDC:WIDTH:COUNT?": "129", "PULSE:OUTPUT?": "OFF"}
            def ask(self, query):
                if query == "DIG:PIN? DIO2_P":
                    return str(self.dc)
                if query.startswith("TDC:WIDTH:DATA:RAW? "):
                    start, count = map(int, query.split()[1].split(","))
                    if self.dc is not None:
                        flags = 2062 if self.dc else 6
                        return ";".join(f"{i+1},{flags},0,0,0,0" for i in range(start, start+count))
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
            def dc_level(self, level):
                self.last_settings = dict(dc_verified=True, dc_level_v=level)
                return self.last_settings
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
            for level, stimulus in ((0, 'dc_low'), (1, 'dc_high')):
                rp.dc = level
                with patch("tdc_rigol_tools.Rigol", FakeRigol):
                    control = bench._acquire_once(stimulus, 5e6, 100., stimulus=stimulus)
                self.assertTrue(control['acquisition_ok'])
                self.assertEqual(control['cleanup_errors'], [])
                self.assertEqual(control['input_gpio']['samples'], [level]*8)
                self.assertTrue(control['input_gpio']['matched'])
                self.assertIsNone(control['reference_ns'])
                self.assertEqual(control['summary']['complete_pulses'], 0)

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
