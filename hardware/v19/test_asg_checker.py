from pathlib import Path
import tkinter
root=Path(__file__).resolve().parent
s=(root/'prj/v0.94/scripts/check_v19_constraints.tcl').read_text()
# Load the actual checker procedures, without querying an absent Vivado design.
t=tkinter.Tcl();t.eval(s[:s.index('foreach core')])
t.eval('''
proc get_cells {args} {
  global fixture
  set filter [lindex $args end]
  regexp {NAME =~ ([^ ]+).*NAME =~ ([^ ]+).*REF_NAME =~ ([^ ]+)} $filter -> hierarchy memory primitive
  set found {}
  foreach {name ref} $fixture {
    if {[string match $hierarchy $name] && [string match $memory $name] && [string match $primitive $ref]} {
      lappend found $name
    }
  }
  return $found
}
''')
for a,b,nested,passes in [(7,7,False,True),(7,7,True,True),(0,14,False,False),(7,6,False,False)]:
    fixture=[]
    for ch,n in [('chA',a),('chB',b)]:
        for i in range(n):fixture.extend([f'i_asg/{ch}/'+('table/' if nested else '')+f'dac_buf_reg_{i}','RAMB36E1'])
    t.setvar('fixture',tuple(fixture))
    try:t.call('v19_check_asg_tables');success=True
    except tkinter.TclError:success=False
    assert success==passes,(a,b,nested)
print('PASS: ASG checker accepts distinct/nested A/B RAMs; rejects merged and incomplete tables')
