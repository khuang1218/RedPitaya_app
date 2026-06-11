# Red Pitaya BNET Project Handover

Date: 2026-06-07

Latest board-test update: 2026-06-08

Latest source update: 2026-06-08 later pass

This workspace contains two separate Git repositories. Treat paths below as
relative to each repository root because absolute paths differ between PCs.

## Project Goal

Build a hardware butterfly network on a Red Pitaya STEMlab 125-14 Zynq-7020
Gen 2, then control it from a PC over Ethernet using the Red Pitaya API and
SCPI server.

Target data path:

```text
ADC or DDR input -> BNET hardware compute -> DAC/output path
```

Current milestone:

- BNET is mapped into the Red Pitaya FPGA system bus at `sys[7]`.
- Hardware supports scalar/debug control plus a DDR-backed stream reader path.
- The butterfly engine has been expanded from a first-stage pair test into a
  full staged fixed-point network. The latest board-proven bitstream used
  `VECTOR_LEN=1024`; the current source now targets `VECTOR_LEN=2048`.
- DDR stream 0 supplies the input samples; DDR stream 1 supplies all
  `VECTOR_LEN * log2(VECTOR_LEN)` packed stage-weight words.
- Software API exposes BNET registers, stream descriptors, and raw DDR upload.
- SCPI exposes those API calls for Ethernet control.
- The notebook `scpi-tests/ddr_bnet_test.ipynb` now contains end-to-end DDR,
  RF loopback, maximum-length, speed, and multi-input stability tests for the
  full staged network.
- Latest board run confirms the full fixed-length DDR path works for the
  `VECTOR_LEN=1024` bitstream:
  stream 0 consumes `2048/2048` bytes, stream 1 consumes `20480/20480` bytes,
  BNET reports `STATUS=0x12`, `ERROR=0`, and RF OUT1 loopback matches the
  PC-side fixed-point model with high waveform correlation.
- Current source changes after that run add `VECTOR_LEN=2048`, hardware timing
  counters, and guarded ping-pong auto-swap/auto-restart support. Rebuild and
  board-test those changes before treating them as validated.

## Repository Layout

- HDL repo: `RedPitaya-FPGA`
- Software repo: `RedPitaya_app`

Important software files:

- `rp-api/api/src/bnet.cpp`
- `rp-api/api/src/bnet.h`
- `rp-api/api/include/rp.h`
- `rp-api/api/src/rp.cpp`
- `rp-api/api/CMakeLists.txt`
- `scpi-server/src/bnet.cpp`
- `scpi-server/src/bnet.h`
- `scpi-server/src/scpi-commands.cpp`

Important hardware files:

- `prj/v0.94/rtl/bnet_regs.sv`
- `prj/v0.94/rtl/bnet_axi_reader_ch.sv`
- `prj/v0.94/rtl/butterfly_network.sv`
- `prj/v0.94/rtl/butterfly_network_static_pipeline.sv`
- `prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`
- `HANDOVER_bnet_ddr_reader_compile_check.md`
- `HANDOVER_butterfly_network.md`

## Hardware Integration

BNET is connected at:

- Red Pitaya system bus slot: `sys[7]`
- Software API base address: `0x00700000`
- API register window size: `0x00001000`

Vivado 2020.1 syntax check status:

- The DDR reader hardware changes passed syntax check on another PC.
- A minor syntax fix was applied there already.
- Later implementation attempts exposed utilization/RAM inference issues in the
  full staged engine. The FPGA handover records fixes already applied:
  block-RAM style hints, a serialized multiplier datapath, an explicit
  true-dual-port RAM wrapper, and a Vivado 2020.1 RAM-template fix with one
  clocked write process per RAM port.
- Re-run Vivado synthesis/implementation/timing after those fixes before
  treating the bitstream as final.

### Hardware Architecture

The hardware now has a selectable BNET input source via `CONFIG[1:0]` at BNET
offset `0x4c`:

| Mode | Meaning |
| --- | --- |
| `0` | ASG test stream: `asg_dat[0]` as sample, `asg_dat[1]` as weight |
| `1` | ADC real-time: `adc_dat[0]` as sample, ASG as weight/test source |
| `2` | DDR stream mode: stream 0 as sample, stream 1 as packed weight |

The normal ASG BRAM/table signal-generation path is intended to remain usable.
The ASG deep-memory AXI path was taken over/stubbed for BNET DDR reader use, so
normal ASG table generation and acquisition remain useful for simple test
stimulus, while the full staged network test should use BNET DDR mode.

For the current full-network build:

```text
VECTOR_LEN     = 2048
STAGE_COUNT    = log2(2048) = 11
PAIR_COUNT     = 1024 butterflies per stage
TOTAL_WEIGHTS  = 22528 packed weight words
```

The staged engine loads the input vector, loads all stage weights, computes each
radix-2 butterfly stage using ping-pong vector RAM banks, then loops the final
vector back to the DAC path.

### DDR Reader Hardware

Added module:

- `bnet_axi_reader_ch.sv`

Purpose:

- Reads from DDR through an AXI read channel.
- Uses `axi_rd_burst` and `asg_dat_fifo`.
- Emits 14-bit sample words from 16-bit lanes.
- Has a `valid_o` / `consume_i` handshake.

Top-level behavior:

- Two DDR readers are currently wired:
  - stream 0: sample/input stream via `axi2_sys`
  - stream 1: weight stream via `axi3_sys`
- The staged network now has separate sample and weight handshakes. This is
  required because stream 0 is one input vector, while stream 1 carries one
  packed weight word for every element in every stage.
- DDR mode consumes stream 0 when `sample_ready_o && stream0_valid`, and consumes
  stream 1 when `weight_ready_o && stream1_valid`.
- For a real full-network DDR test:

```text
stream 0 length = VECTOR_LEN * 2 bytes = 4096 bytes
stream 1 length = VECTOR_LEN * STAGE_COUNT * 2 bytes = 45056 bytes
```

### BNET Register Map

Offsets are relative to `0x00700000`.

| Offset | Name | Access | Meaning |
| --- | --- | --- | --- |
| `0x00` | `CONTROL` | RW | start/reset/debug/commit control |
| `0x04` | `STATUS` | RO | busy/done/error status |
| `0x08..0x24` | `CH0_DATA..CH7_DATA` | RW | scalar/debug channel registers |
| `0x28..0x34` | `OUT0_DATA..OUT3_DATA` | RO | scalar/debug output registers |
| `0x38` | `VECTOR_LEN` | RW | vector length in samples |
| `0x3c` | `STREAM_COUNT` | RO | number of hardware streams |
| `0x40` | `ACTIVE_MASK` | RO | active-buffer mask |
| `0x44` | `PENDING_MASK` | RO | pending-swap mask |
| `0x48` | `ERROR_MASK` | RO | stream error mask |
| `0x4c` | `CONFIG` | RW | input mode plus ping-pong control bits |
| `0x50` | `TIME_TOTAL` | RO | last start-to-done cycle count |
| `0x54` | `TIME_LOAD` | RO | last load-state cycle count |
| `0x58` | `TIME_COMPUTE` | RO | last compute-state cycle count |
| `0x5c` | `TIME_PLAYBACK` | RO | last playback cycle count |
| `0x100 + n*0x40` | stream window | RW/RO | stream descriptor block |

`CONFIG` bits:

| Bit(s) | Meaning |
| --- | --- |
| `1:0` | input mode: `0` ASG, `1` ADC, `2` DDR |
| `2` | auto-swap to a valid pending ping/pong buffer when compute finishes |
| `3` | auto-restart after a successful auto-swap |
| `4` | static weight reuse: skip stream 1 and reuse weights already loaded |
| `5` | static-weight frame pipeline enable in DDR mode |

Auto-restart is guarded in hardware: it only fires if enabled streams have a
valid pending inactive buffer and no stream/descriptor error. Software must
commit the next inactive buffer while the current buffer is running.

Static weight reuse preserves the current variable-weight training path while
starting the fixed-weight hardware path. Run once with bit 4 clear to load the
full staged weight RAM from stream 1. Then set bit 4 and run with only stream 0
enabled/committed; BNET reuses the BRAM-resident weights and only consumes the
input vector.

Static pipeline mode is selected with bit 5 while `CONFIG[1:0]` is DDR. It uses
the new fixed-weight frame-pipelined hardware path after its per-stage weights
have been loaded. The raw config value for DDR pipeline mode is `34`.

`CONTROL` bits currently used:

| Bit | Meaning |
| --- | --- |
| `0` | start |
| `1` | soft reset |
| `2` | LED debug enable |
| `3` | LED6 heartbeat enable |
| `5` | commit all enabled streams |

Per-stream register window:

| Stream Offset | Name | Meaning |
| --- | --- | --- |
| `0x00` | `BASE0` | ping buffer base address |
| `0x04` | `BASE1` | pong buffer base address |
| `0x08` | `LENGTH` | buffer length in bytes |
| `0x0c` | `STRIDE` | byte stride |
| `0x10` | `FORMAT` | format tag |
| `0x14` | `CONTROL` | stream enable/commit/swap/clear |
| `0x18` | `STATUS` | stream status |
| `0x1c` | `READ_PTR` | current DDR read pointer |

Per-stream `CONTROL` bits:

| Bit | Meaning |
| --- | --- |
| `0` | enable stream |
| `1` | commit buffer 0 |
| `2` | commit buffer 1 |
| `3` | force swap |
| `4` | clear descriptor/runtime error |

Per-stream `STATUS` includes runtime error bit 5.

## Software API

The BNET API lives in:

- `rp-api/api/src/bnet.cpp`
- `rp-api/api/src/bnet.h`
- public declarations in `rp-api/api/include/rp.h`

It maps:

- `BNET_BASE_ADDR = 0x00700000u`
- `BNET_BASE_SIZE = 0x00001000u`

### Scalar/Debug API

- `rp_BNetSetChannelData(uint32_t channel, int32_t value)`
- `rp_BNetGetChannelData(uint32_t channel, int32_t* value)`
- `rp_BNetStart()`
- `rp_BNetReset()`
- `rp_BNetGetStatus(uint32_t* status)`
- `rp_BNetGetOutputData(uint32_t index, int32_t* value)`
- `rp_BNetSetLed6Heartbeat(bool enable)`
- `rp_BNetGetLed6Heartbeat(bool* enable)`

### Stream/Register API

- `rp_BNetCommitAllEnabledStreams()`
- `rp_BNetSetConfig(uint32_t config)`
- `rp_BNetGetConfig(uint32_t* config)`
- `rp_BNetSetInputMode(uint32_t mode)`
- `rp_BNetGetInputMode(uint32_t* mode)`
- `rp_BNetSetStaticWeightReuse(bool enable)`
- `rp_BNetGetStaticWeightReuse(bool* enable)`
- `rp_BNetSetStaticPipeline(bool enable)`
- `rp_BNetGetStaticPipeline(bool* enable)`
- `rp_BNetGetTiming(uint32_t index, uint32_t* cycles)`
- `rp_BNetSetVectorLength(uint32_t samples)`
- `rp_BNetGetVectorLength(uint32_t* samples)`
- `rp_BNetGetStreamCount(uint32_t* count)`
- `rp_BNetGetActiveMask(uint32_t* mask)`
- `rp_BNetGetPendingMask(uint32_t* mask)`
- `rp_BNetGetErrorMask(uint32_t* mask)`
- `rp_BNetSetStreamBase(uint32_t stream, uint32_t buffer, uint32_t address)`
- `rp_BNetGetStreamBase(uint32_t stream, uint32_t buffer, uint32_t* address)`
- `rp_BNetSetStreamLength(uint32_t stream, uint32_t bytes)`
- `rp_BNetGetStreamLength(uint32_t stream, uint32_t* bytes)`
- `rp_BNetSetStreamStride(uint32_t stream, uint32_t bytes)`
- `rp_BNetGetStreamStride(uint32_t stream, uint32_t* bytes)`
- `rp_BNetSetStreamFormat(uint32_t stream, uint32_t format)`
- `rp_BNetGetStreamFormat(uint32_t stream, uint32_t* format)`
- `rp_BNetEnableStream(uint32_t stream, bool enable)`
- `rp_BNetGetStreamEnable(uint32_t stream, bool* enable)`
- `rp_BNetCommitStreamBuffer(uint32_t stream, uint32_t buffer)`
- `rp_BNetForceStreamSwap(uint32_t stream)`
- `rp_BNetClearStreamError(uint32_t stream)`
- `rp_BNetGetStreamStatus(uint32_t stream, uint32_t* status)`
- `rp_BNetGetStreamReadPtr(uint32_t stream, uint32_t* read_ptr)`

Important implementation detail:

- Pulse-style stream control writes preserve the stream enable bit. The helper
  reads the current enable bit, ORs in the requested pulse bit, then writes the
  stream control register. This avoids accidentally disabling a stream when
  committing, forcing swap, or clearing errors.

### BNET DDR Upload API

The software now has a BNET-owned DDR upload path for fixed-point buffers.
It reuses the existing `axi_manager` `/dev/mem` mapping and reservation logic,
but bypasses generator AXI float conversion. This is the path intended for
fixed-point BNET weights and test input vectors.

New calls:

- `rp_BNetDdrGetMemoryRegion(uint32_t* start, uint32_t* size)`
- `rp_BNetDdrReserve(uint32_t slot, uint32_t address, uint32_t size)`
- `rp_BNetDdrRelease(uint32_t slot)`
- `rp_BNetDdrGetSlotBase(uint32_t slot, uint32_t* address)`
- `rp_BNetDdrGetSlotSize(uint32_t slot, uint32_t* size)`
- `rp_BNetDdrAttachStreamBuffer(uint32_t slot, uint32_t stream, uint32_t buffer)`
- `rp_BNetDdrWriteRaw(uint32_t slot, uint32_t offset_bytes, const uint8_t* data, uint32_t bytes)`
- `rp_BNetDdrWriteI16(uint32_t slot, uint32_t offset_samples, const int16_t* data, uint32_t samples)`
- `rp_BNetDdrWriteU16(uint32_t slot, uint32_t offset_samples, const uint16_t* data, uint32_t samples)`

Slots:

- Software slot indexes are `0..7`.
- Slot size must currently be a multiple of `0x80` bytes, matching the existing
  generator AXI reservation convention.
- Slot base addresses must also be page-aligned, currently use `0x1000`
  spacing between test slots. The BNET DDR reserve path maps each slot
  independently through `/dev/mem`, and `axi_manager::osc_axi_map()` rejects
  non-page-aligned physical offsets. In the notebook, this means slot 0 at
  `0x01000000` and slot 1 at `0x01001000`, not `0x01000100`.
- `rp_BNetDdrAttachStreamBuffer()` writes the reserved slot's physical base
  address and size into the chosen BNET stream ping/pong descriptor.

Fixed-point convention:

- PC-side floating weights should be quantized before upload.
- Samples are signed 14-bit integer lanes carried in little-endian `int16`
  words.
- Stage weights are packed into signed 14-bit lanes. Each lane contains two
  signed 7-bit Q1.6 weights:

```text
weight[13:7] = contribution to first butterfly output
weight[ 6:0] = contribution to second butterfly output
```

- Q1.6 cannot represent exactly `+1.0`; the notebook's near-identity staged
  weights use `+63/64` on pass-through terms and `0` on cross terms.
- SCPI upload sends raw little-endian bytes, so PC code should pack `int16`
  arrays into little-endian byte buffers.

## SCPI Surface

SCPI handlers live in:

- `scpi-server/src/bnet.cpp`
- `scpi-server/src/bnet.h`
- `scpi-server/src/scpi-commands.cpp`

### Scalar/Debug Commands

- `BNET:RST`
- `BNET:START`
- `BNET:STATUS?`
- `BNET:CH#:DATA`
- `BNET:CH#:DATA?`
- `BNET:OUT#:DATA?`
- `BNET:LED6:HB`
- `BNET:LED6:HB?`

Example scalar test:

```text
BNET:RST
BNET:CH0:DATA 10
BNET:CH1:DATA 32
BNET:START
BNET:STATUS?
BNET:OUT0:DATA?
```

Expected scalar output: `OUT0_DATA` returns `42`.

### Stream/Register Commands

- `BNET:COMMIT:ALL`
- `BNET:CONFIG <value>`
- `BNET:CONFIG?`
- `BNET:MODE ASG|ADC|DDR`
- `BNET:MODE?`
- `BNET:WEIGHT:REUSE <0|1>`
- `BNET:WEIGHT:REUSE?`
- `BNET:PIPELINE <0|1>`
- `BNET:PIPELINE?`
- `BNET:TIME#?`
- `BNET:VLEN <samples>`
- `BNET:VLEN?`
- `BNET:STREAM:COUNT?`
- `BNET:ACTIVE?`
- `BNET:PENDING?`
- `BNET:ERROR?`
- `BNET:STREAM#:BASE# <address>`
- `BNET:STREAM#:BASE#?`
- `BNET:STREAM#:LENGTH <bytes>`
- `BNET:STREAM#:LENGTH?`
- `BNET:STREAM#:STRIDE <bytes>`
- `BNET:STREAM#:STRIDE?`
- `BNET:STREAM#:FORMAT <format>`
- `BNET:STREAM#:FORMAT?`
- `BNET:STREAM#:ENABLE <0|1>`
- `BNET:STREAM#:ENABLE?`
- `BNET:STREAM#:COMMIT#`
- `BNET:STREAM#:SWAP`
- `BNET:STREAM#:CLEAR`
- `BNET:STREAM#:STATUS?`
- `BNET:STREAM#:RPTR?`

### DDR Upload Commands

- `BNET:DDR:START?`
- `BNET:DDR:SIZE?`
- `BNET:DDR:SLOT#:RESERVE <address>,<bytes>`
- `BNET:DDR:SLOT#:RELEASE`
- `BNET:DDR:SLOT#:BASE?`
- `BNET:DDR:SLOT#:SIZE?`
- `BNET:DDR:SLOT#:STREAM#:BUF#`
- `BNET:DDR:SLOT#:OFFSET#:DATA# <byte buffer>`

SCPI upload uses raw bytes because the existing SCPI parser extension has
byte-buffer and float-buffer input helpers, but no int16-buffer input helper.

Example DDR/fixed-point flow:

```text
BNET:DDR:START?
BNET:DDR:SIZE?

BNET:DDR:SLOT0:RESERVE <aligned_start>,4096
BNET:DDR:SLOT0:OFFSET0:DATA4096 <packed little-endian int16 input bytes>
BNET:DDR:SLOT0:STREAM0:BUF0

BNET:DDR:SLOT1:RESERVE <page_aligned_slot1>,45056
BNET:DDR:SLOT1:OFFSET0:DATA# <packed little-endian int16 staged weight bytes>
BNET:DDR:SLOT1:STREAM1:BUF0

BNET:VLEN 2048
BNET:STREAM0:FORMAT 0
BNET:STREAM1:FORMAT 0
BNET:STREAM0:ENABLE 1
BNET:STREAM1:ENABLE 1
BNET:STREAM0:COMMIT0
BNET:STREAM1:COMMIT0
BNET:CONFIG 2
BNET:START
BNET:STATUS?
BNET:TIME0?
BNET:TIME1?
BNET:TIME2?
BNET:TIME3?
BNET:STREAM0:STATUS?
BNET:STREAM1:STATUS?
BNET:STREAM0:RPTR?
BNET:STREAM1:RPTR?
```

## Recent Work

At a high level, recent work moved BNET from a simple scalar/debug register
block toward a DDR-backed full staged butterfly compute block.

### Hardware

- A BNET DDR AXI reader module was added.
- Two hardware DDR streams were wired into the BNET top-level path.
- The BNET input source became selectable: ASG test, ADC real-time, or DDR.
- Ping-pong stream descriptors were added through BNET registers.
- The butterfly network was expanded into a serial full staged radix-2 engine.
  The latest board-proven build used 1024 input samples, 10 stages, and 10240
  packed weight words; the current source now uses 2048 input samples, 11
  stages, and 22528 packed weight words.
- The network now uses independent sample and weight valid/ready handshakes, so
  the short sample stream and long staged-weight stream can drain correctly from
  DDR.
- BNET status now reflects compute progress: busy, done, and playback-valid are
  exported through the register block.
- Added high-level hardware timing counters for total, load, compute, and
  playback phases, exposed through API and `BNET:TIME0?..BNET:TIME3?`.
- Added guarded ping-pong auto-swap and auto-restart control bits in `CONFIG`.
- Resource/utilization fixes were applied in the FPGA repo after Vivado DRC and
  RAM inference feedback: BRAM hints, serialized multiply states, explicit
  true-dual-port RAM wrappers, and separate write processes for Vivado 2020.1
  RAM inference.

### Software API

- Added wrappers for input mode, vector length, stream descriptor registers,
  stream enable/commit/swap/error/status, and stream read pointers.
- Added BNET-specific DDR slots for raw fixed-point upload.
- Reused Red Pitaya's existing AXI memory manager rather than making a second
  `/dev/mem` mapping system.
- Avoided reusing `GEN:AXI` waveform upload because it converts floats for DAC
  output; BNET weights need raw fixed-point values.

### SCPI

- Added `BNET:MODE`, `BNET:CONFIG`, `BNET:TIME#?`, `BNET:STREAM#:...`, and
  global status/mask queries.
- Added `BNET:DDR:SLOT#...` commands to reserve, write, and attach DDR buffers.
- Kept old scalar/debug BNET commands so the simple register test remains
  available.

### Notebook Tests

`scpi-tests/ddr_bnet_test.ipynb` was updated for the full staged DDR network:

- Added full-network fixed-point helpers for signed 14-bit samples and packed
  Q1.6 stage weights.
- Rewrote the DDR slot smoke test to upload the current source payload:
  - stream 0: 2048 input samples / 4096 bytes
  - stream 1: 22528 packed weight words / 45056 bytes
- Added comments to the DDR smoke-test commands so the reservation, upload,
  descriptor attach, commit, mode select, start, status, and read-pointer checks
  are easier to follow.
- Reworked the RF loopback block to run the full staged network, drive RF OUT1,
  acquire RF IN1, and plot the capture against the PC-side fixed-point
  reference.
- Added a maximum-length input test.
- Added a coarse output-speed test that times `BNET:START` to `STATUS[1]=done`.
- Added a multiple-input stability test that sends several full-length vectors,
  validates RF-captured output shape with sliding normalized correlation, and
  repeats the ramp input to check run-to-run stability.

## Validation Status

Completed:

- Hardware DDR reader changes passed Vivado 2020.1 syntax check on another PC.
- Software source-level `git diff --check` passed for API/SCPI edits.
- Notebook JSON validation passed after the full-network DDR/RF test updates.
- Notebook Python code-cell parsing passed after the full-network DDR/RF test
  updates.
- `git diff --check` passed for `scpi-tests/ddr_bnet_test.ipynb`.
- Board diagnostics confirmed the latest bitstream includes the BNET soft-reset
  path: after `BNET:RST`, both `BNET:STREAM0:RPTR?` and
  `BNET:STREAM1:RPTR?` returned `0`.

### Recent Board Debug Findings

The DDR smoke and RF-loopback tests exposed several important bugs. The latest
board run confirms these fixes are working for the board-proven fixed-length
`VECTOR_LEN=1024` staged network.

First bug, now fixed in HDL:

- Symptom: immediately after `BNET:RST`, stream read pointers remained nonzero
  from a previous run, for example `stream0_rptr=1152` and
  `stream1_rptr=7528`.
- Root cause: `BNET:RST` reset `bnet_regs`, but the soft-reset pulse was not
  exported to the DDR readers or the staged butterfly engine.
- Fix applied:
  - `bnet_regs.sv` now exports `soft_reset_pulse_o`.
  - `red_pitaya_top_LED7_mod.sv` wires `bnet_soft_reset_pulse` into both DDR
    readers and `butterfly_network`.
  - `bnet_axi_reader_ch.sv` resets visible read-pointer/output state and its
    AXI-side FSM on soft reset.
  - `butterfly_network.sv` resets its FSM on soft reset.

Second bug, fixed and verified on board:

- Symptom after the reset fix: `BNET:RST` correctly cleared both pointers, but
  the DDR smoke test still timed out. At timeout, BNET was busy with no stream
  error and only partial consumption:

```text
expected stream0 bytes = 2048
actual   stream0_rptr  = 1152

expected stream1 bytes = 20480
actual   stream1_rptr  = 7552
```

- Interpretation: `BNET:START` was accepted and both DDR readers began
  streaming, but the readers stopped before the configured buffers drained. The
  staged butterfly engine then remained busy, most likely waiting in load state
  for missing samples/weights.
- Likely root cause: `bnet_axi_reader_ch.sv` issued read bursts based on
  `axi_rd_burst.ctrl_busy_o`, but `ctrl_busy_o` is registered/delayed inside
  `axi_rd_burst`. The reader could therefore issue another `ctrl_val` before
  the previous burst was visibly busy, causing `bytes_requested_axi` to run
  ahead of actual delivered DDR data.
- Fix applied:
  - Added `ctrl_req_inflight_axi` and `ctrl_busy_seen_axi` in
    `bnet_axi_reader_ch.sv`.
  - The reader now waits for each AXI burst to go busy and then idle before
    issuing the next burst.
  - FIFO write/read logic now observes `wr_rst_busy` and `rd_rst_busy`.

Third bug, fixed and verified on board:

- Symptom after the burst-handshake fix: stream 0 completed, but stream 1 still
  stopped early on longer transfers. One observed run delivered all stream 0
  bytes and only `14032/20480` stream 1 bytes.
- Root cause: AXI read data could arrive while the async FIFO was temporarily
  unable to accept a write, especially around reset/burst boundaries. The
  original reader connected `rd_dval` directly to FIFO write enable, so a valid
  AXI beat could be lost if FIFO write side was reset-busy or full.
- Fix applied in `bnet_axi_reader_ch.sv`:
  - Added a small AXI-clock skid buffer between `axi_rd_burst` and the async
    FIFO.
  - AXI `rd_drdy_i` now follows skid-buffer capacity rather than raw FIFO
    readiness.
  - FIFO writes drain from the skid buffer only when FIFO write side is ready.
  - Debug register `DBG0` reports skid-buffer ready/count/overflow plus AXI and
    FIFO state.
- Board confirmation:

```text
Payload sizes: stream0=2048 bytes, stream1=20480 bytes
After START: status=0x12, active=0x0, pending=0x0, error=0x0
Stream 0: status=0x4, rptr 0 -> 2048
Stream 1: status=0x4, rptr 0 -> 20480
```

Fourth bug, fixed in the notebook test:

- Symptom: the first RF multiple-input validation failed with ramp correlation
  around `0.496`.
- Root cause: the test compared RF OUT1 against the full 1024-sample PC
  reference vector. In the HDL playback state, DAC A/RF OUT1 carries the even
  indexed `y0` stream (`expected[0::2]`), while DAC B/RF OUT2 carries the odd
  indexed `y1` stream (`expected[1::2]`).
- Fix applied:
  - RF OUT1 capture and stability tests now compare against `expected[0::2]`.
  - The RF capture cell now computes and prints a direct PC-reference
    comparison: correlation, RMSE, and sliding offset.
- Latest board confirmation:

```text
ramp         corr=0.996 rmse=0.090 offset=1154 repeat_delta=nan
sine         corr=1.000 rmse=0.013 offset=1347 repeat_delta=nan
triangle     corr=0.994 rmse=0.110 offset=223  repeat_delta=nan
cosine_mix   corr=0.998 rmse=0.073 offset=1175 repeat_delta=nan
ramp_repeat  corr=0.996 rmse=0.090 offset=1031 repeat_delta=0.003
Multiple-input RF validation and repeat-stability checks passed
```

Important diagnostic limitation:

- Current underrun reporting is not enough to catch starvation because top-level
  `consume_i` is gated by reader `valid_o`. If the reader becomes empty while
  the butterfly engine is ready, `consume_i` is false and `underrun_o` may not
  assert. A future debug pass should add explicit reader diagnostics such as
  requested byte count, delivered AXI beat count, FIFO empty/full state, and
  load-state counters.

Potential remaining problems to watch after rebuilding:

- If `RPTR` reaches the expected stream lengths but `STATUS[1]` still never
  sets, the next bug is likely inside `butterfly_network.sv`, not the DDR
  reader. For the board-proven 1024 build those lengths were `2048` and
  `20480`; for the current 2048 source they should be `4096` and `45056`.
- If `RPTR` still stops early, inspect the AXI reader internals: `running_axi`,
  `bytes_requested_axi`, `ctrl_req_inflight_axi`, `ctrl_busy`, FIFO flags, and
  whether `axi2_sys`/`axi3_sys` are receiving read data.
- Confirm in Vivado hierarchy that ASG deep-memory AXI is really stubbed and
  only BNET drives `axi2_sys`/`axi3_sys`.
- Confirm `asg_dat_fifo` IP remains `96` bits wide with enough depth. The
  checked XCI currently shows `Input_Data_Width=96`, `Output_Data_Width=96`,
  and `Input_Depth=256`, which matches `{rd_addr, rd_data}`.

Not yet completed:

- Board-validating the current `VECTOR_LEN=2048` source build, then expanding
  beyond it if utilization and timing allow.
- Turning the current fixed-length load/compute/playback transaction into a
  true streaming design with ping-pong or ring-buffer scheduling.
- Adding lower-level reader diagnostics such as delivered-word, starvation, and
  backpressure counters. High-level total/load/compute/playback counters now
  exist, while SCPI-poll timing still includes software/network latency.
- Reworking the engine/dataflow if higher sustained rate is required. The
  current staged engine loads a complete vector and all weights, computes, then
  loops playback; it is not yet a continuous DDR-fed pipeline.

## Recommended Next Steps

1. Preserve the current working fixed-length milestone:

- keep the passing bitstream/software pair identifiable
- keep `scpi-tests/ddr_bnet_test.ipynb` as the regression suite
- rerun DDR smoke, RF capture, maximum-length, speed, and multi-input stability
  after any HDL/API change

2. Use the new timing counters for real throughput measurement:

- query `BNET:TIME0?..BNET:TIME3?` after each run
- compare hardware cycle counts with the notebook's wall-clock timing
- add stream 0/1 delivered-word counters next
- add stream starvation/backpressure counters next

3. Validate and expand input size beyond the current `VECTOR_LEN=2048` source:

- build the 2048 source in Vivado and check BRAM use/timing first
- parameterize/check larger vectors only after the 2048 bitstream is stable
- increase input stream length from `VECTOR_LEN * 2`
- increase weight stream length from `VECTOR_LEN * log2(VECTOR_LEN) * 2`
- update notebook payload generation and assertions for the larger build

4. Move from fixed-length loading to actual streaming:

- current behavior is still batch-style:

```text
PC uploads fixed buffers -> hardware START -> load complete vector/weights
  -> compute complete vector -> playback loop
```

- desired DDR-streaming behavior should be closer to:

```text
PC keeps filling DDR ping/pong or ring buffers
  -> FPGA readers consume buffers continuously
  -> BNET overlaps load/compute/output where possible
  -> software only refills/commits buffers ahead of the hardware read pointer
```

- likely HDL work:
  - ping-pong or ring-buffer scheduler for stream descriptors
  - interrupt/status or watermark when a buffer has been consumed
  - decouple load, compute, and playback stages so DDR can refill the next
    vector while the current vector computes or outputs
  - consider whether weights are static per run, streamed per vector, or stored
    once in BRAM/DDR and reused

5. If running the SCPI flow manually, use the current full staged DDR sizes:

- reserve two DDR slots
  - use page-aligned slot bases; for the default region start `0x01000000`,
    use slot 0 at `0x01000000` and slot 1 at `0x01001000`
- upload 2048 `int16` input samples to stream 0
- upload 22528 packed `int16` stage-weight words to stream 1
- attach slot 0 to stream 0 and slot 1 to stream 1
- set config to `2` for DDR one-shot, `6` for DDR plus auto-swap, or `14` for
  DDR plus auto-swap plus auto-restart. Use `18` for DDR one-shot with
  preloaded static weight reuse, or `34` for DDR static pipeline mode. The named
  SCPI helpers are `BNET:WEIGHT:REUSE <0|1>` and `BNET:PIPELINE <0|1>`.
- start BNET
- check `BNET:STATUS?`, `BNET:ERROR?`, stream status, and read pointers
  - stream 0 read pointer should reach at least 4096 bytes
  - stream 1 read pointer should reach at least 45056 bytes
  - timing registers should be nonzero after `done`

6. Keep or extract the notebook helpers into a Python PC-side script once the
streaming architecture is chosen. The helper should:

- quantize float weights to fixed-point
- pack arrays as little-endian `int16`
- reserve DDR slots
- upload byte buffers
- attach streams and commit ping-pong buffers
- query status/read pointers/errors

## Known Risks / Watch Points

- The HDL currently uses two DDR readers. If the final butterfly network needs
  more independent DDR channels, the design will need arbitration or more AXI
  master wiring.
- `BNET:DDR:SLOT#:OFFSET#:DATA#` uploads raw bytes. PC-side endianness and
  packing must be correct.
- The fixed-point format is not enforced by the `FORMAT` register yet; `FORMAT`
  is currently a tag. PC-side packing must match the hardware interpretation:
  signed 14-bit samples and packed signed 7-bit Q1.6 weights.
- The software DDR slot reservation can overlap with other AXI users if the
  same reserved DDR region is manually reused outside `axi_manager`.
- Normal ASG BRAM/table mode is intended to remain available, but ASG deep
  memory AXI is no longer treated as an independent generator feature in this
  BNET hardware path.
- The SCPI/API changes are source-checked only on Windows; Linux compile is
  still required.
- RF loopback validation is analog, so output comparison uses waveform shape
  correlation rather than bit-exact sample comparison.
- The notebook speed test is SCPI-poll based. It is useful for regression
  comparison, but it includes command/status polling latency and is not a pure
  FPGA-cycle benchmark.
- The full staged engine is serial to fit resources. Confirm the resulting
  latency is acceptable for the intended experiment after timing closure.

## Quick Search Commands

From `RedPitaya_app`:

```powershell
rg -n "BNet|BNET|bnet|BNetDdr" rp-api scpi-server
```

From `RedPitaya-FPGA`:

```powershell
rg -n "bnet_regs|bnet_axi_reader|butterfly_network|sys\[7\]|axi2_sys|axi3_sys" prj\v0.94\rtl
```

## Current Git State To Expect

Software repo modified files:

- `HANDOVER.md`
- `rp-api/api/include/rp.h`
- `rp-api/api/src/bnet.cpp`
- `rp-api/api/src/bnet.h`
- `scpi-tests/ddr_bnet_test.ipynb`
- `scpi-server/src/bnet.cpp`
- `scpi-server/src/bnet.h`
- `scpi-server/src/scpi-commands.cpp`
- `scpi-tests/ddr_bnet_test.ipynb`

Hardware repo modified/added files from the DDR reader milestone:

- `HANDOVER_bnet_ddr_reader_compile_check.md`
- `HANDOVER_butterfly_network.md`
- `prj/v0.94/rtl/bnet_tdp_ram.sv` if kept as a separate source in the latest
  RAM-inference fix, otherwise the wrapper lives inside `butterfly_network.sv`
- `prj/v0.94/rtl/bnet_regs.sv`
- `prj/v0.94/rtl/bnet_axi_reader_ch.sv`
- `prj/v0.94/rtl/butterfly_network.sv`
- `prj/v0.94/rtl/butterfly_network_static_pipeline.sv`
- `prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`

