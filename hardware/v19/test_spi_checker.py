from pathlib import Path
import tkinter
root=Path(__file__).resolve().parent
s=(root/'prj/v0.94/scripts/check_v19_constraints.tcl').read_text()
t=tkinter.Tcl();t.eval(s[:s.index('foreach core')])
t.eval('''
proc get_cells {args} {
  global fixture
  set expression [lindex $args end]
  set found {}
  foreach {name ref} $fixture {
    if {[lsearch -exact $args -regexp]>=0} {
      if {[regexp $expression $name]} {lappend found $name}
    } else {
      regexp {NAME =~ ([^ ]+).*REF_NAME =~ ([^ ]+)} $expression -> hierarchy primitive
      if {[string match $hierarchy $name] && [string match $primitive $ref]} {lappend found $name}
    }
  }
  return $found
}
proc get_pins {args} {
  global fixture
  set expression [lindex $args end]
  regexp {NAME =~ ([^ ]+)} $expression -> hierarchy
  set found {}
  foreach {name ref} $fixture {
    if {[string match FD* $ref] && [string match $hierarchy ${name}/D]} {lappend found ${name}/D}
  }
  return $found
}
''')
outputs=['sclk_o','mosi_pin','cs_n_o','ldac_n_o']
for missing,shift_bits,raw_bits,extra,passes in [(None,24,24,False,True),('mosi_pin',24,24,False,False),(None,23,24,False,False),(None,24,23,False,False),(None,24,24,True,False)]:
    fixture=[]
    for name in outputs:
        if name!=missing:fixture.extend([f'i_dac_spi/{name}_reg','FDRE'])
    if extra:fixture.extend(['replica/i_dac_spi/mosi_pin_reg','FDRE'])
    for prefix,n in [('tx_shift',shift_bits),('raw_tx',raw_bits)]:
        for i in range(n):fixture.extend([f'i_dac_spi/{prefix}_reg[{i}]','FDRE'])
    t.setvar('fixture',tuple(fixture))
    try:t.call('v19_check_spi_outputs');success=True
    except tkinter.TclError:success=False
    assert success==passes,(missing,shift_bits,raw_bits,extra)
for meta,sync,rx_bits,result_bits,passes in [(True,True,24,24,True),(False,True,24,24,False),(True,False,24,24,False),(True,True,23,24,False),(True,True,24,0,False)]:
    fixture=[]
    for name,present in [('miso_meta',meta),('miso_sync',sync)]:
        if present:fixture.extend([f'i_dac_spi/{name}_reg','FDRE'])
    for prefix,n in [('rx_shift',rx_bits),('raw_rx',result_bits)]:
        for i in range(n):fixture.extend([f'i_dac_spi/{prefix}_reg[{i}]','FDRE'])
    t.setvar('fixture',tuple(fixture))
    try:t.call('v19_check_spi_readback');success=True
    except tkinter.TclError:success=False
    assert success==passes,(meta,sync,rx_bits,result_bits)
print('PASS: SPI checker requires four output FFs, both settling stages and complete TX/RX register banks')
