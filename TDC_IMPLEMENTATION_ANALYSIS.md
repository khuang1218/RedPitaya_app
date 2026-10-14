# TDC measurement notes and historical findings

Last reconciled: 2026-10-14.

The authoritative setup, current source status, validation boundary and next actions are in [HANDOVER.md](HANDOVER.md). This file retains the useful TDC measurement evidence and its interpretation. It is not a second operational handover.

Results below were recorded in the earlier analysis and notebook history. They apply to the particular older placed/routed images used in those experiments. Mentioned raw calibration artifacts are not assumed to be available in every clone. No new board measurements or Vivado runs were performed during this reconciliation.

## 1. Prior MMCM sweep and source corrections

A user-reported real-board run of scpi-tests/tdc_internal_selftest.ipynb locked the dedicated MMCM and produced a 40-step INCREASE sweep. After accounting for the FIFO decoding error described below, the recorded raw indices progressed monotonically.

This supports operation of the MMCM and phase-step path in that particular image. It does not establish absolute picosecond accuracy, validate a later bitstream, or replace routed timing/CDC/DRC checks.

Two bugs exposed by that work are corrected in the current RTL:

- FIFO packing used a 9-bit fine-raw field for the 512-tap configuration while the API expected a fixed 10-bit field. The 127-bit concatenation shifted the higher fields. It could produce a spurious +512 raw index and corrupt FIFO-derived fine/total times.
- trigger_pending was set only in the reset branch. A one-shot trigger that could not immediately arm could be lost, resulting in a measurement timeout. Its set logic was moved into normal operation.

The run exposing those bugs predates the fixes. Their presence in the source tree and the later Icarus logic PASS do not establish fresh board acceptance of every affected behavior.

### Fixed FIFO record layout

The current 128-bit record uses:

| Bits | Field | Width |
|---|---|---:|
| 15:0 | Sequence | 16 |
| 23:16 | Status | 8 |
| 55:24 | Coarse cycles | 32 |
| 65:56 | Fine raw index, zero-extended | 10 |
| 81:66 | Fine time, ps | 16 |
| 127:82 | Total time, ps | 46 |

The histogram indexes the hardware raw fine value directly and bypasses the FIFO; the earlier FIFO packing error did not explain its missing-code region.

## 2. Historical 100k-event calibration

An internal-stimulus run of scpi-tests/tdc_calibrate.py reported:

| Metric | Recorded result |
|---|---:|
| Events | 100,000 |
| Useful bins | 414 |
| Peak absolute DNL | 2.196 LSB |
| Peak absolute INL | 8.426 LSB |
| Small low/zero-count regions | Near raw indices 99..100 and 203..204 |
| Long zero-count region | Raw indices 305..320 inclusive |

A second 100k-event run, identified in the old notes as tdc_calibration_20260806_170814.json, reproduced the long region. The old report associated it with approximately CARRY4 stages 76..80.

The user also reported querying CLOCK_REGION around stages 74..82 in the old implemented design. Locations SLICE_X45Y96..Y99 and Y100..Y104 straddled the reported region boundary near stages 77/78. These are **historical observations, not a recommended column/start row for the new build**.

### Physical interpretation remains qualified

A persistent missing-code region correlated with a clock-region boundary deserves investigation of the actual routed carry connections, sampling-clock skew and tap paths.

The old analysis went further and asserted that a dedicated 7-series carry cascade cannot cross a clock-region boundary, that crossing necessarily uses general routing, and that the dead region therefore cannot be improved by changing placement. That architectural conclusion was too strong and has been removed.

AMD describes carry cascading as limited by the slice-column height and identifies SLR crossings as a restriction on applicable SSI devices. A clock-region association by itself does not prove that a carry cascade was broken or establish the physical cause of missing codes.

Reference: [AMD 7-series carry logic](https://docs.amd.com/r/en-US/ug474_7Series_CLB/Carry-Logic).

For a new image, inspect the routed connections and repeat calibration. Fixed LOC/BEL constraints improve control of placement, but they do not freeze every routed delay or guarantee uniform bins. Missing raw-code positions also do not translate directly into a uniform percentage loss of time resolution.

### Calibration-tool handling

The current calibration tool:

- Finds internal zero-count runs, distinguishing the unpopulated tail and short runs controlled by --max-benign-dead-run.
- Stores large regions under metrics.large_dead_zones.
- Accepts repeated --known-dead-zone START-END arguments, inclusive.
- Records characterized regions under metrics.documented_dead_zones and flags uncovered anomalies under metrics.new_dead_zones.
- Provides --collect-only for inspection before LUT activation.

A known-dead-zone flag documents a characterized image; it does not repair missing codes. Re-establish regions after relevant image/placement/routing changes. Confirm that an internal source actually samples suitable phases before treating its histogram as code-density calibration.

## 3. MMCM random-delay coarse ambiguity

The recorded scpi-tests/tdc_mmcm_random_delay_test.py run used 40 random targets with five repeats each.

Many targets returned identical fine indices across repeats. In part of the commanded phase range, below roughly 120 of the 448 nominal steps per period in that run, the coarse result differed by one 8000 ps clock cycle.

A representative phase-117 target returned:

| Repeats | Coarse cycles | Fine index |
|---|---:|---|
| 3 of 5 | 7 | Approximately 221..222 |
| 2 of 5 | 6 | Approximately 221..222 |

The fine result did not distinguish the two coarse outcomes. A proposed correction based on a high fine index was rejected; those indices were within the ordinary populated range, and the captured pair alone did not justify adding or subtracting a coarse cycle.

The fire request crosses from the ADC-clock domain into the phase-swept MMCM output domain. The observation is consistent with a phase-dependent crossing/latency ambiguity. The current source adds toggle_settled as a third settling stage; **its effect on the observed hardware problem has not been re-measured**.

Further characterization should use dense, repeated targets around the affected phase boundary, including wrap-around and warm-up checks. Inspect raw coarse/fine distributions and the clock-domain protocol before assigning a cause or claiming a fix. Record any residual risky internal-self-test phase range explicitly.

Nominal MMCM settings are 125 MHz reference, 1000 MHz VCO and 448 phase steps per ADC period, approximately 17.86 ps each. Those settings are a commanded internal stimulus scale, not an independent absolute-delay calibration standard.

## 4. Timing and measurement invariants

- A carry-tap snapshot is registered before the controller observes it. Preserve the current observation-cycle compensation when changing the controller.
- Re-arming waits for the return/source and sampled taps to return low; test stuck-high, missing-return and queued-trigger cases.
- The iterative 512-tap encoder limits accepted-event throughput. Sampling at 125 MHz does not make this a 125-million-events/s instrument.
- The chain's useful time coverage, bin widths, clock-boundary behavior and temperature dependence require measurement.
- Calibration belongs to the actual board and bitstream, including its placement/routing. Verify an external known-delay reference before claiming absolute accuracy.
- External analog-to-time conversion is an additional PCB transfer-function problem. The FPGA currently reports timing; inverse conversion to an analog value remains a separate calibration/application task.

For current pin allocation, constraints, the unresolved placement-helper ordering correction, pulse-only scope and the latest logic-test results, use the master handover.
