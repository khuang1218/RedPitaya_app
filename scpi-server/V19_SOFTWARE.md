# V19 API and SCPI

This software supports `red_pitaya_v19.bit`: two full TDCs, the shared pulse
generator, two ASG outputs, FPGA DAC80516 SPI and the fixed LED7 heartbeat.
No FPGA sources or experiment notebooks are changed by this software update.

## Initialization and compatibility

`rp_Init()` identifies the custom image through the first TDC ID. On v19 it
initializes housekeeping and ASG, skips acquisition, AMS, daisy and BNET, and
resets the pulse generator and both TDCs. It sends no external DAC transactions.
`rp_GetCustomFpgaVersion(&version)` / `SYST:FPGA:VERS?` returns 19 for v19, 18
for v18 and 0 for other images. Release/reinitialize after replacing an image;
stop the server before loading a different bitstream.

The original TDC API and `TDC:` commands always select channel 1. Every TDC API
also has an explicit `Ch` variant with `rp_channel_t channel` as its first
argument, using `RP_CH_1` or `RP_CH_2`. For example:

```cpp
rp_TdcWidthArmCh(RP_CH_2, 16384);
rp_TdcWidthReadCh(RP_CH_2, 0, records, count);
rp_TdcWidthWriteLutCh(RP_CH_2, false, start, values, count);
```

SCPI uses `TDC1:` and `TDC2:` with the same command suffixes, including legacy
TDC, MMCM, input selection, finite width bursts, LUTs, offsets and diagnostics.
`TDC:` is the channel 1 alias. Channel 2 and DAC SPI reject v18 with `RP_EUF`.
Each core owns its mapping, lock and indexed register state. No global selected
channel is shared between network clients. Keep a single owner for each core's
multi-command acquisition/calibration workflow.

V19 hides ACQ, BNET, ANALOG, DAISY, LCR and generator AXI commands from its
command table and `SYST:HELP?`. Calls to the corresponding removed API features
return `RP_EUF`. V13-only DELAY/LATENCY commands are also hidden on v19.
ASG `SOUR1:`, `SOUR2:`, `OUTPUT1:`, `OUTPUT2:` and local ARB tables retain their
existing behavior. DDR/AXI ASG mode is unavailable. Application GPIOs and LED7
reject individual direction/state writes; LED7 continues in FPGA hardware.

## Shared pulse generator and duty cycle

The 50% width-ARM restriction is removed. Both TDCs check the hardware minimum
frame period (40 ns on v19), HIGH >=8 ns and LOW >=8 ns. Frame offsets, legacy
TDC exclusion and stopped-trigger/busy checks remain enforced. The GPIO pulse
generator itself still supports 2 ns HIGH increments and 4 ns period increments.
The output must be OFF when changing timing, frequency, HIGH or duty.

```text
PULSE:OUTPUT OFF
PULSE:TIMING 10000,2000
PULSE:DCYCLE 30
PULSE:TIMING?
PULSE:DCYCLE?
PULSE:OUTPUT ON
TDC1:WIDTH:ARM 1024
TDC2:WIDTH:ARM 1024
TDC1:WIDTH:STATUS?
TDC2:WIDTH:STATUS?
```

Here timing readback is `10000,3000` ns and duty is 30 percent. Frequency changes
preserve the actual duty ratio with HIGH rounded to 2 ns. Duty changes round
HIGH to 2 ns; query timing/duty to obtain the actual quantized values. The C API
adds `rp_PulseSetDutyCycle(percent)` / `rp_PulseGetDutyCycle(&percent)`.

The two ARM calls are sequential: they do not promise identical starting launch
edges or simultaneous first records. Both cores observe the same running launch
generator. Each core requires its own calibration for the v19 routed image;
v18 LUT qualification does not transfer automatically.

## FPGA DAC80516 SPI

These commands control the FPGA block at `0x40740000`, independently of existing
Linux `SPI:` commands. Codes are unsigned 16-bit values, ordered OUT0..OUT3.
No voltage range/reference/power configuration is assumed. Configure the actual
DAC using its board-specific register settings through raw writes before using
the weight commands. RESET, power/reference supplies and wiring remain external.

| Command | Meaning |
|---|---|
| `DAC:SPI:STATUS?` | FPGA status flags |
| `DAC:SPI:PERIOD n` / `?` | SCLK period, 4..250 controller ticks of 8 ns |
| `DAC:SPI:FREQ hz` / `?` | Quantized SCLK rate; setter rounds period up |
| `DAC:LDAC:WIDTH n` / `?` | LDAC LOW width, 13..250 ticks of 8 ns |
| `DAC:WEIGHTS a,b,c,d` | Load all four codes and pulse LDAC |
| `DAC:WEIGHTS:LOAD a,b,c,d` | Load four DAC input registers without LDAC |
| `DAC:LDAC` | Apply the previously loaded four-code group |
| `DAC:WEIGHTS?` | FPGA shadow codes |
| `DAC:APPLIED?` | Last group applied by LDAC; error if unknown |
| `DAC:SPI:RAW:WRITE frame` | One 24-bit write frame; bit23 must be 0 |
| `DAC:SPI:RAW:READ? frame` | Read frame with bit23=1, followed by automatic NOP |
| `DAC:SPI:COUNTERS?` | Serial frame count, LDAC application count |

Defaults are 12 SCLK ticks (~10.4167 MHz) and 16 LDAC ticks (128 ns). A period of
5 ticks selects 25 MHz. The API supports periods down to the hardware minimum of
4 ticks (31.25 MHz); use a rate qualified for the actual wiring/device. Raw reads
temporarily use at least 16 ticks (<=7.8125 MHz) for MISO settling and restore the
write period after success. On timeout the slower period can remain selected.

```text
DAC:SPI:PERIOD 5
DAC:WEIGHTS:LOAD 0,16384,32768,65535
DAC:LDAC
DAC:APPLIED?
```

C APIs mirror these operations with `rp_DacSpi...` functions in `rp.h`. Group
updates use `rp_DacSpiSetWeights(codes, apply)` with exactly four `uint16_t`
values. Raw writes invalidate the tracked loaded/applied group; load all four
again before calling LDAC. FPGA status bits are BUSY=bit0, READY=bit2,
LOADED=bit3, APPLIED=bit4, DONE=bit5. Raw frame values accept decimal or SCPI
`#H` hexadecimal syntax. Raw read returns the complete 24-bit shifted response.

Transactions are synchronous, serialized within the API process and bounded by
a 100 ms wait. They verify register writes, DONE and frame/application counters,
because the retained bus bridge masks peripheral error responses. A failed or
timed-out operation is not automatically retried or cancelled. Do not mix this
API with direct MMIO or another process controlling the same block.

LOADED/APPLIED and readbacks describe the FPGA engine. SPI has no external
acknowledgement; these do not establish DAC connectivity or output voltage.
Ethernet command arrival and sequential ARM/LDAC calls provide no deterministic
alignment to pulse edges. There is no autonomous weight-update queue in v19.

## Build and validation

Use the existing ARM Linux/board build environment and installation prefix.
Rebuild and deploy both librp and the SCPI server together; the API source list
includes the new modules and the SCPI source glob picks up the new handlers.
For an already provisioned dependency prefix:

```sh
cmake -S rp-api/api -B rp-api/api/build -DINSTALL_DIR="$RP_PREFIX" -DBUILD_PYTHON_MODULE=OFF -DBUILD_DOC=OFF
cmake --build rp-api/api/build --target install -j4
cmake -S scpi-server -B scpi-server/build -DINSTALL_DIR="$RP_PREFIX"
cmake --build scpi-server/build --target install -j4
```

The root Makefile's `make scpi` also builds the normal API dependencies. The
repository expects the Red Pitaya libscpi fork in `scpi-server/scpi-parser`.
Restart the server after deployment. Building or running host tests here does
not install the server or load a bitstream on the board.

Hardware-free regression (C++20 compiler and Python 3):

```sh
SCPI_PARSER_DIR=scpi-server/scpi-parser/libscpi bash scpi-tests/run_v19_software_tests.sh
```

The tests compile changed production translation units and use the actual API,
production command table, handlers and parser. Unrelated command callbacks and
board infrastructure are stubbed; a register model provides MMIO side effects.
They check independent core state and indexed reads/LUTs, v18 fallback, unequal
duty/quantization and real timing guards, DAC group/load/LDAC/raw read operations,
counter wrap, ignored writes/commands, timeouts and malformed SCPI parameters.
Electrical behavior and actual v19 calibration still require board acceptance.

Local result (2026-11-06): all 12 modified production translation units compile
with GCC 15 / C++20. The dual-TDC/DAC/SCPI, existing TDC compatibility and actual
API startup/unsupported-feature regressions pass. Existing host-width printf
warnings remain in the AMS debug header. No target ARM build or deployment has
been performed. A SHA256-verified overlay is available at
`build/v19-software/red_pitaya_v19_software_sources.zip`.
