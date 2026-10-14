# Red Pitaya master handover

Updated: 2026-10-14. Target: STEMlab 125-14 Z7020 Gen 2 / Z20_G2, xc7z020clg400-1; existing Vivado project uses 2020.1.

This is the authoritative workspace handover for BNET, the LVDS CARRY4 TDC, and the single-channel GPIO pulse generator. It replaces the separate BNET and pulse handovers. Repository source, public headers, command tables and the TDC register specification remain the detailed interface references.

## 1. Current objective and working rules

The current objective is pulse generation and initial external TDC operation, while supplying an external PCB from the dedicated 3.3 V power pins. The merged top retains BNET, TDC and pulse logic.

- **Do not run Vivado on this device unless the user changes that instruction.** The recorded local HDL checks used Slang and Icarus.
- Preserve the existing TDC instance, E3 allocation, dedicated MMCM, BNET datapaths and shared bus decoder when transferring changes.
- Pulse-only testing may skip generating a new TDC placement XDC. Keep the TDC timing XDC and any existing placement constraints if TDC remains instantiated. Full implementation timing/DRC checks still apply.
- Before accepting TDC measurements from a new bitstream, revisit placement, routed behavior and calibration.
- The user built and loaded a merged image on 2026-10-14. It exposed BNET and TDC, but pulse reads returned zero. The subsequent pulse readback fix in this repository has not been rebuilt or deployed, and the pulse waveform has not been electrically measured.

## 2. Repositories and source baseline

Paths in the feature sections are relative to the named repository; clone locations can differ between PCs.

| Repository | Current workspace root | HEAD when this consolidation began |
|---|---|---|
| RedPitaya_app | C:/Users/kairan/vscodeprj/RedPitaya_app | 9413b4e35, merged tdc and pulse gen |
| RedPitaya-FPGA | C:/Users/kairan/vscodeprj/fpgaprj/RedPitaya-FPGA | 16e9b99, merged tdc and pulse gen |

A separate saved Vivado project exists under C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project. It can reference imported copies. Refresh the files that the project actually uses; editing a different checkout does not refresh those copies.

### Important FPGA sources

- prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv — active custom definition of red_pitaya_top; integration, clocks, GPIO and slot-7 mux.
- prj/v0.94/rtl/bnet_regs.sv, bnet_axi_reader_ch.sv — BNET registers/descriptors and DDR reader.
- prj/v0.94/rtl/butterfly_network.sv — serial engine and bnet_tdp_ram definition.
- prj/v0.94/rtl/butterfly_network_static_sdf.sv — currently selected static SDF engine.
- prj/v0.94/rtl/butterfly_network_static_pipeline.sv — alternate full-frame static engine.
- prj/v0.94/rtl/tdc_*.sv — TDC controller, LVDS I/O, carry chain, encoder, FIFO, calibration, registers, internal and MMCM stimulus.
- prj/v0.94/rtl/pulse_gen.sv — bus mailbox, pulse timing, ownership guard and ODDR.
- rtl/red_pitaya_pll.sv — existing PLL; ser_clk is nominally 250 MHz.
- rtl/classic/red_pitaya_asg_ch.sv — includes the declaration/enum corrections from the October review.
- prj/v0.94/sdc/ — board, TDC and pulse constraints.
- prj/v0.94/scripts/tdc_placement.tcl — placement helper; see its outstanding correction in section 9.
- prj/v0.94/doc/tdc_registers.md — detailed TDC register/electrical specification.
- red_pitaya_vivado_project_Z20_G2.tcl and red_pitaya_vivado_Z20_G2.tcl — project/non-project entry points and custom constraint inclusion.

### Important app sources

Each feature has API files in rp-api/api/src/ and SCPI handlers in scpi-server/src/: bnet.cpp/.h, tdc.cpp/.h and pulsegen.cpp/.h. Public declarations are in rp-api/api/include/rp.h; lifecycle integration is in rp-api/api/src/rp.cpp. The API CMake source list and scpi-server/src/scpi-commands.cpp must match the feature files. SCPI CMake glob-loads src/*.cpp.

## 3. Validation boundary and recorded results

These results include the original documentation consolidation and the later pulse bus investigation.

| Scope | Evidence | Limit |
|---|---|---|
| Pulse module/testbench, 2026-10-14 | Slang 12.0: 0 errors, 0 warnings | Logic/semantic check |
| Merged Z20_G2 top | Slang: 0 errors, 33 warnings; SCOPE_ONLY: 0 errors, 16 warnings | Default timescale 1ns/1ps; generated PS/IP and unprovided primitives treated as external modules |
| Pulse regression | Icarus 12.0 PASS with portable ODDR model, and separately with installed Xilinx UNISIM ODDR source plus glbl | No Vivado/XSim invocation; no physical edge-speed proof |
| Pulse bus readback fix, 2026-10-14 | Delayed-read regression failed before the RTL fix and passed with both Icarus ODDR variants afterward | The corrected RTL has not been copied into the saved Vivado project, built or loaded |
| Timing repair, 2026-10-14 | Revised pulse regression PASS with both ODDR models; BNET scheduler/snapshot test PASS; TDC full controller/register/FIFO integration PASS with ideal taps; selected top hierarchy Slang 0 errors, 2 existing SDF warnings; Tcl collection/placement tests PASS against mocked objects | No new synthesis/route; full PS/IP/vendor elaboration and hardware timing remain unverified |
| Existing TDC logic/MMCM regression | Icarus PASS with UNISIM MMCME2_ADV/BUFG source models | Encoder/FIFO/controller/self-test behavior; no physical carry-delay or absolute phase proof |
| Shared decoder | Extracted current decoder and pulse instance passed all 16 subregions, WEN/REN isolation, readback and error cases | BNET/TDC responses were registered probes, not full accelerator/measurement models |
| Pulse software | Earlier native Windows GCC 16.2 C++20 syntax checks against repository headers and scpi-parser 4e879901b51cbb43dab36dd83f95a23f1dbaa4c0; Python AST and --help passed | Windows shims were used; latest Linux/ARM build, linking and live MMIO/SCPI remain unverified |
| Historical BNET hardware | June 1024-point DDR run drained 2048 sample bytes and 20480 weight bytes; ERROR=0; RF shape correlations about 0.994–1.000 | Applies to that historical bitstream |
| Later BNET notebook records | Saved serial-2048, static-4096 and SDF/capture/bank test outputs exist | Mixed execution order and stale helper output versions; rerun from a clean kernel against an identified image |
| Historical TDC hardware | MMCM lock/phase sweep and 100k-event calibration were reported on a prior placed build | Predates some source fixes and the merged pulse image; see section 7 |

The normal-top warnings comprise 20 unconnected input ports, 11 unconnected output ports and two final-stage SDF shift-count warnings. The final-stage group-base result is zero as intended; the port warnings are in existing diagnostic, parallel/daisy, interconnect and ASG/scope code. Review the actual vendor elaboration.

Local reproduction tools/scripts/logs are in the app repo's ignored build/hdl-tools/ and build/hdl-review/ directories. These are machine-local and are not design/deployment sources:

~~~text
wsl -d Ubuntu-24.04 -- bash build/hdl-review/run_pulse_sim.sh
wsl -d Ubuntu-24.04 -- bash build/hdl-review/run_tdc_sim.sh
~~~

Regenerate the extracted decoder test with build/hdl-review/make_decoder_tb.py before running run_decoder_sim.sh after top edits. check_hdl.py and the saved Slang logs are in the same directory.

The user generated a merged bitstream in the separate saved Vivado project and loaded its bootgen-converted red_pitaya_top.bit.bin with fpgautil. Direct board reads returned BNET stream count 8 at 0x4070003c and TDC ID 0x54444303 at 0x40710000, but pulse ID/tick both zero at 0x40720000/0x40720018. The SCPI pulse command was recognized and reported 9516 Unsupported Feature. The routed timing summary of that image reports WNS -10.290 ns and 29,540 failing endpoints; it is not timing accepted. No Vivado was run on this device by this assistant, and no pulse/PCB waveform measurement is recorded.

## 4. Shared system bus and software mapping

Slot sys[7] covers physical 0x40700000..0x407fffff.

| Slot-local addr[19:16] | Physical base | Owner |
|---|---|---|
| 0 | 0x40700000 | BNET |
| 1 | 0x40710000 | TDC |
| 2 | 0x40720000 | Pulse generator |
| 3..15 | Other local regions | Registered acknowledged bus error |

Gate **both WEN and REN** independently for every slave and retain one rdata/ack/err mux. Preserve full addresses into BNET/TDC; pulse decodes the low 16 bits. Transactions must not leak into another block.

The existing UIO map already covers the entire slot; no new device-tree window is required. API offsets are relative to the UIO system map:

- BNET maps 0x00700000, size 0x1000.
- TDC maps slot offset 0x00700000, size 0x11000, then advances its register pointer by 0x10000.
- Pulse maps slot offset 0x00700000, size 0x21000, then advances by 0x20000.

**Do not map 0x00710000 or 0x00720000 directly with cmn_Map and assume it selects the subregion.** The helper rounds the offset to a one-MiB UIO map index. Pulse mapping is lazy; rp_Release unmaps it. Unsupported MMIO on an older image can cause a bus error, so software signature checking does not replace matching the image first.

## 5. PCB wiring and automatic power

Use the **E1 connector**:

| Function | Physical E1 pin | Detail |
|---|---|---|
| PCB +3.3 V feed 1 | 1 | Dedicated supply rail |
| PCB +3.3 V feed 2 | 2 | Same supply rail/budget |
| Common ground | 25 and/or 26 | PCB ground and pulse reference |
| Pulse output | 5 | DIO1_P = exp_p_io[1] = FPGA H16, LVCMOS33 |

The user confirmed that the two DC connections supply **PCB power**. Pins 1/2 are automatically powered once the board's 3.3 V rail starts; no GPIO configuration or SCPI command enables them. PULSE:OUTPUT controls pin 5 independently and leaves PCB power on.

The user's current estimates are approximately 7 mA and 70 mA; if simultaneous separate loads, about 77 mA total. The published E1 +3V3 budget is **0.5 A total across both pins**. Exact steady-state/startup interpretation and actual supply margin have not been measured.

Identify E1 pin 1 from the board marking/pinout. The pulse receiver's thresholds, input capacitance, required minimum pulse width, interconnect and independent-power behavior remain to be confirmed. Use a common ground and a suitable high-impedance probe/load. A 50-ohm DC load at 3.3 V would draw 66 mA and is unsuitable for this GPIO.

Official pinout and supply specification:
https://redpitaya.readthedocs.io/en/latest/developerGuide/hardware/GEN2/125-14_Gen2_Z7020_Pro/top.html#e1-connector-digital-i-o-can

## 6. BNET architecture and operation

### Engine selection and data movement

- Serial engine: fixed 2048-point, 11-stage network; variable weights per run, or CONFIG[4] static weight reuse.
- Static path: CONFIG[5] with DDR input selects the static engine. **BNET_ENABLE_SDF is currently defined inside the custom top**, so the selected implementation is the experimental SDF engine. Omitting a project define does not disable this in-file definition.
- Commenting out that in-file definition selects the alternate fixed 4096-point full-frame pipeline. That fallback does not acquire the SDF runtime vector/bank interface merely because the registers exist.
- SDF runtime lengths are 1024, 2048 and 4096, with 4, 2 and 1 resident weight banks respectively.
- Stream 0 supplies samples through axi2_sys; stream 1 supplies weights through axi3_sys. Eight descriptors exist, but only streams 0/1 have physical readers.
- Ordinary ASG BRAM/table generation remains available. ASG deep-memory AXI is stubbed/reassigned to BNET.
- DDR cold static runs preload weights, then launch the sample reader using bnet_pipe_sample_start_pending. Warm runs retain weights and launch samples immediately.
- Keep one-clock reader starts, the stateful cold-start handoff, soft-reset propagation, AXI burst-inflight/busy-seen guards, FIFO reset-busy handling and the AXI skid buffer.

The current asg_dat_fifo XCI has 96-bit input/output and depth 256, matching the 32-bit address plus 64-bit AXI beat. Preserve that format when regenerating IP. If static weights drain but stream 0 and TIME4 stay zero, inspect the pending sample-reader launch. If a pointer stops early, inspect AXI/FIFO/debug state; if both pointers complete but done never arrives, inspect the engine state and payload interpretation.

Samples are signed 14-bit values carried in little-endian 16-bit lanes. Each packed weight lane holds two signed 7-bit Q1.6 coefficients: bits 13:7 contribute to the first output and bits 6:0 to the second. +1 is not representable; +63/64 is the near-identity positive coefficient.

### DDR payloads

| Engine/configuration | Sample bytes | Cold weight bytes |
|---|---:|---:|
| Serial fixed 2048 | 4096 | 45056 = 2048 × 11 × 2 |
| Alternate full-frame fixed 4096 | 8192 | 98304 = 4096 × 12 × 2 |
| Current SDF 1024, four banks | 2048 | 81920 = 4 × 1024 × 10 × 2 |
| Current SDF 2048, two banks | 4096 | 90112 = 2 × 2048 × 11 × 2 |
| Current SDF 4096, one bank | 8192 | 98304 = 4096 × 12 × 2 |

SDF cold preload supplies **all resident banks**, ordered bank, then stage, then sample index. Warm runs reuse them. The smaller-vector SDF payload is not the serial engine's one-bank payload.

For 1024/2048 register lengths, explicitly select a valid bank **before each START**. Accepted START consumes the bank-selected flag; changing VLEN also clears it. The API's start guard currently applies regardless of selected engine. At 4096 there is one implicit bank and the bank-setting API is unsupported. Bank selection does not change the serial engine's fixed datapath length.

Keep mode, vector length and descriptors stable during a run. Changing SDF vector length changes the resident-bank layout; reset and reload the complete matching weight payload before using the new length. Bank switching between runs reuses the already loaded banks for that length.

DDR software slots are 0..7. Query BNET:DDR:START? and BNET:DDR:SIZE?; use page-aligned, non-overlapping bases and reservations in multiples of 0x80 bytes. Account for the entire sample allocation before placing weights: 0x1000 spacing is insufficient for an 8192-byte sample vector. Upload raw little-endian bytes through BNET:DDR:SLOT#:OFFSET#:DATA# and attach slots to the appropriate stream/buffer.

Set STRIDE=2 and FORMAT=0 for packed lanes. STRIDE currently affects pointer accounting, not physical lane skipping; FORMAT is a stored tag. Enable/commit only the streams required by the run. Stream control pulse writes must preserve ENABLE.

### Registers and SCPI

Offsets below are relative to the BNET base.

| Offset | Purpose |
|---|---|
| 0x00 / 0x04 | CONTROL / STATUS |
| 0x08..0x24 / 0x28..0x34 | Scalar/debug input / output registers |
| 0x38 / 0x3c | VLEN / descriptor count |
| 0x40 / 0x44 / 0x48 | Active / pending / error masks |
| 0x4c | CONFIG |
| 0x50..0x64 | TIME0..TIME5 |
| 0x68 / 0x6c / 0x70 / 0x74 | Capture count / address / data / overflow status |
| 0x78 | Weight-bank index and selected flag |
| 0x100 + stream × 0x40 | Descriptor window |

CONFIG bits: 1:0 input mode (0 ASG, 1 ADC, 2 DDR); 2 auto-swap; 3 auto-restart; 4 serial weight reuse; 5 static engine; 6 single-DAC serialization; 7 split-DAC encoding; 8 ADC recombination; 9 recombination sample phase.

Examples: 2 serial DDR, 18 serial DDR with weight reuse, 34 static DDR, 66 serial DDR with single DAC, 98 static DDR with single DAC. Auto-restart requires valid committed pending buffers for enabled streams, no descriptor/runtime error, and a fresh bank selection when VLEN is below 4096.

CONTROL bits: 0 START, 1 soft reset, 2 LED debug, 3 LED6 heartbeat, 5 commit all enabled streams. STATUS bits include 0 busy, 1 sticky done, 3 any pending, 4 output-valid mirror.

Descriptor offsets: +0x00/+0x04 bases, +0x08 byte length, +0x0c stride, +0x10 format, +0x14 control, +0x18 status, +0x1c consumed-byte pointer, +0x20/+0x24 debug. Control bits 0 enable, 1/2 commit ping/pong, 3 force swap, 4 clear error.
Descriptor STATUS bit 5 includes the runtime error indication.

TIME0 total; TIME1 load/weight preload; TIME2 compute in serial or input-load alias in static mode; TIME3 playback/output; TIME4 input load; TIME5 latency. Warm counters can remain zero/stale depending on engine/controller behavior: do not infer speedup from zero TIME0. Network-poll timing includes software latency.

Current SCPI groups include BNET:RST, START, STATUS?, CONFIG, MODE, VLEN, WEIGHT:REUSE, PIPELINE, WEIGHT:BANK, WEIGHT:BANK:COUNT?, DAC:SINGLE, DAC:SPLIT, ADC:COMBINE, ADC:COMBINE:PHASE, TIME#?, CAPTURE:COUNT?/STATUS?/DATA?, STREAM#:..., and DDR:SLOT#:.... The command table is authoritative for exact argument forms.

### Output and regression interpretation

Normal output sends even/odd pair lanes to RF OUT1/OUT2. A full-vector comparison must interleave both captures. CONFIG[6] emits both lanes sequentially on RF OUT1 with backpressure. Split mode holds high7/low7 fields for four clocks per field; CONFIG[8:9] controls corresponding ADC-A reconstruction for scope acquisition. These analog paths need actual loopback characterization.

Digital output capture has depth 4096 and exposes an overflow flag. Use it for fixed-point comparisons before diagnosing analog differences. Busy/done includes serializer drain so completion should follow the last emitted saved sample.

Preserve explicit true-dual-port RAM inference and separate clocked write processes per port. The former 16384-point static target is obsolete; do not expand beyond the current resource target without utilization/timing evidence. Reader starvation may not assert underrun when consume is gated by valid; inspect requested-byte/debug/FIFO/engine-load state if a run stalls.

Use the current SDF/capture notebook for banks and runtime lengths. Older DDR/pipeline notebooks retain useful reference models and historical data, but their payloads and stored outputs must be checked against the selected engine.

## 7. TDC architecture, measured history and outstanding work

The TDC uses 128 explicit CARRY4 cells, 512 sampling FDREs, an iterative bubble-filtering encoder, coarse/fine arithmetic, a 256-entry result FIFO, histogram and double-buffered calibration LUT.

- External LVDS launch to PCB: E3 contacts **7/9**, DIO17 P/N, exp_e3p_o[0]/exp_e3n_o[0], package T5/U5.
- External LVDS return from PCB: E3 contacts **31/33**, DIO18 P/N, exp_e3p_i[0]/exp_e3n_i[0], package V11/V10. Use E3 ground contact 16, 22 or 26.
- Alternative single-ended return: **DIO2_P, E1 contact 7**, exp_p_io[2], package **J18**, with E1 ground 25/26. The user confirmed a **3.3 V digital output**. This pin is permanently input-only in the custom top; housekeeping GPIO output settings cannot drive it. The existing board sdc/red_pitaya.xdc supplies J18/LVCMOS33; no new pin constraint is needed. No differential termination belongs on this input.
- Both pairs are LVDS_25. The user confirmed an LVDS return without external termination; the updated instance and TDC module defaults enable internal 100-ohm differential return termination. If external termination is later added, disable the internal terminator. Analog voltages must first pass through the external compatible receiver.
- E3 indices 3:1 retain one clock and two auxiliary serializer data lanes; index 0 is reserved for TDC.
- Sources: external LVDS/SINGLE return selected by INPUT_SELECT; divided independent PS fclk[0] stimulus selected by CONTROL[10]; dedicated phase-swept MMCM stimulus selected by CONTROL[11], with MMCM priority.
- The dedicated MMCME2_ADV is separate from the shared Red Pitaya PLL. Nominal parameters give 448 phase steps per 8 ns ADC period, about 17.86 ps per commanded step. This is a nominal stimulus setting, not certified TDC resolution.
- Current source register ID is **0x54444304** (v4 selectable external input). The earlier board reading 0x54444303 identifies the previous v3 image. MMCM registers are at 0x80 control, 0x84 status, 0x88 coarse delay, 0x8c signed step count; INPUT_SELECT is at 0x90, relative to the TDC base.
- Source code now includes the fixed 128-bit FIFO layout with a 10-bit fine-raw field, the normal-operation pending-trigger latch, and the third toggle-settling stage.
- The iterative encoder needs roughly 512 clocks per event. A 125 MHz sampling clock does not imply 125 million accepted measurements per second. No PS interrupt line is connected.

Detailed register/flag/record definitions are in the FPGA repo's prj/v0.94/doc/tdc_registers.md. App interfaces are rp_Tdc* and TDC:*; tests cover reset/enable/mode/trigger, FIFO/measurement, calibration and MMCM commands.

External selection (new source changes, not yet loaded on the board):

- `TDC:INPUT LVDS` (FPGA-reset default), `TDC:INPUT SINGLE`, `TDC:INPUT?`; API rp_TdcSetInput/rp_TdcGetInput with rp_tdc_input_t. INPUT_SELECT is physical 0x40710090, value 0 or 1. The API requires ID version 4+ and rejects the earlier v3 image rather than falsely reporting selection success.
- Disable the TDC and wait for BUSY=0, or issue TDC:RESET to abort a pending measurement, before selecting. Changed selection resets controller, results/FIFO, sequence/event counters and histogram, and disables LUT correction. Rewriting the same source while disabled/idle has no reset side effects. Source survives soft reset; FPGA reset selects LVDS.
- Turn TEST:INTERNAL and MMCM:ENABLE OFF for either PCB input. One external input is measured at a time. The selected rising edge is fed directly into the delay line; the existing synchronized signal is only used for re-arm. Keep the input LOW before starting and let it return LOW between acquisitions.
- The E3 launch pair stays at contacts 7/9 for both return types. The E1 pulse generator remains a separate function; these changes do not make it the TDC start reference. A periodic unrelated PCB signal does not establish a controlled launch-to-return delay.
- Re-characterize the selected input path and reload its calibration before calibrated use; LVDS and LVCMOS input/routing offsets differ. Wait for histogram-clear completion before collecting calibration. The stored LUT banks are not automatically replaced by a source change.
- Rebuild/reload FPGA plus API and SCPI server; the static SCPI link embeds the API. The source-refresh helper now includes tdc_registers.sv. Verify ID 0x54444304 and query INPUT before acquisition.

For SINGLE bring-up, use the external single-shot sequence in section 9 with `TDC:INPUT SINGLE` after RESET. Query `TDC:INPUT?` before enabling. Switch back with `TDC:INPUT LVDS` after disabling/resetting.

Local checks for this addition passed: Slang selected custom-top hierarchy (0 errors, two existing BNET shift warnings); Icarus TDC integration with LVDS/SINGLE isolation, enabled/busy write rejection, source preservation through reset and FIFO/LUT clearing; mocked project-refresh Tcl check; memory-backed API plus actual pinned SCPI parser/handlers (set/query, abbreviations, bad parameters, old-image and busy guards). The host C++ check used standalone GCC 6.2 C++14 with Windows mmap/syslog shims and an unused span declaration shim; it is not the required Linux/ARM C++20 production build. The persistent host test is scpi-tests/tdc_input_selection_test.cpp; compile it with scpi-server/src/tdc.cpp and libscpi, rather than separately linking a second API tdc.cpp. No Vivado, board upload, routed timing or electrical test was performed for this addition.

Historical findings, preserved with scope:

- A prior real build locked its dedicated MMCM and produced a monotonic phase sweep. That run exposed a 127-versus-128-bit FIFO packing bug causing spurious +512 raw indices and shifted fine/total fields; the source fix requires a new image.
- A pending-trigger latch was previously set only in reset; its operating-branch fix is in source.
- A 100k-event internal calibration reported 414 useful bins, peak |DNL| 2.196 LSB and peak |INL| 8.426 LSB. A repeated run reported missing raw codes 305..320 and smaller dips near 99..100 and 203..204.
- The long dead zone correlated with a clock-region boundary in the old placed design. **A universal claim that 7-series carry cascades cannot cross clock regions is not supported by AMD's architecture documentation.** Retain the observation; inspect actual routing/clock skew and characterize the new image instead of assuming the physical cause is proven or unavoidable.
- A 40-target × 5-repeat MMCM random-delay test showed an 8000 ps coarse-count ambiguity in part of the phase range. At phase 117, coarse values 6/7 occurred with essentially identical fine indices 221/222. A fine-index-based correction was rejected.
- The third settling stage is in source, but its effect on that hardware ambiguity has not been re-measured. Run dense repeated boundary tests and document any residual self-test exclusion range. Do not promote the source change or logic PASS to proof that the issue is fixed.

The supporting TDC_IMPLEMENTATION_ANALYSIS.md contains the retained measurement details. Its operational setup/status material has been consolidated here.

For new TDC acceptance: verify the 128/512 primitive counts, inspect placement/routing, meet ordinary logic timing, establish external LVDS single-shot/timeout/re-arm behavior, characterize clock boundaries and code density, then calibrate against the exact bitstream. A fixed synchronous loopback alone does not establish uniform code-density coverage. Confirm phase walking for an internal source before activating its LUT; --collect-only supports inspection first.

Keep calibrated LUTs tied to the actual board, bitstream, placement/routing and relevant temperature. A documented dead-zone flag records measured behavior; it does not recover missing resolution or justify ignoring new anomalies. Absolute accuracy needs an independent known-delay reference.

## 8. Pulse generator

### Timing and ownership

The module uses the existing nominal 250 MHz ser_clk and an ODDR output register; it creates no additional PLL and uses no DDR memory.

| Setting | Supported logical timing at a 125 MHz reference |
|---|---|
| Tick | 2 ns half-cycle |
| Period | 4..8,589,934,588 ns, in multiples of 4 ns |
| HIGH duration | Multiples of 2 ns, from 2 ns to period minus 2 ns |
| Maximum repetition | 250 MHz logically: 2 ns HIGH + 2 ns LOW |
| Reset default | 1 ms period / 500 us HIGH |

A 6 ns period is rejected. PERIOD preserves the prior duty ratio with rounding/clamping to the 2 ns grid; FREQUENCY rounds to the nearest supported period and preserves duty. TIMING sets both explicitly. Query actual timing. An external ADC reference other than 125 MHz invalidates the advertised nominal ns conversion.

Timing changes require OFF. ON starts a fresh period after mailbox/driver startup. OFF may truncate the final HIGH; this is a continuous generator with no complete-last-pulse guarantee.

- FPGA reset: disabled and unclaimed, ordinary GPIO state applies.
- First ON claims DIO1_P. OFF retains ownership and holds LOW.
- PULSE:RESET restores default timing and releases the pin to saved GPIO data/direction, which may request HIGH.
- DIG:PIN/DIR writes do not change the physical pin while claimed. DIG:RST does not reset the pulse generator.
- API release, client disconnect and server exit do not automatically stop the hardware. Send OFF explicitly.
- The ODDR also passes ordinary GPIO data while unclaimed, now through a two-stage fast-clock synchronizer (allow a few fast cycles for GPIO changes). Preserve the **direct ODDR-Q-to-selected-IOBUF** connection; GPIO/pulse selection stays before ODDR. Fast-clock loss affects passthrough.

October review fixes now in source: missing pulse instance and undriven pin signals; missing TDC enables/shared decoder; missing XDC inclusion; SCOPE_ONLY slot-7 stub; input-claim startup skew; stale ENABLE-status live-update rejection; seven declaration-order/enum-width errors in TDC MMCM and legacy ASG code. The delayed-claim regression failed before the guard fix and passes afterward.

Board bring-up exposed a further bus-interface bug: pulse_gen cleared sys_rdata_o immediately after the local request ended, while sys_bus_cdc returned data to the PS several clocks later. This produced zero pulse ID/tick despite BNET and TDC reading correctly. The source now holds the last read response until another request; a delayed-read regression failed before this change and passes afterward. Refresh the imported pulse_gen.sv in the separate Vivado project and rebuild/reload before retrying SCPI.

The later timing repair precomputes the terminal phase count in the bus mailbox instead of subtracting in the 250 MHz feedback path, synchronizes GPIO data before ODDR, and adds a dedicated final reset stage for ODDR. BNET burst planning is separated from address/count feedback; BNET debug counters/flags now cross through a coherent snapshot mailbox instead of directly entering the register mux. Public addresses, timing units and FIFO format remain the same. These changes need a fresh implementation and timing review.

### Register contract

Base 0x40720000; period/HIGH counts are 2 ns units.

| Offset | Register / meaning |
|---|---|
| 0x00 | ID_VERSION = 0x50554c01, read-only |
| 0x04 | Shadow ENABLE bit 0 |
| 0x08 | STATUS: BUSY[0], active ENABLE[1], CLAIMED[2], sticky ERROR[3], READY[4] |
| 0x0c / 0x10 | Shadow PERIOD / HIGH |
| 0x14 | COMMAND: exactly 1 APPLY, 2 RESET/RELEASE, or 4 CLEAR_ERROR |
| 0x18 / 0x1c | TICK_NS=2 / positive-bank GPIO index=1 |
| 0x20 / 0x24 | Applied PERIOD / HIGH |

PERIOD must be even and at least 2 ticks; HIGH is 1..PERIOD-1. APPLY captures the complete shadow configuration into a mailbox held until ACK. Busy, invalid or live-ON APPLY is rejected; disabling is allowed. RESET/RELEASE is rejected while busy/not ready.

The API uses a process-local mutex, MMIO fence, settled reads, a 100 ms timeout and applied-value readback. Independent processes directly editing registers are not serialized by that mutex.

### SCPI and initial test

Only use after the matching image/API/server is installed and DIO1_P is available:

~~~text
PULSE:OUTPUT OFF
PULSE:TIMING 1000,500
PULSE:PIN?
PULSE:TIMING?
PULSE:FREQUENCY?
PULSE:OUTPUT ON
PULSE:STATUS?
PULSE:OUTPUT OFF
~~~

Expected pin DIO1_P, timing 1000,500, frequency about 1000000 Hz. Typical status: 16 after reset/unclaimed, 22 while ON, 20 after OFF/claimed LOW.

Other commands: PULSE:PERIOD[?], WIDTH[?], FREQUENCY[?], OUTPUT[?], STATUS?, TIMING[?], PIN?, RESET. Numeric ns values are unsigned integers without a unit suffix.

The provided smoke test is:

~~~text
python scpi-tests/pulse_generator_test.py <board-host>
~~~

It briefly enables 1 MHz by default and finishes OFF/claimed LOW. Faster ON tests require --fast; register checks do not measure the electrical waveform. The script has not been run against a board in this session.

## 9. Existing Vivado project: transfer and constraints

These are instructions for the user on the build device, not authorization to run Vivado here.

1. Back up the working project/image. In the existing GUI project, source prj/v0.94/scripts/refresh_custom_sources.tcl from this repository. It replaces the six changed module references (pulse_gen, bnet_axi_reader_ch, tdc_top, tdc_registers, tdc_mmcm_stimulus, tdc_lvds_io), selects the repository's merged red_pitaya_top_LED7_mod.sv, disables competing top source copies, refreshes the Gen2/custom XDCs, sets their implementation use and board defines, and removes SCOPE_ONLY. It does not launch runs. Retain prior ASG declaration/enum corrections.
2. Set top module red_pitaya_top from red_pitaya_top_LED7_mod.sv; remove/disable competing top definitions in that fileset. Set Z20_G2 and Z20_xx, preserve other required defines, and leave SCOPE_ONLY absent for the full feature build. Confirm DWE=11 and PS GPIO width 33.
3. Add/update constraints in the active constrs_1 set. Keep existing board/clock/pin XDCs and avoid duplicate imported copies:

| Constraint under prj/v0.94/sdc/ | Synthesis | Implementation |
|---|---|---|
| pulse_gen_Z20_G2.xdc | OFF | ON |
| tdc_Z20_G2.xdc | OFF | ON |
| bnet_reader_Z20_G2.xdc | OFF | ON |
| tdc_placement_selected.xdc, when generated | OFF | ON |

The two updated Z20_G2 build Tcl entry points include the pulse/TDC constraints for a non-SCOPE_ONLY v0.94 build, and include the selected-placement XDC if it exists. Existing GUI projects need their files/properties refreshed manually.

4. Keep testbenches out of Design Sources. Use Xilinx UNISIM for Vivado tests. Never add tbn/pulse_gen_oddr_model.sv or tbn/tdc_carry_chain_logic_model.sv to a Vivado fileset. The latter is only an ideal tap source for the standalone controller test, not a physical TDC model.
5. Elaborate/synthesize. Confirm i_pulse_gen, i_tdc, i_bnet_regs, one selected H16 IOBUF, the single slot-7 response driver, bus period 8 ns and pulse ser_clk period 4 ns.
6. For the present pulse-only test, skip new TDC manual placement if desired. Vivado can automatically place its instantiated logic. Keep its existing timing/placement constraints. This does not establish calibrated TDC performance.
7. The placement helper now sets tap FF BEL before LOC in both the live procedure and emitted XDC. Its tap-name selector also accepts Vivado's generated gen_tap[index].i_tap_ff hierarchy. No placement coordinates were selected here.
8. For TDC work, open the synthesized design, source prj/v0.94/scripts/tdc_placement.tcl, verify 128 CARRY4 / 512 tap FDRE cells, and choose a real legal column/start row or recover a prior working placement. Use tdc_place_chain X Y0 and tdc_report_placement; write prj/v0.94/sdc/tdc_placement_selected.xdc with tdc_write_placement_xdc. Add it to constrs_1 before controlled implementation. No selected-placement XDC was found in either working checkout or the saved Vivado project.
9. Reset stale implementation runs, implement, and inspect timing summary, clock interaction, CDC, exceptions, DRC, I/O and hierarchical utilization. Source scripts/check_custom_constraints.tcl in the open design to verify 128 carries, 512 tap D pins, six pulse first-stage synchronizers, eight BNET first-stage synchronizers and nonempty bundled-data collections. Verify the 4 ns mailbox and 8 ns readback bounds remain effective; do not blanket-false-path the pulse clock pair. Check ODDR IOB placement and direct Q-to-IOBUF connectivity, LVCMOS33, FAST slew and the existing drive setting.
10. Confirm RAM inference/resource use and ordinary 250 MHz pulse paths close. Produce an identifiable bitstream only after applicable checks pass. Controlled TDC placement constrains locations, not all routed delays; calibrate the resulting image.

AMD constraint-order reference:
https://docs.amd.com/r/2024.2-English/ug912-vivado-properties/BEL

AMD 7-series carry architecture:
https://docs.amd.com/r/en-US/ug474_7Series_CLB/Carry-Logic

### Timing repair and initial TDC bring-up

The saved 2026-10-14 run reported unsupported Tcl if blocks in the two custom managed XDCs; its worst -10.290 ns path ended at an asynchronous carry tap. The tap selector also assumed a slash where the synthesized generated hierarchy uses a dot. Both custom XDCs now contain supported constraint commands with no control flow, and the tap pattern is corrected. Only tap D measurement inputs and documented first synchronizer stages/reset synchronizer CLR inputs are exempt. Encoder, controller, FIFO, clocks, functional reset release and ordinary datapaths remain timed. No global asynchronous clock grouping is applied.

The remaining real paths were addressed in the pulse counter and BNET scheduler/debug transfer as described above. The Gen2 E3 receive clock now uses the P pin only, fixing the previous two-source clock warning. These source changes are an attempted timing repair; they are not a timing-closure result. Refresh the files, reset old synthesis/implementation runs, rebuild and inspect the new report. Resolve any non-measurement negative slack before accepting operation.

After the new image passes the applicable implementation checks:

- Verify current TDC ID 0x54444304 at 0x40710000 and NUM_TAPS 512 at 0x40710018; verify pulse ID 0x50554c01 and tick 2 as well.
- Route PCB LVDS return P/N to E3 contacts 31/33. For a controlled launch-to-return test, route E3 launch contacts 7/9 to the PCB input and supply a common ground. E1's 3.3 V pulse output requires an LVDS driver before any connection to the E3 input.
- The user confirmed no external return termination, so RETURN_DIFF_TERM is now true and the FPGA's internal 100-ohm differential termination is enabled. Do not add another terminator in parallel.
- Start with external single-shot mode and no LUT. Configure source selection with ENABLE OFF. The TDC generates its own launch; an unrelated free-running input does not establish a controlled delay.
- Check a captured record, raw thermometer data, missing-return timeout and repeated re-arm. Uncalibrated fine/total ps values are diagnostic estimates.
- Repeat dense MMCM boundary tests and code-density work before calibrated use. The historical missing-code region and one-cycle internal coarse ambiguity remain hardware characterization items.

SCPI sequence for the external single-shot test (write commands do not return a reply):

~~~text
TDC:ENABLE OFF
TDC:TEST:INTERNAL OFF
TDC:MMCM:ENABLE OFF
TDC:RESET
TDC:INPUT LVDS
TDC:MODE SINGLE
TDC:CALIBRATION:LUT:ACTIVATE OFF
TDC:LAUNCH:WIDTH 2
TDC:TIMEOUT 125000
TDC:TAPS?
TDC:ENABLE ON
TDC:MEASURE?
TDC:MEASURE:RAW?
TDC:ENABLE OFF
~~~

WIDTH and TIMEOUT here are clock counts (2 gives nominal 16 ns; 125000 gives nominal 1 ms). MEASURE? issues its own trigger and consumes a FIFO result. Start from reset/empty FIFO and let the return settle LOW before arming. Poll SYST:ERR:NEXT? to check command errors.

Tests added for this repair: tbn/tb_bnet_reader_scheduler.sv with tbn/run_bnet_reader_scheduler.py covers short/final bursts, FIFO backpressure, delayed AXI busy, diagnostic snapshots and reset; tbn/tb_tdc_top.sv with the ideal tap model covers controller, register, FIFO, timeout and re-arm behavior. The normal pulse and TDC component regressions also pass. Physical carry delay, new routed timing, calibration accuracy, and the real external link remain untested.

## 10. Software build, deployment and tests

Build the latest API and SCPI server in the established Linux/ARM/chroot environment:

~~~text
make api
make scpi
~~~

Confirm both artifacts use the updated public header, symbols and command table. The SCPI CMake links rp statically, so replacing librp.so alone does not update its embedded API. Source checking on Windows is insufficient. Preserve existing BNET/TDC functionality when merging pulse additions.

Before deployment, back up the working FPGA image, librp.so and SCPI server; identify commits/local changes and checksums. Stop services that access the FPGA, replace matching artifacts using the board image's established overlay/fpgautil workflow, then restart. Do not substitute a legacy /dev/xdevcfg flow for the current board's loader.

| App test | Purpose |
|---|---|
| scpi-tests/pulse_generator_test.py | Pulse SCPI/register smoke test; finishes OFF |
| scpi-tests/bnet_sdf_capture_feature_test.ipynb | Current SDF, digital capture, runtime lengths/banks and optional split/combine tests |
| scpi-tests/bnet_pipeline_mode_test.ipynb | Serial/static comparison and cold/warm diagnostics; check engine compatibility and stale outputs |
| scpi-tests/ddr_bnet_test.ipynb | DDR/fixed-point/RF regression and historical models |
| scpi-tests/ddr_bnet_complex_rf_test.ipynb | Complex RF experiments |
| scpi-tests/asg_125mhz_alternating_loopback_test.ipynb | ASG/RF alternating-pattern diagnostic |
| scpi-tests/tdc_calibrate.py | Code density, LUT/calibration, precision and documented dead zones |
| scpi-tests/tdc_internal_selftest.ipynb, tdc_internal_test_py.py | TDC internal/MMCM experiments |
| scpi-tests/tdc_mmcm_random_delay_test.py | Commanded phase/coarse-delay repeatability and boundary ambiguity |

Saved notebook outputs are not a fresh acceptance run. For example, the SDF notebook's current split-helper source says v5 while a stored output says v3; the pipeline notebook contains a zero warm-total timing result and an implausible derived speedup. Restart the kernel, select an identified matching image, rerun setup and tests in order, and inspect raw status/pointers/counters before accepting performance numbers.

## 11. Next actions and unresolved items

Immediate pulse/TDC work:

1. Refresh all affected sources/constraints with scripts/refresh_custom_sources.tcl in the existing Vivado project. Rebuild/reload and verify both feature IDs before SCPI tests.
2. Resolve the routed timing failures before treating the pulse output as reliable; inspect the 250 MHz phase counter and other failing path groups in the saved timing report.
3. Wire E1 pins 1/2 for +3.3 V, 25/26 for common ground, and pin 5 for the PCB pulse input. PCB power is automatic.
4. Run the 1 MHz smoke test, then measure voltage, period, HIGH/LOW widths, OFF/LOW and restart behavior at the actual PCB receiver.
5. Progress to 24 ns, 8 ns and 4 ns periods only after the receiver, interconnect and measurement setup are characterized.

Outstanding broader work:

- Full generated-IP vendor elaboration, CDC/timing/DRC and resource acceptance for the merged image.
- Select and inspect a legal controlled TDC placement; no selected-placement XDC has been generated here. The helper BEL/LOC ordering and tap selector are now corrected.
- Fresh BNET engine-specific regression with correct SDF multi-bank payloads and explicit per-start bank selection; validate cold/warm counters before throughput claims.
- TDC source fixes and third-stage crossing changes need fresh hardware tests; re-characterize coarse ambiguity and missing-code regions against the new placed/routed image.
- Exact Linux/ARM API/server build identity and successful live pulse SCPI remain unverified. The running server recognizes PULSE:OUTPUT and reports the hardware-signature failure.
- Actual PCB receiver specifications, pulse electrical performance, exact supply startup demand and independent-power sequencing remain unconfirmed.

Maintain this file when new evidence arrives. Record source/image identity, tool version, test scope and measured results; retire superseded instructions instead of accumulating contradictory status sections.
