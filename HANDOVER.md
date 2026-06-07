# Red Pitaya BNET Project Handover

Date: 2026-06-07

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
  full staged fixed-point network for `VECTOR_LEN=1024`.
- DDR stream 0 supplies the 1024 input samples; DDR stream 1 supplies all
  `1024 * log2(1024) = 10240` packed stage-weight words.
- Software API exposes BNET registers, stream descriptors, and raw DDR upload.
- SCPI exposes those API calls for Ethernet control.
- The notebook `scpi-tests/ddr_bnet_test.ipynb` now contains end-to-end DDR,
  RF loopback, maximum-length, speed, and multi-input stability tests for the
  full staged network.

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
VECTOR_LEN     = 1024
STAGE_COUNT    = log2(1024) = 10
PAIR_COUNT     = 512 butterflies per stage
TOTAL_WEIGHTS  = 10240 packed weight words
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
  required because stream 0 is only 1024 words, while stream 1 is 10240 words.
- DDR mode consumes stream 0 when `sample_ready_o && stream0_valid`, and consumes
  stream 1 when `weight_ready_o && stream1_valid`.
- For a real full-network DDR test:

```text
stream 0 length = VECTOR_LEN * 2 bytes = 2048 bytes
stream 1 length = VECTOR_LEN * STAGE_COUNT * 2 bytes = 20480 bytes
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
| `0x4c` | `CONFIG` | RW | bits `1:0` select input mode |
| `0x100 + n*0x40` | stream window | RW/RO | stream descriptor block |

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
- `rp_BNetSetInputMode(uint32_t mode)`
- `rp_BNetGetInputMode(uint32_t* mode)`
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
- `BNET:MODE ASG|ADC|DDR`
- `BNET:MODE?`
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

BNET:DDR:SLOT0:RESERVE <aligned_start>,2048
BNET:DDR:SLOT0:OFFSET0:DATA2048 <packed little-endian int16 input bytes>
BNET:DDR:SLOT0:STREAM0:BUF0

BNET:DDR:SLOT1:RESERVE <page_aligned_slot1>,20480
BNET:DDR:SLOT1:OFFSET0:DATA# <packed little-endian int16 staged weight bytes>
BNET:DDR:SLOT1:STREAM1:BUF0

BNET:VLEN 1024
BNET:STREAM0:FORMAT 0
BNET:STREAM1:FORMAT 0
BNET:STREAM0:ENABLE 1
BNET:STREAM1:ENABLE 1
BNET:STREAM0:COMMIT0
BNET:STREAM1:COMMIT0
BNET:MODE DDR
BNET:START
BNET:STATUS?
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
- The butterfly network was expanded into a serial full staged radix-2 engine:
  1024 input samples, 10 stages, and 10240 packed weight words.
- The network now uses independent sample and weight valid/ready handshakes, so
  the short sample stream and long staged-weight stream can drain correctly from
  DDR.
- BNET status now reflects compute progress: busy, done, and playback-valid are
  exported through the register block.
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

- Added `BNET:MODE`, `BNET:STREAM#:...`, and global status/mask queries.
- Added `BNET:DDR:SLOT#...` commands to reserve, write, and attach DDR buffers.
- Kept old scalar/debug BNET commands so the simple register test remains
  available.

### Notebook Tests

`scpi-tests/ddr_bnet_test.ipynb` was updated for the full staged DDR network:

- Added full-network fixed-point helpers for signed 14-bit samples and packed
  Q1.6 stage weights.
- Rewrote the DDR slot smoke test to upload:
  - stream 0: 1024 input samples / 2048 bytes
  - stream 1: 10240 packed weight words / 20480 bytes
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

Not yet completed:

- Final HDL synthesis/implementation/timing after the latest staged-network RAM
  inference and resource-utilization fixes.
- Linux API compile.
- Linux SCPI server compile/link.
- Board-level test with an actual bitstream and SCPI client.
- End-to-end full staged DDR upload into BNET stream readers on hardware.
- Verification that stream 0 consumes 2048 bytes and stream 1 consumes 20480
  bytes with error masks clear.
- Verification that BNET RF OUT1 output is correctly routed and observed through
  RF IN1 for the intended loopback setup.
- Hardware execution of the maximum-length, speed, and multi-input stability
  notebook tests.

## Recommended Next Steps

1. Build software on Linux:

```bash
make librp
make scpi
```

2. Fix compile/link issues if any, especially around:

- `scpi-server/src/bnet.cpp`
- `rp-api/api/src/bnet.cpp`
- public prototypes in `rp-api/api/include/rp.h`

3. Build FPGA beyond syntax:

- run synthesis
- run implementation
- inspect timing
- check AXI reader resource usage
- confirm `bank0`, `bank1`, and `weight_ram` infer as block RAM
- confirm the serialized multiplier/full staged engine fits the Zynq-7020

4. Deploy bitstream and software to the board.

5. Run the notebook checks in `scpi-tests/ddr_bnet_test.ipynb`:

- DDR slot smoke test for the full staged network
- RF OUT1 to RF IN1 full-network capture
- maximum-length input test
- output speed test
- multiple-input output validation and stability test

6. If running the SCPI flow manually, use the full staged DDR sizes:

- reserve two DDR slots
  - use page-aligned slot bases; for the default region start `0x01000000`,
    use slot 0 at `0x01000000` and slot 1 at `0x01001000`
- upload 1024 `int16` input samples to stream 0
- upload 10240 packed `int16` stage-weight words to stream 1
- attach slot 0 to stream 0 and slot 1 to stream 1
- set mode to `DDR`
- start BNET
- check `BNET:STATUS?`, `BNET:ERROR?`, stream status, and read pointers
  - stream 0 read pointer should reach at least 2048 bytes
  - stream 1 read pointer should reach at least 20480 bytes

7. Keep or extract the notebook helpers into a Python PC-side script once the
SCPI server compiles cleanly. The helper should:

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
- `prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`

