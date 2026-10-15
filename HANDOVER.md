# Red Pitaya master handover

Updated: 2026-10-15. Target: STEMlab 125-14 Z7020 Gen 2 / Z20_G2, xc7z020clg400-1; existing Vivado project uses 2020.1.

This is the authoritative workspace handover for BNET, the LVDS CARRY4 TDC, and the single-channel GPIO pulse generator. It replaces the separate BNET and pulse handovers. Repository source, public headers, command tables and the TDC register specification remain the detailed interface references.

## 1. Current objective and working rules

The current objective is low-frequency testing of the PCB's voltage-dependent pulse duration while supplying it from dedicated 3.3 V power pins. Interface v6 expands finite pulse-width capture to 16384 records using online encoding and compact storage, retaining the initial 1 MHz limit. Legacy TDC commands retain launch-to-return timing. The new FPGA image, API and SCPI server still require the user's external Vivado build, deployment and board tests.

- **Do not run Vivado on this device unless the user changes that instruction.** The recorded local HDL checks used Slang and Icarus.
- Preserve BNET, pulse generation and shared bus addressing when transferring changes. The newly requested PCB pulse-width redesign is authorized to replace the TDC measurement controller/encoder and its interfaces; preserve useful input selection and calibration/self-test support where applicable. Document any changed hierarchy, placement selectors and register/version semantics.
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
| PCB width burst implementation, 2026-10-15 | Icarus PASS for both edge captures, varying widths, full buffer, coarse and synthetic rise/fall LUT results, missing/extra edges, constant HIGH, sub-sample pulse rejection, lost triggers, timestamp wrap, abort/rearm and delayed reads; selected merged top Slang 0 errors, 2 existing SDF warnings; project-copy/constraint/placement Tcl checks PASS with mocked objects | Ideal uniform tap delays and reduced test capacity; no physical carry calibration, metastability, full vendor elaboration, resource or routed timing acceptance |
| Width RAM inference repair, 2026-10-15 | Single write-port RTL; Icarus PASS for trigger-boundary rise/next-address and fall writes, integrated TDC, and a full production 512-tap / 1024-record burst with every result checked; merged top Slang 0 errors, 2 existing BNET warnings | Repairs the unsupported source access pattern reported by external Vivado synthesis; local simulation does not prove Vivado BRAM inference, utilization or timing. External synthesis rerun is pending |
| V6 16384-record width capture, 2026-10-15 | Icarus PASS for a full production 512-tap / 16384-record burst at 1 MHz, all results checked, online capture/processing overlap; small-burst error/LUT/boundary/abort tests and forced ring-overflow recovery PASS; encoder matches an independent reference for all 65536 16-tap patterns plus 17/512-tap cases; selected merged top Slang 0 errors, 2 existing BNET warnings | Ideal delays, not physical carry calibration or metastability; no Vivado run here. New grouped encoder timing, BRAM inference/total utilization and board operation remain external acceptance gates |
| V6 software readout, 2026-10-15 | Actual API/SCPI host regression PASS for 16384 ARM, last-record read, capacity/overflow and guards; Python mocked-client tests PASS for chunk boundaries through 16384 records, full CSV, old-image capacity rejection and cleanup | Mock MMIO/client and Windows host shims; no live board or ARM/Linux build in this session |
| Width API/SCPI, 2026-10-15 | Standalone host build/test PASS using the actual API and SCPI handlers with pinned scpi-parser; checks feature versions, busy/rate/duty guards, record decoding and invalid parameters | Mock MMIO and Windows host shims; matching Linux/ARM API/server build and live board SCPI still required |
| Width board-test script, 2026-10-15 | Python syntax and mocked-client sequence PASS: source ON before ARM, chunked record reads, CSV output, invalid-result rejection and output-OFF/abort cleanup | No board connection or electrical measurement |
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

The legacy TDC uses 128 explicit CARRY4 cells, 512 sampling FDREs, an iterative bubble-filtering encoder, coarse/fine arithmetic, a 256-entry result FIFO, histogram and double-buffered calibration LUT.

### Confirmed PCB behavior and pending redesign

The user verified that the PCB converts analogue voltage into a digital pulse train. FPGA output pulses trigger its operation; the analogue voltage seen at the trigger rising edge controls PCB output duty cycle/HIGH duration, with larger voltage producing longer pulses. The intended single-ended trigger is pulse_gen on DIO1_P (E1 contact 5); the existing selectable return inputs remain available in source.

The retained legacy acquisition timestamps the PCB rising edge relative to its own E3 launch; its falling edge is used only for re-arm. Use the new TDC:WIDTH:* commands for PCB HIGH duration. The legacy external single-shot procedures below are not acceptance tests for PCB voltage-to-pulse-width conversion. E3 launch contacts 7/9 are one differential output pair and are not connected for the PCB trigger on E1 contact 5.

The requested redesign should support cycle-by-cycle acquisition associated with each pulse_gen rising edge, retaining the previous result before clearing per-cycle state. A CARRY4 propagation chain is combinational and does not retain a cumulative filled count: a falling input edge propagates through it, and a pulse longer than its finite traversal delay saturates the HIGH pattern. Snapshot storage and, for a range beyond the chain delay, a coarse counter plus calibrated fine edge timing are needed. Do not treat a reset of sampling flip-flops as an instantaneous clear of the physical carry path.

The user has now clarified the redesign requirements:

| Requirement | Agreed value / meaning |
|---|---|
| Measured interval | PCB rising edge to PCB falling edge (HIGH pulse width); exclude trigger-to-PCB response delay |
| FPGA trigger frequency | 1–125 MHz target; use the existing pulse generator and query the actual quantized frequency |
| FPGA trigger duty | 50%; nominal HIGH/LOW range 500 ns / 500 ns at 1 MHz to 4 ns / 4 ns at 125 MHz |
| PCB repetition | One active-HIGH output pulse per FPGA rising edge in normal operation, completing before the next trigger |
| PCB HIGH range | Up to 100% duty; minimum detectable HIGH and LOW duration must be characterized, not inferred from a register's ps units |
| Full-scale / missing edge | Report SATURATED / NO_FALL or other explicit invalid status when individual pulses cannot be distinguished; do not fabricate a measured width |
| Acquisition | Capture every pulse within finite bursts, then read the buffer; continuous full-rate raw Ethernet streaming is not required |
| Precision | Best achievable after physical implementation, calibration and measurement; no numerical ps accuracy has been accepted or demonstrated |
| Bring-up | Start at 1 MHz and increase; 125 MHz is an unverified target for the PCB/link and FPGA capture |

The initial low-frequency width implementation is now in source. The previous v4 input-selector tests do not establish its physical accuracy or throughput; use the new width tests and hardware procedure below.

#### Current v6 implementation: 16384 pulse-width records

- HDL: prj/v0.94/rtl/tdc_pulse_width.sv. Separate capture and processing controllers overlap acquisition and encoding. Only four raw rise/fall frames are staged; completed frames are consumed by an eight-tap-per-clock encoder before the next 1 MHz frame. The carry path stays running across trigger boundaries. The shared encoder retains its original one-tap mode by default for legacy TDC operation.
- Current top-level TDC ID: **0x54444306** at 0x40710000. Width sub-block signature remains **0x50574201** at 0x40710100; the five-word readout/API layout is compatible with v5. Rebuild the matching API/server for the updated overflow definition; the SCPI server links the API statically. CAPACITY? distinguishes the 16384-record default from older images.
- Width acquisition deliberately rejects trigger periods below **1000 ns** (above **1 MHz**). The API requires pulse_gen already ON, 50% drive, and legacy TDC enable/internal/MMCM modes OFF. The initial 250 MHz sampler uses a **4 ns coarse tick**; HIGH and LOW should each be at least **8 ns** for coarse capture, subject to actual board characterization. Shorter pulses/gaps may be missed or merged. This release does not implement 125 MHz acquisition.
- Burst length is 1..16384, default 16. N records require N+1 output trigger boundaries. Encoding runs during capture; readout starts after the last frame is processed. A full 1 MHz burst covers 16.384 ms plus initial alignment/final processing. This matches the ADC's sample count, not its sample rate. It remains finite capture/readout, with gaps between bursts.
- Storage at 512 taps is 114 bits per record (flags, coarse ticks, two 9-bit indices and width_ps), or 228 KiB for 16384 records. Cycle IDs are derived from addresses, so no public fields are dropped. The four raw staging frames use 544 bytes of logical storage, plus 2 KiB of rise/fall LUT data. Raw staging uses distributed RAM; the compact result buffer uses block RAM with one write and one synchronous read. Scaling the previous v5 raw-burst arrays directly would need about 2.44 MiB and is not the chosen implementation. Verify inference, total utilization and timing alongside BNET/scope/ASG externally.
- Uncalibrated width is the difference between the PCB edge timestamps in 4 ns ticks. Raw carry indices and status bytes are diagnostic. Missing/extra edges, HIGH at cycle start, saturation, trigger timeout, boundary ambiguity and out-of-range results are explicit flags. A stalled processor sets global OVERFLOW (status bit 7) and discards the burst; it never silently overwrites an unread frame. CAPTURING and PROCESSING can both be set. Completed memory is frozen and can be read repeatedly.
- Optional fine correction uses separate rise/fall LUTs for the new 250 MHz carry path: width_ps = coarse_ticks*4000 + rise_LUT - fall_LUT. Both 512-entry tables must be uploaded before activation. Editing a table or changing input disables correction; source changes also invalidate previous width records. Old 125 MHz calibration tables are not valid for this path. No automatic width calibration or certified ps accuracy is claimed.
- New commands: TDC:WIDTH:ARM <count>, ABORT, CLEAR, STATUS?, COUNT?, CAPACITY?, TICK?, DATA? <start>,<count>, TIMEOUT[?], and CALIBRATION:LUT:WRITE/READ? / CALIBRATION:ACTIVATE[?]. DATA returns semicolon-separated records: cycle_id,flags,coarse_ticks,rise_raw,fall_raw,width_ps. Up to 128 records per query. The detailed register/flag definitions and example are in the FPGA repo's prj/v0.94/doc/tdc_registers.md.
- Script: **scpi-tests/tdc_pulse_width_test.py BOARD_IP --count 16384 --csv tdc_width_16384.csv --quiet** (default 1 MHz / 50%, SINGLE input; count defaults to 16 when omitted). It queries hardware capacity, starts pulse_gen before ARM, polls completion, reads 128 records per query and checks IDs/flags/count. The full burst takes 128 data queries. --quiet suppresses per-pulse printing but saves every CSV record and reports validity/status. Cleanup sends output OFF / abort. Use --frequency 100000 for a slower run or --input LVDS for the differential return.
- New carry hierarchy: i_tdc/i_width/i_carry, 128 CARRY4 / 512 FDREs, alongside the retained legacy chain. The placement helper accepts this hierarchy as an optional last argument. Use separate legal sites; no width-chain placement has been selected. The existing TDC XDC now includes the width tap/synchronizer exceptions and bounded control/completion transfers. Ordinary capture, arithmetic, RAM and encoder paths remain timed.
- The project-copy refresh now imports all rtl/tdc_*.sv dependencies, pulse_gen, bnet_axi_reader_ch, the merged top and four XDCs. It uses project-local copies as requested. Keep all tbn carry/ODDR replacements out of Vivado filesets.

**Prior synthesis failure and retained repair (2026-10-15):** v5 failed externally with Synth 8-3391 on rise_memory_reg (512 x 1024 = 524288 bits). Conditional writes to current/next-frame addresses prevented BRAM inference. The repaired source selects write enable/address/data before a single clocked write per array, with no storage reset. V6 retains that access pattern while replacing the full raw-burst arrays with shallow staging and compact results. Do not raise dissolveMemorySizeLimit to expand the array into bits. Refresh copies and reset synthesis on the build machine; no Vivado has been run here and new inference/utilization/timing remain pending.

Run tb_tdc_pulse_width.FULL_SIZE=1 for the production 512-tap / 16384-record configuration, checking every record and overlap of acquisition/encoding. Default FULL_SIZE=0 covers the smaller controller/fault cases, including forced staging overflow and recovery. The grouped encoder regression exhaustively checks all 65536 16-tap inputs and also tests 17/512-tap vectors against an independent reference. Machine-local Icarus scripts/logs are under build/hdl-review/.

After an externally generated image passes timing/CDC/DRC/resource checks, rebuild and deploy the matching API/server, then run:

~~~text
python scpi-tests/tdc_pulse_width_test.py 169.254.77.151 --count 16 --csv tdc_width.csv
python scpi-tests/tdc_pulse_width_test.py 169.254.77.151 --count 16384 --csv tdc_width_16384.csv --quiet
~~~

Connect E1 pin 5 to PCB trigger, the PCB's 3.3 V return to E1 pin 7, and common ground to E1 pin 25/26. No E3 launch pair is needed. Compare valid coarse widths against an oscilloscope at several input voltages before progressing to narrow pulses or fine calibration. Initial PC/PCB operation and routed timing remain unverified here.

#### Target architecture and remaining high-rate work

- Use an internal pulse_gen cycle marker aligned with the ODDR output edge for cycle IDs and burst boundaries. Do not clock the controller from a GPIO output routed back through fabric or assume a delayed synchronizer marks the physical output edge exactly.
- Keep the carry interpolation paths and coarse timebase running during a burst. At a trigger boundary, retain the previous completed cycle's record and prepare new per-cycle bookkeeping. Reset capture ownership/valid flags, not the propagation path near an arriving edge. A captured result must survive re-arm.
- Capture PCB leading and trailing edges independently, including when both arrive within one 125 MHz clock interval. Capture must not wait for thermometer decoding or software. The old 512-clock iterative encoder cannot serve this throughput requirement.
- Combine a coarse timestamp with calibrated fine timing for each edge, then subtract falling minus rising timestamps. A 1 MHz / near-full-scale pulse can approach 1 us, far beyond the finite traversal time of the existing carry line. Counting HIGH taps alone is insufficient.
- Use a pipelined or buffered encoder/capture arrangement able to accept a new pulse every 8 ns at the target rate. Check clustered transitions at changing duty cycles as well as steady 50% signals; nominal sample clock frequency alone does not prove edge throughput or a minimum detectable pulse/gap.
- Preserve correct cycle IDs across a fixed processing latency. The previous cycle's raw capture can be retained at the next trigger even if its encoded result emerges several pipeline stages later. Do not overwrite an in-flight edge pair at each trigger.
- V6 stores up to 16384 compact results and encodes during capture at the initial <=1 MHz rate. Increasing capacity alone does not increase edge throughput. A future 125 MHz design would need substantially faster capture/encoding and transport; that rate and continuous streaming are not implemented or verified.
- Preserve selectable LVDS and 3.3 V single-ended return routes unless a later instruction changes this. E1 DIO1_P remains the single-ended trigger output; no E3 differential launch connection is needed for this PCB protocol. Disable the independent E3 launch function in the new pulse-width acquisition mode.
- Carry tap calibration, rising/falling polarity offsets, input route offsets, clock/coarse boundary handling and missing-code behavior require fresh characterization. A numeric value expressed in ps is not evidence of that resolution or accuracy.

Acceptance work for the redesign must include simulation of long pulses, both edges in one clock interval, narrow HIGH and LOW gaps, minimum/maximum duty, adjacent cycles with sharply changing widths, full-scale constant HIGH, missing/extra edges, counter boundaries, buffer limits and delayed readout. After source checks/simulation, the user must run Vivado timing/CDC/DRC/resource checks elsewhere and then compare widths to an oscilloscope from 1 MHz upward. No Vivado is to be run here.

### Retained legacy implementation

- External LVDS launch to PCB: E3 contacts **7/9**, DIO17 P/N, exp_e3p_o[0]/exp_e3n_o[0], package T5/U5.
- External LVDS return from PCB: E3 contacts **31/33**, DIO18 P/N, exp_e3p_i[0]/exp_e3n_i[0], package V11/V10. Use E3 ground contact 16, 22 or 26.
- Alternative single-ended return: **DIO2_P, E1 contact 7**, exp_p_io[2], package **J18**, with E1 ground 25/26. The user confirmed a **3.3 V digital output**. This pin is permanently input-only in the custom top; housekeeping GPIO output settings cannot drive it. The existing board sdc/red_pitaya.xdc supplies J18/LVCMOS33; no new pin constraint is needed. No differential termination belongs on this input.
- Both pairs are LVDS_25. The user confirmed an LVDS return without external termination; the updated instance and TDC module defaults enable internal 100-ohm differential return termination. If external termination is later added, disable the internal terminator. Analog voltages must first pass through the external compatible receiver.
- E3 indices 3:1 retain one clock and two auxiliary serializer data lanes; index 0 is reserved for TDC.
- Sources: external LVDS/SINGLE return selected by INPUT_SELECT; divided independent PS fclk[0] stimulus selected by CONTROL[10]; dedicated phase-swept MMCM stimulus selected by CONTROL[11], with MMCM priority.
- The dedicated MMCME2_ADV is separate from the shared Red Pitaya PLL. Nominal parameters give 448 phase steps per 8 ns ADC period, about 17.86 ps per commanded step. This is a nominal stimulus setting, not certified TDC resolution.
- Current source register ID is **0x54444306** (v6: compact 16384-width bursts plus selectable input). Earlier IDs 0x54444303/04/05 identify v3/v4/v5 images. MMCM registers are at 0x80 control, 0x84 status, 0x88 coarse delay, 0x8c signed step count; INPUT_SELECT is at 0x90, relative to the TDC base.
- Source code now includes the fixed 128-bit FIFO layout with a 10-bit fine-raw field, the normal-operation pending-trigger latch, and the third toggle-settling stage.
- The iterative encoder needs roughly 512 clocks per event. A 125 MHz sampling clock does not imply 125 million accepted measurements per second. No PS interrupt line is connected.

Detailed register/flag/record definitions are in the FPGA repo's prj/v0.94/doc/tdc_registers.md. App interfaces are rp_Tdc* and TDC:*; tests cover reset/enable/mode/trigger, FIFO/measurement, calibration and MMCM commands.

External selection (new source changes, not yet loaded on the board):

- `TDC:INPUT LVDS` (FPGA-reset default), `TDC:INPUT SINGLE`, `TDC:INPUT?`; API rp_TdcSetInput/rp_TdcGetInput with rp_tdc_input_t. INPUT_SELECT is physical 0x40710090, value 0 or 1. The API requires ID version 4+ and rejects the earlier v3 image rather than falsely reporting selection success.
- Disable the TDC and wait for BUSY=0, or issue TDC:RESET to abort a pending measurement, before selecting. Changed selection resets controller, results/FIFO, sequence/event counters and histogram, and disables LUT correction. Rewriting the same source while disabled/idle has no reset side effects. Source survives soft reset; FPGA reset selects LVDS.
- Turn TEST:INTERNAL and MMCM:ENABLE OFF for either PCB input. One external input is measured at a time. The selected rising edge is fed directly into the delay line; the existing synchronized signal is only used for re-arm. Keep the input LOW before starting and let it return LOW between acquisitions.
- The E3 launch pair stays at contacts 7/9 for both return types. The E1 pulse generator remains a separate function; these changes do not make it the TDC start reference. A periodic unrelated PCB signal does not establish a controlled launch-to-return delay.
- Re-characterize the selected input path and reload its calibration before calibrated use; LVDS and LVCMOS input/routing offsets differ. Wait for histogram-clear completion before collecting calibration. The stored LUT banks are not automatically replaced by a source change.
- Rebuild/reload FPGA plus API and SCPI server; the static SCPI link embeds the API. The source-refresh helper now includes all rtl/tdc_*.sv dependencies. Verify ID 0x54444306 and query INPUT before acquisition; PCB width acquisition uses TDC:WIDTH:* instead of the legacy MEASURE command.

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

1. Back up the working project/image. In the existing GUI project, source prj/v0.94/scripts/refresh_custom_sources.tcl from this repository. Per the user's preference, it now uses import_files -force -norecurse -flat to copy all rtl/tdc_*.sv dependencies plus pulse_gen and bnet_axi_reader_ch, the merged red_pitaya_top_LED7_mod.sv, and the four Gen2/custom XDCs into <project>.srcs/sources_1/imports/ and <project>.srcs/constrs_1/imports/. It replaces matching file membership, selects the imported top, disables competing top source copies, sets constraint use and board defines, and removes SCOPE_ONLY. Later workspace edits require rerunning this script; project copies are not live references to the repository. It prints each imported path and does not launch runs. Retain prior ASG declaration/enum corrections.
2. Set top module red_pitaya_top from red_pitaya_top_LED7_mod.sv; remove/disable competing top definitions in that fileset. Set Z20_G2 and Z20_xx, preserve other required defines, and leave SCOPE_ONLY absent for the full feature build. Confirm DWE=11 and PS GPIO width 33.
3. Add/update constraints in the active constrs_1 set. Keep existing board/clock/pin XDCs and avoid duplicate imported copies:

| Constraint under prj/v0.94/sdc/ | Synthesis | Implementation |
|---|---|---|
| pulse_gen_Z20_G2.xdc | OFF | ON |
| tdc_Z20_G2.xdc | OFF | ON |
| bnet_reader_Z20_G2.xdc | OFF | ON |
| tdc_placement_selected.xdc and a separate width placement XDC, when generated | OFF | ON |

The two updated Z20_G2 build Tcl entry points include the pulse/TDC constraints for a non-SCOPE_ONLY v0.94 build, and include the selected-placement XDC if it exists. Existing GUI projects need their files/properties refreshed manually.

The project-copy refresh was checked with Tcl mocks and actual file copies in a temporary folder: all imported files matched repository bytes, a second refresh replaced a stale copy without duplicate membership, imported top/XDC properties were correct, and an existing selected-placement reference and user defines were preserved. This did not run Vivado or modify the saved project.

4. Keep testbenches out of Design Sources. Use Xilinx UNISIM for Vivado tests. Never add tbn/pulse_gen_oddr_model.sv, tbn/tdc_carry_chain_logic_model.sv or tbn/tdc_carry_chain_timing_model.sv to a Vivado fileset. The latter is only an ideal tap source for the standalone controller test, not a physical TDC model.
5. Elaborate/synthesize. Confirm i_pulse_gen, i_tdc, i_bnet_regs, one selected H16 IOBUF, the single slot-7 response driver, bus period 8 ns and pulse ser_clk period 4 ns.
6. For a standalone pulse-generator test, new TDC manual placement can be skipped. Vivado can automatically place its instantiated logic. Keep existing timing/placement constraints. This does not establish calibrated TDC performance.
7. The placement helper now sets tap FF BEL before LOC in both the live procedure and emitted XDC. Its tap-name selector also accepts Vivado's generated gen_tap[index].i_tap_ff hierarchy. No placement coordinates were selected here.
8. For TDC work, open the synthesized design and source prj/v0.94/scripts/tdc_placement.tcl. Each chain has 128 CARRY4 / 512 tap FDRE cells: legacy i_tdc/i_carry and new width i_tdc/i_width/i_carry. Choose separate legal columns/start rows or recover a compatible prior placement. The helpers default to the legacy chain; pass i_tdc/i_width/i_carry as the final argument for the new chain. Generate separate placement XDCs, add both to constrs_1 with the properties above, and retain them with the image's calibration. Do not overwrite one chain's placement file with the other. No selected placement was found or chosen here.
9. Reset stale implementation runs, implement, and inspect timing summary, clock interaction, CDC, exceptions, DRC, I/O and hierarchical utilization. Source scripts/check_custom_constraints.tcl in the open design to verify 128 carries / 512 tap D pins for each chain, five width, six pulse and eight BNET first-stage synchronizers, and nonempty bundled-data collections. Verify the 4 ns mailbox and 8 ns readback bounds remain effective; do not blanket-false-path the pulse clock pair. Check ODDR IOB placement and direct Q-to-IOBUF connectivity, LVCMOS33, FAST slew and the existing drive setting.
10. Confirm RAM inference/resource use and ordinary 250 MHz pulse paths close. Produce an identifiable bitstream only after applicable checks pass. Controlled TDC placement constrains locations, not all routed delays; calibrate the resulting image.

AMD constraint-order reference:
https://docs.amd.com/r/2024.2-English/ug912-vivado-properties/BEL

AMD 7-series carry architecture:
https://docs.amd.com/r/en-US/ug474_7Series_CLB/Carry-Logic

### Timing repair and retained legacy delay test

The saved 2026-10-14 run reported unsupported Tcl if blocks in the two custom managed XDCs; its worst -10.290 ns path ended at an asynchronous carry tap. The tap selector also assumed a slash where the synthesized generated hierarchy uses a dot. Both custom XDCs now contain supported constraint commands with no control flow, and the tap pattern is corrected. Only tap D measurement inputs and documented first synchronizer stages/reset synchronizer CLR inputs are exempt. Encoder, controller, FIFO, clocks, functional reset release and ordinary datapaths remain timed. No global asynchronous clock grouping is applied.

The remaining real paths were addressed in the pulse counter and BNET scheduler/debug transfer as described above. The Gen2 E3 receive clock now uses the P pin only, fixing the previous two-source clock warning. These source changes are an attempted timing repair; they are not a timing-closure result. Refresh the files, reset old synthesis/implementation runs, rebuild and inspect the new report. Resolve any non-measurement negative slack before accepting operation.

Use the width burst procedure in section 7 for the PCB's voltage-dependent HIGH duration. The following optional legacy test measures launch-to-return rising-edge delay and does not validate the new pulse-width function. After the new image passes the applicable implementation checks:

- Verify current TDC ID 0x54444306 at 0x40710000 and NUM_TAPS 512 at 0x40710018; verify pulse ID 0x50554c01 and tick 2 as well.
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

1. Refresh project-local source/constraint copies with scripts/refresh_custom_sources.tcl in the existing Vivado project on the build machine. Reset the old runs, rebuild and inspect timing/CDC/DRC and utilization, including BRAM inference for the width buffer. Do not run Vivado on this laptop.
2. Resolve the previously reported timing failures in a fresh implementation before accepting the merged image. Check the grouped encoder's ordinary 250 MHz paths and compact-result RAM inference/utilization. The updated collection checker requires RAMB primitives under i_tdc/i_width. Check both carry hierarchies and select separate legal placements before fine calibration. Local syntax/logic checks do not prove timing closure.
3. Load the new image and rebuild/redeploy the matching API and statically linked SCPI server. Verify TDC ID 0x54444306 at 0x40710000, width ID 0x50574201 at 0x40710100, and the pulse feature ID before SCPI tests.
4. Wire E1 pins 1/2 for +3.3 V, 25/26 for common ground, pin 5 to the PCB trigger, and the PCB's 3.3 V return to pin 7. PCB power is automatic. No E3 launch pair is needed.
5. Run a short width test first, then scpi-tests/tdc_pulse_width_test.py BOARD_IP --count 16384 --csv tdc_width_16384.csv --quiet (1 MHz / 50%, SINGLE). Compare widths against an oscilloscope at several analogue voltages; inspect flags and verify output HIGH/LOW and restart behavior. Use --frequency 100000 for a slower run.
6. Characterize coarse accuracy, narrow HIGH/LOW detection limits and separate rise/fall LUTs. Width acquisition above 1 MHz requires further HDL work and verification; the pulse generator's faster standalone settings do not establish TDC support at those rates.

Outstanding broader work:

- Full generated-IP vendor elaboration, CDC/timing/DRC and resource acceptance for the merged image.
- Select and inspect a legal controlled TDC placement; no selected-placement XDC has been generated here. The helper BEL/LOC ordering and tap selector are now corrected.
- Fresh BNET engine-specific regression with correct SDF multi-bank payloads and explicit per-start bank selection; validate cold/warm counters before throughput claims.
- TDC source fixes and third-stage crossing changes need fresh hardware tests; re-characterize coarse ambiguity and missing-code regions against the new placed/routed image.
- Exact Linux/ARM API/server build identity and successful live pulse SCPI remain unverified. The running server recognizes PULSE:OUTPUT and reports the hardware-signature failure.
- Actual PCB receiver specifications, pulse electrical performance, exact supply startup demand and independent-power sequencing remain unconfirmed.

Maintain this file when new evidence arrives. Record source/image identity, tool version, test scope and measured results; retire superseded instructions instead of accumulating contradictory status sections.
