"""Read the existing synthesized DCP's EDIF without launching Vivado."""
from pathlib import Path
import re,zipfile,json,fnmatch
import difflib
app=Path(__file__).resolve().parents[2]
dcp=Path('C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/redpitaya.runs/synth_1/red_pitaya_top.dcp')
name=r'(?:\(rename\s+(\S+)\s+"([^"]+)"\)|([^\s()]+))'
cell_re=re.compile(r'^\s*\(cell\s+'+name)
inst_re=re.compile(r'^\s*\(instance\s+'+name+r'\s+\(viewref\s+\S+\s+\(cellref\s+([^\s()]+)')
cells={};current=None
with zipfile.ZipFile(dcp) as z:
    with z.open('red_pitaya_top.edf') as f:
        for raw in f:
            line=raw.decode()
            m=cell_re.match(line)
            if m:
                current=m[1] or m[3];cells.setdefault(current,[])
            m=inst_re.match(line)
            if m and current:cells[current].append((m[2] or m[3] or m[1],m[4]))
leaves=[]
def visit(cell,prefix=''):
    for name,ref in cells.get(cell,[]):
        path=prefix+'/'+name if prefix else name
        if ref.startswith('RAMB'):leaves.append(dict(name=path,ref=ref))
        elif ref in cells:visit(ref,path)
visit('red_pitaya_top')
asg=[x for x in leaves if 'dac_buf' in x['name']]
out=app/'build/tdc-v19-review/asg_synthesis_review.json'
out.write_text(json.dumps(dict(dcp=str(dcp),ram_primitives=len(leaves),asg=asg),indent=2))
for ch in ('chA','chB'):
    found=[x for x in asg if ch in x['name']]
    print(ch,len(found))
    for row in found:print(row['ref'],row['name'])
print('Total RAM primitives',len(leaves))
for cell,children in cells.items():
    for name,ref in children:
        if 'chA' in name or 'chB' in name or 'i_asg' in name:
            if '/' not in name or name.endswith(('chA','chB')):
                print('Hierarchy:',cell,name,'->',ref)
print('ASG or unclassified RAM:',[x for x in leaves if 'i_tdc' not in x['name']])
for ref in ['red_pitaya_asg_ch','red_pitaya_asg_ch__parameterized0']:
    print(ref,'children',len(cells.get(ref,[])),'RAM',[p for p in cells.get(ref,[]) if p[1].startswith('RAMB')])
with zipfile.ZipFile(dcp) as z:
    current=None;capture=[]
    for raw in z.open('red_pitaya_top.edf'):
        line=raw.decode();m=cell_re.match(line)
        if m:current=m[1] or m[3]
        if current in ['red_pitaya_asg','red_pitaya_asg_ch','red_pitaya_asg_ch__parameterized0']:capture.append(line)
(out.parent/'asg_netlist_excerpt.edf').write_text(''.join(capture))
repo=app.parent/'fpgaprj/RedPitaya-FPGA'
imports=dcp.parents[2]/'redpitaya.srcs/sources_1/imports/RedPitaya-FPGA'
for relative in ['rtl/classic/red_pitaya_asg.sv','rtl/sys_bus_interconnect.sv']:
    a=(repo/relative).read_text().splitlines()
    b=(imports/relative).read_text().splitlines()
    print('Imported source normalized match',relative,a==b)
    if a!=b:print('\n'.join(list(difflib.unified_diff(a,b,fromfile='repository',tofile='project import'))[:100]))
