#!/bin/bash
set -euo pipefail
root=/mnt/c/Users/kairan/vscodeprj/RedPitaya_app
overlay=$root/hardware/v19
fpga=/mnt/c/Users/kairan/vscodeprj/fpgaprj/RedPitaya-FPGA
tool=/mnt/c/Users/kairan/RedPitaya_local_data/RedPitaya_app/build/hdl-tools/iverilog-linux/extracted/usr
out=$root/build/tdc-v19-review
mkdir -p "$out"
iv=("$tool/bin/iverilog" -B "$tool/lib/x86_64-linux-gnu/ivl" -g2012)
"${iv[@]}" -s tb_dac80516_spi -o "$out/spi.vvp" "$overlay/tbn/tb_dac80516_spi.sv" "$overlay/prj/v0.94/rtl/dac80516_spi.sv" >"$out/spi_compile.log" 2>&1
for hold in 1 2 3; do
 "$tool/bin/vvp" "$out/spi.vvp" +BUS_HOLD_CYCLES=$hold >"$out/spi_hold$hold.log" 2>&1
 cat "$out/spi_hold$hold.log"
done
width=("$fpga/tbn/tdc_carry_chain_timing_model.sv" "$fpga/prj/v0.94/rtl/tdc_pulse_width.sv" "$fpga/prj/v0.94/rtl/tdc_frame_delay.sv" "$fpga/prj/v0.94/rtl/tdc_thermometer_encoder.sv" "$fpga/prj/v0.94/rtl/tdc_population_pipeline.sv")
"${iv[@]}" -s tb_v19_dual_width -o "$out/dual.vvp" "$overlay/tbn/tb_v19_dual_width.sv" "${width[@]}" >"$out/dual_compile.log" 2>&1
for hold in 1 2 3; do
 "$tool/bin/vvp" "$out/dual.vvp" +BUS_HOLD_CYCLES=$hold >"$out/dual_hold$hold.log" 2>&1
 cat "$out/dual_hold$hold.log"
done
# Existing width/pulse regressions compile current retained datapaths. Redirect
# every old review output into v19, preserving previous v18 acceptance evidence.
for script in run_pulse_v18.sh run_legacy_v18.sh; do
 sed 's@tdc-v18-review@tdc-v19-review@g' "$root/build/tdc-v18-review/$script" >"$out/$script"
done
# The parameterized wrappers are the only modified TDC RTL. Test V19 identity
# with the existing legacy/width isolation and reset regression.
sed -e "s/tdc_top #(.NUM_CARRY4(4))/tdc_top #(.VERSION(8'd19),.NUM_CARRY4(4))/" -e 's/54444312/54444313/g' "$fpga/tbn/tb_tdc_top.sv" >"$out/tb_tdc_top_v19.sv"
# Explicit source array keeps retained dependencies in the original repository.
legacy=("$out/tb_tdc_top_v19.sv" "$fpga/tbn/tdc_carry_chain_logic_model.sv" "$overlay/prj/v0.94/rtl/tdc_top.sv" "$overlay/prj/v0.94/rtl/tdc_registers.sv")
for module in tdc_pulse_width tdc_population_pipeline tdc_frame_delay tdc_calibration_mem tdc_result_fifo tdc_thermometer_encoder tdc_internal_stimulus tdc_mmcm_stimulus tdc_lvds_io; do legacy+=("$fpga/prj/v0.94/rtl/$module.sv");done
vendor=/mnt/c/Xilinx/Vivado/2020.1/data/verilog/src
for module in MMCME2_ADV BUFG OBUFDS IBUFDS;do legacy+=("$vendor/unisims/$module.v");done
"${iv[@]}" -s tb_tdc_top -s glbl -o "$out/legacy_v19.vvp" "${legacy[@]}" "$vendor/glbl.v" >"$out/legacy_v19_compile.log" 2>&1
"$tool/bin/vvp" "$out/legacy_v19.vvp" >"$out/legacy_v19.log" 2>&1
cat "$out/legacy_v19.log"
# Bounded full-size fine pipeline at 25 MHz. The unchanged 16K buffer has the
# earlier v18 full-depth acceptance evidence; do not repeat that long run here.
"${iv[@]}" -s tb_tdc_pulse_width -Ptb_tdc_pulse_width.FULL_SIZE=1 -Ptb_tdc_pulse_width.FULL_DEPTH=32 -Ptb_tdc_pulse_width.FRAME_FAST_CYCLES=10 -Ptb_tdc_pulse_width.FULL_FINE=1 -o "$out/fine25.vvp" "$fpga/tbn/tb_tdc_pulse_width.sv" "${width[@]}" >"$out/fine25_compile.log" 2>&1
"$tool/bin/vvp" "$out/fine25.vvp" >"$out/fine25.log" 2>&1
cat "$out/fine25.log"
bash "$out/run_pulse_v18.sh"
