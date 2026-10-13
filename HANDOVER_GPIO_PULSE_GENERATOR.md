# Single-channel 3.3 V GPIO pulse generator handover

Date: 2026-10-13. Target: STEMlab 125-14 Z7020 Gen 2 / Z20_G2.

## Scope and current validation boundary

The source implements one continuous pulse output on **DIO1_P**, controlled by
new `PULSE:*` SCPI commands. DIO means digital I/O: these E1 DIO pins are the
board's GPIOs. `_P` and `_N` identify the two pin banks; they can be independent
single-ended GPIOs. This feature uses one pin, not a differential pair.

There are two separate repositories. Paths below are relative to their roots:
`RedPitaya-FPGA` and `RedPitaya_app`. This device's FPGA checkout has **no TDC
RTL**, although the app repo has TDC API/SCPI code and a document describing
TDC integration. The other device may hold the unsynced TDC-integrated design.
**Merge into that design; do not replace its custom top or decoder wholesale.**

The user instructed that HDL checks and Vivado compilation should be performed
on the other device. No further local HDL checks were run after that instruction.
Before the instruction arrived:

- Icarus Verilog 13.0 simulation reported `tb_pulse_gen: PASS`, using the
  explicitly test-only ideal ODDR model, not Xilinx UNISIM or physical delays.
- slang 12.0 compiled the pulse module/testbench semantically with no errors.
- The custom top passed a syntax parse before the final `ser_clk` hookup.

Those HDL results refer to the preceding revision. Subsequent source review
added a startup driver guard and its regression case: a saved HIGH GPIO data
bit on an input must not leak a pulse while ON claims it. The ODDR is switched
to LOW before the driver is enabled. **The current revision, including that
guard and final clock hookup, still needs fresh Vivado/UNISIM verification on
the other device.** The guard was not locally simulated after the stop request.

Software checks completed: the new API and SCPI `.cpp` files passed native
Windows GCC 16.2 C++20 syntax checks against the real repository headers and
RedPitaya/scpi-parser commit `4e879901b51cbb43dab36dd83f95a23f1dbaa4c0`.
Minimal Windows-only shims supplied `MAP_FAILED` and syslog constants. This
does **not** establish ARM/Linux compilation, linking, memory-mapped operation,
or live SCPI correctness. The full Linux/API/server build remains required.
The provided Python smoke test passed an AST syntax check and its `--help`
invocation; neither operation contacted hardware.

**No Vivado synthesis, UNISIM simulation, placement, routing, timing/DRC,
bitstream generation, deployment, or board/PCB measurement has been completed
for this feature. No board was contacted.** Do not claim 250 MHz electrical
performance from the logic test. Temporary local check tools are under the
app repo's ignored `build/` directory and are not deployment files.

## Timing contract

The generator uses the existing **250 MHz `ser_clk`** from `red_pitaya_pll`
(`CLKOUT4_DIVIDE=4`, nominal 125 MHz reference). It creates no new PLL/MMCM and
does not access DDR memory. DDR here means an **ODDR output register** sends
one value at the rising clock edge and another at the falling edge.

| Setting | Nominal supported range |
|---|---|
| Half-cycle timing unit | 2 ns |
| Period | 4..8,589,934,588 ns, in multiples of 4 ns |
| HIGH duration | 2..period-2 ns, in multiples of 2 ns |
| LOW duration | period minus HIGH, also in multiples of 2 ns |
| Maximum logical repetition frequency | 250 MHz: 2 ns HIGH + 2 ns LOW |
| Requested 8 ns period | 125 MHz, e.g. 4 ns HIGH + 4 ns LOW |
| Example unequal duty | 8 ns period, 2 ns HIGH + 6 ns LOW |

Every multiple of 8 ns is supported within the finite counter range. Periods
such as 6 ns are deliberately rejected: the design emits two half-cycle values
per fast clock and keeps period boundaries aligned to whole fast clocks.
ON and OFF lengths therefore do **not** have to be multiples of 8 ns.

`PULSE:PERIOD` sets an exact integer period and preserves the previous duty ratio
with HIGH rounded/clamped to the 2 ns grid. `PULSE:FREQUENCY` rounds to the
nearest supported period and similarly preserves duty. Query actual timing
after either command. `PULSE:TIMING period_ns,high_ns` sets both explicitly.
All ns values are plain unsigned integers, without a unit suffix; frequency is
numeric hertz. Absolute accuracy follows the reference oscillator. An external
ADC reference other than 125 MHz invalidates the advertised nominal ns values.

Timing changes require output **OFF**. ON starts a fresh period. OFF takes
effect through the mailbox and ODDR pipeline and may truncate the last HIGH
pulse; this is not a burst generator or a guarantee to finish the last pulse.
Global asynchronous reset can truncate it too. Network latency determines when
a command arrives, not the interval between generated edges.

## Pin and ownership

- DIO1_P = `exp_p_io[1]`, E1 physical pin 5, package H16, LVCMOS33.
- Existing constraints set FAST slew and DRIVE 8; no package pin or voltage
  standard was changed for the selected output.
- Default after FPGA reset: generator disabled/unclaimed; normal GPIO control
  applies. First ON claims DIO1_P. OFF retains ownership and drives LOW.
- `PULSE:RESET` stops, restores 1 ms / 500 us defaults, and releases the pin to
  its existing GPIO data/direction registers. Those registers might request
  HIGH, so RESET differs from OFF.
- `DIG:PIN`/`DIG:PIN:DIR` writes do not change the physical pin while claimed.
  Avoid changing its saved GPIO state during pulse use. `DIG:RST` resets normal
  GPIO registers, not this generator. Use `PULSE:OUTPUT OFF` explicitly.
- API release, SCPI client disconnect, and server exit do not stop hardware
  automatically. It runs until OFF, pulse reset, FPGA reset/reload, or clock loss.
- Other GPIOs, trigger/CAN routes, E3/TDC pins, and BNET data paths keep their
  existing functions. `SCOPE_ONLY` does not include this feature.

The ODDR also passes ordinary GPIO data through while unclaimed, so static GPIO
writes on DIO1_P now reach the pad through the fast clock. A stopped/unlocked
clock affects that passthrough. Its ODDR Q connects directly to the dedicated
IOBUF. **Do not put the GPIO/pulse mux after ODDR Q.** Selection is at D1/D2.

## Files to transfer or merge

New FPGA files:

- `prj/v0.94/rtl/pulse_gen.sv`
- `prj/v0.94/sdc/pulse_gen_Z20_G2.xdc`
- `tbn/tb_pulse_gen.sv`
- `tbn/pulse_gen_oddr_model.sv` (portable tests only; never a design source)

Merge FPGA edits in:

- `prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv`: selected-pin IOBUF routing, pulse
  instance, and slot-7 decoder. Preserve the other device's TDC code.
- `red_pitaya_vivado_project_Z20_G2.tcl` and `red_pitaya_vivado_Z20_G2.tcl`:
  select the custom top definition and add the new implementation-only XDC.
  The project script now defines both `Z20_G2` and `Z20_xx`, matching the batch
  script and the 11-wide expansion/33-wide PS GPIO configuration.

New app files:

- `rp-api/api/src/pulsegen.cpp`, `pulsegen.h`
- `scpi-server/src/pulsegen.cpp`, `pulsegen.h`
- `scpi-tests/pulse_generator_test.py`
- this handover

Merge app edits in `rp-api/api/include/rp.h`, `rp-api/api/src/rp.cpp`,
`rp-api/api/CMakeLists.txt`, `scpi-server/src/scpi-commands.cpp`, and `README.md`.
SCPI CMake already glob-loads `src/*.cpp`; the API source list needs its explicit
new entry. Public API mapping is lazy so ordinary initialization does not probe
the optional block. `rp_Release()` unmaps it. Existing BNET/TDC calls are kept.

## Shared slot-7 decode and register interface

| Address | Owner |
|---|---|
| `0x40700000`, local region 0 | BNET |
| `0x40710000`, local region 1 | TDC on the other device; error here because its RTL is absent |
| `0x40720000`, local region 2 | Pulse generator |
| Other local regions | Acknowledged bus error |

Select using slot-7 `addr[19:16]`. Gate **both WEN and REN** independently for
each slave, and mux one rdata/ack/err driver onto `sys[7]`. Preserve the full
address to BNET/TDC as required by those modules; pulse_gen decodes low 16 bits.
On the other device, keep its region-1 TDC branch in that same response mux.
Pulse writes must never reach BNET or TDC, and vice versa.

The existing UIO `test` map covers the entire one-MiB slot. Because `cmn_Map`
rounds the requested offset to a one-MiB UIO map index, the new API maps slot 7
at UIO-relative `0x00700000`, size `0x21000`, then advances its pointer by
`0x20000`. Do not map `0x00720000` and assume that helper selects the subregion.
Use the matching bitstream before issuing pulse commands; unsupported MMIO
addresses can produce AXI/bus errors on older images.

Offsets below are relative to `0x40720000`; counts are **2 ns units**:

| Offset | Register | Meaning |
|---|---|---|
| `0x00` | ID_VERSION, RO | `0x50554c01` |
| `0x04` | CONTROL, RW | Shadow ENABLE bit 0 |
| `0x08` | STATUS, RO | BUSY bit 0, active ENABLE bit 1, CLAIMED bit 2, sticky ERROR bit 3, READY bit 4 |
| `0x0c` | PERIOD, RW | Shadow period count; even, >=2 |
| `0x10` | HIGH, RW | Shadow HIGH count; 1..PERIOD-1 |
| `0x14` | COMMAND, WO | Write exactly 1=APPLY, 2=RESET/RELEASE, or 4=CLEAR_ERROR |
| `0x18` | TICK_NS, RO | 2, nominal |
| `0x1c` | GPIO_INDEX, RO | Positive-bank index, currently 1 |
| `0x20` | ACTIVE_PERIOD, RO | Applied period count |
| `0x24` | ACTIVE_HIGH, RO | Applied HIGH count |

Shadow writes do not change an active waveform. APPLY captures period/HIGH/
enable together into a mailbox held until ACK. A busy/invalid/live-ON APPLY is
rejected with bus error and sticky ERROR; existing active timing is preserved.
Disable is permitted while ON. RESET/RELEASE is rejected while busy. Single-bit
request/ACK/ownership/status signals have synchronizers. Active readback is
sampled after ACK settles. Software uses a process-local mutex, MMIO ordering
fence, settled reads, a 100 ms timeout and applied-value readback; concurrent
independent processes directly editing registers are not serialized by it.

## SCPI examples

125 MHz, 8 ns period with adjustable width:

```text
PULSE:OUTPUT OFF
PULSE:TIMING 8,4
PULSE:PIN?
PULSE:TIMING?
PULSE:FREQUENCY?
PULSE:OUTPUT ON
PULSE:OUTPUT?
PULSE:STATUS?
PULSE:OUTPUT OFF
```

Expected queries: `DIO1_P`, `8,4`, approximately `125000000`, `1`, and normally
STATUS `22` (`0x16`, READY|CLAIMED|ENABLED). OFF normally leaves STATUS `20`
(`0x14`, READY|CLAIMED). Before any ON/after RESET, normal STATUS is `16`.

```text
PULSE:WIDTH 2
PULSE:PERIOD 24
PULSE:TIMING?
PULSE:FREQUENCY 1000000
PULSE:TIMING?
PULSE:RESET
```

WIDTH/period/frequency setters require OFF. This sequence illustrates duty
preservation: after 8/2 timing, PERIOD 24 gives 24/6, not 24/12. To request exact
50% duty, use `PULSE:TIMING 24,12`. `PULSE:PERIOD?` and `PULSE:WIDTH?` return
individual applied ns values. The 250 MHz logical case is `PULSE:TIMING 4,2`;
first verify the PCB and scope connection before enabling that case.

## Required checks on the Vivado device

1. Sync/merge the files above. Confirm only the intended custom file defines
   active `red_pitaya_top`. Keep the TDC instance, E3 routing, placement XDC and
   dedicated MMCM if they exist there. Never include the portable ODDR model
   in a Vivado design/simulation fileset; use Xilinx UNISIM instead.
2. Run fresh behavioural simulation of `tb_pulse_gen` with real UNISIM ODDR.
   Require its final PASS. It covers 4/8/24 ns and 1 us periods, odd/even HIGH
   counts, saved-HIGH GPIO startup ownership, OFF LOW, normal GPIO restoration, invalid timing, rejected live
   updates, max register values, a frozen/busy mailbox and reset with stopped
   fast clock. It does not establish electrical edge speed or post-route timing.
   A CLI flow in a scratch directory is:

   ```text
   xvlog -sv "<FPGA_ROOT>/prj/v0.94/rtl/pulse_gen.sv" "<FPGA_ROOT>/tbn/tb_pulse_gen.sv"
   xelab tb_pulse_gen -L unisims_ver -s pulse_gen_sim
   xsim pulse_gen_sim -runall
   ```

3. Elaborate and synthesize the **full merged** Z20_G2 design. Verify DWE=11,
   GPIO width 33, one selected IOBUF on DIO1_P/H16 and one pulse ODDR. Check no
   multiple drivers, duplicate tops, unconnected pulse nets or TDC/BNET aliases.
4. Inspect clocks: pulse `fast_clk_i`/ODDR C must receive **4.000 ns `ser_clk`**
   from the existing PLL and bus_clk must be 8.000 ns. The serial clock was
   chosen so legacy broad ADC-to-DAC false paths do not hide mailbox timing.
   Confirm actual clock names/relationships in the merged project.
5. Ensure `pulse_gen_Z20_G2.xdc` is enabled for implementation and disabled for
   synthesis. Its five first-stage synchronizer matches must resolve; bundled
   register collections must be nonempty. Confirm the 4 ns mailbox and 8 ns
   readback max-delay constraints cover the intended bits and are not overridden
   by another broad false path. Do not blanket-false-path the pulse clock pair.
6. Implement and inspect `report_timing_summary`, `report_clock_interaction`,
   `report_cdc`, `report_exceptions`, `report_drc`, `report_io`, and hierarchical
   utilization. All ordinary 250 MHz counter/comparator/ODDR paths must close.
   Confirm ODDR placement in H16's output IOB and direct Q-to-IOBUF connectivity;
   verify LVCMOS33, FAST slew and allowed drive strength. No new timing/DRC issue
   may be accepted simply because a bitstream was generated.
7. Run existing BNET regression and the TDC logic/UNISIM tests in the merged
   project. Test interleaved BNET/TDC/pulse register transactions to rule out
   decoder leakage. Confirm TDC primitive preservation/placement and MMCM lock
   remain correct after the new placement/routing run. Existing TDC calibration
   must remain tied to the exact placed bitstream.
8. Build API/server in the established Linux/ARM environment (`make api`,
   `make scpi`). This fetches the parser dependency absent from this checkout's
   source tree. Confirm both the library and server use the updated public header,
   symbols and command table; native Windows syntax checks are insufficient.
9. Deploy the **matching** bitstream/API/server using the existing board workflow
   with backups and an identifiable build. Record checksums/commits and reports.
   Do not issue pulse commands against an unmatched old image.
10. Run `python scpi-tests/pulse_generator_test.py <board-host>` after confirming
    DIO1_P is free; it enables a 1 MHz waveform briefly and ends OFF/LOW. This
    script is provided but has **not** been run against a board. It checks register
    control only. Test errors for period 6 ns, HIGH 0/3 ns, HIGH>=period, overflow,
    and timing writes while ON; they must not alter the running waveform.
11. Measure with a suitable high-bandwidth scope and high-impedance low-capacitance
    probe. Start slowly; verify LOW/HIGH voltage, period, both widths, edge shape,
    ringing, OFF state and restart. Then test 24 ns, 8 ns and finally 4 ns periods
    with the **actual PCB receiver and traces**. Quantify jitter and receiving
    threshold/minimum-pulse compliance. Do not infer performance from a counter.

## PCB connection and unresolved 3.3 V DC request

The PCB's input circuitry determines the usable pulse speed: input capacitance,
logic thresholds, minimum pulse width, trace/interconnect length, grounding and
termination must be known. Use a common ground and review signal return paths.
Allow for source damping/ buffering if measurement shows it is needed. A 50-ohm
DC load would draw 66 mA at 3.3 V, beyond the documented GPIO drive capability;
do not treat this output as a 50-ohm signal-generator port.

**Pending colleague confirmation, requested for 2026-10-14:** Are the proposed
two DC pins meant to **power the PCB** or provide **constant HIGH logic inputs**?
The user does not yet know. No GPIOs have been allocated or configured for that
request. Record the colleague's answer before deciding the wiring/code:

- Power: use dedicated E1 +3V3 pins 1/2 and GND pins 25/26, after checking PCB
  steady-state/inrush current and the board supply budget. Red Pitaya publishes
  a **0.5 A total** budget for the two E1 3.3 V supply pins; confirm the actual
  board revision and available margin. GPIO pins are not PCB supply outputs.
- Constant HIGH references: existing `DIG:PIN:DIR OUT,<pin>` and
  `DIG:PIN <pin>,1` can already do this on spare GPIOs. Confirm input loading,
  voltage compatibility and required state during boot/reset/power sequencing.
  Do not parallel GPIO outputs to obtain more supply current.
- Also obtain receiver part numbers/schematic, input impedance/capacitance,
  PCB/connector lengths, logic threshold/minimum pulse width, and whether the
  PCB can be powered independently of the Red Pitaya.

Official references:

- [Red Pitaya Z7020 Gen 2 connector and electrical specifications](https://redpitaya.readthedocs.io/en/latest/developerGuide/hardware/GEN2/125-14_Gen2_Z7020_Pro/top.html)
- [AMD ODDR SAME_EDGE behaviour](https://docs.amd.com/r/en-US/ug953-vivado-7series-libraries/ODDR)
