# Red Pitaya master handover

Updated: 2026-10-22. Target: STEMlab 125-14 Z7020 Gen 2 / Z20_G2, xc7z020clg400-1; existing Vivado project uses 2020.1.

This is the authoritative workspace handover for BNET, the CARRY4 TDC (currently focused on single-ended input), and the single-channel GPIO pulse generator. It replaces the separate BNET and pulse handovers. Repository source, public headers, command tables and the TDC register specification remain the detailed interface references.

## 1. Current objective and working rules

### Local calibration storage and Ubuntu sync (2026-10-22)

Calibration captures/LUTs,plots,local HDL review/tool folders and simulation
output have been moved outside the API/SCPI repository to:
**`C:/Users/kairan/RedPitaya_local_data/RedPitaya_app`**.

- Preserved original relative paths: `scpi-tests/tdc_rigol_results/`,
  `scpi-tests/tdc_external_square_results/`, `scpi-tests/tdc_sine_results/`,
  `build/`, `xsim.dir/`, Python cache and five root-level TDC JSON reports.
  **12831files /459385209bytes** moved and verified by SHA256; no calibration
  measurements/LUTs discarded. Manifest:local root's
  `relocation_manifest_20261022.json`. Full executed copies of five notebooks
  are in `executed_notebooks/20261022_before_cleanup/` before clearing outputs
  in the repository's active notebooks. Notebook code/settings are retained.
- All historical `build/...` and `scpi-tests/tdc_*_results/...` paths below now
  resolve relative to that local storage root, not the source checkout. This
  includes the passing v12 bitstream/checkpoint, v13 archive and v14 manifests.
  Archived scripts/JSON retain their original paths as historical evidence;
  rebase machine-local tool paths if rerunning those scripts. Do not create
  symlinks/junctions from the repo to the archive that bulk sync might follow.
- `scpi-tests/local_data.py` resolves future output locations outside the
  checkout. Windows default is the path above; Linux default is
  `~/.local/share/redpitaya/RedPitaya_app`. Override with an absolute
  **`REDPITAYA_DATA_DIR`** before launching Jupyter/CLI. In VirtualBox, point it
  at a shared host storage directory if measurements must not consume VM disk.
- Rigol,external-square andPCB-sine notebooks use this external result root.
  Legacy calibration/MMCM CLI default JSONs also go there. Pulse-width CLI
  relative `--csv` paths go under `scpi-tests/tdc_width_results` in local data;
  an explicit absolute output path is honored. One-time notebook migration
  backups use the external `build/tdc-calibration-backup` directory.
- Restart notebook kernels and rerun setup before further captures; an old
  `RUN_DIR`/Bench in memory still points at the previous repository directory.
  Generated-result/cache patterns are ignored by Git. Tracked old result and
  simulation artifacts now appear as deletions: include those removals and
  the new path helper in the next commit for Git-based Ubuntu sync to receive
  the cleanup. Ignore rules alone do not untrack previously committed files.
  No commit/history rewrite or Ubuntu deletion was performed here. Existing
  Git history can still contain old blobs; this migration frees the checkout.
- API/SCPI calibration implementation,source notebooks and scripts remain in
  the repo for builds. No HDL/API protocol,instrument behavior or qualification
  gate changes. Notebook/Python syntax parsed; relocation verified, no tests,
  instruments,builds or deployment run for this storage migration.

### Input priority: single-ended active; LVDS temporarily deferred

- User decision, 2026-10-21: focus development, timing repair, characterization
  and calibration on the **3.3 V single-ended input**, which the user reports
  already provides good resolution and low noise. Further LVDS work is
  temporarily suppressed and is not a prerequisite for single-ended progress.
- Use **DIO2_P / E1 contact 7** for the return or direct AWG input, with common
  ground on E1 contacts 25/26. Use **DIO1_P / E1 contact 5** as the FPGA launch
  reference. Explicitly select `TDC:INPUT SINGLE` while idle and confirm
  `TDC:INPUT?` after loading/resetting hardware; the retained HDL reset default
  may still select LVDS.
- Defer LVDS bring-up, termination/placement optimization, calibration and
  external differential-link tests until the user resumes that work. Retain
  its HDL, API support, wiring notes and historical results for future use.
  This is a work-priority change in this handover, not an HDL disable or a
  change to the hardware reset default.
- Prioritize single-ended timing closure, fresh separate RISE/FALL fine LUTs,
  width bias/jitter/tails, narrow-pulse limits and launch/return synchronization.
  Keep AWG period = FPGA launch period = acquisition frame duration. Document
  measured performance for the actual input/build; the user's observation is
  not a claim that remaining timing, accuracy or synchronization issues passed.
- The current priorities above supersede LVDS recommendations in the retained
  legacy sections below. Do not switch back to LVDS as a routine next step.

Active source is now **VERSION14 / ID0x5444430e**, based on the timing-passing
v12-timing-r1 capture with a fixed frame-offset timer. V14 is source-ready,
not implemented or loaded by the assistant; new routed WNS is unknown. The
preserved v12 baseline passed WNS+0.031ns/0setup/hold failures,WIDTH+0.110ns.
That result must not be attributed to V14. Latest observed hardware was v12.
BNET remains excluded; single-ended input remains the active focus.

### October 22: V14 fixed frame offset from passing v12 (active source)

- User requests phase compensation based on v12 while preserving timing.
  Preserved original v12 sources and all changed software/notebook files,
  passing .bit,routed .dcp and timing summary under
  `build/hdl-review/20261022-v14/passing-v12-source/` and `passing-v12-build/`.
  `baseline_manifest.json` records hashes. No git reset or v13 restore.
- New `tdc_frame_delay.sv` registers each delayed launch marker;offset0 retains
  the original second-marker-FF sampling latency. A 16-bit byte-wise counter,
  registered carry and two registered8-bit comparison halves bound feedback;
  zero/one/offset-2 are precomputed on the bus side. Held config is captured
  on ARM. Offset<period is registered before controller validation. No new
  timer arithmetic/equality cone drives the state combinationally. Timer
  overrun returns RATE_ERROR. Actual launches drive the timer,not a free-running
  synthesized source. No sampling/raw-vector/timestamp pipelines retimed.
- `TDC:WIDTH:OFFSET ns` / `OFFSET?`,APIrp_TdcWidthSet/GetFrameOffset. Idle-only,
  multiples4ns,0..262140ns,strictlyless than the launch period,FPGA-reset0.
  Register0x158ns andfeature0x15c=0x46524d01 relativeTDCbase0x40710000.
  VERSION14 uses v12 record packing/single-frame pairing,not v13 spill/latency
  features. API and clients now gate DELAY/LATENCY to exactVERSION13;v14 uses
  capability-checked OFFSET. Matching API/header and SCPI rebuild/deploy needed.
- AWG/source period = launch period = full acquisition frame duration remains
  mandatory. Offset moves boundaries into LOW; choose margin for all pulse
  widths and jitter from scope measurements. ExampleT1004,rise800,fall1500,
  offset600 -> frame[600,1604),width700. This is an example,not a measured offset.
  V14 still rejects pulses cut by the shifted boundary. Fixed offset requires
  stable relative phase; it does not lock clocks or prove launch causality.
- Rigol notebook expects14,hasFRAME_OFFSET_NS plusperiod-keyed overrides;
  everycapture programs/readbacks/logs offset. Original outputs archived before
  clearing the source notebook. Helper still restarts continuous sources with
  AWGINT reference,so one fixed offset does not automatically fix independent
  AWG startup/drift. No automatic retry/selection/gate relaxation added. Scope
  phase must apply to the actualcapture. Fine phase coverage remains separate.
  CLI adds--frame-offset-ns;sine helper acceptsconfigframe_offset_ns.
- Carry chains,sampler placement,encoder population policy,width arithmetic,
  BRAM packing,capacity andrate limits retain v12. ASG/decimator timing repairs
  from the passing baseline retained. No clock,maximum-delay,false-path or
  multicycle relaxation. Refresh copies/verifies the new timer with allRTL
  inside Vivado project directories; checker/diagnostics include frame timer.
- Static full-top compilation:139sources,0errors,33existingwarnings;
  Python/notebook AST/JSON parsed. Further static/source checks and hashes
  are recorded in `build/hdl-review/20261022-v14/source_manifest.json`.
  No Vivado,synthesis/implementation,behavioral tests/simulation,API/SCPI build,
  instrument commands or deployment performed. New WNS/resource use/CDC and
  hardware phase compensation remain unverified. Implement externally,check
  timing/layout,load identified14 and collect fresh RISE/FALL LUTs.

### October 22: identity qualification blocked by 700.2 ns frame cuts

- Latest run `scpi-tests/tdc_rigol_results/20261022T093129_360386Z` reports
  VERSION12. Build label is still a placeholder/WNSnull; do not rewrite saved
  metadata as proof of a unique loaded image. Common period1004ns,launch HIGH
  502ns. The acquisition frame is the full1004ns,not the launch HIGH interval.
- Baseline now passes8192/8192complete,bothfineedges100%valid,coarse mean
  501.866ns versus500.2ns AWGreadback,SD1.996ns. Fine LUTs remainOFF.
  DC LOW correctly returns0/4096complete withflagsNO_RISE|NO_FALL.
- Identity100.2ns:4096/4096complete,coarse mean101.820ns,error+1.620ns;
  300.2ns:4096/4096complete,mean301.534ns,error+1.334ns. Both edges100%valid.
  700.2ns:0/4096complete,allflags0x081c=HIGH_START|EXTRA_EDGES|NO_FALL|SATURATED.
  All acquisition/status/count/integrity/cleanup checks pass. Identity gate
  fails only because700.2ns has no complete samples,not a measured wrong width.
- Same known v12 boundary/phase limitation as the previous baseline failure.
  Alignment restarts yield1024/1024,1024/1024,0/1024,1024/1024. Helper restarts
  bothsources at everypoint. A700.2ns pulse has approximately303.8ns available
  RISE placement within1004ns before detection offsets/margins. Scope phase
  confirmation/repeatable startup is still needed; no claim that700ns itself
  exceeds v12 width capacity or that physical phase was independently measured.
- Notebook now surfaces actual `SIGNAL_IDENTITY.errors` in its exception and
  distinguishes missingcompleteframes from wrongsignal/DC failures. Corrected
  stale1000ns/500ns prose to actual commonperiod policy. Criteria and equal
  periods preserved; no retries/filtering/waivers added. Original notebook
  archived beside captures; `identity_failure_review.json` records this review.
  Notebook JSON/code AST parsed; no tests,HDL changes,instrument commands or
  calibration/LUT upload performed. Synchronization remains the next work.

### October 21: matched-period baseline stopped before calibration (22:34 BST)

- Latest run `scpi-tests/tdc_rigol_results/20261021T213344_059638Z` reports
  VERSION12,512taps,4000psticks. Image label remains a placeholder and WNSnull,
  so this run does not independently prove the uniquely loaded bitstream.
- Alignment restarts00/01/02 each return1024/1024complete,withbothfineedges
  valid; coarse means501.961/502.297/501.465ns versus500.2ns AWGreadback.
  Restart03 returns0/1024complete. The following baseline returns0/8192complete.
  All requested records were returned;statusDONE=8,record integritypasses,
  acquisition_oktrue,cleanupempty. Calibration stops at the minimum100complete
  pulse gate, not a transport/count/integrity or fine-LUT upload failure.
- Every failed frame hasflags0x081c=HIGH_START|EXTRA_EDGES|NO_FALL|SATURATED.
  This is consistent with a frame startingHIGH,anoldpulseFALL arriving before
  its trackedRISE,andthe nextRISE's FALL landing beyond that frame. V12 rejects
  this sequence. Raw indices/width zero on invalid records do not prove missing
  input transitions: invalid frames skip fine encoding. Scope confirmation of
  relative phase is still needed; flags alone do not establish physical timing.
- Requested997003Hz is snapped to1004ns/996015.936Hz forbothinstruments;
  FPGAreadback1004ns,AWGperiodquery1004.1ns,FREQquery996015.936254Hz.
  The two AWG readbacks differ within recorded quantization; neither is an
  independent measurement of physical drift/clock lock. Source remainsINT.
  Helper reconfigures/restarts bothoutputs for eachacquisition,soalignment
  survey success is not carried into baseline. Equalperiod does not set phase.
- Next software/bench work: establish repeatable phase/startup while retaining
  the common period; inspectDIO1_P andDIO2_P together. V12 has no programmable
  frame delay or cross-frame retention. Do not waive calibration gates,detune
  frames,automaticallyretry/discard failures,orclaim LUTcalibration fixes this.
- Updated `quality_guard` to report exact failingconditions,completecount and
  flags,withv12-specific phase guidance. Acceptance criteria stay the same.
  Original notebook error and saved captures preserved. No HDL,hardware
  commands,tests/simulation or deployment in this review.

### October 21: v12-timing-r1 routed report review (22:18 BST)

- Read the current impl_1 routed timing, route status, DRC/methodology and
  placed-utilization reports. Setup WNS **+0.031ns**, TNS0,0failing endpoints;
  hold WHS **+0.010ns**, THS0,0failing endpoints; pulse-width WPWS+0.750ns,
  0failures. Original v12 was -0.071ns/6setup failures; v13 was -1.997ns/6067.
  Current 250MHz pll_ser_clk setup+0.110ns/hold+0.017ns. All41907routable nets
  are fully routed,0routing errors. Standard routed DRC has60warnings,0errors.
- Worst displayed setup path is legacy histogram write-index -> distributed
  histogram data, +0.031ns,7.411ns datapath with78%routing. Worst WIDTH-group
  setup is rise_sampler_rstn -> tap504..507 synchronous R,+0.110ns. These
  margins are small but positive for this routed image; they are not fine
  resolution/accuracy measurements or a guarantee for another implementation.
- All10checked project-owned copies match repository bytes:WIDTH,registers,
  encoder,carry,top,pulse,ASG,decimator,TDCmailboxXDC andsamplerlayoutXDC.
  Placed use:17909LUTs(33.66%),28916FFs(27.18%),86BRAMtiles(61.43%),22DSPs(10%).
- Timing pass is limited to active constraints. check_timing still reports
  1unclocked DNA clock,2unconstrained internal endpoints,26inputs and58outputs
  without complete delay coverage. Methodology has7critical warnings:6clock
  relationship warnings across par_clk_1/pll_adc_clk and pll_adc_clk/clk_fpga_0,
  plus the unclocked DNA cell. Additional CDC/synchronizer warnings, broad
  false paths between synchronous clocks and4overridden max-delay datapath
  constraints remain. Do not call this complete CDC/I/O/constraint signoff or
  silence those warnings with blanket false paths. No XDC/HDL edited here.
- Bitstream exists at `C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/redpitaya.runs/impl_1/red_pitaya_top.bit`,
  generated22:25BST,2506992bytes,SHA256
  `fa5db9b5aae4ab352f320e764f2882f0078e9ed4357f4910268ad7baab0f5bed`.
  Preserve this image/report/source association. Next hardware work: load the
  identified image,verifyVERSION12,selectSINGLE,inspect sampler placement and
  collect fresh RISE/FALL LUTs with matched source/launch/frame periods. V12
  boundary-cut rejection remains; synchronization is not solved by timing pass.
- Archived report copies,bit/source hashes and parsed paths in
  `build/hdl-review/20261021-v12-return/routed-review/review.json`. No Vivado,
  simulations/tests,instrument commands or programming performed in this review.

### October 21: user-requested v12 rollback and limited timing repair (active)

- Preserved all21files listed by the v13 source manifest, including HDL,
  software and notebook, under `build/hdl-review/20261021-v12-return/preserved-v13/`.
  `preserved-v13.json` records original paths and SHA256. Historical captures,
  original v12 backups and routed reports remain intact. No git reset used.
- Restored `tdc_pulse_width.sv` and `tdc_registers.sv` from saved pre-v13 files;
  core TDC source is unmodified from that v12 snapshot. No encoder, physical
  carry chain, sampler layout, pulse generator or top-level wiring changes.
  Restored v12 mailbox XDC/checker collections and existing bench expectations.
  Active ID0x5444430c. No cross-frame retention/return-window/latency support.
- Only timing edits beyond v12 are local scope decimation/averaging config
  registers and combinational ASG pointer arithmetic. ASG now compresses
  p+step+~size before a short carry-select adder, preserving modular arithmetic
  and live configuration without the v13 cached wrap step. Normal pointer
  uses the same segmented adder. Scope configuration settles one ADC clock
  before ARM. No timing exceptions relaxed. These target precisely the two
  scope/four ASG endpoints reported by v12; closure still needs implementation.
- Rigol notebook restored from the saved same-period v12 version, outputs
  cleared after preserving v13. Helper defaults to12 and calls return-bound/
  latency commands only for13+. Existing v12 API/server is sufficient; optional
  v13 extensions remain version guarded for future work. Same nominal AWG,
  launch and acquisition period remains mandatory. V12 rejects boundary-cut
  pulses, so synchronization and one complete return per launch remain open;
  partial-yield results are saved, not retried/filtered into a pass.
- Interface VERSION12 is not a unique build ID: label the new bitstream
  v12-timing-r1 plus actual build/hash, enter new routed WNS and calibrate fresh
  RISE/FALL LUTs after loading. Do not reuse old LUTs or claim old WNS for it.
- Full v13 endpoint export parsed:6067unique endpoints,5937insideWIDTH.
  Large groups include snapshot RAM controls/read selection, encoder load/CE,
  sampler reset distribution and result broadcast, as well as the worst new
  config-validation/controller cones. Classification is archived in
  `build/hdl-review/20261021-v13-routed/full_classification.json`.
- No Vivado, behavioral tests/simulation, instrument commands or deployment.
  Full-top static compilation:138sources,0errors,33existing warnings. Python/
  notebook AST/JSON and Tcl structural checks pass. Restored capture/register
  bytes match their saved pre-v13 copies; encoder/calibration/top/register
  hashes match the saved v12 manifest. Results and source hashes are recorded
  in `build/hdl-review/20261021-v12-return/source_manifest.json`.

### October 21: V13 implementation regression review (latest report, no source repair yet)

- Latest standard impl_1 routed summary is now the October21 16:35 report: WNS **-1.997ns**, TNS **-3157.159ns**, **6067** failing endpoints; WHS+0.015ns,0holdfails. Previousv12 was -0.071/-0.159/6. This is a substantial regression. Source VERSION13 remains unchanged and no HDL repair was made during this review. Board loaded version is not newly checked.
- Intra250MHz pll_ser_clk: WNS-1.702,TNS-3124.109,5939failingendpoints. pll_adc_clk:WNS-0.564,TNS-30.905,118endpoints. ADC->SER config maxdelay:WNS-1.997,7endpoints. Pulse reset recovery:WNS-0.024,10endpoints. Group counts need not sum to global unique endpoints. The summary provides only37detailed violating examples, so do not assign all6067 to those examples without a full endpoint report.
- Confirmed new-v13 critical cones: delay_max_cfg[0] -> 16bit subtraction/wide period comparison -> state,6.026ns/12levels/7CARRY4 vs4ns maxdelay; state[1] -> phase_running/frame_marker -> flags/control -> state[1],5.668ns with4.468nsrouting,6LUTlevels,statefanout86. My v13 controller structure introduced these paths; unchanged sampler fine-bin ordering is not the cause demonstrated here. Need held-payload setup/validation stages, registered frame markers with matched raw-edge/timestamp latency, simpler state transitions/encoding and local registered capture/process/reset enables before another build. Do not relax clocks/maxdelay/false paths to hide failures. Many downstream failing endpoints may share control roots; full classification still needed.
- Additional displayed paths: scope filter pp_mult DSP CLK->P clock-to-output4.009ns -> fabric carry subtract -> DSP B,slack-0.564; legacy encoder_start->shiftreg[167],slack-0.325,91.21%routing; legacy launch_period->idle_period_counter CE,slack-0.319,14levels/9CARRY4; pulse_gen fast_reset_pipe[2]->active_high/periodCLR recovery -0.024. ScopeIIR feedback must be retimed with its transfer function preserved; legacy control needs localized/registered enables; pulse reset needs local distribution/synchronous data control without suppressing recovery timing. Old ASG/decimator paths are not among displayed worst examples, which does not prove every one is fixed.
- Byte comparisons confirm all4main project-owned imports match current repository files:tdc_pulse_width.sv,tdc_registers.sv,red_pitaya_asg_ch.sv,rp_decim.v. New features also appear in failing-path names. Resource utilization35.33%LUT,28.01%FF,61.43%BRAM,10%DSP; not a capacity overflow. Physical local routing/fanout can still be problematic. Existing `tdc_width_diagnostics` reports are OLD (summary-5.754/39710withBNET) and must not be mixed with this build.
- Saved latest routed report snapshot,37parsedexamples and quantified review/import hashes in `build/hdl-review/20261021-v13-routed/`. No Vivado, tests/simulations, hardware commands or HDL edits in this review. Need full current per-endpoint max timing report before claiming a complete6067-path classification; obtaining it requires read-only reporting from the already routed design, not a rebuild. Fine LUT calibration cannot repair these synchronous controller failures.

### October 21: V13 launch-associated acquisition and remaining setup repair (source ready, not built)

- User authorizes a new bitstream and necessary API/server changes, and additionally asks to repair the remaining timing failures. Latest loaded hardware is still v12; current SOURCE is now VERSION13 / ID0x5444430d. Do not mistake new source/version expectations for loaded hardware or reuse old fine LUTs. BNET remains disabled/source retained. Do not run Vivado on this device.
- V12 matched-period run `20261021T134927_260213Z`: preflight v12 passes, baseline8192/8192 valid with both fine edges100%; first identity attempt has100.2/300.2ns4096/4096 each but700.2ns0/4096, rerun reverses to100.2/300.2ns0 and700.2ns4096/4096(mean703.0898ns). DC0V correctly0both attempts. Failed frames uniformly0x081c = HIGH_START|EXTRA_EDGES|NO_FALL|SATURATED. Integrity/cleanup pass. V12 frame-local edge pairing explains how a FALL-before-RISE straddle can reject a whole matched-rate burst; independent AWG phase is uncontrolled. This is separate from the earlier remote connection reset and missing-feature errors.
- V13 `tdc_pulse_width.sv` accepts RISEs in programmable [launch+Dmin,launch+Dmax), preserving period T. Two live contexts retain the corresponding FALL across the following frame boundary, finalizing at origin+2T; one ordered record per requested tracked launch, including missing/invalid returns. A FALL at that final deadline is accepted. Unassociated/pre-burst FALLs ignored, duplicate/overlapping RISEs and simultaneous opposite-edge observations flagged. Raw/metadata memories retain single write ports; four staging slots guarded; last pulse has two-origin drain and timeout flush handles both contexts. Real-launch credits prevent a stopped source from inventing records. Whole-cycle Dmin supported by a phase timer anchored to first actual launch. Stable period checked; stopped/aborted/rate-invalid bursts fail explicitly and may return partial records. Existing 500ns minimum, parallel population encoders, sampler macros, capacity16384 and coarse HIGH/LOW>=8ns detection limitation unchanged; no50MHz/streaming claim.
- New idle registers0x14c/0x150 in TDC base0x40710000: min/exclusive-max in4ns ticks0..65534; min<max,span<=T. Explicit configuration required before ARM (reset max65534 usually too wide). New0x154 selected-record coarse marker-to-RISE ticks,FFFFunavailable. No fine/pin-delay calibration is applied. A known delay may contain whole periods, but independent bounds/trigger causality are needed to prove launch association; periodic waveforms alone cannot identify the correct integer-cycle offset. Frame cadence remainsT even if the RISE gate is narrower. New flags13LATENCY_OVERFLOW(info,width may remainvalid),14CROSS_FRAME(info,VALID permitted),15RETURN_LATE(frameerror). Existing six-field struct/SCPI record ABI unchanged. Compact storage reclaims coarse high bits:21coarse+16latency,104bits/record default, still3x36-bit BRAM lanes per1024bank. OUT_OF_RANGEinvalid coarse field retains low21bits only; width0.
- API additions `rp_TdcWidthSetDelay/GetDelay` in ns (4ns grid,0<=min<max<=262136), `rp_TdcWidthReadLatency` ticks. SCPI `TDC:WIDTH:DELAY min_ns,max_ns`, `DELAY?`, `LATENCY? start,count` (1..128). Version guard13 for new features. API/HDL both check rise-window span; return-late added to record-consistency errors. Updated rigol helper/notebook expects13, sets/reads bounds each acquisition, reads latency with ready polling and consistency checks, saves latency columns in raw CSV and statistics in JSON. Defaults fullT for free AWG; hardware still does not configure AWGexternal trigger/reference. Scope observation does not auto-program bounds. Identity/density qualification now requires100%complete records; diagnostic survey retains failures without retry/filtering, existing fine/CDF/LUT gates preserved. Full-period AWG tests with this bounded latency interface need T<=262136ns; slower tests require an explicit narrower gate. Shared sine acquisition helper/CLI now configure v13 bounds while preserving older version support.
- Preserved current completed notebook at `scpi-tests/tdc_rigol_results/20261021T134927_260213Z/completed_notebook_before_v13.ipynb`; original captures untouched. Revised active notebook outputs cleared. Previous archival copy before period matching also retained. Earlier statements below that timestamps/phase control are absent describe V12, not current V13 source. `tdc_registers.md` now specifies scheduling, registers/flags, limitations, calibration and deployment.
- Latest available timing is still V12 October21 13:04:WNS-0.071ns/TNS-0.159ns/6setupfails/0holdfails. Two failing scope paths indep_mode->decimation mux/17-bit compare->adc_sum29/31; `rp_decim.v` now locally registers decimation/averaging config, one ADC-clock setting settle before ARM, unchanged steady-state sample/valid arithmetic. Four ASGpaths dac_pnt0->dac_pnt1/2/A and48/49/B: ASG caches step-(size*2^32+1) with the same step updates as before; independent short carry-select additions produce normal/wrapped pointer, avoiding serial wide add/subtract feedback. Table size must settle before trigger. No ASG sample/start/wrap/stop priority change or relaxed timing exceptions.
- `refresh_custom_sources.tcl` still imports byte-verified PROJECT-OWNED copies and now includes `rtl/classic/rp_decim.v`. Source identity text/checker/diagnostics reflect v13; existing mailbox max-delay constraints extended to delay payload with the same4ns limit. No new false paths/clock groups/multicycle relaxation. Must refresh external Vivado project, reset synthesis/implementation, build externally, audit sampler layout and global timing/DRC/CDC, deploy matching API/server+identifiedbitstream, then run fresh qualification/LUTcalibration from clean kernel. No source-copy refresh or board deployment was performed here.
- Accepted RISE latency is retained even for an invalid width (e.g. NO_FALL); NO_RISE or LATENCY_OVERFLOW determines availability, not VALID alone. Helper checks latency/flags and configured bounds. New latency adder is only17bits with separate upper-bit overflow registration; eligibility threshold is locally registered; marker arriving exactly at watchdog deadline restarts it. Existing benches were adapted for required v13 gate configuration/ID and revised HIGH_START/boundary expectations only; no test cases added and none executed.
- Static final validation: full-top Slang12 with138sources/actual primitive declarations and DISABLE_BNET, generatedPS/IPexternal:0errors/33existingwarnings; Python/notebook AST/JSON and Tcl/XDC structural checks passed. No tests, simulations, Vivado, instrument access, source import or board deployment ran. C++/ARM build was not performed: installed WSL distributions lack g++; deploy/build API first, then matching SCPI against updated installed headers. New routed WNS and hardware qualification remain unverified. Source hashes, checks and last six timing paths are recorded in `build/hdl-review/20261021-v13/source_manifest.json`.

### October 21: matched source / launch / acquisition period contract

- Latest user requirement overrides earlier asynchronous-window advice: every new test and future HDL operation must use the same nominal AWG/source period, FPGA launch period and TDC acquisition-frame period. Do not shorten frames as a function of HIGH/LOW time, add a frame-period offset to walk phase, or drive overspeed AWG pulses into slower frames as a representative operating benchmark. At different rate test points, both instruments change together. Reject unsupported common rates. The current frame grid is 4 ns and minimum is 500 ns (2 MHz); 997003 Hz is requested but both instruments are programmed to a common 1004 ns / 996015.936 Hz nominal rate.
- Updated `scpi-tests/tdc_rigol_tools.py` and `tdc_rigol_characterisation.ipynb`: plan the common period once, verify both readbacks, retain requested/applied settings, and report frame completeness against a 100% operating target AFTER synchronization/alignment. Incomplete frames remain diagnostic evidence, not a predicted loss allowance. Added a software-restart alignment survey; it is not a commanded phase scan and cannot measure launch-to-return delay. Unsupported 5/10/50 MHz requests are reported without mismatched acquisitions. Existing signal identity, record integrity, LUT validity/sample/coverage/CDF and arithmetic gates remain. Historical and matched-period density captures cannot be mixed in one candidate.
- Equal nominal settings do NOT establish equal physical oscillator rates, phase lock or latency calibration. The helper still uses continuous PULSE output and the Rigol internal reference; shared reference, hardware triggering and controlled phase sweep are not implemented. `MEASURED_RETURN_DELAY_NS` records an independent scope observation only; no hardware delay correction is applied. Measure launch and return together at the FPGA pins to characterize fixed delay, width dependence, drift and jitter. Do not label a successful width calibration as launch-delay calibration.
- Current HDL already derives frames from pulse-generator cycle markers. Future HDL priority is explicit launch association, launch-relative RISE/FALL timestamps / frame IDs and programmable frame-origin phase while retaining the common period. Choose the period/phase with sufficient return-delay, maximum HIGH, recovery and margin; define cross-cycle latency association if needed. Present compact WIDTH ABI has no such timestamps or frame-phase register. Added this contract to `prj/v0.94/doc/tdc_registers.md` and the `tdc_pulse_width.sv` header; HDL changes this turn are comments only, VERSION12 unchanged, no new bitstream/API/server rebuild needed for these notebook changes.
- Fine code density still requires uniform input-edge phase across the 4 ns sampling clock. Equal periods alone do not guarantee it. Establish coverage using controlled input phase/delay sweep or characterized independent-clock drift without detuning source versus frame periods. Moving only the frame boundary does not move the input edge relative to the fine sampling clock. Keep quality gates and report unresolved phase/selection bias.
- Preserved the full completed historical notebook at `scpi-tests/tdc_rigol_results/20261021T122658_792319Z/completed_notebook_before_period_matching.ipynb`; all original raw captures/reports are untouched. Cleared outputs/execution counts in the revised active notebook so historical unmatched-period results are not presented as matched-period evidence. Earlier geometric fractions / overspeed results below describe the OLD protocol only and do not supersede this contract.
- Static Python AST and notebook JSON/code-cell parsing passed; no tests, simulations, Vivado or live instrument commands ran. Current hardware results and routed timing remain the previously recorded v12 results (global WNS -0.071 ns, six setup failures); this source-only workflow change does not improve or requalify that bitstream.

### October 21: completed V12 hardware characterisation

- Notebook executions69..84 complete all main cells including optional5/10/50MHzdiagnostic, no saved errors. End-of-run cleanup reports AWG/FPGA outputsOFF and widthidle. Actual VERSION12,4000pstapclock,512taps,16384reportedcapacity. Metadata still has placeholder bitstream label and WNSnull; do not rewrite historical metadata as a proven unique bitstream association.
- Independent replay of all116CSV captures:602112records,144024calibrated;0width arithmetic mismatches using saved candidate/uploaded tables (identical); saved acquisition/integrity/cleanup checks allpass. No +131072ps signature. All24density captures yield85189complete with RISE/FALL100%observedvalid,occupied ranks1..216/1..213,no missing runs,no exceptions. Both LUTs uploaded/readbackverified. This supports the v12 encoder repair on this setup; does not certify all patterns/environmental conditions.
- Fresh coarse/fine pairs near997kHz,500.2ns nominal: coarseSD1.617..1.622ns,fineSD0.208..0.213ns (7.58..7.79x reduction),fine means503.203..503.213ns (~+3nsbias). Inferred-phase-bin mean span falls~3.92..3.96ns to~21.8..23.6ps, but phase is inferred from the same calibrated RISELUT. Non-Gaussian tails persist:39/38/41fresh fine samples exceed1nsfrommedian; both normal and bubble-corrected statuses contribute. Central MAD~45ps at997003Hz is not a substitute for full SD/tail reporting. MeanLUTbin spacing~18.5/18.8ps is not achieved single-shot accuracy.
- Width sweep: fine mean error~+6.59ns at4.2ns,+6.86ns at5ns,+6.84ns at6ns,+6.28ns at8ns,+5.31ns at12ns,+3.99ns at20ns,then~+3ns for100..900ns. 4.2nsfine3491/3531complete calibrated (FALL98.867%valid);>=8nsboth edges100%observedvalid in this sweep, but widthbias remains. These results do not establish accurate4.2ns or arbitrarywhole-subclock measurement. Need scope widths at actual pin to separate AWG/reference/edge-response effects from HDL/inputpath causes; no cause asserted from these records alone.
- Small-step means are monotonic across17readbackwidths100..104ns;0.25nsrequested steps quantize to0.2/0.3ns AWGreadback. FineSD~0.316..0.339ns,so adjacent single-pulse distributions overlap. Local mean fit slope1.02128,residualRMSE38.9ps,minimum mean increment87.6ps; not an independent clock-scale or250pssingle-shotresolution certificate.
- All15frequency/duty cases100kHz..1.997MHz x10/50/90%complete with100%observedfinevalid; finite frame acceptance broadly matchesgeometry. FineSD across these cases0.110..0.718ns. This is not continuous detection efficiency/streaming. Overspeed5/10/50MHzall4096frames invalidEXTRA_EDGES each; expected multi-edge rejection,not50MHzoperation.
- Pasted section8 is HOSTONLY affine reference calibration after FPGA fine LUT correction: corrected_ns=1.000780165696304*measured_ns-3.432539966453961. Five training references20.2,100.2,250.2,500.2,800.2ns;20.2nsmean24.144ns(+3.944) is nonlinear versuslonger~+3ns, pulling globalfit. Its corrected training residuals+0.530,-0.403,-0.217,-0.039,+0.128ns show affine inadequacy. Held-out40.2/150.2/350.2/650.2nserrors improvefrom+2.846/+3.096/+2.970/+2.991ns to-0.553/-0.217/-0.187/+0.068ns; correctedSD0.336/0.334/0.387/0.295ns essentiallyunchanged. HostfitdoesnotalterFPGA/LUTs/earlierrawcapturedwidths. Nottraceable withoutindependentreferences; extrapolationfalse onlymeansinside trainingrange,unseencodes0meansLUTcoverage.
- Cell example20.25requested reads20.2nsfromAWG; frame880ns,sourceperiodreadback1003.1ns,expectedcomplete=(880-20.2)/1003.1=85.714%,actual3499/4096=85.425%. Fraction counts selected completeframes,not lost source pulses.0x01=VALID,0x21=VALID|BUBBLE_CORRECTED;calibrated3499meansFPGAfine correction applied before hostfit.
- New routed summary13:04local:WNS-0.071ns,TNS-0.159ns,6failing setup endpoints,WHS+0.015ns,0holdfailures. All6reportedviolations:2scope decimator,4ASGpointer; no histogram/WIDTH/PS failures in latest summary.250MHzpll_ser_clk WNS+0.044ns. Improvements fromv11 -0.437/-14.323/129 substantial butglobal timingstillfails; keepresultsprovisional. No Vivado or liveinstrument commands ran in this review; no tests/HDL/notebook edits. Saved derived analysis/overview `completed_run_review.json/png` beside captures.

### October 21: regional analysis and V12 source repair

- Read all265reports (88samplers x Q/async-max/async-min plus complete129-endpoint failing setup report) in `C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/tdc_width_regions_20261021_114302`. summary.txt has no skipped/failed queries. Console Timing38-91/38-78 messages are normal reporting progress. Sample-Q setup slack +0.494..+2.906ns. Main adjacent pairs RISE82/83,166/167,174/175,206/207 and FALL170/171 have data step-114ps slow/max and-25ps fast/min with0ps local clock step in both reported clock models. Placement is already verified correct. These are model bounds, not actual threshold measurements or proof of unique physical cause.
- Local threshold sweeps using each corner as a point model show reordered raw regions up to8taps in the selected neighborhoods. This supports an eight-tap bounded design choice, not a certified silicon limit. Strict majority+leading-one encoding can reject such reordered single-edge patterns and skip prefix codes. WIDTH now counts RAW ones with a balanced per-chunk population tree, and registers its final span decision. Its majority-filtered region from first zero to last one must fit8taps for a reversed code to be corrected (VALID|BUBBLE_CORRECTED); wider multiple transitions and raw all-zero/all-one still rejected. Numerical code is population rank, not a physical leading-prefix index. No host gate/threshold exceptions changed. Shared legacy encoder defaults to strict mode with unchanged latency/index semantics. WIDTH adds one decision clock, retains64+32-clock budget/default500ns frames. No old LUT reuse.
- Full129 endpoint classification:80legacy histogram,43ASG,4WIDTH,2generatedPS/IP. Legacy histogram now pipelines read/increment/write, forwarding both same-bin hazards including consecutive updates; clear flushes pipeline. Legacy calibration completion is delayed to ST_CALCULATE after the final histogram write drains. WIDTH compares watchdog in two registered16bit halves (same terminal cycle), and P_IDLE uses small staging occupancy instead of wide processed/captured comparison. ASG next-pointer sum is unconditional; the pointer register's enable/priority retains start/wrap/stop behavior and removes dac_do from arithmetic. PS/XADC endpoints not edited; all paths still require new routed assessment.
- Source VERSION12/ID0x5444430c, unchanged ABI/capacity/rate, no API/server rebuild. Refresh copies shared ASG along with all TDC dependencies and existing daisy/CDC repairs into project-owned files. Checker/diagnostics updated for watchdog halves, population/span registers and histogram pipeline. Notebook/helper source expects12 and notes fresh density/LUTs; original outputs, configuration and saved captures retained. Existing testbench ID expectation updated; no tests or behavioral simulations run for this repair.
- Static full-top Slang12:138sources, DISABLE_BNET, actual primitive declarations, generatedPS/IPexternal;0errors/33existingportwarnings. Tcl structure and Python/notebook AST/JSON checks pass. No Vivado or live commands run. Logs, parsed regional evidence, endpoint classification and source hashes: `build/hdl-review/20261021-v12/regional_analysis_and_repairs.json`. Physical recovery, 99% qualification, fine precision, BRAM inference/resourcefit and new WNS remain unverified. Next: refresh, implement externally, audit layout/timing, load identified v12 and run fresh calibration from a clean kernel. The source change does not remove the sampler's whole-subclock detection limitation or implement50MHz/streaming.

### October 21: actual sampler audit and diagnostic-script repair

- User pasted audit output reporting1024 lane mismatches with0unplaced cells. This was an audit-script formatting bug: Vivado2020.1 returned SLICEL.AFF/BFF/CFF/DFF; `[file tail $ff_bel]` did not remove the SLICEL. prefix. Replaced with leaf normalization after slash/dot; raw BEL remains preserved in TSV. No HDL/XDC/bitstream change or rebuild required.
- Independently read all1024 actual rows from `C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/tdc_sampler_layout_20261021_113535/placement.tsv`: all512RISE FFs and512FALL FFs colocated with expected carry and correct lane;128consecutive stages each. RISE SLICE_X37Y22..Y149; FALL SLICE_X60Y22..Y149. Corrected mismatch count0. Full Tcl audit replay against these actual rows reproduces old1024false errors, passes fixed version, and still rejects injected wrong location/wrong lane. Tcl normalization also checks unqualified, SLICEL/SLICEM and site-qualified forms. No Vivado invocation.
- This confirms macro locality in the current routed design. It rules out gross displaced sampling FFs as the explanation for remaining v11 rejects, but does not establish tap-arrival monotonicity or fix failed global timing. Next: run `inspect_tdc_width_regions.tcl` on current routed design for local clock/data reports; no rebuild needed. Review JSON: `build/rigol-tdc-review/v11_sampler_layout_review.json`. Saved original report unchanged.

### October 21: latest V11 hardware and routed-report review

- Latest run `20261021T095951_714523Z` preflight reads VERSION 11. All 24 density bursts finish with valid status/count/record integrity: 85473 complete pulses, RISE 84598 valid / 875 rejected = 98.9763%, FALL 85135 valid / 338 rejected = 99.6046%. Host upload qualification blocks at the existing 99% RISE gate AND uncharacterized missing triplets (RISE 83..85,167..169,175..177,207..209; FALL 171..173). No v11 LUT upload/fresh fine validation occurred. Section-5 execution-45 integrity error is retained v9 output; it is not this run's failure.
- V11 RISE improves from v10 92.6287% but remains worse than v9 99.9937%; code-2 reject cluster disappears and valid range returns to 1..218 (v10 84..294). RISE 844/875 rejects concentrate at prefix codes 82,166,174,206 immediately before missing triples; 26 at110 and5 at47. All FALL rejects are at170. 870/875 RISE rejects and all338 FALL rejects have prefix index2 modulo4, a recurring four-tap/CARRY4-lane pattern; prefix counts alone do not identify which individual tap arrives out of order. Every rejection has MULTIPLE_TRANSITIONS (some also BUBBLE_CORRECTED). Repeats at all three detuned frequencies; supports local sampled-pattern issues rather than random sampling shortage, but raw 512-bit vectors/current regional data are unavailable, so do not assert an exact physical cause.
- Signal identity passes: DC LOW gives zero complete pulses; requested 100.2/300.2/700.2 ns yields 101.567/301.663/701.582 ns coarse means. Baseline mean501.663ns vs500.2ns nominal (+1.463ns), std1.972ns. Baseline complete43.7378% vs predicted43.8441% agrees with 940ns frame geometry. No calibrated fine precision established. Original stimulus/config/results preserved.
- Latest routed report October21 10:48:15 local: WNS -0.437ns, TNS -14.323ns,129 setup endpoints, WHS +0.050ns,0hold failures. Modest improvement from v10 -0.487/-21.055/131; TNS magnitude reduces31.97%. pll_adc_clk has123 failures (worst legacy captured_fine_raw -> distributed histogram read/increment/write,13levels/8CARRY4,7.676ns datapath,4.626ns routing); pll_ser_clk4failures (watchdog_expired -0.190ns, process_state CE -0.134ns); generated clk_fpga_3 has2 failures (AXI/XADC -0.045/-0.013ns). Worst legacy histogram failure is separate from host width-LUT qualification and does not establish why fine codes reject. Prior reported width completion/result/pulse critical paths no longer lead this summary; full endpoint report needed for complete classification.
- Imported core RTL/top/daisy/layout XDC matches workspace. Routed checkpoint contains both layout macros and drain_ready/fine_in_range/phase_last, confirming consolidated repair features are present. This is not an actual FF/carry placement audit. Saved metadata still uses placeholder bitstream label / WNS null; fill these for subsequent runs, do not modify historical acquisition metadata to claim a unique build association.
- Added read-only FPGA `scripts/inspect_tdc_width_regions.tcl` for current RISE/FALL reject neighborhoods and tap0: placement, C/D net delays, Q-to-pipeline expanded clocks, ignored async min/max reports and up to200 failing endpoints. Run alongside `audit_tdc_width_sampler_layout.tcl` on current routed design before another rebuild; no constraint/run/property changes. Tcl structure/range parsing and mocked command control-flow checked (88taps/265timing queries); not run in Vivado. No HDL, gates, live instruments or implementation changed during this result review. Analysis JSON/PNG: latest run's `v11_results_review.*`.

### October 21: consolidated V11 prebuild review

- Reviewed active TDC/pulse/top wiring, CDC, signed arithmetic, capture/write alignment, physical constraints and project-copy coverage against the latest v10 report. No additional TDC input/output pin miswire was identified. DIO2_P remains input-only; both independent edge samplers and frame marker remain connected.
- Registered width `drain_ready` moves the wide captured/processed equality away from completion fanout while preserving final-bank-write ordering. New `CHECK_RANGE` registers range flags before record formatting. Pulse `phase_last` registers the terminal equality one pair early; new `prelast` immutable mailbox data is included in its bounded CDC constraint. No timing exception was widened and calibration rejection remains strict.
- Found a real incomplete combinational daisy TX selector: modes 6/7 retained prior data/valid. Added defaults and blocking assignments. Tied unused E3 parallel TX inputs and housekeeping diagnostic input to zero. Refresh now also imports/verifies the shared daisy source into the project directory. Entry-point BNET XDC inclusion now follows DISABLE_BNET; BNET source stays preserved/excluded.
- Updated stale test references to both parallel encoders, VERSION 11 and the existing extra pulse-output stage. Focused offline Icarus checks PASS: signed/frozen LUT corrections, errors/watchdog, abort/rearm, overflow, boundary writes, width-first readout, legacy LVDS/SINGLE isolation, pulse waveforms with portable/Xilinx ODDR, odd HIGH durations, 8/16-bit phase rollovers and 4 ns minimum period. Bus hold cycles 1/2/3 PASS. Production-size 512-tap / short 32-record capture PASS at 500 ns frames with every requested result checked; ideal delay model, not a fine-accuracy measurement. Exact-source selector regression reproduces old mode-6 failure and passes repaired modes 0..7.
- Full-top Slang compilation: 138 active sources with vendor primitive declarations, generated PS/IP external, DISABLE_BNET; 0 errors / 33 warnings. Remaining warnings reviewed: interconnect clock/reset ports have interface drivers; other flagged ports are unused diagnostics/wrapper signals. This does not replace vendor elaboration or CDC signoff. Tcl structural checks and two 640-cell macro definitions PASS. Logs, source map and hashes: `build/hdl-review/20261021-prebuild/review_summary.json`.
- No Vivado, live instrument commands or full-16384-record simulation ran. Latest routed WNS remains -0.487 ns until a new implementation. The physical RISE failure remains a hypothesis; the relative macro legality/locality and smaller ASG/PDM/legacy failing paths need the next routed assessment. Refresh once with project-owned copies, audit sampler placement after placement/route, check timing/DRC, and repeat fresh calibration before accepting performance.


### October 20: automated Rigol characterisation notebook

- Added `scpi-tests/tdc_rigol_characterisation.ipynb` and its adjacent helper `tdc_rigol_tools.py`. Uses vendor USB VISA address `USB0::0x1AB1::0x0647::DG5R270700006::INSTR`, checks DG5502 Pro identity/serial, and defaults to board `169.254.77.151:5000`. The existing USB discovery notebook records Python `miniconda3/envs/envscpi/python.exe`, PyVISA 1.16.2 and working vendor VISA. No live commands were sent during authoring.
- AWG CH1 goes directly to DIO2_P/E1 contact 7 with common signal return. PCB disconnected; DIO1_P/E1 contact 5 remains disconnected and provides internal frame markers only. Selected AWG output uses HighZ amplitude convention, 0..3.3 V, normal polarity, continuous PULSE mode and internal reference. Reference selection is global to the generator.
- Workflow: strict v9 preflight; coarse baseline; code-density collection interleaved across 997003/991027/983039 Hz; independent rise/fall 4000 ps LUTs with sample/validity/missing-code/concentration/time/frequency consistency gates; backup/upload/readback; fresh coarse/fine comparisons; inferred-phase residuals; 4.2..900 ns pulse-width sweep; 0.25 ns width increments; <=1 MHz rate/duty coverage; optional overspeed rejection diagnostic; host-only multiwidth scale/offset fit with different held-out widths. All raw/rejected records, metadata and PNGs are saved in timestamped `scpi-tests/tdc_rigol_results/` directories, including failures. Cleanup attempts both outputs OFF and width ABORT after every capture, with a reconnecting STOP cell.
- Rigol's official DG5000 Pro guide specifies minimum 4.2 ns HIGH/LOW in PULSE mode, so this stimulus cannot certify an entire <4 ns pulse. Width increments below 4 ns test interpolation, not minimum pulse capture. v9 still detects through sampled tap 0 and expects monotonic edge codes; it does not solve arbitrary sub-clock pulse capture. Frame acceptance is not source-pulse detection efficiency or continuous throughput.
- The user's original system objective is a lower-power ADC replacement using PCB voltage-to-time conversion, with a proposed 50 MS/s target. This requires separate measurement of VTC slope/range, noise, conversion/reset time, sampling behaviour, full-chain distortion and incremental power. No calibrated ADC ENOB, fine timing precision or 50 MS/s performance has been established. The notebook isolates the digital TDC and does not make those claims. Width-reference fits use nominal AWG readback unless independent scope widths are supplied.
- Authoring validation: helper and all notebook code cells parsed; notebook JSON/cell IDs/empty outputs checked. No hardware execution, simulation or Vivado run. Implementation WNS defaults to unknown and must be entered from the new report; unknown/failed timing keeps results provisional.
- Readback repair: saved run `20261020T124904_184795Z` failed before acquisition because the Rigol returned 500.2 ns for 500.25 ns requested; binary floating-point difference 0.05000000000001137 ns exceeded the old 0.05 ns guard. Its pulse period also read 1003.1 ns for a nominal 1003.006009009 ns request, which would fail the old fixed frequency tolerance next. Official Rigol width setting resolution is 100 ps or five significant digits. The helper now accepts one setting/readback quantum with a numerical margin, compares periods rather than using a fixed Hz tolerance, retains a separate FREQ? query, records all deviations and uses returned pulse width/period in analysis. Larger changes remain errors. Notebook imports reload the helper and display readbacks; configuration, outputs and existing results were preserved. Offline replay of the saved responses passed with both quantizations, large width/period/frequency deviations and invalid values were rejected, and all code cells compile. No live instruments were accessed during repair. Reload the notebook and rerun configuration/import/preflight/baseline.
- First completed v9 run `20261020T125634_774763Z`: 4096/8192 complete (predicted 49.826%), mean 502.513671875 ns, std 1.939200040 ns, 1525 at 500 ns / 2568 at 504 ns / 3 at 508 ns. Raw audit has zero violations; fine correction OFF. RISE fine codes 100% valid, FALL 4083/4096=99.6826%, with 13 multiple-transition rejects. Valid-frame clusters repeat every ~334.207 frames, consistent with the ~3 kHz beat between independent 1 MHz frames and ~997 kHz source; this supports external stimulus but does not prove physical source identity. The +2.314 ns mean error and three 508 ns outliers remain to be characterized. `SATURATED` here is finish_flags' HIGH-without-FALL frame flag, not analogue clipping. Saved an additional `baseline_review.json` beside the capture.
- Added notebook section 2b and helper `signal_identity_check`: fixed 1000 ns frame/500 ns internal window HIGH; drive AWG DC 0 V as a non-floating negative control, then 100.2/300.2/700.2 ns pulses on CH1. Require zero complete DC pulses and width tracking before code-density calibration. Failed identity is recorded and blocks calibration. The new diagnostic has been syntax checked but not run on instruments; user configuration and previous notebook outputs were preserved. Rigol APPLy:DC placeholders and offset query follow the official programming guide. No HDL changes were made based only on this baseline.
- DC control compatibility repair: run `20261020T130633_466741Z` stopped before FPGA acquisition because FUNCtion? returned ARB after APPLy:DC, although offset was zero and the command queue reported no errors. The helper had required exactly DC. It verifies waveform-specific identity via APPLy? or, if generic ARB is reported, FUNCtion:ARBitrary?. Only explicit DC identification with zero offsets passes; zero-offset arbitrary waveforms alone remain rejected. An initially added explicit FUNCtion DC selector was subsequently removed after the queue error described below. Readback details are saved on failure and output stays OFF until verification succeeds. Notebook source notes updated while preserving configuration and prior outputs; rerun imports/setup and preflight before section 2b.
- Queue repair: run `20261020T131219_364834Z` reported -350 Queue overflow immediately after the redundant FUNCtion DC selector. Logs do not establish the internal cause or exclude a delayed error. Read-only live VISA diagnostics then confirmed CH1 OFF, FUNCtion? ARB, APPLy? DC with all-zero fields, FUNCtion:ARBitrary? DC, offset zero and an empty error queue. Saved under `build/rigol-tdc-review/live_readback_after_queue_overflow.json`. The helper now uses the already accepted APPLy:DC route without the redundant selector, spaces every instrument command/error query by a configurable 20 ms default, logs every queue reply, drains pre-existing errors at session startup, and reports all newly generated errors after a bounded full drain. It does not hide failures with *CLS. Offline replay using the actual live DC replies and full queue-drain/error rejection checks passed. No output was enabled and no FPGA capture was initiated during this repair; the full section 2b hardware diagnostic remains pending.
- Subsequent completed run `20261020T132039_815639Z`: section 2b passed (DC LOW 0/4096 complete; AWG 100.2/300.2/700.2 ns measured means 102.458/302.548/702.532 ns). Across 24 calibration bursts: 95927 complete pulses; RISE 95921 valid (99.9937%), 211 occupied codes; FALL 95693 valid (99.7561%), 207 occupied codes. All sample/validity/concentration/CDF consistency gates pass. Upload is blocked solely by FALL zero-count code runs 91..93 and 99..101; both persist at every frequency. FALL invalid debug raw indices: 90=105, 98=126, 6=2, 7=1. The concentration beside the missing runs suggests localized tap-order/sampling-skew/bubble-encoding behaviour, but exact cause is not established. Inspect FALL sampling region roughly taps 88..104 / CARRY4 instances 22..25; current WIDTH records do not include full 512-bit raw snapshots. Do not mark gaps harmless automatically from zero counts, especially with adjacent rejected phases and failed global timing. Additional review JSON and zoomed PNG are saved beside the capture as `calibration_gate_review.*`. Upload error text now separates image mismatch from explicit per-edge quality reasons; qualification thresholds and LUTs were not changed. Syntax checked; no instrument commands were sent during this result review.
- User's later Vivado placement paste confirms all 128 FALL carries and 512 tap FDREs. Carries 22..25 are SLICE_X91Y38/Y39/Y40/Y41, each with matching four FDREs in AFF/BFF/CFF/DFF order; tap 104 is AFF at X91Y42. There is no obvious discontinuity or wrong FF-to-slice placement in this excerpt. Missing raw codes 91..93 span DFF at Y38 then AFF/BFF at Y39; 99..101 span DFF at Y40 then AFF/BFF at Y41. Reject indices 90/98 correspond to CFF at Y38/Y40. Vivado hierarchy uses `gen_carry[22].gen_next.i_carry4` and `gen_tap[90].i_tap_ff`, not slash-separated generate names. Added FPGA script `prj/v0.94/scripts/inspect_tdc_fall_region.tcl` to export placement, D/C pin net delays (ps), sampling-Q to pipeline reports with expanded clock paths, and user-ignored asynchronous falling-input to rising tap-D reports for taps 84..108. Script changes no design properties/constraints and defaults to a timestamped report directory under the current Vivado project. Tcl structural completeness checked only; not run in Vivado. Next evidence needed is routed data/clock delay variation across these boundaries; placement coordinates alone do not establish the missing-code cause.

- Routed falling-region review: read all 50 path reports plus placement/net tables in `C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/tdc_fall_region_20261020_144711`; summary logs no skipped/failed queries. Placement remains contiguous and colocated. Across taps 84..108, early clock insertion is 5.603..5.607 ns and late insertion 6.126..6.130 ns (4 ps spread within each model). All selected sampler-Q to pipeline setup paths pass, slack +1.967..+2.507 ns; this does not clear other paths or global WNS -0.862 ns. Complete asynchronous setup/max slow-corner paths have nonmonotonic per-tap delays: taps 90/91 = 14.448/14.334 ns with identical 5.604 ns capture-clock delay; taps 98/99 = 14.676/14.562 ns with identical 5.605 ns clock delay. Similar -114 ps steps recur at other odd taps. This supports investigating sampled tap order and the strict majority/prefix encoder, but max-corner bounds are not measured arrival order and do not uniquely explain only the two observed hardware holes. D net-delay objects also differ by tap lane (SLOW_MAX 92 ps for CO0..2, 336 ps for CO3); complete timing reports show zero interconnect at these local final connections, so do not add the net-table numbers to already-complete timing paths or infer a CO3-only root cause. Input-to-selection routing is 7.060 ns plus 1.883 ns selection-to-inverter routing, worth optimizing for differential latency, but common input delay alone does not explain localized code gaps. Saved extracted JSON/CSV/PNG under `build/rigol-tdc-review/fall_region_timing_review.*`. No HDL, LUTs, timing exceptions, implementation or instruments changed. Next diagnostic should expose raw thermometer snapshots around the failing transitions before selecting a tap remap or broader bubble correction; do not waive calibration gates from these modelled reports alone.

- User decision after the routed review: defer root-cause investigation, log the unresolved FALL gaps, and continue provisional calibration. Added edge-specific `provisional_missing_code_ranges` to `build_candidate`; notebook acknowledges only FALL 91..93 and 99..101. This is separate from physically characterized `KNOWN_DEAD_ZONES`, which remains empty. Candidates/upload records retain the exception, actual missing runs, validity metrics and accepted-edge bias limitation. All other gates and rejection remain unchanged. New section-4 requalification cell reloads the helper and reuses `calibration_captures` already in memory, so the existing 24 bursts need not be repeated in a live kernel. It saves `provisional_calibration_issue.json` and a rebuilt candidate before the existing backup/upload/readback step. Section 5 fresh coarse/fine validation is the next hardware step; it has not been run by the assistant. Existing notebook outputs/configuration preserved; no HDL changes, instrument commands, LUT upload or tests performed in this edit. The provisional exception does not establish that the gaps are harmless or repair rejected events/global failed timing. Raw-snapshot diagnostics are deferred rather than a prerequisite for this experimental continuation.

- Latest provisional calibration run `20261020T141845_303335Z`: source identity passed; 24 density bursts yielded 95944 complete pulses, RISE 95930 valid (99.9854%), FALL 95694 valid (99.7394%). Only the acknowledged FALL 91..93/99..101 triples needed exceptions (FALL 56 was additionally empty as a single bin). Both LUTs uploaded, read back exactly, and activated. Section 5 stopped on the FIRST fine capture at 996983 Hz: 8192 records, 4001 complete, 3996 calibrated, 2510 `invalid_fine_correction` audit failures. Exact offline comparison of all 3996 calibrated rows with uploaded LUTs shows every negative `RISE_LUT-FALL_LUT` delta (2510 rows) reported +131072 ps too large, and every nonnegative delta (1486 rows) exact. This strongly identifies unsigned interpretation/zero extension of the signed 17-bit correction, separate from the deferred missing-code issue. Source and imported Vivado copy both reconstruct readout with `read_coarse_ps+32'(read_fine_delta)` at tdc_pulse_width.sv:175; use explicit sign extension when repairing, and review related arithmetic. Reported fine mean/std 584.843564/63.366789 ns are invalid. Diagnostic host recomputation from raw indices plus uploaded LUTs gives mean 502.513554 ns, std 0.107696 ns for 3996 pulses; fresh coarse fine-eligible mean/std 502.559606/1.920351 ns for 4060 pulses. This suggests ~17.8x lower spread but is an offline reconstruction, not a passed FPGA validation; nominal AWG HIGH is 500.2 ns, leaving +2.313554 ns mean offset. Saved `fine_validation_review.json` beside capture; original records unchanged. No later sweeps/reference fit ran. No HDL changes, hardware commands or further tests during this review. Next necessary repair is the fine-width sign handling, or an explicitly separate host-calibrated diagnostic path if rebuilding is deferred; keep hardware integrity checks active.

- Retry `20261020T142933_512273Z` failed the first fine validation again: all 2501 negative fine deltas are +131072 ps too large, all 1528 nonnegative deltas match the uploaded LUT exactly. Status DONE=8 and 8192/8192 count are correct; only fine-correction integrity fails. Prior review had diagnosed but not edited HDL. Now changed source `tdc_pulse_width.sv` readout to explicit 17-to-32-bit sign extension using replicated sign bits before the unsigned coarse addition; also made the 45-bit internal fine addition's sign extension explicit. The existing imported Vivado source and loaded image have not been updated. Refresh project-local source copies, rebuild and load the resulting bitstream before repeating fine validation. No Vivado invocation or tests were run for this change. Calibration captures/LUTs/raw files preserved; calibration must be repeated for any newly implemented image because routing may change. Helper error now includes status/count/audit details and identifies the known +131072 ps signature as a diagnostic hint; integrity checks remain active.

- V10 source update requested before the next rebuild: reviewed the October 20 routed report (not the stale October 16 `tdc_width_diagnostics`). Worst classes: width FALL LUT -> fine_delta -0.862 ns; legacy tap reduction -> controller/arithmetic -0.793 ns; pulse DDR mux -> ODDR D2 -0.764 ns; phase -> DDR data -0.731 ns. Width now has two concurrent eight-tap/cycle encoders (`i_rise_encoder`, `i_fall_encoder`), separate reset-free inputs without the 512-bit edge mux, preserved local LUT output registers, and a registered low-byte borrow/high-byte fine subtraction. Default hardware minimum frame period becomes 500 ns / 2 MHz; a static 64-clock scan + 32-clock processing budget reserves margin within the 125-clock frame and lengthens the limit for larger parameterized scans. Existing overflow, strict majority/transition rejection, 16384 capacity and register/record ABI remain. Explicit signed correction fix retained. Legacy 512-tap event reduction now uses two registered levels with matched tap data delay, coarse correction 3 instead of 1 clocks, and two-clock timeout delay/adjustment to preserve the original observation window. Pulse generator now registers the final GPIO/ownership mux before direct ODDR data inputs, matches the additional 4 ns pair latency in drive guard/marker, removes phase+1 from the D2 compare, and increments phase in bytes with lookahead carries. BNET remains disabled; no timing exceptions or carry placement coordinates changed. VERSION=10 / ID=0x5444430a distinguishes this source from loaded v9. Existing API/server version guards and hardware minimum-period check support it without rebuild. Refresh helper now prints v10 identity and still imports/verifies project-local copies. Diagnostics select both encoders and the local LUT/borrow registers; collection checker requires both encoders, 32 local LUT output FFs, and two final pulse data FFs. Rigol notebook expects v10, new bitstream label/WNS, fresh density capture, no inherited v9 missing-code exceptions, and rate points near 1.5/2 MHz. CLI width script permits up to 2 MHz with a version guard. Existing saved notebook outputs/configuration unrelated to image identity preserved. Static Slang 12 component elaboration (tdc_top and pulse_gen, all TDC dependencies; default 1ns/1ps; vendor primitives treated as external) passed 0 errors/0 warnings using base Python 3.13 and `build/hdl-tools-py313`; envscpi Python 3.14 cannot load the older local compiler wheel. Python/notebook AST and Tcl structural completeness passed. No simulation/tests, Vivado, instrument access, source-copy refresh or bitstream build were run. New timing closure, utilization, CDC/DRC, pulse restart/odd-HIGH/byte-boundary behaviour, calibration integrity and 2 MHz acquisition still require build/hardware acceptance. 50 MHz/continuous streaming/subclock whole-pulse capture are not implemented; the tap-0 detection limit and deferred physical FALL-code issue remain. Recalibrate both LUTs after new placement/routing.

- V10 hardware review: latest notebook run `20261020T161623_677883Z` confirms VERSION=10, 512 taps, 4000 ps tick, 16384 capacity, but label is still the pending-build placeholder and WNS field null. New routed report actually exists at the normal impl_1 path, October 20 17:01:23 local: WNS -0.487 ns, TNS -21.055 ns, 131 failing setup endpoints, WHS +0.050 ns, zero failing hold endpoints. This improves materially from v9 -0.862 ns / 4074 endpoints. Current listed failures involve captured_count -> width state/completion, pulse phase feedback, fine_width -> record-write resets, plus smaller ASG/PDM/calibration paths. Notebook source identity passes and coarse width mean errors are now about +0.12..+0.20 ns at 100.2/300.2/700.2 ns nominal AWG. However, RISE fine validity regressed: latest 24 bursts give 85738 complete pulses, RISE 79418 valid (92.6287%), FALL 85534 valid (99.7621%). RISE valid indices now span 84..294 vs v9 1..214; FALL 1..218 vs 1..214. RISE rejected debug indices: 2=5914, 290=230, 110=176 (6320 total, 93.58% at raw 2, mostly status 0x24). The preceding v10 run `20261020T160922_812380Z` reproduces the same RISE range and 92.6818% validity. RISE missing codes 291..293; FALL 139..141 and 191..193. Candidate upload correctly blocked; no uploaded_luts or fresh fine validation files exist in either v10 run. Section 5 execution 45 and its signed-correction error are stale v9 outputs, not a v10 failure. The RISE LUT zero plateau through code 83 is due to no valid observations, not a known absolute delay offset; do not shift indices or stretch a biased density map to force acceptance. Suspect early RISE sampler tap timing/placement relative to tap-0 event detection, but full raw vectors and new local clock/data reports are needed to distinguish physical skew from a capture/encoder alignment bug. No active LOC/BEL lines for the width RISE hierarchy were found in routed DCP XDC/EDIF inspection; this alone does not establish actual placement. The default notebook frame changed from 1000 ns to 940 ns at ~997 kHz: 43.811% accepted vs 43.844% predicted is normal window geometry, not a missed-pulse regression; comparison of coarse statistics is also affected by phase exclusion. Saved `v10_rise_review.json/png` beside captures. No source/HDL/LUT edits, hardware commands, Vivado or tests during this result review. Next useful evidence is placement/data/clock timing at RISE taps 0..8 and 76..96, plus raw samples for rejects at code 2; current FALL-region v9 reports do not describe this implementation.

- V11 targeted source repair after the v10 RISE regression: added mandatory flat implementation constraint `prj/v0.94/sdc/tdc_width_sampler_layout.xdc`. Two distinct 640-cell XDC macros each hold 128 consecutive CARRY4 stages plus four AFF/BFF/CFF/DFF sampling FFs in each carry slice; absolute origins are left to the placer. Default hierarchy is explicitly 128 carries/512 taps; other sizes must regenerate constraints. This targets the unverified early-tap displacement/skew hypothesis; DONT_TOUCH by itself had not enforced colocation. Width sampler Q pins now feed only reset-free raw_pipe_0/fall_raw_pipe_0; edge detection and sampled-level decisions use this timed pipeline stage. Added raw_pipe_2/fall_raw_pipe_2 and a second marker register so raw snapshots, write enables and frame boundaries remain aligned. Both edge timestamps receive the same common extra clock, preserving pulse-width difference. Adds 1024 FFs; preserves two parallel encoders, 500 ns default frame minimum, capacity/ABI, strict thermometer rejection and calibration gates. Version ID now 0x5444430b / VERSION 11; no API/server rebuild. Both project entry points and refresh_custom_sources include the new XDC, and refresh still imports byte-verified project-local copies. Checker requires the layout file. Added read-only `audit_tdc_width_sampler_layout.tcl`: checks all 1024 width samplers against carry LOC and expected BEL, carry continuity and placed status; logs placement.tsv and fails on errors. Can audit the existing v10 routed design before rebuilding and should audit v11 after placement/routing. Diagnostics now include the third raw stage. Notebook/helper expect v11, preserve saved v10 outputs, require fresh data and keep exception ranges empty. Static Slang 12 selected-component compilation (tdc_top/pulse_gen with TDC dependencies, vendor primitives external, timescale 1ns/1ps) passed 0 errors/0 warnings. Python AST and Tcl structural completeness passed; static constraint reading confirms 2 independent macros, 640 unique cells and 128 correctly numbered stages each. No Vivado, physical implementation, live instruments, tests or simulation were run. New macro legality/actual origin placement, routed timing and hardware RISE recovery remain unverified. Existing chosen absolute LOCs, if present, must agree with the macro geometry. Do not claim this fixes intrinsic carry bubbles or subclock pulse capture; rerun fresh calibration after rebuilding.

- **Do not run Vivado on this device unless the user changes that instruction.** The recorded local HDL checks used Slang and Icarus.
- For the V7 BRAM repair, the user requested skipping further simulation and will verify in Vivado. The in-flight full-buffer V7 run was stopped; do not restart it for this repair. Completed short regressions and host checks are recorded below.
- Preserve BNET source for future re-enabling, but exclude its hardware from the next build (user request October 19). Preserve pulse generation and shared bus addressing when transferring changes. The PCB pulse-width redesign is authorized to replace the TDC measurement controller/encoder and its interfaces; preserve useful input selection and calibration/self-test support where applicable. Document changed hierarchy, placement selectors and register/version semantics.
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

- prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv â€” active custom definition of red_pitaya_top; integration, clocks, GPIO and slot-7 mux.
- prj/v0.94/rtl/bnet_regs.sv, bnet_axi_reader_ch.sv â€” BNET registers/descriptors and DDR reader.
- prj/v0.94/rtl/butterfly_network.sv â€” serial engine and bnet_tdp_ram definition.
- prj/v0.94/rtl/butterfly_network_static_sdf.sv â€” currently selected static SDF engine.
- prj/v0.94/rtl/butterfly_network_static_pipeline.sv â€” alternate full-frame static engine.
- prj/v0.94/rtl/tdc_*.sv â€” TDC controller, LVDS I/O, carry chain, encoder, FIFO, calibration, registers, internal and MMCM stimulus.
- prj/v0.94/rtl/pulse_gen.sv â€” bus mailbox, pulse timing, ownership guard and ODDR.
- rtl/red_pitaya_pll.sv â€” existing PLL; ser_clk is nominally 250 MHz.
- rtl/classic/red_pitaya_asg_ch.sv â€” includes the declaration/enum corrections from the October review.
- prj/v0.94/sdc/ â€” board, TDC and pulse constraints.
- prj/v0.94/scripts/tdc_placement.tcl â€” placement helper; see its outstanding correction in section 9.
- prj/v0.94/doc/tdc_registers.md â€” detailed TDC register/electrical specification.
- red_pitaya_vivado_project_Z20_G2.tcl and red_pitaya_vivado_Z20_G2.tcl â€” project/non-project entry points and custom constraint inclusion.

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
| V7 BRAM reduction, 2026-10-15 | 99-bit records / 198 KiB logical result storage; Slang 0 errors, 2 existing BNET warnings; short Icarus tests PASS for signed +/-65535 ps corrections, frozen calibration after LUT edits, width-first reads, faults and integrated TDC; API/SCPI v5/v6/v7 host compatibility PASS | The full 16384-record V7 simulation was stopped at the user's explicit request. No V7 Vivado run here; actual BRAM fit, DRC and routed timing are for the user's external verification. The earlier full V6 simulation does not establish V7 resource fit |
| Width API/SCPI, 2026-10-15 | Standalone host build/test PASS using the actual API and SCPI handlers with pinned scpi-parser; checks feature versions, busy/rate/duty guards, record decoding and invalid parameters | Mock MMIO and Windows host shims; matching Linux/ARM API/server build and live board SCPI still required |
| Width board-test script, 2026-10-15 | Python syntax and mocked-client sequence PASS: source ON before ARM, chunked record reads, CSV output, invalid-result rejection and output-OFF/abort cleanup | No board connection or electrical measurement |
| Existing TDC logic/MMCM regression | Icarus PASS with UNISIM MMCME2_ADV/BUFG source models | Encoder/FIFO/controller/self-test behavior; no physical carry-delay or absolute phase proof |
| Shared decoder | Extracted current decoder and pulse instance passed all 16 subregions, WEN/REN isolation, readback and error cases | BNET/TDC responses were registered probes, not full accelerator/measurement models |
| Pulse software | Earlier native Windows GCC 16.2 C++20 syntax checks against repository headers and scpi-parser 4e879901b51cbb43dab36dd83f95a23f1dbaa4c0; Python AST and --help passed | Windows shims were used; latest Linux/ARM build, linking and live MMIO/SCPI remain unverified |
| Historical BNET hardware | June 1024-point DDR run drained 2048 sample bytes and 20480 weight bytes; ERROR=0; RF shape correlations about 0.994â€“1.000 | Applies to that historical bitstream |
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
| Serial fixed 2048 | 4096 | 45056 = 2048 Ã— 11 Ã— 2 |
| Alternate full-frame fixed 4096 | 8192 | 98304 = 4096 Ã— 12 Ã— 2 |
| Current SDF 1024, four banks | 2048 | 81920 = 4 Ã— 1024 Ã— 10 Ã— 2 |
| Current SDF 2048, two banks | 4096 | 90112 = 2 Ã— 2048 Ã— 11 Ã— 2 |
| Current SDF 4096, one bank | 8192 | 98304 = 4096 Ã— 12 Ã— 2 |

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
| 0x100 + stream Ã— 0x40 | Descriptor window |

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
| FPGA trigger frequency | 1â€“125 MHz target; use the existing pulse generator and query the actual quantized frequency |
| FPGA trigger duty | 50%; nominal HIGH/LOW range 500 ns / 500 ns at 1 MHz to 4 ns / 4 ns at 125 MHz |
| PCB repetition | One active-HIGH output pulse per FPGA rising edge in normal operation, completing before the next trigger |
| PCB HIGH range | Up to 100% duty; minimum detectable HIGH and LOW duration must be characterized, not inferred from a register's ps units |
| Full-scale / missing edge | Report SATURATED / NO_FALL or other explicit invalid status when individual pulses cannot be distinguished; do not fabricate a measured width |
| Acquisition | Capture every pulse within finite bursts, then read the buffer; continuous full-rate raw Ethernet streaming is not required |
| Precision | Best achievable after physical implementation, calibration and measurement; no numerical ps accuracy has been accepted or demonstrated |
| Bring-up | Start at 1 MHz and increase; 125 MHz is an unverified target for the PCB/link and FPGA capture |

The initial low-frequency width implementation is now in source. The previous v4 input-selector tests do not establish its physical accuracy or throughput; use the new width tests and hardware procedure below.

#### Current v7 implementation: reduced-BRAM 16384 pulse-width records

- HDL: prj/v0.94/rtl/tdc_pulse_width.sv. Separate capture and processing controllers overlap acquisition and encoding. Only four raw rise/fall frames are staged; completed frames are consumed by an eight-tap-per-clock encoder before the next 1 MHz frame. The carry path stays running across trigger boundaries. The shared encoder retains its original one-tap mode by default for legacy TDC operation.
- Current top-level TDC ID: **0x54444307** at 0x40710000. Width sub-block signature remains **0x50574201** at 0x40710100; the five-word readout/API layout is compatible with v5/v6. V7 changes internal storage and write-port controls without dropping fields. The SCPI server links the API statically. CAPACITY? returns 16384, as in V6; use the TDC ID to identify the storage repair.
- Width acquisition deliberately rejects trigger periods below **1000 ns** (above **1 MHz**). The API requires pulse_gen already ON, 50% drive, and legacy TDC enable/internal/MMCM modes OFF. The initial 250 MHz sampler uses a **4 ns coarse tick**; HIGH and LOW should each be at least **8 ns** for coarse capture, subject to actual board characterization. Shorter pulses/gaps may be missed or merged. This release does not implement 125 MHz acquisition.
- Burst length is 1..16384, default 16. N records require N+1 output trigger boundaries. Encoding runs during capture; readout starts after the last frame is processed. A full 1 MHz burst covers 16.384 ms plus initial alignment/final processing. This matches the ADC's sample count, not its sample rate. It remains finite capture/readout, with gaps between bursts.
- Storage at 512 taps is now 99 bits per record (flags, coarse ticks, two 9-bit indices and a signed 17-bit fine correction), or 198 KiB for 16384 records. V6 used 114 bits / 228 KiB; V7 removes the redundant 32-bit final width, saving 30 KiB. width_ps is reconstructed from the stored coarse count and correction, with invalid records still returning zero. The correction is frozen per record; later LUT edits do not alter old measurements. Cycle IDs remain derived from addresses and no public fields are dropped. Four raw frames use 544 bytes, plus 2 KiB of LUT data. Raw staging uses distributed RAM; results use block RAM. A synchronous write-port pipeline isolates asynchronous state/address resets from BRAM controls. The existing API's 16 settling reads cover the additional readout scale stage. Verify actual packing/utilization/timing alongside BNET/scope/ASG externally.
- Uncalibrated width is the difference between the PCB edge timestamps in 4 ns ticks. Raw carry indices and status bytes are diagnostic. Missing/extra edges, HIGH at cycle start, saturation, trigger timeout, boundary ambiguity and out-of-range results are explicit flags. A stalled processor sets global OVERFLOW (status bit 7) and discards the burst; it never silently overwrites an unread frame. CAPTURING and PROCESSING can both be set. Completed memory is frozen and can be read repeatedly.
- Optional fine correction uses separate rise/fall LUTs for the new 250 MHz carry path: width_ps = coarse_ticks*4000 + rise_LUT - fall_LUT. Both 512-entry tables must be uploaded before activation. Editing a table or changing input disables correction; source changes also invalidate previous width records. Old 125 MHz calibration tables are not valid for this path. No automatic width calibration or certified ps accuracy is claimed.
- New commands: TDC:WIDTH:ARM <count>, ABORT, CLEAR, STATUS?, COUNT?, CAPACITY?, TICK?, DATA? <start>,<count>, TIMEOUT[?], and CALIBRATION:LUT:WRITE/READ? / CALIBRATION:ACTIVATE[?]. DATA returns semicolon-separated records: cycle_id,flags,coarse_ticks,rise_raw,fall_raw,width_ps. Up to 128 records per query. The detailed register/flag definitions and example are in the FPGA repo's prj/v0.94/doc/tdc_registers.md.
- Script: **scpi-tests/tdc_pulse_width_test.py BOARD_IP --count 16384 --csv tdc_width_16384.csv --quiet** (default 1 MHz / 50%, SINGLE input; count defaults to 16 when omitted). It queries hardware capacity, starts pulse_gen before ARM, polls completion, reads 128 records per query and checks IDs/flags/count. The full burst takes 128 data queries. --quiet suppresses per-pulse printing but saves every CSV record and reports validity/status. Cleanup sends output OFF / abort. Use --frequency 100000 for a slower run. Keep SINGLE selected for current work; the retained --input LVDS option is deferred.
- New carry hierarchy: i_tdc/i_width/i_carry, 128 CARRY4 / 512 FDREs, alongside the retained legacy chain. The placement helper accepts this hierarchy as an optional last argument. Use separate legal sites; no width-chain placement has been selected. The existing TDC XDC now includes the width tap/synchronizer exceptions and bounded control/completion transfers. Ordinary capture, arithmetic, RAM and encoder paths remain timed.
- The project-copy refresh now imports all rtl/tdc_*.sv dependencies, pulse_gen, bnet_axi_reader_ch, the merged top and four XDCs. It uses project-local copies as requested. Keep all tbn carry/ODDR replacements out of Vivado filesets.

**Prior synthesis failure and retained repair (2026-10-15):** v5 failed externally with Synth 8-3391 on rise_memory_reg (512 x 1024 = 524288 bits). Conditional writes to current/next-frame addresses prevented BRAM inference. The repaired source selects write enable/address/data before a single clocked write per array, with no storage reset. V6 retains that access pattern while replacing the full raw-burst arrays with shallow staging and compact results. Do not raise dissolveMemorySizeLimit to expand the array into bits. Refresh copies and reset synthesis on the build machine; no Vivado has been run here and new inference/utilization/timing remain pending.

**V6 implementation failure / V7 source repair (2026-10-15):** implementation DRC UTLZ-1 reported 286 RAMB18-equivalent units required versus 280 available. Read-only inspection of the saved synth_1/runme.log confirms record_memory_reg inferred 57 RAMB36 blocks (16K x 114). The saved synthesis utilization report lists 131 RAMB36 + 8 RAMB18 = 135 tiles; the later implementation DRC reports 143 tile equivalents. Synthesis totals alone did not establish fit. The new 16K x 99 result array predicts about 50 RAMB36 blocks, roughly seven fewer, subject to fresh synthesis/implementation. The optimized DRC also reported REQP-1839 on asynchronous write-address/control sources; V7 registers the RAM write port with synchronous control. No new Vivado run or resource-fit claim is made here. Reset synthesis and implementation and inspect the new optimized/implemented counts, DRC and timing.

The user asked to skip the remaining simulation and verify V7 in Vivado. The full-buffer Icarus run was stopped, with no V7 full-run PASS claimed. Short signed-correction/frozen-result/readout and integration regressions had already passed, as had the HDL and host API checks. Read-only V6 report snapshots are under build/hdl-review/width_v6_{utilization_synth.rpt,drc_opted.rpt,synthesis.log}; they are baseline evidence, not new verification.

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
- V7 stores up to 16384 compact results and encodes during capture at the initial <=1 MHz rate. Increasing capacity alone does not increase edge throughput. A future 125 MHz design would need substantially faster capture/encoding and transport; that rate and continuous streaming are not implemented or verified.
- Preserve selectable LVDS and 3.3 V single-ended return routes unless a later instruction changes this. E1 DIO1_P remains the single-ended trigger output; no E3 differential launch connection is needed for this PCB protocol. Disable the independent E3 launch function in the new pulse-width acquisition mode.
- Carry tap calibration, rising/falling polarity offsets, input route offsets, clock/coarse boundary handling and missing-code behavior require fresh characterization. A numeric value expressed in ps is not evidence of that resolution or accuracy.

Acceptance work for the redesign must include simulation of long pulses, both edges in one clock interval, narrow HIGH and LOW gaps, minimum/maximum duty, adjacent cycles with sharply changing widths, full-scale constant HIGH, missing/extra edges, counter boundaries, buffer limits and delayed readout. After source checks/simulation, the user must run Vivado timing/CDC/DRC/resource checks elsewhere and then compare widths to an oscilloscope from 1 MHz upward. No Vivado is to be run here.

### Retained legacy implementation

**LVDS work is temporarily deferred.** The differential wiring and procedures
in this section are retained reference material, not current acceptance steps.
The single-ended input is the active development and calibration path.

- External LVDS launch to PCB: E3 contacts **7/9**, DIO17 P/N, exp_e3p_o[0]/exp_e3n_o[0], package T5/U5.
- External LVDS return from PCB: E3 contacts **31/33**, DIO18 P/N, exp_e3p_i[0]/exp_e3n_i[0], package V11/V10. Use E3 ground contact 16, 22 or 26.
- Active single-ended return: **DIO2_P, E1 contact 7**, exp_p_io[2], package **J18**, with E1 ground 25/26. The user confirmed a **3.3 V digital output**. This pin is permanently input-only in the custom top; housekeeping GPIO output settings cannot drive it. The existing board sdc/red_pitaya.xdc supplies J18/LVCMOS33; no new pin constraint is needed. No differential termination belongs on this input.
- Both pairs are LVDS_25. The user confirmed an LVDS return without external termination; the updated instance and TDC module defaults enable internal 100-ohm differential return termination. If external termination is later added, disable the internal terminator. Analog voltages must first pass through the external compatible receiver.
- E3 indices 3:1 retain one clock and two auxiliary serializer data lanes; index 0 is reserved for TDC.
- Sources: external LVDS/SINGLE return selected by INPUT_SELECT; divided independent PS fclk[0] stimulus selected by CONTROL[10]; dedicated phase-swept MMCM stimulus selected by CONTROL[11], with MMCM priority.
- The dedicated MMCME2_ADV is separate from the shared Red Pitaya PLL. Nominal parameters give 448 phase steps per 8 ns ADC period, about 17.86 ps per commanded step. This is a nominal stimulus setting, not certified TDC resolution.
- Current source register ID is **0x54444307** (v7: reduced-BRAM 16384-width bursts plus selectable input). Earlier IDs 0x54444303/04/05/06 identify v3/v4/v5/v6 images. MMCM registers are at 0x80 control, 0x84 status, 0x88 coarse delay, 0x8c signed step count; INPUT_SELECT is at 0x90, relative to the TDC base.
- Source code now includes the fixed 128-bit FIFO layout with a 10-bit fine-raw field, the normal-operation pending-trigger latch, and the third toggle-settling stage.
- The iterative encoder needs roughly 512 clocks per event. A 125 MHz sampling clock does not imply 125 million accepted measurements per second. No PS interrupt line is connected.

Detailed register/flag/record definitions are in the FPGA repo's prj/v0.94/doc/tdc_registers.md. App interfaces are rp_Tdc* and TDC:*; tests cover reset/enable/mode/trigger, FIFO/measurement, calibration and MMCM commands.

External selection (new source changes, not yet loaded on the board):

- `TDC:INPUT LVDS` (FPGA-reset default), `TDC:INPUT SINGLE`, `TDC:INPUT?`; API rp_TdcSetInput/rp_TdcGetInput with rp_tdc_input_t. INPUT_SELECT is physical 0x40710090, value 0 or 1. The API requires ID version 4+ and rejects the earlier v3 image rather than falsely reporting selection success.
- Disable the TDC and wait for BUSY=0, or issue TDC:RESET to abort a pending measurement, before selecting. Changed selection resets controller, results/FIFO, sequence/event counters and histogram, and disables LUT correction. Rewriting the same source while disabled/idle has no reset side effects. Source survives soft reset; FPGA reset selects LVDS.
- Turn TEST:INTERNAL and MMCM:ENABLE OFF for either PCB input. One external input is measured at a time. The selected rising edge is fed directly into the delay line; the existing synchronized signal is only used for re-arm. Keep the input LOW before starting and let it return LOW between acquisitions.
- The E3 launch pair stays at contacts 7/9 for both return types. The E1 pulse generator remains a separate function; these changes do not make it the TDC start reference. A periodic unrelated PCB signal does not establish a controlled launch-to-return delay.
- Re-characterize the selected input path and reload its calibration before calibrated use; LVDS and LVCMOS input/routing offsets differ. Wait for histogram-clear completion before collecting calibration. The stored LUT banks are not automatically replaced by a source change.
- Rebuild/reload FPGA plus API and SCPI server; the static SCPI link embeds the API. The source-refresh helper now includes all rtl/tdc_*.sv dependencies. Verify ID 0x54444307 and query INPUT before acquisition; PCB width acquisition uses TDC:WIDTH:* instead of the legacy MEASURE command.

For current pulse-width work, use `TDC:WIDTH:*` with `TDC:INPUT SINGLE` selected while idle. Query `TDC:INPUT?` before acquisition. The section-9 single-shot procedure is retained for legacy delay measurements; switching back to LVDS is deferred until requested.

Local checks for this addition passed: Slang selected custom-top hierarchy (0 errors, two existing BNET shift warnings); Icarus TDC integration with LVDS/SINGLE isolation, enabled/busy write rejection, source preservation through reset and FIFO/LUT clearing; mocked project-refresh Tcl check; memory-backed API plus actual pinned SCPI parser/handlers (set/query, abbreviations, bad parameters, old-image and busy guards). The host C++ check used standalone GCC 6.2 C++14 with Windows mmap/syslog shims and an unused span declaration shim; it is not the required Linux/ARM C++20 production build. The persistent host test is scpi-tests/tdc_input_selection_test.cpp; compile it with scpi-server/src/tdc.cpp and libscpi, rather than separately linking a second API tdc.cpp. No Vivado, board upload, routed timing or electrical test was performed for this addition.

Historical findings, preserved with scope:

- A prior real build locked its dedicated MMCM and produced a monotonic phase sweep. That run exposed a 127-versus-128-bit FIFO packing bug causing spurious +512 raw indices and shifted fine/total fields; the source fix requires a new image.
- A pending-trigger latch was previously set only in reset; its operating-branch fix is in source.
- A 100k-event internal calibration reported 414 useful bins, peak |DNL| 2.196 LSB and peak |INL| 8.426 LSB. A repeated run reported missing raw codes 305..320 and smaller dips near 99..100 and 203..204.
- The long dead zone correlated with a clock-region boundary in the old placed design. **A universal claim that 7-series carry cascades cannot cross clock regions is not supported by AMD's architecture documentation.** Retain the observation; inspect actual routing/clock skew and characterize the new image instead of assuming the physical cause is proven or unavoidable.
- A 40-target Ã— 5-repeat MMCM random-delay test showed an 8000 ps coarse-count ambiguity in part of the phase range. At phase 117, coarse values 6/7 occurred with essentially identical fine indices 221/222. A fine-index-based correction was rejected.
- The third settling stage is in source, but its effect on that hardware ambiguity has not been re-measured. Run dense repeated boundary tests and document any residual self-test exclusion range. Do not promote the source change or logic PASS to proof that the issue is fixed.

The supporting TDC_IMPLEMENTATION_ANALYSIS.md contains the retained measurement details. Its operational setup/status material has been consolidated here.

For current single-ended TDC acceptance: verify the 128/512 primitive counts, inspect placement/routing, meet ordinary logic timing, establish SINGLE-input WIDTH capture/timeout/re-arm behavior, characterize clock boundaries and code density, then calibrate against the exact bitstream. External LVDS acceptance is deferred. A fixed synchronous loopback alone does not establish uniform code-density coverage. Confirm phase walking for an internal source before activating its LUT; --collect-only supports inspection first.

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

### 2026-10-19 latest source: v9 rising-polarity fall sampler and timing repair

User authorized investigating/fixing the four-tap FALL rejection pattern and
remaining timing paths. No explicit logical error was established in the
shared majority/prefix encoder. The physical FALL path previously inverted the
snapshot AFTER a falling wave propagated through CARRY4; it cannot remove
polarity-dependent propagation skew. V9 avoids relying on falling-wave tap
order by adding `i_tdc/i_width/i_fall_carry` driven with `~event_i`. External
RISE still uses `i_tdc/i_width/i_carry`; both now encode rising waves with the
unchanged strict encoder. This is a design repair supported by the polarity
asymmetry, not a proven explanation of every old malformed code.

- Falling detection and timestamping use the new sampler's own tap zero, not
  the old chain's falling detector. Separate unconditional raw pipeline stages
  align that snapshot with its write enable/address. No inversion after capture.
  Both chains have local registered reset leaves on the same sampler clock.
- Adds 128 CARRY4 and approximately 1536 tap/pipeline FFs plus control, without
  increasing raw-ring, result or LUT memory capacity. Remaining FF/carry fit,
  clock distribution, routed timing and power require external implementation.
- LUT readiness uses 32-bit registered groups then a registered all-ready bit.
  Bitmap writes/clear are independent of shared activation validation. Readiness
  asserts two bus clocks after the last entry; invalidation flushes both stages.
- Registered `last_frame` is loaded from requested count and updated from the
  pre-decrement count at markers, removing that comparison from capture enables.
- Registered watchdog expiry uses a precomputed TIMEOUT-2 match and explicit
  TIMEOUT=1 restart seed. Manual cycle review preserves the previous timeout
  terminal edge and marker priority. No simulation was run to establish this.
- Unused metadata cycles hold frame-derived data with write-enable inactive,
  removing the all-zero default decode from wide metadata control pins.
- ID is now 0x54444309; width ID stays 0x50574201. Registers/record layout and
  API semantics remain compatible with current v8 software. VERSION? returns 9.
  No API/SCPI changes needed for this source repair. Existing TB's ID expectation
  changed to 9; no tests were added or run.
- Managed XDC includes only the new asynchronous sampler tap D exception and
  updates the renamed timeout/last-frame mailbox bounds. No blanket clock or
  functional datapath false paths were added. Collection checker expects three
  chains; placement helper and diagnostics cover the new hierarchy. All three
  chains need distinct legal locations. No coordinates were selected here.
- Refresh helper still imports/byte-verifies project-owned copies, defaults
  BNET off and includes the updated width/register RTL and TDC XDC. Its message
  now identifies v9 and the extra sampler placement requirement.

Validation: static Slang 12 compile of the complete `tdc_top` hierarchy with
default timescale 1ns/1ps and unresolved vendor primitives allowed: 0 errors,
0 warnings. This is not vendor elaboration or synthesis. Tcl `info complete`
passes on refresh/checker/diagnostics/placement scripts and TDC XDC; it does not
execute Vivado commands or validate synthesized collections. git diff --check
passes. No simulations, numerical tests, builds or live board actions were run.
The prior parser cache requires a missing Python 3.12 runtime; a compatible
Slang package was installed only in ignored `build/hdl-tools-py313` for static
checking. No project runtime dependencies were changed.

Next: `set custom_enable_bnet 0`, source refresh helper in external Vivado,
reset runs, implement, inspect three chains and timing/CDC/DRC/utilization.
After loading, confirm VERSION?=9. Update notebook's manual image label/WNS,
restart kernel, repeat direct AWG baseline at 997 kHz/50%, and recollect BOTH
LUTs after validity passes. Old v8 LUTs are invalid for the new placed image.
Check fixed rise/fall input-route offset against independent known pulse widths
after code-density calibration; separate line delays can add a constant bias.

### 2026-10-19 latest: direct AWG with PCB disconnected restores frame capture

User disconnected all PCB connections and connected AWG directly to FPGA,
still 997000 Hz/50%, same -1.143 ns image. Read latest notebook and all 25 CSVs
from `scpi-tests/tdc_external_square_results/20261019T160425_675216Z`. No board
actions, code changes, LUT uploads or new measurements made during this review.

- Baseline acceptance 4119/8192 (50.28%), versus old 38/8192 (0.464%) and
  predicted 49.7%. Mean 499.732945 ns, std 1.040491 ns, range 496..504 ns,
  nominal HIGH 501.504514 ns (mean error -1.771569 ns). Scope reference is None,
  so this comparison uses generator settings, not an independent width reading.
- Across all 25 captures: 102311/204800 accepted (49.9565%). 101051 frames
  report EXTRA_EDGES, and every one also reports HIGH_START; no extra-edge
  flags occur in frames that started LOW. Boundary rejection now explains this
  pattern; the previous pervasive extra-event symptom is gone. All 25 saved
  record audits pass. Status/cleanup are normal.
- Calibration RISE: 98192 valid samples, 214 populated bins, 100% valid,
  CDF drift 0.001362, no gate errors. FALL: 92826 valid samples, 130 populated
  bins, 94.5352% valid, CDF drift 0.001494. Largest FALL bin is only 2.075%,
  versus previous 82.51%. Enough data and broad stable coverage now exist.
- Remaining gate failure: 5366/98192 complete pulses have invalid fall codes
  (5.4648%). Across baseline+calibration, all 5590 invalid falls have status
  0x24 (MULTIPLE_TRANSITIONS + BUBBLE_CORRECTED); all their returned fall_raw
  indices satisfy index % 4 == 1. Valid falling codes also favor positions 0/1
  modulo four. This points to structured carry/encoder behavior at CARRY4
  granularity, but index statistics alone cannot identify a specific tap fault.
- Rising BUBBLE_CORRECTED-valid codes are 5630/102311; falling
  BUBBLE_CORRECTED-valid codes are 71844/102311. Corrected bubbles remain
  accepted, while codes still having multiple transitions remain rejected.

Conclusion: disconnecting PCB largely resolves physical event capture; this
supports a connection-related cause for the earlier extra edges, without
identifying output contention, grounding, loading or coupling individually.
Fine width calibration is still blocked by the FALL >=99% validity gate;
candidate ready=False and upload/validation remain unexecuted. Do not increase
batch count or lower that gate to force acceptance. Next HDL investigation:
falling-polarity tap ordering/skew and majority/chunk boundary handling, ideally
with raw thermometer snapshots; also close the remaining capture control timing.
Separate per-edge LUTs are still needed. Existing falling code holes are
structured and repeat every four taps; missing raw codes alone do not prove
missing physical time coverage. No accuracy/precision acceptance while timing
fails and a 5.5% phase-dependent subset is excluded from code-density scaling.

### 2026-10-19 latest external calibration result: failed, no LUT upload

Read saved notebook outputs and all 25 raw CSV captures from
`scpi-tests/tdc_external_square_results/20261019T154652_282886Z` (one baseline
plus 24 calibration bursts). Settings: 997000 Hz, 50%, 3.3 Vpp/+1.65 V,
8192 frames/burst, 1000 ns internal windows. Preflight reports width version 8,
512 taps, 4000 ps ticks, capacity 16384, SINGLE. User identifies loaded image
as the -1.143 ns build. Actual scope waveform/settings were not independently
observed during this review.

- Baseline: only 38/8192 complete pulses (0.464%, versus predicted 49.7%). All
  have 480 ns coarse width, versus nominal 501.5045 ns, error -21.5045 ns.
  Zero reported standard deviation is a severe selection/quantization artifact,
  not demonstrated high precision. Baseline fall validity is 32/38 (84.2%).
- Calibration: 848 complete pulses out of 196608 frames (0.431%). Rise valid
  samples 848, 106 populated bins, 100% valid among selected complete pulses.
  Fall valid samples 749, 8 bins, 88.33% valid. Bin 168 contains 618/749 fall
  samples (82.51%). Gates require 50000 samples, >=32 bins and >=99% per-edge
  validity. Candidate ready=False; upload/validation cells are unexecuted.
- Across baseline+calibration: 886/204800 complete pulses (0.433%), all 480 ns;
  203836 frames (99.53%) report EXTRA_EDGES. Notebook raw-record invariant
  audits pass; this addresses the previous contradictory-record symptom but
  does not establish correct physical capture. Status is DONE without timeout
  or overflow and cleanup succeeds.
- Accepted frame groups recur about every 334 windows, often as adjacent
  pairs, consistent with a narrow accepted phase region near the 1 MHz/997 kHz
  beat. The distributions are phase-selected and unsuitable for full-tick
  code-density normalization. Sparse missing bins do not yet characterize
  physical dead zones. More batches alone do not fix selection bias.

No unique root cause follows from result records: check the actual HIGH/LOW
duration and frequency on pin 7, AWG-only input (PCB return disconnected), and
physical pin 5 isolation. Repeating the baseline at 100003 Hz/50% with matching
notebook settings can distinguish a window/rate dependence; it does not repair
the existing internal 250 MHz timing failures. If a clean input is confirmed,
investigate capture-edge/extra-edge qualification and close the remaining HDL
control paths before attempting LUT calibration again. Do not upload this
candidate or fit an offset to conceal the failure.

Added a notebook baseline gate before the 24-burst collection using existing
guard_reference_capture: fewer than 100 complete pulses or severely low yield
now stops early. Matching migration utility updated; all saved outputs retained.
No HDL changes, live board actions or new acquisition were made for this review.

### 2026-10-19 board loaded: provisional external fine calibration prepared

User confirms the loaded image is the BNET-disabled build with WNS -1.143 ns,
not a timing-closed successor. Streaming and dual-channel work are set aside;
the current task is calibrating the single-ended width TDC using the manual AWG.
The AWG can be configured as needed; actual settings have not been confirmed
or programmed by the agent. No live board connection, acquisition or LUT upload
was performed in this preparation.

Updated `scpi-tests/tdc_external_square_test.ipynb` for 997000 Hz, 50%, 3.3 Vpp,
+1.65 V offset, 8192 frames/burst and 24 calibration bursts. Internal windows
are 1000 ns; expected HIGH is 501.5045 ns, with approximately half of frames
containing a complete pulse. Wire AWG to DIO2_P/E1 pin 7 and common ground on
25/26; leave FPGA output DIO1_P/pin 5 disconnected from the AWG signal.

Notebook changes:

- Preflight disables the FPGA pulse output, aborts old capture, selects SINGLE
  and disables correction. Optional VERSION? is probed on a disposable socket;
  v8+ servers use DATA:RAW?, older servers use installed DATA?. Existing API,
  SCPI and HDL are unchanged in this notebook task.
- Full raw-record invariant audit blocks calibration of contradictory flags,
  frame IDs, widths or indices. Every received record is saved before errors
  propagate. Per-edge status/validity is reported among complete pulses.
- Keep the existing >=99% per-edge valid fraction and histogram coverage/drift
  gates, now requiring >=50000 valid codes per edge. Do not relax these to
  force the former low falling-edge validity through calibration.
- Both LUTs are backed up, uploaded, read back and activated only when candidate
  gates pass. Fresh captures verify width_ps equals coarse*4000 + rise_LUT -
  fall_LUT for CALIBRATED records, and compare coarse/fine precision under the
  same fine-code eligibility rule.
- FIT_HOST_REFERENCE_OFFSET defaults False. Fine improvement is evaluated
  without a fitted mean offset; the optional old reference experiment remains.
- Image label/WNS and provisional status are saved with captures/LUTs. No final
  precision or accuracy acceptance is possible while capture timing fails;
  redo calibration after a new place/route image. Uniform phase remains an
  assumption to assess with histograms and changed frequency/duty validation.

Historical notebook/settings/outputs were preserved at
`build/tdc-calibration-backup/tdc_external_square_before_20261019.ipynb`; working
notebook outputs are cleared to avoid presenting old-image results as current.
Notebook code cells were parsed for syntax and git diff whitespace checked.
No notebook cells, numerical tests, simulation, API builds or Vivado were run.
Next user action: configure the physical AWG, restart notebook kernel, confirm
RP_IP, run sections 1â€“4, inspect integrity and rise/fall histograms; then use
sections 5â€“6 if candidate gates pass. Await new hardware results for assessment.

### 2026-10-19 latest assessment: BNET-disabled routed build, 14:54 report

User completed the next implementation. Read the new impl_1 routed timing,
route status, bus-skew and DRC reports plus placed utilization; no Vivado,
software or hardware tests were run, and no HDL was changed for this review.

Compared with the earlier October 19 build:

| Metric | Earlier | Latest |
|---|---:|---:|
| Setup WNS | -4.119 ns | -1.143 ns |
| Setup TNS | -27627.521 ns | -1596.396 ns |
| Failing setup endpoints | 29251 | 4951 |
| Worst hold slack | +0.049 ns | +0.005 ns |
| Failing hold / pulse-width endpoints | 0 / 0 | 0 / 0 |
| BRAM tiles | 136/140 | 86/140 |
| Occupied slices | 79.73% | 60.89% |
| LUTs | 28605 | 19268 |
| DSPs | 72 | 22 |

WNS deficit fell 72.25%, TNS magnitude 94.22% and failing endpoint count 83.07%.
Routing completed with zero routing errors. All eight bus-skew summary entries
pass (minimum +2.817 ns). Inter-clock groups now all pass, including ADC to
sampler +0.576 ns and ADC to PS +1.181 ns. Sampler reset recovery now passes
at +0.054 ns. Hold passes with a small +0.005 ns minimum margin.

The active XPR file membership uses the flat project-local source copies,
which match the repository for width, legacy TDC, encoder, top and shared CDC.
DISABLE_BNET is present in the project. Older nested copies still exist on disk
but are not active XPR members for these modules. The combined HDL changes and
BNET exclusion account for the new build; their individual effects are not
separable from these reports alone.

Remaining reported worst paths are all in i_tdc/i_width:

- 125 MHz: lut_written[444] to lut_written[697], -1.143 ns, nine LUT levels,
  8.810 ns data delay, 81.45% routing. The 1024-bit all-written reduction feeds
  LUT activation validity and shared write acceptance, creating a long path
  back into the bitmap. Next repair should register grouped completion checks
  and decouple bitmap writes/clear from activation validation.
- 250 MHz: target_count[3] to state[0], -1.129 ns, six LUT levels. Remaining
  count/last-frame decisions feed capture state and timestamp enables. Next
  repair should precompute/register the final-frame decision with exact count
  alignment.
- 250 MHz: watchdog[4] to metadata pipeline synchronous R pins, -1.058 ns;
  mapped path crosses carry logic and metadata selection. Timeout qualification
  and wide metadata defaults should be separated/pipelined while retaining the
  correct edge timestamp and timeout cycle. These are setup failures at a
  synchronous reset input, not the old asynchronous recovery failure.

Only the worst ten paths per clock group are included; absence of legacy
multiply/encoder paths from those lists does not prove every such path passes.
4951 setup endpoints still fail: the image is not timing closed and neither
measurement accuracy nor fine calibration is accepted by this review. Existing
constraint coverage warnings remain (120 no-clock pins, 53 unconstrained
internal endpoints, 26 inputs and 58 outputs without complete delay coverage).
Routed DRC contains warnings/advisories, no Error/Critical Warning entries in
its summary. The requested task was assessment; further HDL repair awaits the
next task.

### 2026-10-19 earlier: routed v8 review and BNET exclusion source repair

New `C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/redpitaya.runs/impl_1`
reports dated October 19 13:29 show WNS -4.119 ns, TNS -27627.521 ns and 29251
failing setup endpoints. Previous values were -5.754 ns, -59898.672 ns and
39710. Hold and pulse-width checks pass. BRAM is 136/140 tiles and occupied
slices 79.73%. Imported TDC/top/SDF sources matched repository bytes before
this repair. Do not use the older October 16 diagnostics folder as this build's
report. Board measurements remain from the previously identified older image.

Source changes after this routed build (not built or simulated):

- `DISABLE_BNET` removes BNET engines, DDR readers, combine/serializer logic,
  register bank and digital capture RAM. Source files stay available. Ordinary
  ADC/scope and local-table ASG/DAC paths remain. Unused HP request outputs are
  tied inactive; ASG deep-memory mode remains stubbed as before.
- `refresh_custom_sources.tcl` defaults `custom_enable_bnet` to 0 when unset,
  imports verified project-owned copies and disables the BNET reader XDC.
  Explicitly set `custom_enable_bnet 0` before sourcing for the next build;
  set it to 1 before sourcing to restore BNET later. Reset synthesis and
  implementation runs after refresh. The collection checker now checks that
  BNET instances are absent when disabled, and fine LUT block RAM is present.
- The disabled BNET bus region returns zeros and acknowledges requests.
  API initialization can still map it; BNET hardware operations check the
  stream-count capability and return RP_EUF when absent. Rebuild API and the
  statically linked SCPI server to get that capability check.
- Worst legacy TDC path (-4.119 ns) combined multiply, fine selection and
  subtraction. It now uses 16x16 partial products, registered sums and a
  two-stage total subtraction (six extra legacy completion clocks).
- Width encoder START reduction/control (-3.377 ns) now has a registered raw
  selector and chunk-based all-zero/all-one accumulation. Its reset is locally
  registered and no longer gates the 512-bit load/shift bank.
- Width capture uses registered period legality instead of a remote period
  comparison in timestamp enables (-2.527 ns). Functional fast resets use
  synchronous local capture/processor reset leaves; the physical carry reset
  synchronizer remains, addressing -0.789 ns recovery violations without
  adding false paths.
- Fine LUT distributed-RAM output paths failed ADC-to-sampler setup by up to
  -0.620 ns. Two tables now use reset-free, dual-clock block RAM read ports;
  existing SCALE/CORRECT sequencing supplies the read latency. This uses RAM
  capacity released by excluding BNET.
- Shared `rtl/sys_bus_cdc.sv` now snapshots slave read data at acknowledgement
  before completion crosses to the PS. This removes live slave/address mux
  logic from the failing return path (-0.185 ns). Refresh imports this shared
  file as a project-owned copy too.

Interface IDs remain TDC 0x54444308 and width 0x50574201. No tests, builds,
simulation or Vivado runs were performed for these changes; routed timing
closure and measurement improvement remain unverified. Next: refresh with BNET
disabled, reset runs, rebuild externally and inspect timing/CDC/DRC/utilization
and diagnostic collections before deploying. Recharacterize fine LUTs for the
new placement after hardware record integrity is established.

### 2026-10-19 earlier: v8 timing and capture integrity (subsequently built)

At this earlier stage the user authorized another HDL review/repair and
API/SCPI changes. Reports and sine captures then available were October 16. The loaded
board image was explicitly identified by the user as predating the October 16
pipeline repair. Do not attribute its measurements to the new HDL.

The latest sine capture is `tdc_pcb_sine_20261016T134802_351244Z`: FPGA 100 kHz,
analogue 1 kHz, 0.4 Vpp, 0.4 V offset. Fit amplitude 56.78 ns, RMSE 15.12 ns,
R2 0.8757; second-harmonic fit amplitude 19.76 ns. There are 2048 missing-mode
records, exactly cycle_id % 8 == 1, 57 VALID/frame-error conflicts, and 291
missing FINE_INVALID flags. Excluding every eighth row barely changes sine
RMSE (14.75 ns), so this flag fault alone does not explain the distortion.
The coarse path has no 5 us/half-clock clamp or voltage/sine mapping; fine
encoder indices do not alter coarse-only widths. Timing errors and a nonlinear
PCB transfer remain separate hypotheses. No unique physical root cause is
established by the review.

Additional source changes:

- Width capture now stores two raw 32-bit edge timestamps plus flags in the
  four-slot ring (560 bytes logical). Timestamp subtraction moves out of capture
  into two 16-bit processor stages, retaining modulo-2^32 wrap behavior.
- Timestamp/watchdog counters use registered one-tick-early byte carries;
  watchdog terminal equality replaces wide arithmetic comparison. LUT fetch,
  fine subtraction, 44-bit coarse scaling and 45-bit correction are separated.
- Encoder chunk analysis uses a balanced prefix tree. Removed the redundant
  512-bit encoder input register and reset of the fully overwritten shift bank.
  Filtering/status rules are unchanged; no acceptance of malformed fine codes.
- `tdc_registers.sv` now reports **0x54444308**. PWB ID stays 0x50574201.
  Width register **0x148 READ_READY bit 0** indicates seven bus-clock pipeline
  settling. Updated API polls it on v8+, with old-image settling fallback.
- API normal width reads reject inconsistent records rather than trusting
  VALID alone. `rp_TdcWidthReadRaw` and **TDC:WIDTH:DATA:RAW? start,count** retain
  the six hardware fields for diagnosis; **TDC:WIDTH:VERSION?** returns 8 for
  v8. These additions require rebuilding API and statically linked SCPI server.
  Sine helper now audits old-server records too, stores the audit in capture
  metadata and blocks acceptance/fitting of contradictory data. Notebook adds
  audit display; saved outputs/settings are preserved as historical data.
- The shared SDF engine now pipelines product/sum/rounding/saturation with all
  metadata and saved feedback aligned. Delays 1/2/4 use a four-entry forwarding
  bank at the delayed calculation stage; longer feedback uses existing RAM.
  Small delay arrays no longer bulk-reset, allowing distributed-RAM inference.
  Added latency is four clocks per active stage (48 clocks for 12 stages).
  BNET numerical/order/performance acceptance must be repeated externally.
- Refresh helper explicitly imports the changed SDF source as a project-owned
  copy. Diagnostics now include timestamp/watchdog, arithmetic, SDF, CDC and
  clock-interaction reports. Carry instance names/placements and actual timing
  requirements are preserved. Existing test-driver ID/settling expectations
  were adjusted; no new tests or test runs were added.

No tests, software builds, simulation or Vivado runs were performed in this
follow-up. Do not run Vivado here. No timing closure or distortion improvement
is claimed. User must refresh project copies, reset old runs, rebuild and
inspect timing/CDC/DRC/utilization, rebuild/deploy API/server, and identify v8
before a fresh independent square-pulse check and sine comparison. Fine LUTs
need recharacterization after the new physical implementation is trustworthy.

### 2026-10-16 TDC timing repair pending implementation

The user ran `diagnose_tdc_width.tcl`; actual reports are readable at
`C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/tdc_width_diagnostics`.
This implementation has WNS -5.754 ns and 39,710 failing setup endpoints.
Targeted TDC slacks: capture rise -2.933 ns, fall -2.422 ns, encoder -3.696 ns,
result write address -3.233 ns, result read/scale -3.042 ns, and capture-counter
to raw RAM WE -4.679 ns. These are real internal synchronous paths. The worst
global path is in butterfly/SDF; it is not repaired by the TDC patch.

At the user's request, `tdc_pulse_width.sv` now pipelines raw capture data and
all associated controls/metadata, adds a fetch wait, tracks staging occupancy
directly, narrows bounded acquisition counters, and uses a remaining-frame
countdown. Timeout terminal count is precomputed on the bus and the XDC/checker
mailbox selector now includes `timeout_last_cfg`. Results use <=1024-record
BRAM banks with preserved local port registers, a registered read mux, and
separate scale/correction arithmetic stages. DONE waits for pending writes.
`tdc_thermometer_encoder.sv` splits chunk filtering, accumulation and output
decode into pipeline stages without relaxing invalid-code rules. The diagnostic
helper follows the new hierarchy and adds capture-stage, utilization and
bus-skew reports. The existing source refresh helper imports these HDL/XDC
files into project-owned copies, including the encoder via its TDC glob.

The register ABI, 16384-record capacity, API, SCPI server and notebooks remain
unchanged. New read-index settling requirement: 4 bus clocks for raw fields,
7 for width, before registering the bus response. Existing `rp_TdcWidthRead`
already performs 16 settling reads of READ_INDEX, confirmed in `tdc.cpp`.
Direct-register clients/testbenches must allow the new latency. No tests,
simulation, synthesis or implementation were run for this patch. Prior PASS
logs do not validate these changes. User must refresh copies, reset old runs,
rebuild, review timing/CDC/DRC/utilization and collect fresh hardware results.
Do not run Vivado on this laptop. Fine calibration stays gated until capture
and readback are trustworthy; these edits are not evidence of timing closure.

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

**Deferred LVDS reference:** the differential launch/return procedure and SCPI
sequence below are preserved for future use. Current work uses the single-ended
WIDTH notebook; LVDS tests are not part of its immediate acceptance criteria.

The saved 2026-10-14 run reported unsupported Tcl if blocks in the two custom managed XDCs; its worst -10.290 ns path ended at an asynchronous carry tap. The tap selector also assumed a slash where the synthesized generated hierarchy uses a dot. Both custom XDCs now contain supported constraint commands with no control flow, and the tap pattern is corrected. Only tap D measurement inputs and documented first synchronizer stages/reset synchronizer CLR inputs are exempt. Encoder, controller, FIFO, clocks, functional reset release and ordinary datapaths remain timed. No global asynchronous clock grouping is applied.

The remaining real paths were addressed in the pulse counter and BNET scheduler/debug transfer as described above. The Gen2 E3 receive clock now uses the P pin only, fixing the previous two-source clock warning. These source changes are an attempted timing repair; they are not a timing-closure result. Refresh the files, reset old synthesis/implementation runs, rebuild and inspect the new report. Resolve any non-measurement negative slack before accepting operation.

Use the width burst procedure in section 7 for the PCB's voltage-dependent HIGH duration. The following optional legacy test measures launch-to-return rising-edge delay and does not validate the new pulse-width function. After the new image passes the applicable implementation checks:

- Verify current TDC ID 0x54444307 at 0x40710000 and NUM_TAPS 512 at 0x40710018; verify pulse ID 0x50554c01 and tick 2 as well.
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
| scpi-tests/tdc_pcb_sine_test.ipynb | External manually configured analogue sine through PCB to WIDTH burst capture; configurable FPGA clock, raw CSV/settings, normalized shape/frequency comparison; no PCB voltage calibration assumed |
| scpi-tests/bnet_sdf_capture_feature_test.ipynb | Current SDF, digital capture, runtime lengths/banks and optional split/combine tests |
| scpi-tests/bnet_pipeline_mode_test.ipynb | Serial/static comparison and cold/warm diagnostics; check engine compatibility and stale outputs |
| scpi-tests/ddr_bnet_test.ipynb | DDR/fixed-point/RF regression and historical models |
| scpi-tests/ddr_bnet_complex_rf_test.ipynb | Complex RF experiments |
| scpi-tests/asg_125mhz_alternating_loopback_test.ipynb | ASG/RF alternating-pattern diagnostic |
| scpi-tests/tdc_calibrate.py | Code density, LUT/calibration, precision and documented dead zones |
| scpi-tests/tdc_internal_selftest.ipynb, tdc_internal_test_py.py | TDC internal/MMCM experiments |
| scpi-tests/tdc_mmcm_random_delay_test.py | Commanded phase/coarse-delay repeatability and boundary ambiguity |

Saved notebook outputs are not a fresh acceptance run. For example, the SDF notebook's current split-helper source says v5 while a stored output says v3; the pipeline notebook contains a zero warm-total timing result and an implausible derived speedup. Restart the kernel, select an identified matching image, rerun setup and tests in order, and inspect raw status/pointers/counters before accepting performance numbers.

### PCB sine-chain notebook (2026-10-16)

Open scpi-tests/tdc_pcb_sine_test.ipynb with tdc_sine_tools.py and tdc_pulse_width_test.py beside it. Enter the external generator frequency, Vpp (not peak/Vrms), DC offset, FPGA trigger frequency and count in CONFIG. The notebook does not control the analogue generator. Defaults are example settings: 1 kHz sine, 1 Vpp, 0.5 V offset, 100 kHz FPGA clock, 16384 samples; verify the PCB's allowed analogue range before applying them. Uses the established E1 pin 5 trigger / pin 7 3.3 V return wiring. Requires NumPy and Matplotlib in the notebook kernel.

The PCB is not voltage-to-duration calibrated. Compare measured width against a sine at the entered frequency with fitted phase/DC/amplitude; also estimate the dominant tone independently. Entered voltage amplitude/offset are reference metadata, not measured volts, gain validation or calibrated reconstruction. Keep original trigger-cycle times when excluding invalid frames. Saves all records, flags, actual trigger period and configuration before analysis under scpi-tests/tdc_sine_results/ (ignored), plus analysis JSON and PNG plots. Starts pulse_gen before ARM, forces coarse mode and attempts output OFF/ABORT on every exit. A separate stop cell is available. Captures are finite bursts, not continuous streaming.

The user's V7 implementation completed routing with failed timing. Saved 2026-10-15 reports show WNS -4.779 ns, 37496 failing endpoints and BRAM usage 135.5/140 tiles. TDC capture and reset paths fail alongside BNET; lowering the trigger rate does not remove the internal 250 MHz violations. Notebook results are diagnostic until timing is repaired. All eight offline numerical/protocol tests in scpi-tests/tdc_sine_tools_test.py passed. Notebook schema and every code cell also passed with a synthetic 16384-record acquisition, CSV/JSON exports and visually checked PNG plots; a 1000.4 Hz synthetic tone was independently estimated at 1000.39996 Hz. These checks do not establish hardware operation or invoke Vivado/HDL simulation. Local reproduction runner/dependencies and synthetic outputs are under ignored build/tdc-sine-review/.

## 11. Next actions and unresolved items

Immediate pulse/TDC work:

**Input scope: SINGLE only for now.** Prioritize the single-ended AWG/PCB path;
LVDS development and calibration remain deferred. The active source baseline is
v12-timing-r1 as described in section 1; older image IDs and deployment notes
below are historical and do not supersede that baseline.

1. Refresh project-local source/constraint copies with scripts/refresh_custom_sources.tcl in the existing Vivado project on the build machine. Reset the old runs, rebuild and inspect timing/CDC/DRC and utilization, including BRAM inference for the width buffer. Do not run Vivado on this laptop.
2. Resolve the previously reported timing failures in a fresh implementation before accepting the merged image. Check the grouped encoder's ordinary 250 MHz paths and compact-result RAM inference/utilization. The updated collection checker requires RAMB primitives under i_tdc/i_width. Check both carry hierarchies and select separate legal placements before fine calibration. Local syntax/logic checks do not prove timing closure.
3. Load the new image and rebuild/redeploy the matching API and statically linked SCPI server. Verify TDC ID 0x54444307 at 0x40710000, width ID 0x50574201 at 0x40710100, and the pulse feature ID before SCPI tests.
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
