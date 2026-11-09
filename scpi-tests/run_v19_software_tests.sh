#!/bin/bash
# Hardware-free regression. CXX may point to a native or ARM C++20 compiler.
set -euo pipefail
cd "$(dirname "$0")/.."
out="${V19_TEST_OUT:-build/v19-software}"
mkdir -p "$out"
mkdir -p "$out/include/common"
cp rp-api/api-sweep/src/rp_sweep.h "$out/include/common/"
parser="${SCPI_PARSER_DIR:-scpi-server/scpi-parser/libscpi}"
if [[ ! -f "$parser/inc/scpi/scpi.h" ]]; then
  echo 'Set SCPI_PARSER_DIR to the pinned libscpi directory (or initialize submodules).' >&2
  exit 1
fi
cxx="${CXX:-g++}"
includes=(-Irp-api/api/include -Irp-api/api-hw-calib/include -Irp-api/api-hw-profiles/include
          -Irp-api/api-250-12/include -I"$parser/inc" -I"$out/include")
flags=(-std=c++20 -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers -pthread)
if [[ "${V19_SKIP_SYNTAX:-0}" != 1 ]]; then
for source in rp-api/api/src/{tdc,pulsegen,dac_spi,custom_hw,rp,bnet,gen_handler}.cpp \
              scpi-server/src/{tdc,pulsegen,dac_spi,scpi-commands,api_cmd}.cpp; do
  echo "Compiling $source"
  "$cxx" "${flags[@]}" "${includes[@]}" -fsyntax-only "$source"
done
echo 'PASS: API and SCPI modified translation units compile'
fi
python3 scpi-tests/prepare_v19_tests.py
mkdir -p "$out/parser-objects"
parser_objects=()
for source in "$parser"/src/*.c; do
  object="$out/parser-objects/$(basename "${source%.c}").o"
  if [[ ! -f "$object" || "$source" -nt "$object" ]]; then
    "$cxx" -x c -std=c11 -I"$parser/inc" -c "$source" -o "$object"
  fi
  parser_objects+=("$object")
done
"$cxx" "${flags[@]}" "${includes[@]}" -DRP_CUSTOM_MMIO_TEST \
  scpi-tests/v19_software_test.cpp "$out/unrelated_scpi_stubs.cpp" \
  rp-api/api/src/{tdc,pulsegen,dac_spi,custom_hw}.cpp \
  scpi-server/src/{tdc,pulsegen,dac_spi,scpi-commands}.cpp \
  "${parser_objects[@]}" -o "$out/v19_software_test"
"$out/v19_software_test"
"$cxx" "${flags[@]}" "${includes[@]}" scpi-tests/tdc_input_selection_test.cpp \
  scpi-server/src/tdc.cpp "${parser_objects[@]}" -o "$out/tdc_input_selection_test"
"$out/tdc_input_selection_test"
"$cxx" "${flags[@]}" "${includes[@]}" -ffunction-sections -fdata-sections \
  scpi-tests/v19_startup_test.cpp rp-api/api/src/{rp,custom_hw}.cpp \
  -Wl,--gc-sections -o "$out/v19_startup_test"
"$out/v19_startup_test"
