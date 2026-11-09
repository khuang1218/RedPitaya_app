"""Package the API/SCPI overlay for an existing RedPitaya_app checkout."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
files = [
    'rp-api/api/CMakeLists.txt', 'rp-api/api/include/rp.h',
    *[f'rp-api/api/src/{name}' for name in [
        'tdc.cpp', 'pulsegen.cpp', 'rp.cpp', 'bnet.cpp', 'gen_handler.cpp',
        'custom_hw.cpp', 'custom_hw.h', 'custom_mmio.h', 'dac_spi.cpp', 'dac_spi.h']],
    'scpi-server/README.md', 'scpi-server/V19_SOFTWARE.md',
    *[f'scpi-server/src/{name}' for name in [
        'tdc.cpp', 'pulsegen.cpp', 'pulsegen.h', 'api_cmd.cpp',
        'scpi-commands.cpp', 'scpi-commands.h', 'dac_spi.cpp', 'dac_spi.h']],
    *[f'scpi-tests/{name}' for name in [
        'v19_software_test.cpp', 'v19_startup_test.cpp', 'tdc_input_selection_test.cpp',
        'run_v19_software_tests.sh', 'prepare_v19_tests.py', 'package_v19_software.py']],
]
out = root/'build/v19-software'
out.mkdir(parents=True, exist_ok=True)
manifest = [{'path': p, 'sha256': hashlib.sha256((root/p).read_bytes()).hexdigest()} for p in files]
bundle = out/'red_pitaya_v19_software_sources.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
    for relative in files:
        archive.write(root/relative, 'RedPitaya_app/'+relative)
    archive.writestr('source_manifest.json', json.dumps(manifest, indent=2))
    archive.writestr('README.txt', 'Overlay these files on the existing RedPitaya_app checkout.\n'
                     'Build librp and scpi-server together on the ARM Linux build system.\n'
                     'See RedPitaya_app/scpi-server/V19_SOFTWARE.md.\n'
                     'No bitstream, target binaries or parser/dependency checkout is included.\n')
with zipfile.ZipFile(bundle) as archive:
    for item in manifest:
        assert hashlib.sha256(archive.read('RedPitaya_app/'+item['path'])).hexdigest() == item['sha256']
(out/'source_manifest.json').write_text(json.dumps(manifest, indent=2))
print(f'PASS: {len(files)} software source/doc/test files packaged and SHA256 verified: {bundle}')
