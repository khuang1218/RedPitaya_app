"""Generate stubs only for unrelated callbacks when testing the real SCPI table."""
from pathlib import Path
import os
import re

root = Path(__file__).resolve().parents[1]
out = root / os.environ.get('V19_TEST_OUT', 'build/v19-software')
parser = Path(os.environ.get('SCPI_PARSER_DIR', root/'scpi-server/scpi-parser/libscpi'))
table = (root/'scpi-server/src/scpi-commands.cpp').read_text()
provided = '\n'.join((root/f'scpi-server/src/{name}.cpp').read_text()
                     for name in ['tdc', 'pulsegen', 'dac_spi', 'scpi-commands'])
provided += '\n' + '\n'.join(p.read_text() for p in (parser/'src').glob('*.c'))
implemented = set(re.findall(r'\bscpi_result_t\s+(\w+)\s*\(', provided))
callbacks = set(re.findall(r'SCPI_CMD\("[^"]+",\s*(\w+)\)', table))
stubs = ['#include "scpi/scpi.h"', '#include <cassert>']
for callback in sorted(callbacks - implemented):
    stubs.append(f'scpi_result_t {callback}(scpi_t*) {{ assert(false && "Unrelated SCPI callback invoked"); return SCPI_RES_ERR; }}')
stubs += [
    'int SCPI_Error(scpi_t*, int_fast16_t) { return 0; }',
    'size_t SCPI_Write(scpi_t*, const char*, size_t n) { return n; }',
    'size_t SCPI_WriteUartProtocol(scpi_t*, const char*, size_t n) { return n; }',
    'scpi_result_t SCPI_Reset(scpi_t*) { return SCPI_RES_OK; }',
    'scpi_result_t SCPI_Flush(scpi_t*) { return SCPI_RES_OK; }',
    'scpi_result_t SCPI_Control(scpi_t*, scpi_ctrl_name_t, scpi_reg_val_t) { return SCPI_RES_OK; }',
]
(out/'unrelated_scpi_stubs.cpp').write_text('\n'.join(stubs) + '\n')
print(f'Prepared real command-table test; {len(callbacks - implemented)} unrelated callbacks stubbed')
