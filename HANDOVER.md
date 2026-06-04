# Red Pitaya BNET Project Handover

Date: 2026-06-04

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
- Software API exposes BNET registers, stream descriptors, and raw DDR upload.
- SCPI exposes those API calls for Ethernet control.

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
- Full synthesis/implementation/timing closure has not yet been reported in
  this handover.

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
normal ASG table generation and acquisition remain the preferred test/observe
path.

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
- The top only consumes DDR data when both stream readers are valid. This keeps
  sample and weight streams aligned.
- `butterfly_network.sv` now has `input_valid_i`; capture/compute only advances
  when valid.

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
- Example Q1.14: `int16_weight = round(float_weight * 16384)`.
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

BNET:DDR:SLOT1:RESERVE <aligned_start_plus_2048>,2048
BNET:DDR:SLOT1:OFFSET0:DATA2048 <packed little-endian int16 weight bytes>
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

## What Was Done Today

At a high level, today moved BNET from a simple scalar/debug register block
toward a DDR-backed streaming compute block.

The hardware work added the foundation for long input/weight streams:

- A BNET DDR AXI reader module was added.
- Two hardware DDR streams were wired into the BNET top-level path.
- The BNET input source became selectable: ASG test, ADC real-time, or DDR.
- Ping-pong stream descriptors were added through BNET registers.
- The butterfly network was made valid-driven so it only advances when stream
  data is available.

The software API work made those hardware registers controllable:

- Added wrappers for input mode, vector length, stream descriptor registers,
  stream enable/commit/swap/error/status, and stream read pointers.
- Added BNET-specific DDR slots for raw fixed-point upload.
- Reused Red Pitaya's existing AXI memory manager rather than making a second
  `/dev/mem` mapping system.
- Avoided reusing `GEN:AXI` waveform upload because it converts floats for DAC
  output; BNET weights need raw fixed-point values.

The SCPI work exposed the same controls over Ethernet:

- Added `BNET:MODE`, `BNET:STREAM#:...`, and global status/mask queries.
- Added `BNET:DDR:SLOT#...` commands to reserve, write, and attach DDR buffers.
- Kept old scalar/debug BNET commands so the simple register test remains
  available.

## Validation Status

Completed:

- Hardware DDR reader changes passed Vivado 2020.1 syntax check on another PC.
- Software source-level `git diff --check` passed for API/SCPI edits.

Not yet completed:

- Full HDL synthesis/implementation/timing.
- Linux API compile.
- Linux SCPI server compile/link.
- Board-level test with an actual bitstream and SCPI client.
- End-to-end DDR upload into BNET stream readers.
- Verification that read pointers advance and error masks remain clear.
- Verification that BNET output is correctly routed/observed through DAC or
  acquisition path for the intended test setup.

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

4. Deploy bitstream and software to the board.

5. Run a small DDR stream test:

- reserve two DDR slots
  - use page-aligned slot bases; for the default region start `0x01000000`,
    use slot 0 at `0x01000000` and slot 1 at `0x01001000`
- upload short known `int16` input/weight arrays
- attach slot 0 to stream 0 and slot 1 to stream 1
- set mode to `DDR`
- start BNET
- check `BNET:STATUS?`, `BNET:ERROR?`, stream status, and read pointers

6. Add a Python PC-side helper script once the SCPI server compiles. The helper
should:

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
- The fixed-point format is not enforced in hardware/software yet; `FORMAT` is
  currently a tag. The actual interpretation must match the BNET multiplier
  implementation.
- The software DDR slot reservation can overlap with other AXI users if the
  same reserved DDR region is manually reused outside `axi_manager`.
- Normal ASG BRAM/table mode is intended to remain available, but ASG deep
  memory AXI is no longer treated as an independent generator feature in this
  BNET hardware path.
- The SCPI/API changes are source-checked only on Windows; Linux compile is
  still required.

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
- `scpi-server/src/bnet.cpp`
- `scpi-server/src/bnet.h`
- `scpi-server/src/scpi-commands.cpp`

Hardware repo modified/added files from the DDR reader milestone:

- `HANDOVER_bnet_ddr_reader_compile_check.md`
- `HANDOVER_butterfly_network.md`
- `prj/v0.94/rtl/bnet_regs.sv`
- `prj/v0.94/rtl/bnet_axi_reader_ch.sv`
- `prj/v0.94/rtl/butterfly_network.sv`
- `prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`

