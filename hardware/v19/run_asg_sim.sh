#!/bin/bash
set -euo pipefail
app=/mnt/c/Users/kairan/vscodeprj/RedPitaya_app
tool=/mnt/c/Users/kairan/RedPitaya_local_data/RedPitaya_app/build/hdl-tools/iverilog-linux/extracted/usr
repo=/mnt/c/Users/kairan/vscodeprj/fpgaprj/RedPitaya-FPGA
out=$app/build/tdc-v19-review
"$tool/bin/iverilog" -B "$tool/lib/x86_64-linux-gnu/ivl" -g2012 -s tb_v19_asg_tables -o "$out/asg_tables.vvp" \
 "$app/hardware/v19/tbn/tb_v19_asg_tables.sv" "$out/red_pitaya_asg_v19_sim.sv" \
 "$out/red_pitaya_asg_ch_v19_sim.sv" "$out/asg_ddr_disabled_stub.sv" "$repo/rtl/rand_lfsr.v" >"$out/asg_tables_compile.log" 2>&1
"$tool/bin/vvp" "$out/asg_tables.vvp" >"$out/asg_tables.log" 2>&1
cat "$out/asg_tables.log"
