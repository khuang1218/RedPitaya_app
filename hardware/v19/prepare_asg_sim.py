from pathlib import Path
import re
root=Path(__file__).resolve().parent
out=root.parents[1]/'build/tdc-v19-review';out.mkdir(parents=True,exist_ok=True)
# Icarus does not support interface ports. Remove only the disconnected AXI
# interface syntax and replace its disabled reader with a zero-output stub.
# All MMIO decoding, memory access and local waveform processing is real RTL.
for name in ['red_pitaya_asg_v19','red_pitaya_asg_ch_v19']:
    s=(root/'prj/v0.94/rtl'/f'{name}.sv').read_text()
    s=re.sub(r'^\s*axi_sys_if\.s\s+\w+\s*,[^\n]*\n','',s,flags=re.M)
    s=re.sub(r'^\s*\.axi_(?:a_sys|b_sys|sys)\s*\([^\n]*\)\s*,[^\n]*\n','',s,flags=re.M)
    (out/f'{name}_sim.sv').write_text(s)
(out/'asg_ddr_disabled_stub.sv').write_text('''
module rp_asg_axi #(parameter RSZ=16)(
 output wire [13:0] dac_o,input wire dac_clk_i,dac_rstn_i,trig_i,set_rst_i,set_axi_en_i,
 input wire [31:0] set_axi_start_i,set_axi_stop_i,set_axi_dec_i,
 input wire [15:0] set_cyc_cnt_i,cyc_cnt_i,
 output wire [15:0] axi_state_o,output wire axi_last_o,
 output wire [31:0] err_cnt_o,transf_cnt_o);
 assign dac_o=0;assign axi_state_o=0;assign axi_last_o=0;assign err_cnt_o=0;assign transf_cnt_o=0;
endmodule
''')
print('Prepared ASG simulation; only disabled DDR interface replaced')
