# Workspace Handover

Date: 2026-06-04

This workspace contains two separate Git repositories. Absolute paths may differ
on another PC, so treat paths below as relative to the two repository roots.

## Repository Layout

- HDL repo: `RedPitaya-FPGA`
- Software repo: `RedPitaya_app`

Current known local paths:

- HDL: `C:\Users\Kairan\VScode\rp_fpga\RedPitaya-FPGA`
- Software: `C:\Users\Kairan\VScode\fp_general\RedPitaya_app`

On a new PC, open a workspace folder that contains both repos, then locate files
by repo name plus relative path.

## BNET Integration Map

BNET is the custom butterfly-network scalar register block.

- Hardware sys bus slot: `sys[7]`
- Software API base offset: `0x00700000`
- Register window size in API: `0x00001000`
- HDL register block: `RedPitaya-FPGA/prj/v0.94/rtl/bnet_regs.sv`
- HDL top-level wiring currently found in:
  - `RedPitaya-FPGA/prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`
- API implementation:
  - `RedPitaya_app/rp-api/api/src/bnet.cpp`
  - `RedPitaya_app/rp-api/api/src/bnet.h`
  - public declarations in `RedPitaya_app/rp-api/api/include/rp.h`
  - included in API init/release in `RedPitaya_app/rp-api/api/src/rp.cpp`
  - added to build in `RedPitaya_app/rp-api/api/CMakeLists.txt`
- SCPI implementation:
  - `RedPitaya_app/scpi-server/src/bnet.cpp`
  - `RedPitaya_app/scpi-server/src/bnet.h`
  - command registration in `RedPitaya_app/scpi-server/src/scpi-commands.cpp`

## BNET Register Map

Offsets are relative to the BNET sys bus slave and API base address
`0x00700000`.

| Offset | Name | Access | Meaning |
| --- | --- | --- | --- |
| `0x00` | `CONTROL` | RW | bit 0 start latch, bit 1 soft reset, bit 2 LED debug enable, bit 3 LED6 heartbeat enable |
| `0x04` | `STATUS` | RO | bit 0 busy, bit 1 done, bit 2 error |
| `0x08` | `CH0_DATA` | RW | scalar input channel 0 |
| `0x0c` | `CH1_DATA` | RW | scalar input channel 1 |
| `0x10` | `CH2_DATA` | RW | scalar input channel 2 |
| `0x14` | `CH3_DATA` | RW | scalar input channel 3 |
| `0x18` | `CH4_DATA` | RW | scalar input channel 4 |
| `0x1c` | `CH5_DATA` | RW | scalar input channel 5 |
| `0x20` | `CH6_DATA` | RW | scalar input channel 6 |
| `0x24` | `CH7_DATA` | RW | scalar input channel 7 |
| `0x28` | `OUT0_DATA` | RO | `CH0 + CH1` |
| `0x2c` | `OUT1_DATA` | RO | `CH2 + CH3` |
| `0x30` | `OUT2_DATA` | RO | `CH4 + CH5` |
| `0x34` | `OUT3_DATA` | RO | `CH6 + CH7` |

## Current API Surface

The C API currently exposes:

- `rp_BNetSetChannelData(uint32_t channel, int32_t value)`
- `rp_BNetGetChannelData(uint32_t channel, int32_t* value)`
- `rp_BNetStart()`
- `rp_BNetReset()`
- `rp_BNetGetStatus(uint32_t* status)`
- `rp_BNetGetOutputData(uint32_t index, int32_t* value)`
- `rp_BNetSetLed6Heartbeat(bool enable)`
- `rp_BNetGetLed6Heartbeat(bool* enable)`

The API maps the register window with:

- `BNET_BASE_ADDR = 0x00700000u`
- `BNET_BASE_SIZE = 0x00001000u`

## Current SCPI Surface

Registered commands:

- `BNET:RST`
- `BNET:START`
- `BNET:STATUS?`
- `BNET:CH#:DATA`
- `BNET:CH#:DATA?`
- `BNET:OUT#:DATA?`
- `BNET:LED6:HB`
- `BNET:LED6:HB?`

Channel indexes are `0..7`. Output indexes are `0..3`.

Example SCPI flow:

```text
BNET:RST
BNET:CH0:DATA 10
BNET:CH1:DATA 32
BNET:START
BNET:STATUS?
BNET:OUT0:DATA?
```

Expected scalar test result for the example: `OUT0_DATA` returns `42`.

## HDL Notes

`bnet_regs.sv` is a scalar test milestone, not the final buffered butterfly
network. It currently:

- stores eight 32-bit channel registers;
- computes four output sums combinationally;
- sets status `done` when `CONTROL[0]` is written;
- clears control, status, and channel registers when `CONTROL[1]` is written;
- drives `led_debug_o` from `CH0_DATA[7:0]`;
- drives `led_debug_en_o` from `CONTROL[2]`;
- drives `led6_heartbeat_en_o` from `CONTROL[3]`.

`red_pitaya_top_LED7_mod.sv` wires `bnet_regs` to `sys[7]`. Other top files
may still have `sys_bus_stub sys_bus_stub_7 (sys[7])`, so confirm the selected
FPGA build top before expecting BNET to exist in hardware.

## Portability Checklist

When continuing on another PC:

1. Clone or copy both repos into the same workspace.
2. Do not rely on the absolute paths in this file.
3. Open the workspace containing both `RedPitaya-FPGA` and `RedPitaya_app`.
4. Confirm both repos are on the intended branches or commits.
5. Check software BNET base address still matches the HDL sys bus slot:
   `rp-api/api/src/bnet.cpp` uses `0x00700000`, matching `sys[7]`.
6. Confirm the FPGA bitstream being built uses the top file with BNET wired,
   currently `prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`.

## Quick Search Commands

From `RedPitaya_app`:

```powershell
rg -n "BNet|BNET|bnet" rp-api scpi-server
```

From `RedPitaya-FPGA`:

```powershell
rg -n "bnet_regs|sys\[7\]|led6_heartbeat" prj\v0.94\rtl
```

## Current Git State

At the time this handover was created, both repos reported clean working trees
before adding this file. After this file is created, `RedPitaya_app` will have
`HANDOVER.md` as a new uncommitted file unless it is committed.

