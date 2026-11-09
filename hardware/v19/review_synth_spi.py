"""Inspect the existing synthesis EDIF; does not launch Vivado."""
from pathlib import Path
import re,zipfile,json,sys
app=Path(__file__).resolve().parents[2]
dcp=Path(sys.argv[1]) if len(sys.argv)>1 else Path('C:/vivadoprj/RedPitaya-FPGA/prj/v0.94/project/redpitaya.runs/synth_1/red_pitaya_top.dcp')
name=r'(?:\(rename\s+(\S+)\s+"([^"]+)"\)|([^\s()]+))'
cell_re=re.compile(r'^\s*\(cell\s+'+name)
inst_re=re.compile(r'^\s*\(instance\s+'+name+r'\s+\(viewref\s+\S+\s+\(cellref\s+([^\s()]+)')
cells={};current=None;spi=[];top=[];signals=[]
with zipfile.ZipFile(dcp) as z:
    for raw in z.open('red_pitaya_top.edf'):
        line=raw.decode();m=cell_re.match(line)
        if m:current=m[1] or m[3];cells.setdefault(current,[])
        m=inst_re.match(line)
        if m and current:cells[current].append((m[2] or m[3] or m[1],m[4]))
        if current and current.startswith('dac80516_spi'):spi.append(line)
        if current=='red_pitaya_top':top.append(line)
        if any(x in line for x in ['raw_tx','tx_shift','mosi_o','group_operation']):signals.append((current,line.strip()))
leaves=[]
def visit(cell,prefix=''):
    for name,ref in cells.get(cell,[]):
        path=f'{prefix}/{name}' if prefix else name
        if ref in cells and cells[ref]:visit(ref,path)
        else:leaves.append(dict(name=path,ref=ref))
visit('red_pitaya_top')
outputs=[x for x in leaves if re.search('sclk_o|mosi_pin|mosi_o|cs_n_o|ldac_n_o|miso_meta|miso_sync',x['name'])]
out=app/'build/tdc-v19-review'
(out/'spi_synthesis_review.json').write_text(json.dumps(dict(dcp=str(dcp),outputs=outputs),indent=2))
(out/'spi_netlist_excerpt.edf').write_text(''.join(spi))
(out/'top_netlist_excerpt.edf').write_text(''.join(top))
for row in outputs:print(row['ref'],row['name'])
for name in ('rx_shift','raw_rx','raw_tx','tx_shift'):
    print('Payload FFs',name,len([x for x in leaves if x['ref'].startswith('FD') and f'{name}_reg' in x['name']]))
print('SPI data signal references',len(signals))
for cell,line in signals[:20]:print(cell,line)
for ch in ('chA','chB'):
    rams=[x for x in leaves if f'i_asg/{ch}/' in x['name'] and x['ref'].startswith('RAMB') and 'dac_buf' in x['name']]
    print('ASG',ch,'waveform RAMs',len(rams))
