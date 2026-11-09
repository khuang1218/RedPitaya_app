from pathlib import Path
import sys,json,xml.etree.ElementTree as E
app=Path(__file__).resolve().parents[2]
overlay=Path(__file__).resolve().parent
sys.path.insert(0,str(app/'build/v19-tools'))
from pyslang.driver import Driver
repo=app.parent/'fpgaprj/RedPitaya-FPGA'
oldrepo=Path('C:/vivadoprj/RedPitaya-FPGA')
project=oldrepo/'prj/v0.94/project'
xpr=E.parse(project/'redpitaya.xpr').getroot()
files=[]
def resolve(s):
    return Path(s.replace('$PSRCDIR',str(project/'redpitaya.srcs')).replace('$PPRDIR',str(project))).resolve()
for f in xpr.findall('./FileSets/FileSet[@Name="sources_1"]/File'):
    attrs=f.findall('./FileInfo/Attr')
    if not any(a.get('Name')=='UsedIn' and a.get('Val')=='synthesis' for a in attrs):continue
    source=resolve(f.get('Path'))
    if source.suffix.lower() not in ('.sv','.v'):continue
    original=next((resolve(a.get('Val')) for a in attrs if a.get('Name')=='ImportPath'),source)
    try: current=repo/original.relative_to(oldrepo)
    except ValueError: current=original
    if not current.exists():current=source
    if current.name.startswith('red_pitaya_top'):continue
    if current not in files:files.append(current)
for f in [*sorted((repo/'prj/v0.94/rtl').glob('tdc_*.sv')),repo/'prj/v0.94/rtl/pulse_gen.sv',
          repo/'rtl/classic/red_pitaya_asg_ch.sv',repo/'rtl/sys_bus_cdc.sv',*sorted((overlay/'prj/v0.94/rtl').glob('*.sv'))]:
    files=[p for p in files if p.name!=f.name];files.append(f)
vendor=Path('C:/Xilinx/Vivado/2020.1/data/verilog/src')
for name in ['CARRY4','FDRE','FDCE','ODDR','BUFG','BUFGCTRL','IBUFDS','OBUFDS','IOBUF','IBUF','OBUF','MMCME2_ADV','PLLE2_ADV']:
    files.append(vendor/'unisims'/f'{name}.v')
files.append(vendor/'glbl.v')
out=app/'build/tdc-v19-review';out.mkdir(parents=True,exist_ok=True)
(out/'elaboration_sources.json').write_text(json.dumps([str(p) for p in files],indent=2))
d=Driver();d.addStandardArgs()
args='slang --timescale 1ns/1ps --ignore-unknown-modules -DZ20_G2 -DZ20_xx -DDISABLE_BNET --top red_pitaya_top --top glbl '+' '.join('"'+p.as_posix()+'"' for p in files)
print('Static v19 top elaboration:',len(files),'sources; generated PS/IP external')
if not d.parseCommandLine(args) or not d.processOptions() or not d.parseAllSources():
    d.reportParseDiags();raise SystemExit(1)
c=d.createCompilation();d.reportCompilation(c,False)
raise SystemExit(0 if d.reportDiagnostics(False) else 1)
