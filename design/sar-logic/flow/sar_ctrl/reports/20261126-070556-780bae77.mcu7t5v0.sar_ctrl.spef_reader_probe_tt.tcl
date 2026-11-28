set pdk_root $env(OPENROAD_PDK_ROOT)
set pdk $env(OPENROAD_PDK)
read_lef $pdk_root/$pdk/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
read_lef $pdk_root/$pdk/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef
read_def layout/adc-top/sar_ctrl/sar_ctrl.def
read_liberty $pdk_root/$pdk/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
set_cmd_units -time ns -capacitance fF
create_clock -name clk -period 62.5 [get_ports clk]
read_spef design/sar-logic/flow/sar_ctrl/reports/20261104-212437-9cde5a64.mcu7t5v0.sar_ctrl.spef
puts "===PROBE_PARASITIC_ANNOTATION_BEGIN==="
report_parasitic_annotation -report_unannotated
puts "===PROBE_PARASITIC_ANNOTATION_END==="
puts "===PROBE_REPORT_NET_BEGIN==="
foreach p {_211_/Q _212_/Q _213_/Q _214_/Q _215_/Q _216_/Q _217_/Q _218_/Q _219_/Q _220_/Q _245_/Q} {
  report_net [get_full_name [get_nets -of_objects [get_pins $p]]]
}
puts "===PROBE_REPORT_NET_END==="
