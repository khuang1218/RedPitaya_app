// Prepare the dedicated v19 source overlay from the current tested v18 tree.
// Run once from RedPitaya_app; never edits the baseline repository.
const fs = require('fs');
const path = require('path');
const repo = path.resolve(__dirname, '../../../fpgaprj/RedPitaya-FPGA');
const read = p => fs.readFileSync(path.join(repo,p),'utf8').replace(/\r\n/g,'\n');
const save = (p,s) => {const f=path.join(__dirname,p);fs.mkdirSync(path.dirname(f),{recursive:true});fs.writeFileSync(f,s.replace(/\r\n/g,'\n'));};
// Braces protect bit indices from Tcl command substitution in flat XDC.
const braceCollections=s=>s.replace(/\[(get_ports|get_pins) ([^\s{}][^\n]*?)\](?=\s|$)/gm,
  (all,cmd,arg)=>`[${cmd} {${arg.trim().replaceAll('\\\\.','\\.')}}]`);
const top=read('prj/v0.94/rtl/red_pitaya_top_LED7_mod.sv');
// Leave the v18 default intact; only the dedicated v19 top overrides identity.
let regs=read('prj/v0.94/rtl/tdc_registers.sv');
if(!/parameter logic \[7:0\] VERSION/.test(regs)) regs=regs.replace('parameter int unsigned NUM_TAPS = 512,',"parameter logic [7:0] VERSION = 8'd18,\n  parameter int unsigned NUM_TAPS = 512,");
regs=regs.replace(/localparam logic \[31:0\] TDC_ID_VERSION\s*=[^;]+;/,
 "localparam logic [31:0] TDC_ID_VERSION = (VERSION==8'd18 ? 32'h5444_4312 : {24'h544443, VERSION});");
save('prj/v0.94/rtl/tdc_registers.sv',regs);
let tdc=read('prj/v0.94/rtl/tdc_top.sv');
if(!/parameter logic \[7:0\] VERSION/.test(tdc)) tdc=tdc.replace('parameter int unsigned NUM_CARRY4 = 128,',"parameter logic [7:0] VERSION = 8'd18,\n  parameter int unsigned NUM_CARRY4 = 128,");
if(!tdc.includes('.VERSION(VERSION)')) tdc=tdc.replace('tdc_registers #(\n','tdc_registers #(\n    .VERSION(VERSION),\n');
save('prj/v0.94/rtl/tdc_top.sv',tdc);
// Normalize first so section extraction works on both LF and CRLF clones.
const norm=top.replace(/\r\n/g,'\n');
const section=(a,b)=>norm.slice(norm.indexOf(a),norm.indexOf(b,norm.indexOf(a)));
const ports=section('module red_pitaya_top #(','////////////////////////////////////////////////////////////////////////////////\n// local signals');
const clocks=section('IBUFDS i_clk','////////////////////////////////////////////////////////////////////////////////\n//  Connections to PS');
const ps=section('red_pitaya_ps ps (','`ifndef SCOPE_ONLY');
const hk=section('red_pitaya_hk #(.DWE(DWE)) i_hk (','////////////////////////////////////////////////////////////////////////////////\n// LED');
const asg=section('red_pitaya_asg i_asg (','////////////////////////////////////////////////////////////////////////////////\n//  MIMO PID');
// Keep each independently writable waveform table as its own synthesis object.
// The first v19 run decloned the seven chA RAMs into chB (Synth 8-223).
// Isolate these attributes to v19 so rebuilding the qualified v18 is unaffected.
let asg19=read('rtl/classic/red_pitaya_asg.sv')
 .replace('module red_pitaya_asg (','(* KEEP_HIERARCHY="yes" *)\nmodule red_pitaya_asg_v19 (')
 .replaceAll('red_pitaya_asg_ch  #','(* KEEP_HIERARCHY="yes" *) red_pitaya_asg_ch_v19 #');
save('prj/v0.94/rtl/red_pitaya_asg_v19.sv',asg19);
let asgch19=read('rtl/classic/red_pitaya_asg_ch.sv')
 .replace('module red_pitaya_asg_ch #(','(* KEEP_HIERARCHY="yes" *)\nmodule red_pitaya_asg_ch_v19 #(')
 .replace('reg   [  14-1: 0] dac_buf', '(* RAM_STYLE="block", DONT_TOUCH="yes" *) reg [14-1:0] dac_buf')
 .replaceAll('rp_asg_pointer_add','rp_asg_pointer_add_v19');
save('prj/v0.94/rtl/red_pitaya_asg_ch_v19.sv',asgch19);
const dac=section('ODDR oddr_dac_clk','////////////////////////////////////////////////////////////////////////////////\n//  House Keeping');
const pulse=section('  pulse_gen #(.GPIO_INDEX(PULSE_GPIO_INDEX))','`ifndef DISABLE_BNET');
const declarations=`
localparam int GDW=DWE;
localparam int RST_MAX=64;
localparam int PULSE_GPIO_INDEX=1;
localparam int TDC_GPIO_INDEX=2;
logic [3:0] fclk,frstn;
logic adc_clk_in,pll_adc_clk,pll_dac_clk_1x,pll_dac_clk_2x,pll_dac_clk_2p;
logic pll_ser_clk,pll_pwm_clk,pll_locked,pll_locked_r;
logic fpll_locked_r,fpll_locked_r2,fpll_locked_r3,rst_after_locked,rstn_pll;
logic [15:0] rst_cnt='0;
logic adc_clk,adc_rstn,dac_clk_1x,dac_clk_2x,dac_clk_2p,dac_axi_clk,dac_axi_rstn;
logic ser_clk,pwm_clk,pwm_rstn,dac_rst;
logic CAN0_rx,CAN0_tx,CAN1_rx,CAN1_tx,can_on;
logic [1:0] digital_loop;
logic [2:0] daisy_mode;
logic trig_ext,trig_asg_out;
logic signed [1:0][13:0] asg_dat;
logic [13:0] dac_dat_a,dac_dat_b;
logic [DWE-1:0] exp_p_in,exp_n_in,exp_p_out,exp_n_out,exp_p_dir,exp_n_dir;
wire [DWE-1:0] exp_p_otr=exp_p_out,exp_p_dtr=exp_p_dir;
logic [7:0] led_hk;
logic [25:0] fpga_marker_cnt;
logic pulse_pin_data,pulse_pin_dir,pulse_cycle_start;
logic [31:0] pulse_active_period,pulse_sys_rdata;
logic pulse_sys_err,pulse_sys_ack,pulse_sys_wen,pulse_sys_ren;
logic spi_clk,spi_mosi,spi_cs_n,spi_ldac_n;
logic [31:0] spi_rdata;
logic spi_ack,spi_err;
logic [1:0][31:0] tdc_rdata;
logic [1:0] tdc_ack,tdc_err;
wire [3:0] region=sys[7].addr[19:16];
wire select_pulse=region==4'h2;
wire select_tdc0=region==4'h1;
wire select_tdc1=region==4'h3;
wire select_spi=region==4'h4;
logic invalid_ack;
sys_bus_if ps_sys (.clk(fclk[0]),.rstn(frstn[0]));
sys_bus_if sys [7:0] (.clk(adc_clk),.rstn(adc_rstn));
gpio_if #(.DW(3*GDW)) gpio ();
axi_sys_if axi0_sys (.clk(adc_clk),.rstn(adc_rstn));
axi_sys_if axi1_sys (.clk(adc_clk),.rstn(adc_rstn));
axi_sys_if axi2_sys (.clk(dac_axi_clk),.rstn(dac_axi_rstn));
axi_sys_if axi3_sys (.clk(dac_axi_clk),.rstn(dac_axi_rstn));
axi_sys_if asg_axi_a_dummy (.clk(dac_axi_clk),.rstn(dac_axi_rstn));
axi_sys_if asg_axi_b_dummy (.clk(dac_axi_clk),.rstn(dac_axi_rstn));
`;
let ties='';
for(const bus of ['axi0_sys','axi1_sys','axi2_sys','axi3_sys'])
 for(const field of ['waddr','wdata','wsel','wsize','wvalid','wlen','wfixed','raddr','rsel','rsize','rvalid','rlen','rfixed','rrdys']) ties+=`assign ${bus}.${field}='0;\n`;
for(const bus of ['asg_axi_a_dummy','asg_axi_b_dummy'])
 for(const [field,val] of [['werr',0],['wrdy',1],['rdata',0],['rerr',0],['rrdym',1],['rardy',1]])ties+=`assign ${bus}.${field}='${val};\n`;
let tdcs='';
for(let i=0;i<2;i++)tdcs+=`
tdc_top #(.VERSION(8'd19),.NUM_CARRY4(128),.FIFO_DEPTH(256),.INVERT_TAPS(1'b0),.RETURN_DIFF_TERM(1'b1)) i_tdc${i} (
 .clk_i(adc_clk),.rstn_i(adc_rstn),.test_clk_i(fclk[0]),.test_rstn_i(frstn[0]),
 .fast_clk_i(ser_clk),.pulse_cycle_start_i(pulse_cycle_start),.pulse_period_i(pulse_active_period),
 .launch_p_o(exp_e3p_o[${i}]),.launch_n_o(exp_e3n_o[${i}]),
 .return_p_i(exp_e3p_i[${i}]),.return_n_i(exp_e3n_i[${i}]),.return_single_i(exp_p_in[${i+2}]),
 .sys_addr_i(sys[7].addr),.sys_wdata_i(sys[7].wdata),
 .sys_wen_i(sys[7].wen && select_tdc${i}),.sys_ren_i(sys[7].ren && select_tdc${i}),
 .sys_rdata_o(tdc_rdata[${i}]),.sys_ack_o(tdc_ack[${i}]),.sys_err_o(tdc_err[${i}]));
`;
save('prj/v0.94/rtl/red_pitaya_top_v19.sv',`// V19: dual full-feature TDC, two local-table ASGs, pulse, DAC80516 SPI/LDAC.
// Scope/ADC processing, PID, AMS/PWM, BNET and daisy engines are absent.
// PS/MIO, housekeeping and analog sampling clocks remain essential infrastructure.
${ports}${declarations}${clocks}${ps}${ties}
assign CAN0_rx=1'b0;
assign CAN1_rx=1'b0;
assign trig_ext=exp_p_in[0];
assign gpio.i[GDW-1:0]='0;
assign gpio.i[2*GDW-1:GDW]=exp_p_in;
assign gpio.i[3*GDW-1:2*GDW]=exp_n_in;
${hk}
always_ff @(posedge adc_clk) begin
 if(!adc_rstn) fpga_marker_cnt<='0;
 else fpga_marker_cnt<=fpga_marker_cnt+1'b1;
end
assign led_o={fpga_marker_cnt[25],led_hk[6:0]};
assign dac_pwm_o='0;
assign adc_clk_o=2'b10;
assign adc_cdcs_o=1'b1;
// Unused differential outputs are driven through proper differential buffers.
OBUFDS #(.IOSTANDARD("DIFF_HSTL_I_18")) daisy_off[1:0](.I(2'b0),.O(daisy_p_o),.OB(daisy_n_o));
OBUFDS #(.IOSTANDARD("LVDS_25")) e3_off[1:0](.I(2'b0),.O(exp_e3p_o[3:2]),.OB(exp_e3n_o[3:2]));
// Dedicated functions always own their pins, independent of housekeeping writes.
for(genvar g=0;g<DWE;g++) begin: gpios
 if(g==1) begin: pulse_pin
  IOBUF i_iobufp(.IO(exp_p_io[g]),.I(pulse_pin_data),.T(~pulse_pin_dir),.O(exp_p_in[g]));
 end else if(g==2 || g==3 || g==6) begin: dedicated_input
  IOBUF i_iobufp(.IO(exp_p_io[g]),.I(1'b0),.T(1'b1),.O(exp_p_in[g]));
 end else if(g==4) begin: spi_clock
  IOBUF i_iobufp(.IO(exp_p_io[g]),.I(spi_clk),.T(1'b0),.O(exp_p_in[g]));
 end else if(g==5) begin: spi_data
  IOBUF i_iobufp(.IO(exp_p_io[g]),.I(spi_mosi),.T(1'b0),.O(exp_p_in[g]));
 end else if(g==7) begin: spi_select
  IOBUF i_iobufp(.IO(exp_p_io[g]),.I(spi_cs_n),.T(1'b0),.O(exp_p_in[g]));
 end else begin: normal_pin
  IOBUF i_iobufp(.IO(exp_p_io[g]),.I(exp_p_out[g]),.T(~exp_p_dir[g]),.O(exp_p_in[g]));
 end
 if(g==4) begin: dac_load
  IOBUF i_iobufn(.IO(exp_n_io[g]),.I(spi_ldac_n),.T(1'b0),.O(exp_n_in[g]));
 end else begin: normal_negative_pin
  IOBUF i_iobufn(.IO(exp_n_io[g]),.I(exp_n_out[g]),.T(~exp_n_dir[g]),.O(exp_n_in[g]));
 end
end
${asg.replace('red_pitaya_asg i_asg (','red_pitaya_asg_v19 i_asg (')}
always_ff @(posedge dac_clk_1x) begin
 dac_dat_a<={asg_dat[0][13],~asg_dat[0][12:0]};
 dac_dat_b<={asg_dat[1][13],~asg_dat[1][12:0]};
end
${dac}
// Removed register regions return bus errors instead of silently emulating hardware.
for(genvar slot=1;slot<7;slot++) begin: unused_slots
 if(slot!=2) begin: stub
  always_ff @(posedge adc_clk) begin
   if(!adc_rstn) sys[slot].ack<=0;
   else sys[slot].ack<=sys[slot].wen || sys[slot].ren;
  end
  assign sys[slot].err=sys[slot].ack;
  assign sys[slot].rdata=32'b0;
 end
end
${tdcs}
assign pulse_sys_wen=sys[7].wen && select_pulse;
assign pulse_sys_ren=sys[7].ren && select_pulse;
${pulse}
dac80516_spi i_dac_spi(
 .clk_i(adc_clk),.rstn_i(adc_rstn),.miso_i(exp_p_in[6]),
 .sclk_o(spi_clk),.mosi_o(spi_mosi),.cs_n_o(spi_cs_n),.ldac_n_o(spi_ldac_n),
 .sys_addr_i(sys[7].addr),.sys_wdata_i(sys[7].wdata),
 .sys_wen_i(sys[7].wen && select_spi),.sys_ren_i(sys[7].ren && select_spi),
 .sys_rdata_o(spi_rdata),.sys_ack_o(spi_ack),.sys_err_o(spi_err));
always_ff @(posedge adc_clk) begin
 if(!adc_rstn) invalid_ack<=0;
 else invalid_ack<=(sys[7].wen || sys[7].ren) &&
                  !(select_tdc0 || select_tdc1 || select_pulse || select_spi);
end
assign sys[7].rdata=select_tdc0 ? tdc_rdata[0] : select_tdc1 ? tdc_rdata[1] :
                      select_pulse ? pulse_sys_rdata : select_spi ? spi_rdata : 32'b0;
assign sys[7].ack=select_tdc0 ? tdc_ack[0] : select_tdc1 ? tdc_ack[1] :
                      select_pulse ? pulse_sys_ack : select_spi ? spi_ack : invalid_ack;
assign sys[7].err=select_tdc0 ? tdc_err[0] : select_tdc1 ? tdc_err[1] :
                      select_pulse ? pulse_sys_err : select_spi ? spi_err : invalid_ack;
endmodule
`);
// Same narrow asynchronous exceptions and mailbox limits for each independent core.
const xdc=read('prj/v0.94/sdc/tdc_Z20_G2.xdc');
save('prj/v0.94/sdc/tdc_v19.xdc',[0,1].map(i=>xdc.replaceAll('i_tdc/',`i_tdc${i}/`)).join('\n'));
const layout=read('prj/v0.94/sdc/tdc_width_sampler_layout.xdc');
save('prj/v0.94/sdc/tdc_v19_sampler_layout.xdc',[0,1].map(i=>layout.replaceAll('i_tdc/',`i_tdc${i}/`).replaceAll('TDC_WIDTH_',`TDC${i}_WIDTH_`)).join('\n'));
save('prj/v0.94/sdc/pulse_gen_v19.xdc',read('prj/v0.94/sdc/pulse_gen_Z20_G2.xdc'));
// Gen2 compatibility constraints: remove references to the eliminated XADC,
// daisy receive clock, ADC loopback and obsolete absent legacy SPI endpoint.
let board=read('prj/v0.94/sdc/red_pitaya_G2.xdc').split(/\r?\n/).filter(l=>!['i_ams/XADC_inst','spi_done_csff','adc_dat*','create_clock -name e3_3i'].some(s=>l.includes(s))).join('\n');
save('prj/v0.94/sdc/red_pitaya_v19_G2.xdc',braceCollections(board));
// Retain package/electrical assignments, not obsolete clock-pair exclusions.
const pins=read('sdc/red_pitaya.xdc').split('\n').filter(l=>
 !/^\s*(set_false_path|create_clock|set_input_delay)/.test(l)).join('\n');
save('prj/v0.94/sdc/red_pitaya_v19_pins.xdc',braceCollections(pins)+'\ncreate_clock -period 8.000 -name adc_clk [get_ports {adc_clk_i[1]}]\n');
// Adapt the existing byte-verified project-copy importer for the v19 overlay.
let refresh=read('prj/v0.94/scripts/refresh_custom_sources.tcl');
refresh=refresh.replace(/set custom_module_names \{[\s\S]*?\n\}/,'set custom_module_names {pulse_gen.sv dac80516_spi.sv red_pitaya_asg_v19.sv red_pitaya_asg_ch_v19.sv}')
 .replace('set custom_top_name red_pitaya_top_LED7_mod.sv','set custom_top_name red_pitaya_top_v19.sv')
 .replace(/set custom_xdc_names \{[^}]+\}/,'set custom_xdc_names {red_pitaya_v19_pins.xdc red_pitaya_v19_G2.xdc tdc_v19.xdc tdc_v19_sampler_layout.xdc pulse_gen_v19.xdc dac80516_v19.xdc}')
 .replace(/set custom_shared_sources \{[^}]+\}/,'set custom_shared_sources {rtl/sys_bus_cdc.sv rtl/classic/red_pitaya_asg_ch.sv}')
 .replace('foreach custom_name [concat $custom_xdc_names {red_pitaya_G2.xdc}]','foreach custom_name $custom_xdc_names')
 .replace('# Refresh the existing Gen2 board constraint copy as well (single E3 clock).\ncustom_import_copy $custom_constraints [file join $custom_repo prj/v0.94/sdc/red_pitaya_G2.xdc]','')
 .replace(/puts "TDC V18 source:[^\n]+/, 'puts "V19: two TDC19 cores, two local-table ASGs, pulse, DAC80516 SPI and LED7; other engines removed from hardware."');
const disable=`
# Disable old application constraints before installing the complete v19 set.
# Generated IP constraints are scoped to their IP and are not members here.
foreach custom_old [get_files -quiet -of_objects $custom_constraints] {
  set_property used_in_synthesis false $custom_old
  set_property used_in_implementation false $custom_old
}
`;
refresh=refresh.replace('foreach custom_name $custom_xdc_names {\n  set custom_local',disable+'\nforeach custom_name $custom_xdc_names {\n  set custom_local');
// Package/primary-clock constraints must also participate in synthesis.
refresh=refresh.replace('set_property used_in_synthesis false $custom_local','set_property used_in_synthesis [expr {$custom_name eq "red_pitaya_v19_pins.xdc" || $custom_name eq "red_pitaya_v19_G2.xdc"}] $custom_local');
save('prj/v0.94/scripts/refresh_v19_sources.tcl',refresh);
// Same physical audit, four distinct macros with independent absolute locations.
let audit=read('prj/v0.94/scripts/audit_tdc_width_sampler_layout.tcl')
 .replaceAll('tdc_audit_width_sampler_layout','tdc_audit_v19_sampler_layout')
 .replace('# Works on v10 to diagnose displacement, and v11 to check the new macros.',
 '# Audits both v19 channels: separate rising and falling sampler macros.')
 .replace('foreach edge {RISE FALL} hierarchy {i_tdc/i_width/i_carry i_tdc/i_width/i_fall_carry}',
 'foreach edge {CH0_RISE CH0_FALL CH1_RISE CH1_FALL} hierarchy {i_tdc0/i_width/i_carry i_tdc0/i_width/i_fall_carry i_tdc1/i_width/i_carry i_tdc1/i_width/i_fall_carry}')
 .replace('Both sampler chains','All four width sampler chains');
save('prj/v0.94/scripts/audit_v19_sampler_layout.tcl',audit);
console.log('Prepared v19 top, version-parameterized TDC wrappers and constraints.');
