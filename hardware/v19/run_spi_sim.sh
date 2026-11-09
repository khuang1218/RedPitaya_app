#!/bin/bash
set -euo pipefail
app=/mnt/c/Users/kairan/vscodeprj/RedPitaya_app
tool=/mnt/c/Users/kairan/RedPitaya_local_data/RedPitaya_app/build/hdl-tools/iverilog-linux/extracted/usr
out=$app/build/tdc-v19-review
"$tool/bin/iverilog" -B "$tool/lib/x86_64-linux-gnu/ivl" -g2012 -s tb_dac80516_spi -o "$out/spi_repair.vvp" \
 "$app/hardware/v19/tbn/tb_dac80516_spi.sv" "$app/hardware/v19/prj/v0.94/rtl/dac80516_spi.sv" >"$out/spi_repair_compile.log" 2>&1
for hold in 1 2 3;do
 "$tool/bin/vvp" "$out/spi_repair.vvp" +BUS_HOLD_CYCLES=$hold >"$out/spi_repair_hold$hold.log" 2>&1
 cat "$out/spi_repair_hold$hold.log"
done
