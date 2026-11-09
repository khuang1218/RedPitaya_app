# SCPI reference: two matrix weights and one TDC at 100 kHz

Companion notebook: [100kHz_matrix_demo.ipynb](100kHz_matrix_demo.ipynb).
It is now a helpers-only reference: running its code cells defines functions
without contacting hardware. The actual demonstration notebook will be built
separately. The final section shows an explicit call sequence with cleanup.
Target: STEMlab 125-14 / Z20_G2, V18 FPGA and the matching API/SCPI server in
this repository. OUT1 and OUT2 control two matrix weights. The external AWG
controls the matrix input and is **not configured by these commands**.

The ASG's SCPI prefix is `SOUR`, not `ASG`. The TDC measurement path for this
demonstration is `TDC:WIDTH:*`. It uses the separate digital `PULSE:*` generator
as its frame/PCB launch source. Ordinary ASG commands do not start that source.

This reference covers the commands needed for the demonstration and relevant
waveform, calibration and diagnostic options. The server also exposes ASG DMA,
frequency-sweep and legacy TDC self-test facilities; those are not required here.

## Transport, syntax and units

- Connect to the board's IP using TCP port **5000**; terminate commands with
  `\r\n`. Send one command/query at a time.
- A setter normally returns no data. A query ends in `?` and returns an ASCII
  line ending with a newline. Read the entire line before sending another query.
- Read `SYST:ERR:NEXT?` after each operation. A response beginning `0,` means
  no error. A timeout or missing response is a failed operation.
- `n` below means ASG channel **1 or 2**, e.g. `SOUR1:VOLT 0.1`.
- Arguments are separated by commas. Times in **PULSE** commands and WIDTH
  **OFFSET** are integer **nanoseconds**. WIDTH results and LUT entries use
  **picoseconds**. WIDTH watchdog uses **4 ns ticks**. Frequencies use **Hz**.
- `ON` / `OFF` are accepted for Boolean setters; queries may return `1` / `0`
  or `ON` / `OFF`, depending on the handler.
- Commands below use valid long names or the registered short spelling.

| Command | Function and use |
|---|---|
| `SYST:ERR:NEXT?` | Read and remove the next server error. Check after setters and queries; stop on nonzero code. |
| `*CLS` | Clear accumulated SCPI status/errors when deliberately beginning a new session. Do not use this to hide an error during a capture. |
| `*IDN?` | Server/device identification when supported by the deployed server. TDC version queries below identify the custom FPGA interface. |

## Wiring and channel roles

| Signal | Connection |
|---|---|
| Weight 1 | OUT1 SMA to PCB weight-1 voltage input |
| Weight 2 | OUT2 SMA to PCB weight-2 voltage input |
| Matrix input | External AWG to the PCB input port; controlled separately |
| Digital launch | DIO1_P, E1 pin 5, to PCB clock/launch input |
| Single pulse return | PCB output to DIO2_P, E1 pin 7; 3.3 V logic and common ground |

Both weight outputs are independent analogue channels. The TDC captures one
selected PCB return; it does not independently measure both weights. Its 250 MHz
sampling clock stays internal. The legacy differential E3 launch is a different
measurement path and is disabled in this demonstration.

## ASG: configure the two analogue weights

Configure channels while outputs are disabled. The notebook uses `INF` load
calibration and `abs(offset) + peak amplitude <= 1 V`. Check the PCB voltage
range and actual load. Load compensation is a numerical setting, not a physical
termination. ASG voltage is not automatically a calibrated numerical weight.

| Command / query | Function, parameters and example |
|---|---|
| `GEN:RST` | Reset both standard generator channels and sweep defaults. Reapply both weight configurations afterwards. This is not an FPGA reload or TDC reset. |
| `OUTPUTn:STATE OFF` / `ON` | Disable/enable one output, e.g. `OUTPUT1:STATE OFF`. |
| `OUTPUTn:STATE?` | Read that channel's output-enable state. |
| `OUTPUT:STATE OFF` / `ON` | Change both output enables synchronously. The notebook enables both after configuring/readback. |
| `SOURn:FUNC DC` | Set waveform: `DC`, `DC_NEG`, `SINE`, `SQUARE`, `TRIANGLE`, `SAWU`, `SAWD`, `PWM`, or `ARBITRARY`. Use `DC` with amplitude zero and offset equal to the static weight voltage. |
| `SOURn:FUNC?` | Read selected waveform. |
| `SOURn:VOLT 0.1` | Set **peak amplitude in volts**, not Vpp. A 0.1 V SINE has 0.2 Vpp before load effects. Set this to zero before changing a DC weight offset. |
| `SOURn:VOLT?` | Read configured peak amplitude. |
| `SOURn:VOLT:OFFS 0.3` | Set DC offset in volts. With DC and amplitude 0, this sets the static output level to 0.3 V. |
| `SOURn:VOLT:OFFS?` | Read configured DC offset. |
| `SOURn:FREQ:FIX 100` | Set waveform repetition frequency in Hz. Irrelevant to a constant DC value; use low frequencies for time-varying weights sampled at 100 kHz. |
| `SOURn:FREQ:FIX?` | Read configured frequency. |
| `SOURn:FREQ:FIX:DIRECT 100` | Optional direct frequency update without the ordinary frequency-setter reset sequence. Use only if continuous phase behaviour is needed; not used by this notebook. |
| `SOURn:PHAS 90` / `SOURn:PHAS?` | Set/read waveform phase in degrees; notebook accepts −360 to +360. |
| `SOURn:DCYC 0.5` / `SOURn:DCYC?` | Set/read PWM duty as a **fraction**, e.g. 0.5 = 50%. It is not a percentage argument and is not the digital PULSE duty setting. |
| `SOURn:RISE:TIME 10` / `SOURn:RISE:TIME?` | Set/read supported waveform rise time in **ns**; hardware/API may enforce a frequency-dependent minimum/maximum. Optional for waveform shaping. |
| `SOURn:FALL:TIME 10` / `SOURn:FALL:TIME?` | Set/read waveform fall time in **ns**; same limits apply. |
| `SOURn:LOAD INF` / `SOURn:LOAD L50` | Select high-impedance or 50 Ω load compensation. `L50` assumes a real matching load and reduces the allowable configured amplitude/offset range. |
| `SOURn:LOAD?` | Read `INF` or `L50`. |
| `PHAS:ALIGN` | Synchronize the two ASG state machines after programming their phases. Does not synchronize ASGs to PULSE or the external AWG. |
| `SOURn:TRIG:SOUR INT` / `SOURn:TRIG:SOUR?` | Select/read ASG trigger source: `INT`, `EXT_PE`, `EXT_NE`, or `GATED`. The demo uses internal triggering. |
| `SOUR:TRIG:INT` | Synchronize/start both ASGs using the standard trigger-both handler. Used after enabling both channels. |
| `SOURn:TRIG:INT` | Software-trigger/restart one ASG channel. Changes its phase relationship to the other channel. |
| `SOUR:TRIG:INT:ONLY` / `SOURn:TRIG:INT:ONLY` | Optional trigger-only variants, without the standard synchronise/reset behaviour. Not needed for this demo. |

### Optional custom and burst waveforms

The notebook uses standard, continuous ASG waveforms. These commands are useful
if a later weight sequence needs an arbitrary shape or finite number of cycles.

| Command / query | Function and example |
|---|---|
| `SOURn:TRAC:DATA:DATA {0,0.5,1,0.5,0,-0.5,-1,-0.5}` | Upload normalized arbitrary samples (−1 to +1, at most the 16,384-sample standard ASG buffer). Then select `SOURn:FUNC ARBITRARY`, amplitude, offset and repetition frequency. Small example only; choose enough samples for the intended waveform. |
| `SOURn:TRAC:DATA:DATA?` | Read back arbitrary waveform samples. Replies can be large. |
| `SOURn:BURS:STAT CONTINUOUS` / `BURST` | Choose generation mode; `CONTINUOUS` is used for static/dynamic demo weights. `STREAM` is also registered but requires a separate streaming setup. |
| `SOURn:BURS:STAT?` | Read generation mode. |
| `SOURn:BURS:NCYC 10` / `SOURn:BURS:NCYC?` | Set/read waveform cycles per ASG burst; this is not the number of TDC frames. |
| `SOURn:BURS:NOR 1` / `SOURn:BURS:NOR?` | Set/read number of burst repetitions. |
| `SOURn:BURS:INT:PER 10000` / `SOURn:BURS:INT:PER?` | Set/read internal burst repetition period in **microseconds**. Do not confuse it with PULSE nanoseconds. |
| `SOURn:BURS:INITVALUE 0` / `SOURn:BURS:INITVALUE?` | Set/read ASG initial normalized waveform value (−1..+1). `SOURn:INITVALUE` is an alias. |
| `SOURn:BURS:LASTVALUE 0` / `SOURn:BURS:LASTVALUE?` | Set/read normalized end-of-burst value. |
| `SOUR:TRIG:EXT:DEBOUNCER:US 1` / `SOUR:TRIG:EXT:DEBOUNCER:US?` | Set/read external ASG trigger debounce in microseconds; irrelevant for the demo's internal trigger. |

### Example: two DC weights

This is a command sequence, not a script to paste into a shell. Read/check the
error queue after each operation, as the notebook does. Outputs are intentionally
enabled only at the end.

```text
OUTPUT:STATE OFF
GEN:RST
SOUR1:VOLT 0
SOUR1:VOLT:OFFS 0
SOUR1:LOAD INF
SOUR1:FUNC DC
SOUR1:BURS:STAT CONTINUOUS
SOUR1:TRIG:SOUR INT
SOUR1:VOLT:OFFS 0.2
SOUR2:VOLT 0
SOUR2:VOLT:OFFS 0
SOUR2:LOAD INF
SOUR2:FUNC DC
SOUR2:BURS:STAT CONTINUOUS
SOUR2:TRIG:SOUR INT
SOUR2:VOLT:OFFS 0.4
PHAS:ALIGN
OUTPUT:STATE ON
SOUR:TRIG:INT
```

For a changing weight 1, disable OUT1, clear amplitude/offset, select `SINE`,
set `SOUR1:FREQ:FIX 100`, `SOUR1:VOLT:OFFS 0.3`, and `SOUR1:VOLT 0.1`, then
enable/start it. This programs approximately 0.2–0.4 V at 100 Hz under the chosen
load convention. To retain two-channel phase alignment, configure both while
off, then align/start both together. Hardware waveforms give controlled timing;
repeated Python voltage writes have network/OS latency and are not a precise
time-varying-weight generator.

## PULSE: digital launch and TDC frame clock

The V18 width API requires the pulse generator ON with **50% duty** when arming.
At 100 kHz use **period 10,000 ns / HIGH 5,000 ns**. This HIGH time is the PCB
launch waveform, not the return width measured by the TDC.

| Command / query | Function and use |
|---|---|
| `PULSE:OUTPUT OFF` / `ON` | Stop/start digital launch. OFF retains ownership of the pin and holds it LOW. Stop before changing timing. |
| `PULSE:OUTPUT?` | Read pulse-generator enable state. |
| `PULSE:TIMING 10000,5000` | Atomically set integer period and HIGH time in ns. Period is on a 4 ns grid; HIGH is on a 2 ns grid, positive and shorter than period. |
| `PULSE:TIMING?` | Return `period_ns,high_ns`; expect `10000,5000`. |
| `PULSE:PERIOD 10000` / `PULSE:PERIOD?` | Set/read period alone, in ns. Prefer TIMING to change period and width together. |
| `PULSE:WIDTH 5000` / `PULSE:WIDTH?` | Set/read HIGH time alone, in ns. |
| `PULSE:FREQUENCY 100000` / `PULSE:FREQUENCY?` | Set/read frequency in Hz; setting is quantized to the timing grid. Query TIMING to verify the actual period/duty. |
| `PULSE:PIN?` | Read selected launch pin; this build returns `DIO1_P`. |
| `PULSE:STATUS?` | Return numeric status: bit0 BUSY, bit1 active ENABLE, bit2 CLAIMED, bit3 ERROR, bit4 READY. Wait for mailbox BUSY to clear before another timing operation. |
| `PULSE:RESET` | Stop/release pulse-generator ownership and restore its defaults. Normal GPIO direction/data resume; use OUTPUT OFF to retain a driven LOW launch. |

## TDC: identify the image and select the one input

Legacy launch-to-return and WIDTH acquisition share resources. Keep the older
engine and its test sources disabled while running WIDTH.

| Command / query | Function and use |
|---|---|
| `TDC:WIDTH:VERSION?` | Read interface version, expected **18**. A version does not identify a unique routed implementation; record the bitstream label separately. |
| `TDC:TAPS?` | Read carry-tap count, expected **512**. |
| `TDC:WIDTH:TICK?` | Read coarse timing unit in **ps**, expected **4000** = 4 ns. |
| `TDC:WIDTH:CAPACITY?` | Read maximum records per burst, expected **16384**. |
| `TDC:WIDTH:MINIMUM:PERIOD?` | Read hardware minimum frame period in **ns**, expected **40** for V18. It does not promise startup yield at that limit. |
| `TDC:ENABLE OFF` / `TDC:ENABLE?` | Disable/read **legacy** TDC enable. Setting this ON is not how WIDTH capture starts. |
| `TDC:TEST:INTERNAL OFF` / `TDC:TEST:INTERNAL?` | Disable/read the legacy asynchronous self-test source. |
| `TDC:MMCM:ENABLE OFF` / `TDC:MMCM:ENABLE?` | Disable/read MMCM phase-sweep test enable. |
| `TDC:INPUT SINGLE` / `TDC:INPUT?` | Select/read single-ended DIO2_P input while disabled/idle. V18 resets to SINGLE; set/read explicitly for repeatability. `LVDS` selects the legacy E3 differential return instead. |
| `TDC:RESET` | Soft-reset shared TDC state. Not needed per burst; may clear active acquisition/calibration state. After reset, explicitly restore/check input, LUT activation and frame offset before fine capture. It does not replace PULSE or GEN reset. |

## TDC WIDTH: frame placement, acquire and read

| Command / query | Function and use |
|---|---|
| `TDC:WIDTH:ABORT` | Stop a previous or interrupted WIDTH acquisition. Poll STATUS until BUSY clears before configuration/readout. |
| `TDC:WIDTH:CLEAR` | Clear completed WIDTH result/status state while idle. A new ARM starts a new burst; read/save previous data before clearing or arming. |
| `TDC:WIDTH:OFFSET 0` / `TDC:WIDTH:OFFSET?` | Set/read frame boundary shift in **ns**, idle only. Multiple of 4 ns, 0..262140, strictly less than the launch period. At 100 kHz that means 0..9996 ns. Place both return edges inside one shifted frame. This is not a width-bias correction. |
| `TDC:WIDTH:TIMEOUT 5032` / `TDC:WIDTH:TIMEOUT?` | Set/read trigger watchdog in **fast ticks**, 4 ns each. **ARM overwrites it** with two launch periods plus 32 ticks: at 100 kHz `(10000/2)+32 = 5032` ticks. Host socket/capture timeouts are separate. |
| `TDC:WIDTH:ARM 4096` | Capture the next 4096 frames; valid count range 1..CAPACITY. Requires legacy engines OFF, PULSE already ON at supported period/50% duty, and valid offset. Does not start or configure analogue outputs. |
| `TDC:WIDTH:STATUS?` | Numeric status bitmask, decoded below. Wait for BUSY=0, then require DONE=1 and no error bits. Sampling completion alone may precede processing completion. |
| `TDC:WIDTH:COUNT?` | Read completed/stored record count. Require it to equal the requested burst length for a complete capture. |
| `TDC:WIDTH:DATA? 0,128` | Read indexed results: zero-based start, count 1..128. Repeat in batches; the command checks hardware-record consistency. Returns semicolon-separated rows, each with six comma-separated integer fields. |
| `TDC:WIDTH:DATA:RAW? 0,128` | Same fields, bypassing the API consistency guard for debugging. Do not reinterpret invalid rows as valid width measurements. Not used in the normal demo. |
| `TDC:WIDTH:DIAGNOSTIC:CONFIG?` | Read `stride,capacity` for sparse edge timestamp storage; normally `64,256`. |
| `TDC:WIDTH:DIAGNOSTIC:EDGE? 0,64` | Read 1..128 sparse diagnostic entries from a zero-based **diagnostic index**. Rows are `cycle_id,rise_ticks,fall_ticks`; timestamps use 4 ns fast ticks and wrap at 32 bits. This is not an ASG/external-AWG phase calibration. |

### Status, records and units

`STATUS?` bits:

| Bit | Meaning |
|---:|---|
| 0 | BUSY — wait before configuration or final readout |
| 1 | CAPTURING |
| 2 | PROCESSING |
| 3 | DONE |
| 4 | TRIGGER_TIMEOUT |
| 5 | RATE_ERROR |
| 6 | ABORTED |
| 7 | OVERFLOW |

Each `DATA?` row is:

```text
cycle_id,flags,coarse_ticks,rise_raw,fall_raw,width_ps
```

- `cycle_id`: one-based sequential frame number. Query indices remain zero-based.
- `flags`: validity, measurement mode and edge-encoder status bits.
- `coarse_ticks`: coarse rise-to-fall difference in 4 ns ticks.
- `rise_raw`, `fall_raw`: tap-code indices used by the two fine LUTs, not ns.
- `width_ps`: reported pulse width in picoseconds; divide by **1000** for ns.
  Invalid records must not be treated as a zero-width physical pulse.

Important record flags:

| Bit | Name / interpretation |
|---:|---|
| 0 | VALID |
| 1 / 2 | NO_RISE / NO_FALL |
| 3 | HIGH_AT_START — pulse was already high at frame start |
| 4 | EXTRA_EDGES |
| 5 | TRIGGER_TIMEOUT |
| 7 | FINE_INVALID — check edge status; coarse records may still be usable |
| 8 | COARSE_ONLY — valid width is `coarse_ticks * 4000` ps |
| 9 | CALIBRATED — valid width includes the FPGA fine correction |
| 10 / 11 | BOUNDARY / SATURATED — unsuitable frame association, not analogue voltage clipping |
| 12 | OUT_OF_RANGE |
| 13 / 14 / 15 | LATENCY_OVERFLOW / CROSS_FRAME / RETURN_LATE — retained compatibility diagnostics |
| 16..23 / 24..31 | RISE / FALL fine-encoder status bytes; bit0 of each byte indicates valid encoding |

In calibrated mode:

```text
width_ps = coarse_ticks * 4000 + RISE_LUT[rise_raw] - FALL_LUT[fall_raw]
```

The notebook verifies this arithmetic and preserves invalid-frame counts. A
small SD within one burst is not absolute accuracy. For changing weights the
width variation includes the intended matrix signal.

## WIDTH calibration: fine-mode setup once per reload

The intended demonstration now uses fine mode to show V18's full measurement
performance. Fine operation uses **two qualified WIDTH LUTs**, one
per edge. V17 tables, the legacy TDC LUT, or a table from another V18 placement
are not interchangeable. Calibration does not prove the PCB's weight/voltage
transfer function or correct every width-dependent systematic error.

| Command / query | Function and use |
|---|---|
| `TDC:WIDTH:CALIBRATION:ACTIVATE OFF` / `ON` | Select coarse/fine width reporting while idle. ON requires qualified tables to have been written to the FPGA. |
| `TDC:WIDTH:CALIBRATION:ACTIVATE?` | Read fine-calibration enable state. |
| `TDC:WIDTH:CALIBRATION:LUT:WRITE RISE,0,0,20,40` | Write consecutive RISE LUT entries from index 0; values are unsigned 16-bit **ps**. This three-entry syntax example is **not a usable calibration**. Write the full qualified 512-entry table, usually in chunks, and repeat for FALL. |
| `TDC:WIDTH:CALIBRATION:LUT:READ? RISE,0,64` | Read 64 LUT entries; use `FALL` for the other table. Compare every uploaded entry before activating. Count 1..512; start+count must stay within TAPS. |

The helper flow is explicit:

```python
calibration = read_calibration(CALIBRATION_FILE)  # PC file only
upload_luts(rp, calibration)                     # FPGA upload + full readback
enable_fine_mode(rp)                            # separate activation step
```

`read_calibration()` accepts `candidate_luts.json` or `uploaded_luts.json`, and
checks V18/tick/taps/input and candidate quality. `upload_luts()` checks the live
interface/input and leaves fine mode OFF until activation. The bundled file
is copied from qualified V18 run `20261026T150410_720673Z`. Verify it belongs to
the exact loaded route; record that implementation in `BITSTREAM_LABEL`.
Version number alone cannot verify physical-route provenance, and the older
calibration file's build label is a placeholder.

### Portable calibration files in this folder

Copy the whole `100kHz_demo` folder into another repository. Open the notebook
with the working directory set to that folder or its new repository root.
`CALIBRATION_FILE` and `FRAME_OFFSETS_FILE` then point to the bundled JSON files;
they no longer depend on the original PC's results directory. If using another
layout, set `DEMO_DIR` explicitly. The existing helper definitions work with
these same files; neither old captures nor the external AWG software are needed.

| File | Contents |
|---|---|
| [v18_luts.json](v18_luts.json) | Exact copy of the qualified V18 candidate: 512 RISE and 512 FALL entries in ps, quality statistics and source provenance. Historical source paths are metadata only. |
| [v18_frame_offsets.json](v18_frame_offsets.json) | Saved frame offsets by launch period, their qualification, and a separate unverified 100 kHz starting value. No universal width-bias correction is supplied. |
| [v18_calibration_manifest.json](v18_calibration_manifest.json) | Build/input/run identity and SHA-256 hashes, including the reference V18 `.bit` hash. Reuse only with that implementation and SINGLE input. |

Saved frame offsets were used successfully in selected complete V18 bursts:

| Frame period | Actual nominal rate | Frame offset |
|---:|---:|---:|
| 1000 ns | 1 MHz | 0 ns |
| 200 ns | 5 MHz | 0 ns |
| 100 ns | 10 MHz | 0 ns |
| 68 ns | approximately 14.706 MHz | 12 ns |
| 52 ns | approximately 19.231 MHz | 0 ns |
| 40 ns | 25 MHz | 0 ns |
| 10000 ns | 100 kHz | **0 ns starting value; not yet measured/qualified** |

These are historical independent-AWG frame settings, not measured PCB latency.
In the real demo, DIO1_P triggers the PCB return on DIO2_P: the return has a
fixed launch-to-rise delay rather than an independently drifting clock phase.
The external AWG modulates the matrix input; it does not supply the timing
reference. Start the PCB setup at `FRAME_OFFSET_NS = 0`, check its return
placement, and configure a different offset once only if needed. Do not apply
AWG phase searching or phase retries to this flow.

```python
calibration = read_calibration(CALIBRATION_FILE)
offset_ns = FRAME_OFFSET_NS        # PCB boundary; default 0, not the AWG map
upload_luts(rp, calibration)        # both tables, once after reload
enable_fine_mode(rp)
set_frame_offset(rp, offset_ns)     # separate setting, while idle
```

The historical `read_frame_offset()` reader remains available for reproducing
AWG tests and prints a notice for its unverified 100 kHz default. The demo flow
does not call it. Override `FRAME_OFFSET_NS` with a checked PCB boundary when
needed. With timing bounds relative to the TDC launch/frame reference, the
optional offline helper `check_pcb_return_window(earliest_rise_ns,
latest_rise_ns, maximum_width_ns, period_ns=10000, offset_ns=FRAME_OFFSET_NS)`
checks both edges fit in the same launch frame. Its default 8 ns guard is an
engineering starting margin; include actual jitter and the full weight/input
range in your bounds. Fixed delay of both edges cancels in width, but the pulse
must still fit inside the shifted 10 microsecond frame. No AWG-derived width
bias correction is automatically applied to the PCB.

The LUTs can be reused without an old PC; the physical route,
input path and measurement conditions must still be appropriate.

Upload/activate once after reload, not per capture. Set/read the frame offset
separately with `set_frame_offset(rp, offset_ns)`, once during setup or when it
changes. `capture_burst()` only reads the configured offset; it never rewrites
it or uploads LUTs. Stopping outputs and closing TCP leave the FPGA settings
intact. FPGA reload/power loss requires restoration. A different routed image
needs new calibration. Coarse mode remains available through the raw SCPI
ACTIVATE OFF command, but `capture_burst()` deliberately requires fine ON.

### Legacy-only commands to avoid confusing with WIDTH

`TDC:MODE SINGLE|CONTINUOUS|CALIBRATION`, `TDC:TRIGGER`, `TDC:MEASURE?`,
`TDC:FIFO:DATA?`, `TDC:LAUNCH:PERIOD`, `TDC:LAUNCH:WIDTH`,
`TDC:CALIBRATION:*` (without WIDTH), and the MMCM phase-step controls belong
to the older E3 launch-to-return/self-test engine. They are not needed for the
PCB pulse-width demonstration. Their timing/count semantics differ; e.g.
legacy launch period/width/timeout are **125 MHz (8 ns) cycles**, not PULSE ns.
Keep that engine OFF while WIDTH runs.

`TDC:WIDTH:DELAY min,max`, `TDC:WIDTH:DELAY?` and
`TDC:WIDTH:LATENCY? start,count` are **V13-specific** return-association controls.
Do not use them on V18. V18 uses the full-period, shifted-frame `WIDTH:OFFSET`
association and sparse `WIDTH:DIAGNOSTIC:EDGE?` timestamps instead.

## Complete acquisition sequence

Configure both weights as above, keeping them OFF initially. The helpers-only
notebook documents the following order for the future experiment notebook.
Configure the AWG matrix-input waveform separately; the PCB response is
triggered by the FPGA launch. Keep launch running between captures. Complete
`upload_luts(rp, calibration)` once, with both tables read back successfully,
before executing the fine-mode acquisition part below.

```text
PULSE:OUTPUT OFF
TDC:WIDTH:ABORT
TDC:WIDTH:STATUS?                 # poll until BUSY bit clears
TDC:ENABLE OFF
TDC:TEST:INTERNAL OFF
TDC:MMCM:ENABLE OFF
TDC:INPUT SINGLE
PULSE:TIMING 10000,5000
PULSE:TIMING?
TDC:WIDTH:OFFSET 0
TDC:WIDTH:OFFSET?
                                 # once: upload BOTH qualified LUTs and verify readback
TDC:WIDTH:CALIBRATION:ACTIVATE ON
TDC:WIDTH:CALIBRATION:ACTIVATE?
OUTPUT:STATE ON
SOUR:TRIG:INT
PULSE:OUTPUT ON
                                 # allow PCB/analogue settling
TDC:WIDTH:ARM 4096
TDC:WIDTH:STATUS?                 # poll until BUSY=0; require DONE and no errors
TDC:WIDTH:COUNT?                  # require 4096
PULSE:OUTPUT OFF
OUTPUT1:STATE OFF
OUTPUT2:STATE OFF
TDC:WIDTH:DATA? 0,128
TDC:WIDTH:DATA? 128,128
                                 # continue through all 4096 records
TDC:WIDTH:ABORT                   # final cleanup, including exceptions
```

Lines after `#` are explanations; do not transmit the comments. Stop all outputs
and request abort in exception cleanup too. A crashed process or lost network
connection cannot guarantee output shutdown; reconnect and run the notebook's
`stop_board()` helper. Do not call GUI Generate Bitstream or reload the FPGA
while this notebook is running.

At 100 kHz, 4096 frames take **40.96 ms** and 16384 take **163.84 ms**, plus
processing and network readout. The flow is finite-burst acquisition, not a
continuous 100,000-result/s SCPI stream. Raw CSV is retained only for completely
successful bursts; call `save_capture()` after cleanup for every returned
attempt to retain compact settings/flags/errors/summary JSON. The external input timing and PCB response
still need validation at this rate.

## Source of truth

These commands and semantics were checked against the local implementation:

- [SCPI command registration](../scpi-server/src/scpi-commands.cpp)
- [ASG handlers](../scpi-server/src/generate.cpp) and [ASG API implementation](../rp-api/api/src/gen_handler.cpp)
- [PULSE handlers](../scpi-server/src/pulsegen.cpp)
- [TDC handlers](../scpi-server/src/tdc.cpp), [TDC API](../rp-api/api/src/tdc.cpp), and [record/status definitions](../rp-api/api/include/rp.h)

No board commands were executed while creating this notebook/reference.
