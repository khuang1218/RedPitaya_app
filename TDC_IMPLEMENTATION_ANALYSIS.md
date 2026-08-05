# LVDS CARRY4 TDC implementation for LED7_mod + BNET

## Current outcome and validation boundary

The TDC has been integrated into the active `red_pitaya_top_LED7_mod.sv` design
so that it and BNET live in the same Z20_G2 bitstream. The implementation now
contains the LVDS path, coarse/fine measurement logic, CARRY4 chain, encoder,
result FIFO, double-buffered calibration LUT, histogram, register block, C API,
SCPI commands, a calibration utility, unit-level logic testbench, timing
exception, placement-generation Tcl helper, an asynchronous internal stimulus
derived from PS `fclk[0]`, and now a dedicated MMCM phase-sweep self-test
source (`tdc_mmcm_stimulus.sv`), all for tests that do not use the E3
connector.

Vivado has deliberately not been run by Codex in this workspace. The user
reported that synthesis completed and the behavioural logic simulation passed
for a preceding revision, before both the internal `fclk[0]` stimulus and the
MMCM phase-sweep stimulus were added. That earlier successful
synthesis/simulation must not be treated as validation of the current source
tree. The current revision still requires a fresh behavioural simulation,
synthesis, primitive-preservation check, physical site selection,
implementation, timing analysis, DRC and bitstream generation. Hardware
performance also remains unproven. In particular, the carry-column coordinates
cannot be selected safely from source code alone, and the dedicated MMCM's
placement, CMT/clock-region legality and post-route timing have likewise not
been checked in Vivado.

## Handover snapshot: what is implemented now

The current source tree implements the following complete path:

```text
External mode: E3 DIO17 LVDS launch -> external delay/loopback
               -> E3 DIO18 LVDS return -> CARRY4 TDC

Internal mode: PS fclk[0] divider -> asynchronous internal event
               -> CARRY4 TDC

CARRY4 taps -> FDRE sampling -> bubble-correcting encoder
            -> coarse/fine calculation -> histogram/calibration LUT
            -> result FIFO -> slot-7 registers -> C API -> SCPI
```

Implemented integration points are:

- BNET remains at physical address `0x40700000`.
- TDC occupies `0x40710000` inside the same existing one-MiB slot-7 UIO map.
- The top-level slot-7 decoder selects BNET or TDC and terminates invalid local
  offsets with a bus error.
- E3 vector index 0 belongs to the TDC; the existing auxiliary E3 serializer
  remains on indices 3:1.
- Register interface v2 identifies itself as `0x54444302`.
- Control bit 10 selects the asynchronous internal source and status bit 18
  reports that selection.
- `TDC:TEST:INTernal ON|OFF` and `TDC:TEST:INTernal?` expose that selection over
  SCPI; matching C API calls are present.
- The calibration script supports `--internal` and `--collect-only`, allowing
  histogram/DNL/INL inspection without activating an untrusted LUT.
- A dedicated `MMCME2_ADV` (`tdc_mmcm_stimulus.sv`), belonging only to the TDC
  self-test and never the shared `red_pitaya_pll`, regenerates the TDC
  sampling-clock frequency at a software-commanded, dynamically stepped phase
  and releases exactly one measurement edge per fire request into the same
  carry-chain node. Register interface v3 identifies itself as `0x54444303`.
  Control bit 11 selects this source (taking priority over bit 10) and status
  bits 19-21 report sweep-enable, MMCM lock and phase-step-busy.
  `TDC:MMCM:*` SCPI commands and matching `rp_TdcMmcm*` C API calls issue one
  phase step at a time, read lock/busy/timeout status, and read/clear the
  accumulated signed phase-step count.

The current internal source is useful for exercising real placed TDC hardware
and, if its phase walks relative to `adc_clk`, for code-density collection. It
does not create a commanded or known delay. The next planned development phase
is therefore a separate MMCM-based phase-sweep source, described below.

## Repository map actually used

FPGA repository:

```text
C:\Users\kairan\vscodeprj\fpgaprj\RedPitaya-FPGA
```

Application/API repository:

```text
C:\Users\kairan\vscodeprj\RedPitaya_app
```

The active source file is:

```text
prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv
```

Its source filename is custom, but the module it defines is still
`red_pitaya_top`. Other files in the RTL directory define the same module name,
so an existing Vivado project must keep only the intended LED7_mod source
enabled for this top-level definition.

The project uses `sys_bus_interconnect` with eight one-MiB regions (`SW=20`).
The interconnect passes the full address to each slave. Slot 7 was already used
by BNET. The existing device tree exposes the complete physical region
`0x40700000..0x407fffff` as the `test` UIO map.

## E3 allocation and coexistence decision

The selected Z20_G2 E3 pairs come directly from
`prj/v0.94/sdc/red_pitaya_G2.xdc`:

| Function | Ports | E3 | Package pins |
|---|---|---|---|
| Isolated launch | `exp_e3p_o[0]`, `exp_e3n_o[0]` | DIO17 | T5/U5 |
| Delayed return | `exp_e3p_i[0]`, `exp_e3n_i[0]` | DIO18 | V11/V10 |

These are Bank 13 `LVDS_25` pairs. They were not unused at the primitive level:
the existing auxiliary E3 daisy block occupied all four vector indices. It has
therefore been narrowed from one clock plus three data lanes to one clock plus
two data lanes on indices 3:1, freeing index 0 for the TDC. The current modified
top did not connect the auxiliary serializer payload ports, but any external
dependency on its third data lane must still be ruled out.

The return `IBUFDS` uses `DIFF_TERM="FALSE"` in the initial build. Do not change
this to internal termination until the PCB schematic confirms that there is not
already a 100-ohm receiver termination.

## Shared address map

No BNET address changes were made.

| Physical address | UIO-relative address | Owner |
|---|---|---|
| `0x40700000` | `0x00700000` | BNET |
| `0x40710000` | mapped slot 7 plus `0x10000` | TDC |

The LED7_mod top now contains a local slot-7 decoder:

```text
address[19:16] == 0 -> BNET
address[19:16] == 1 -> TDC
anything else       -> acknowledged bus error
```

This prevents an invalid slot-7 access from hanging the PS bus. The TDC API maps
the slot-7 UIO region once and then advances its register pointer by `0x10000`.
It checks the `0x54444302` signature family lazily so loading a bitstream without the
TDC does not make ordinary API initialization fail.

## FPGA changes

New RTL under `prj/v0.94/rtl/`:

- `tdc_lvds_io.sv`: dedicated `OBUFDS`/`IBUFDS`, LVDS_25, selectable internal
  return termination.
- `tdc_carry_chain.sv`: 128 explicit CARRY4 cells, 512 explicit FDRE tap
  samplers, preserved hierarchy, and an inversion parameter.
- `tdc_thermometer_encoder.sv`: iterative three-tap-majority bubble correction,
  leading-one encoding, and invalid-pattern flags.
- `tdc_result_fifo.sv`: 256-entry, 128-bit inferred-memory FIFO with coherent
  pop-to-snapshot semantics.
- `tdc_internal_stimulus.sv`: gated divided-PS-clock source for exercising the
  real carry chain without an E3 connection.
- `tdc_mmcm_stimulus.sv`: dedicated `MMCME2_ADV` (1000 MHz VCO from the 125 MHz
  `clk_i` reference, `CLKOUT0_DIVIDE_F=8` regenerating 125 MHz with
  `CLKOUT0_USE_FINE_PS="TRUE"`, nominal dynamic phase-shift step
  `1/(56*1000 MHz) ~= 17.86 ps`), its own PSCLK/PSEN/PSINCDEC/PSDONE
  controller with a watchdog timeout, a signed accumulated phase-step counter,
  an optional whole-`clk_i`-cycle coarse delay, and a toggle-based CDC that
  hands exactly one commanded edge from the phase-shifted `CLKOUT0` domain to
  the existing asynchronous carry-chain measurement node.
- `tdc_calibration_mem.sv`: two 512x16 LUT banks and a 512x32 histogram.
  Software can write only the inactive LUT. A bank swap is ignored until every
  inactive entry has been written since invalidation.
- `tdc_registers.sv`: system-bus slave and the documented register map.
- `tdc_top.sv`: launch/timeout controller, coarse/fine arithmetic, calibration
  control, FIFO packing, return-low re-arm, source selection and a pending-
  trigger latch so a software trigger is not lost while the internal source is
  high.

Other FPGA changes:

- `red_pitaya_top_LED7_mod.sv`: E3 allocation, TDC instance, and shared BNET/TDC
  slot decoder.
- `prj/v0.94/sdc/tdc_Z20_G2.xdc`: narrow asynchronous input-to-tap-D false paths
  for the E3 return and internal test source; no guessed physical LOCs.
- `prj/v0.94/scripts/tdc_placement.tcl`: primitive discovery, temporary
  placement, reporting, and generation of the final placement XDC.
- `prj/v0.94/doc/tdc_registers.md`: electrical contract, address/register map,
  bit fields, FIFO packing, and timing convention.
- `tbn/tb_tdc_logic.sv`: ideal, bubble, malformed, saturated thermometer tests,
  FIFO ordering/overflow/underflow tests, and a reduced-divider check of the
  internal stimulus enable/toggle/disable behaviour.
- Both Z20_G2 Vivado Tcl entry points add `tdc_Z20_G2.xdc`.

### Timing convention

The physical FDRE bank samples the return propagation at edge S. The controller
can observe that registered vector only at edge S+1, so it removes that one
observation cycle when recording the coarse count:

```text
coarse_cycles = controller_counter - launch_counter - 1
total_ps      = coarse_cycles * clock_period_ps - fine_propagation_ps
```

This convention is derived from synchronous simulation semantics. It must be
confirmed with known delays immediately before and after a 125 MHz clock edge.

The normal path emits a FIFO result. Calibration mode accepts asynchronous
return events and updates the histogram, but intentionally does not enqueue
millions of calibration records into the 256-entry measurement FIFO.

## Software changes

The public API in `rp-api/api/include/rp.h` now provides TDC modes, result and
status flags, core control/result calls, calibration access, and the userspace
code-density LUT calculation helper.

`rp-api/api/src/tdc.cpp` implements lazy signature-checked mapping, range
validation, process-local FIFO serialization, CDC-settled indexed reads, fixed
record unpacking, inactive-bank upload/readback, and guarded activation. It also
locally detects `MAP_FAILED` because the existing common mapper checks the wrong
pointer in its failure test.

The SCPI server registers the requested `TDC:*` command family and delegates to
the C API. Result query order is:

```text
sequence,status,coarse_cycles,fine_raw,fine_ps,total_ps,analogue_code
```

All time fields ending in `_ps` are integer picoseconds. `analogue_code` is zero
in this version: the separate external PCB delay-to-analogue conversion belongs
in userspace until its transfer function has been measured.

`scpi-tests/tdc_calibrate.py` collects a ranged histogram, computes bin-center
LUT values and DNL/INL metrics, uploads and verifies all entries, activates the
new bank, optionally performs a fixed-delay precision test, and stores JSON tied
to a caller-supplied bitstream identifier.

## Internal hardware self-test without E3 wiring

Control bit 10 selects a divided `fclk[0]` square wave instead of the E3 return
at the carry-chain input. At a 125 MHz PS fabric clock, divider bit 10 gives a
61.0 kHz rising-event rate and 8.192 us high/low intervals. This is slow enough
for the 512-cycle encoder. The counter is held at zero while disabled, and
internal mode suppresses external launch pulses. `fclk[0]` is generated by the
Zynq processing system and enters the programmable logic as an internal clock;
it is not a signal driven on an E3 pin. The enable is synchronized into its
clock domain, while the resulting event is deliberately asynchronous to
`adc_clk`. A software trigger is retained as pending until the selected source
is idle and the next rising event can be captured. A soft TDC reset preserves
the internal-source selection so `TEST:INTERNAL ON` followed by `CAL:START`
continues using the intended source.

The intended commands are:

```text
TDC:TEST:INTernal ON
TDC:TEST:INTernal?
```

For one physical-chain capture, enable internal test, select SINGLE, enable the
core and use `TDC:MEASure?`. The total time contains the arbitrary wait until the
next internal edge; status and the fine/raw capture are the meaningful fields.

For a no-connection code-density run:

```text
python scpi-tests/tdc_calibrate.py rp-xxxxxx.local --internal \
  --collect-only --events 100000 --bitstream-id <placed-bitstream-id>
```

The PS fabric clock and ADC clock use different clock paths and are expected to
walk through phase. This must be demonstrated rather than assumed: accept the
source for calibration only when many fine bins are populated. A concentrated
histogram indicates coherent clocks or inadequate phase coverage.

This mode tests the implemented carry cells, sampling FDREs, encoder, histogram,
register/API and SCPI path. It bypasses `IBUFDS` and therefore cannot validate
E3 electrical levels, polarity, termination, PCB delay or analogue conversion.

## Dedicated MMCM phase-sweep self-test (implemented, unvalidated in Vivado)

This section previously described a design proposal; that proposal is now
implemented in RTL, registers, API and SCPI, but **has not been through
Vivado** (behavioural simulation, synthesis, placement, implementation, or
hardware) in this workspace. In this context, "internal simulation" means a
hardware self-test source operating inside the programmed FPGA; it is
distinct from Vivado behavioural simulation.

### Objective

A second internal stimulus mode moves a test edge through a known,
software-commanded sequence of phase positions relative to the TDC sampling
clock, to test monotonicity, transition boundaries, missing bins,
repeatability and approximate linearity without the external PCB. It does not
replace an external calibrated delay generator for absolute accuracy and does
not test the E3 electrical path.

BNET, the TDC and the new clock block remain together in one bitstream:

```text
Existing Red Pitaya PLL/clocking -> ADC/system clocks -> BNET and TDC logic

adc_clk (clk_i) -> dedicated MMCME2_ADV -> phase-shifted CLKOUT0 (BUFG)
                                        -> toggle-CDC one-edge generator
                                        -> existing TDC carry-chain input
```

"Dedicated" means the new MMCM instance (`tdc_mmcm_stimulus.sv`) belongs only
to the TDC self-test. It does not mean another FPGA project or bitstream. The
existing `red_pitaya_pll` is a separate `PLLE2_ADV` that supplies ADC, DAC,
serial and PWM clocks; its phase is untouched by this change.

### How the fine delay is produced

A 7-series MMCM's dynamic phase-shift interface moves its generated clock in
nominal increments of one fifty-sixth of the MMCM VCO period:

```text
fine_step_time = 1 / (56 * VCO_frequency)
requested_delay = coarse_cycles * ADC_period + phase_steps * fine_step_time
```

The implemented configuration uses `CLKFBOUT_MULT_F=8`, `DIVCLK_DIVIDE=1`
(1000 MHz VCO from the 125 MHz `clk_i` reference) and `CLKOUT0_DIVIDE_F=8`
(regenerating 125 MHz) with `CLKOUT0_USE_FINE_PS="TRUE"`, giving a nominal
fine step of `1/(56*1000 MHz) ~= 17.86 ps`. This has not been confirmed
legal for the Zynq-7020 speed grade/CMT site by Vivado.

The MMCM control state machine uses:

- `PSCLK` tied to `clk_i` as the phase-shift control-interface clock;
- `PSEN` for a one-step phase-change request;
- `PSINCDEC` to select increment or decrement;
- `PSDONE` to acknowledge completion of each step, with a 256-`clk_i`-cycle
  watchdog that aborts and sets a sticky timeout flag if it never arrives;
- `LOCKED`, double-flopped into `clk_i`, gates whether a phase step or fire
  request is accepted.

The stimulus releases exactly one rising edge into the carry-chain input per
fire request, after an optional whole-`clk_i`-cycle coarse delay
(`MMCM_COARSE_DELAY`); it does not feed a continuous high-rate clock into the
iterative encoder. The fire request itself is a `clk_i`-domain toggle handed
into the `CLKOUT0` domain through a conventional two-flop synchronizer; the
resulting +/-1 `CLKOUT0`-cycle latency uncertainty does not affect the
within-one-period position the TDC measures, and is absorbed by the coarse
counter exactly like the other sources.

### Source modes and control model

All three measurement sources coexist, each answering a different question:

| Source | Purpose | Timing knowledge |
|---|---|---|
| External E3 return | Final PCB/electrical and end-to-end test | Determined by external equipment/path |
| Asynchronous divided `fclk[0]` | Simple activity test and possible code density | Phase intentionally unknown |
| MMCM phase sweep | Deterministic internal boundary/monotonicity sweep | Commanded nominal coarse/fine phase |

`CONTROL` bit 11 (`MMCM_SWEEP_ENABLE`) selects the MMCM source and takes
priority over bit 10 (`INTERNAL_TEST`) if both are set; `SOFT_RESET`
preserves both bits, matching the existing internal-source behaviour.
Register interface v3 (`ID_VERSION = 0x54444303`) adds:

- `MMCM_CONTROL` (`0x80`): `PS_REQUEST` (pulse), `PS_INCDEC` (persistent),
  `PHASE_COUNT_CLEAR` (pulse), `MMCM_RESET` (pulse), `TIMEOUT_CLEAR` (pulse);
- `MMCM_STATUS` (`0x84`): `LOCKED`, `PS_BUSY`, `PS_TIMEOUT`;
- `MMCM_COARSE_DELAY` (`0x88`, R/W): whole-`clk_i`-cycle delay before firing;
- `MMCM_PHASE_COUNT` (`0x8c`, R): signed accumulated step count.

The FPGA does not automate a sweep; software issues one `PS_REQUEST` at a
time (matching `rp_TdcMmcmPhaseStep()` / `TDC:MMCM:STEP`), polls
`MMCM_STATUS`, then triggers a single-shot measurement. Automatic
start/stop/step-size sweep control and per-phase repetition counting, listed
as optional in the original proposal, remain host-side (Python) work, not
implemented in the FPGA.

### Implementation sequence status

1. **Not done in this workspace**: Report Utilization / Report Clock
   Utilization to confirm a legal spare MMCM, BUFG and clock routing after
   BNET and the existing TDC. This must be run in Vivado before trusting the
   design closes.
2. **Not done**: confirming `clk_i` (adc_clk) is a legal MMCM CLKIN source
   from the implemented clock topology and that the auto-placed MMCM/CMT site
   is legal and does not disturb the existing CARRY4/FDRE column choice.
3. **Done**: `tdc_mmcm_stimulus.sv` — `MMCME2_ADV`, feedback `BUFG`, output
   `BUFG`, reset/lock handling, dynamic phase controller, coarse-delay counter
   and toggle-CDC one-edge generator.
4. **Done**: `tdc_top.sv` three-way `measurement_event` mux
   (`mmcm_sweep_enable ? mmcm_event : internal_test_enable ? internal_test_event : return_event`).
   Source switching is gated the same way single/continuous arming always was
   (`enable && !return_sync && !(|sampled_taps)`), so a source change while a
   measurement is in flight cannot appear as a spurious hit; it has not been
   separately re-verified for a switch occurring mid-flight from a different
   source than the one just disabled.
5. **Done**: registers, C API (`rp_TdcMmcm*`), SCPI (`TDC:MMCM:*`). The
   calibration/test Python utility has **not** been extended for MMCM sweeps.
6. **Done, not yet run**: `tb_tdc_logic.sv` now instantiates the real
   `tdc_mmcm_stimulus` (and therefore the Xilinx UNISIM `MMCME2_ADV`
   behavioural model) and checks one PSEN/PSDONE step in each direction,
   phase-count bookkeeping, phase-count clear, and exactly one edge per fire
   request. This requires Vivado's UNISIM simulation library and has not
   actually been simulated; the watchdog timeout path is not exercised by
   this test. It cannot and does not establish physical picosecond accuracy.
7. **Done, not yet checked in Vivado**: `tdc_Z20_G2.xdc` adds a false path
   from the stimulus's `event_reg` output to the tap-D pins (mirroring the
   existing internal-stimulus exception) and an explicit
   `set_clock_groups -asynchronous` between `adc_clk` and the MMCM's
   `CLKOUT0`, generated via `create_generated_clock` if Vivado has not already
   inferred it. The hierarchical cell-name patterns used to find `CLKOUT0` and
   `event_reg` are best-effort and must be confirmed against the actual
   synthesized netlist; do not assume they resolve correctly before checking.
8. **Not done**: re-run synthesis, implementation, DRC, clock-interaction and
   timing reports; confirm the additional clock resources do not disturb the
   selected CARRY4/FDRE placement or BNET timing.
9. **Not done**: on hardware, sweep at least one complete ADC period, repeat
   each phase many times, and plot raw code versus commanded phase. Repeat
   across the wrap boundary and after warm-up. Compare with an external
   known-delay test.

### MMCM self-test acceptance criteria

This mode must not be called successful merely because the MMCM locks. At
minimum, still to be demonstrated on hardware:

- every requested phase operation receives `PSDONE` within a defined timeout;
- exactly one TDC event is accepted for each one-shot request;
- increasing phase produces a predominantly monotonic progression through raw
  TDC codes, allowing for measured jitter near bin boundaries;
- repeated samples at one phase form a narrow, stable distribution;
- the coarse result changes correctly at the sampling-clock boundary;
- a complete sweep neither deadlocks nor overflows the FIFO at the configured
  acquisition rate;
- BNET regression tests still pass in the same bitstream;
- post-route timing and DRC contain no new unresolved failures;
- external E3 mode remains unchanged and selectable after the internal test.

The phase-step value is nominal and the clock network adds fixed skew and
jitter. Consequently this mode can characterize response against an internally
commanded phase, but it cannot independently certify absolute picoseconds. The
final calibration must remain tied to the exact placed bitstream and should be
cross-checked with external calibrated hardware.

## Exact actions in the existing Vivado project

Do not start with implementation. First make the project source set
unambiguous. Because the latest internal-source changes postdate the previously
reported synthesis, treat the existing synthesis and implementation runs as
out of date after refreshing the files.

Before the fresh synthesis, add `tbn/tb_tdc_logic.sv` with **Add Sources -> Add
or Create Simulation Sources** and set `tb_tdc_logic` as the simulation top.
Keep `tdc_internal_stimulus.sv`, `tdc_thermometer_encoder.sv` and
`tdc_result_fifo.sv` as design sources; the testbench references them but must
not contain duplicate copies. Run behavioural simulation and require the final
`tb_tdc_logic: PASS`. The added internal-source checks use an intentionally
small divider and verify disabled-low, enabled toggling and disabled-low again.
This is a controller/logic check, not a model of CARRY4 propagation delay.

### 1. Copy/refresh the files

Copy these nine changed/new design files into the locations from which your
open Vivado project reads sources:

```text
red_pitaya_top_LED7_mod.sv
tdc_top.sv
tdc_lvds_io.sv
tdc_carry_chain.sv
tdc_thermometer_encoder.sv
tdc_calibration_mem.sv
tdc_result_fifo.sv
tdc_registers.sv
tdc_internal_stimulus.sv
```

Also copy/add:

```text
prj/v0.94/sdc/tdc_Z20_G2.xdc
prj/v0.94/scripts/tdc_placement.tcl
```

If the project source paths already point at these workspace files, use
**Tools -> Refresh Changed Modules** or **Sources -> Refresh Hierarchy** rather
than creating duplicate copies.

### 2. Add sources and choose the intended top definition

1. In **Project Manager -> Add Sources**, choose **Add or Create Design
   Sources** and add all eight `tdc_*.sv` files.
2. Ensure Vivado identifies them as **SystemVerilog**.
3. Add/refesh `red_pitaya_top_LED7_mod.sv`.
4. In **Sources -> Hierarchy**, right-click the module from the LED7_mod file and
   choose **Set as Top** if required. The top module name shown will still be
   `red_pitaya_top`.
5. In **Sources -> Compile Order**, disable or remove from this fileset every
   other source file that defines module `red_pitaya_top` (notably the stock
   `red_pitaya_top.sv` and other top variants). Do not delete those repository
   files; they simply must not compete with LED7_mod in this build.
6. Confirm the project/RTL define `Z20_G2` is present exactly as in the currently
   working project.

### 3. Add the non-placement constraint

1. Use **Add Sources -> Add or Create Constraints**.
2. Add `prj/v0.94/sdc/tdc_Z20_G2.xdc` to `constrs_1`.
3. Leave it enabled for synthesis and implementation.
4. Confirm the normal `red_pitaya_G2.xdc` remains enabled.

### 4. Elaborate before synthesis

Run **RTL Analysis -> Open Elaborated Design** and check:

- `i_tdc` exists beneath `red_pitaya_top`;
- `i_bnet_regs` also exists;
- the slot-7 bus has one muxed driver for rdata/ack/err;
- E3 index 0 connects only to `i_tdc/i_lvds`;
- E3 indices 3:1 connect to `i_serlines_add`;
- there are no width or multiple-driver messages.

In the Tcl console, confirm the pin constraints:

```tcl
foreach p {exp_e3p_o[0] exp_e3n_o[0] exp_e3p_i[0] exp_e3n_i[0]} {
  puts "$p pin=[get_property PACKAGE_PIN [get_ports $p]] iostd=[get_property IOSTANDARD [get_ports $p]]"
}
report_io -file tdc_pre_synth_io.rpt
```

Expected pin order is T5, U5, V11, V10 and every port must report `LVDS_25`.
Stop if it differs; do not edit package pins to force a match.

### 5. Synthesize and prove primitive preservation

Run **Synthesis -> Run Synthesis**, then **Open Synthesized Design**. Execute:

```tcl
set tdc_carry [get_cells -hierarchical -filter {REF_NAME == CARRY4 && NAME =~ *i_tdc/i_carry/*}]
set tdc_ff [get_cells -hierarchical -filter {REF_NAME == FDRE && NAME =~ *i_tdc/i_carry/gen_tap*/i_tap_ff}]
puts "TDC CARRY4=[llength $tdc_carry] tap_FDRE=[llength $tdc_ff]"
report_utilization -hierarchical -hierarchical_depth 5 -file tdc_post_synth_util.rpt
```

The required initial counts are exactly 128 CARRY4 and 512 tap FDRE cells. Stop
if either count differs or if synthesis reports that the chain was optimized,
replicated, or absorbed.

### 6. Choose a real carry column and generate its XDC

This is the one required action that cannot be pre-filled in the repository.

1. In the synthesized design open **Window -> Device**.
2. Highlight the TDC return I/O and carry cells. The following is useful:

   ```tcl
   source C:/Users/kairan/vscodeprj/fpgaprj/RedPitaya-FPGA/prj/v0.94/scripts/tdc_placement.tcl
   highlight_objects [tdc_get_carries]
   ```

3. Find a carry-capable slice X column with 128 consecutive legal Y sites,
   reasonably close to the Bank 13 return input and not already congested by
   BNET, BRAM, DSP or clocking logic. A 128-slice line will cross clock-region
   boundaries on this part; inspect those boundaries deliberately.
4. Test the candidate in the open synthesized design. Replace `<x>` and `<y0>`:

   ```tcl
   tdc_place_chain <x> <y0>
   tdc_report_placement
   ```

5. If every cell is contiguous and legal, create a persistent constraint file:

   ```tcl
   tdc_write_placement_xdc C:/Users/kairan/vscodeprj/fpgaprj/RedPitaya-FPGA/prj/v0.94/sdc/tdc_placement_selected.xdc <x> <y0>
   ```

6. Add `tdc_placement_selected.xdc` to `constrs_1`. In its file properties set
   **Used In Synthesis = false** and **Used In Implementation = true**.
7. Reset the implementation run if one already exists. Do not rely on the
   temporary in-memory `tdc_place_chain` properties alone; the generated XDC is
   what makes placement repeatable in later runs.

Keep this selected-placement XDC with the exact bitstream and its calibration.
A LUT from a differently placed/routed build is invalid.

### 7. Implement and inspect

Run **Implementation -> Run Implementation**, open the implemented design, and
execute:

```tcl
source C:/Users/kairan/vscodeprj/fpgaprj/RedPitaya-FPGA/prj/v0.94/scripts/tdc_placement.tcl
tdc_report_placement
report_exceptions -summary -file tdc_exceptions.rpt
report_timing_summary -file tdc_post_route_timing_summary.rpt
report_utilization -hierarchical -file tdc_post_route_util.rpt
report_drc -file tdc_post_route_drc.rpt
report_io -file tdc_post_route_io.rpt
```

Visually verify all of the following in Device view:

- 128 CARRY4s occupy one X column in exact consecutive Y order;
- each stage's four tap FDREs share that stage's slice at AFF/BFF/CFF/DFF;
- there is no unexpected physical jump at a clock-region boundary;
- no other cells were pulled into or displaced from the chain unexpectedly;
- only the asynchronous E3-input-to-tap-D measurement path is false-pathed;
- ordinary controller, encoder, FIFO, LUT, register and CDC-facing paths meet
  timing;
- DRC has no new critical warnings.

If placement or routing is poor, choose another column and regenerate the
placement XDC. Do not accept a build merely because Vivado can generate a
bitstream.

### 8. Generate the bitstream

Only after the preceding checks, run **Generate Bitstream**. Record together:

- Git commit/working-tree identifier;
- Vivado version;
- selected `SLICE_X/Y` range;
- post-route timing, DRC, utilization and I/O reports;
- `.bit`/`.bin` checksum;
- board serial and later calibration JSON.

For a repository-driven build, the existing commands remain:

```text
make project PRJ=v0.94 MODEL=Z20_G2
make PRJ=v0.94 MODEL=Z20_G2
```

The normal non-project outputs are `prj/v0.94/out/red_pitaya.bit` and
`red_pitaya.bin`, but the custom active-top source selection must first be made
unambiguous as described above.

## API/SCPI build and deployment

Build in the project's established Red Pitaya Linux/chroot environment, not in
Vivado:

```text
make api
make scpi
```

Before deployment, back up the existing FPGA image, `librp.so`, and SCPI server.
Stop services that access the FPGA, copy replacements under temporary names,
atomically rename them, and restart the service. Use the board image's current
overlay/fpgautil path; do not use legacy `/dev/xdevcfg` on a modern image.

Initial API checks should be:

1. Existing BNET commands still read the unchanged address range.
2. `TDC:TAPs?` returns 512, proving signature and register mapping.
3. With TDC disabled, launch output is low.
4. After `TDC:ENABle ON` and `TDC:TRIGger`, a missing return produces a timeout
   result rather than permanent BUSY.
5. `TDC:FIFO:DATA?` preserves order and returns seven numeric fields.

## Hardware bring-up and calibration order

1. With power off, continuity-check DIO17 launch, DIO18 return and common ground.
2. Confirm a standards-compatible LVDS receiver/transmitter and exactly one
   return termination. Never connect the analogue voltage directly to E3.
3. Begin with a fixed external LVDS loopback/delay. Use a 2-3 clock launch pulse
   and a return high time of at least 16-24 ns.
4. On an oscilloscope verify P/N polarity, common mode, differential amplitude,
   pulse width, ringing and one clean rising transition.
5. Test single shot, timeout, stuck-high re-arm and coarse timing before trusting
   fine results.
6. Sweep phase/delay and inspect `TDC:MEASure:RAW?`. The transition must move
   through the chain, invalid flags must remain visible, and the physical chain
   must cover more than one 8 ns clock period over temperature and voltage.
7. Use an external asynchronous source or deliberate phase sweep for code
   density. A synchronous fixed loopback is not a calibration source.
8. Run, for example:

   ```text
   python scpi-tests/tdc_calibrate.py rp-xxxxxx.local --bitstream-id <git-hash-or-bitstream-sha256> --board-serial <serial>
   ```

9. Inspect dead bins, DNL/INL and invalid fraction before accepting the LUT.
10. Use known delays just before/after clock boundaries, then run a fixed-delay
    precision test. Repeat after warm-up and at relevant temperatures.
11. Build the separate delay-to-analogue inverse calibration in userspace only
    after the TDC timing calibration is stable and the PCB response is proven
    monotonic.

## Remaining risks and deliberate limitations

- The E3 auxiliary serializer loses its third data lane; external use must be
  checked.
- Return termination and polarity require the external PCB schematic and scope.
- The 128-CARRY4 chain length is an initial experiment, not a guaranteed 8 ns
  coverage specification.
- Physical carry bins and clock-boundary regions cannot be validated in RTL.
- Calibration LUT/histogram storage intentionally uses distributed RAM for its
  asynchronous indexed reads. Check LUT utilization and timing; a later
  synchronous BRAM pipeline is available if resource pressure requires it.
- The first encoder is iterative and needs roughly 512 clocks per valid event,
  so this is not a full-rate continuous 125 MHz TDC.
- Continuous forwarded-clock mode and FPGA analogue-code conversion are not
  implemented; both are explicit later phases.
- The dedicated MMCM phase-sweep source is implemented in RTL/registers/API/
  SCPI but has not been run through Vivado. Its CMT site legality, VCO/BUFG
  resource availability, generated-clock/async-group constraints and
  hierarchical XDC cell-name patterns are all unverified and must be checked
  against post-synthesis clock-utilization and netlist data before trusting
  it. Sweep automation (start/stop/step size, per-phase repeat counts) is not
  implemented in the FPGA; software issues one phase step at a time.
- The interrupt registers are present, but no PS interrupt line is connected in
  interface v1.
- Hardware acceptance criteria cannot be claimed until synthesis, contiguous
  placement, timing, DRC, loopback, code-density, boundary and temperature tests
  have been performed.

## Sources inspected

- `prj/v0.94/sdc/red_pitaya_G2.xdc`
- `rtl/sys_bus_interconnect.sv`
- `rtl/sys_bus_cdc.sv`
- `prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`
- `rtl/red_pitaya_pll.sv`
- `dts/uio-api.dtsi`
- `rp-api/api/src/common.cpp`
- existing BNET API, register and SCPI implementations
- Red Pitaya Z7020 Gen 2 E3 documentation
- AMD 7-series CARRY4 primitive documentation
