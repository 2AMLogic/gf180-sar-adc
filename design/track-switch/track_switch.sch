v {xschem version=3.4.7 file_version=1.2
* Sample/track switch -- CMOS transmission gate, 4x upsized, with
* dummy-half-switch charge-injection compensation (DR-0007).
*
* DECISION (spec/decision-records/DR-0007-track-switch-topology.md):
* plain transmission gate, NOT bootstrapped. gf180mcu's 3.3 V supply has
* no dead zone (Vthn + |Vthp| well below V_DD, sim/device-characterization
* -report.md Sec 3.2), so the classic reason to bootstrap is absent. The
* nominal 10u/20u geometry (sim/device-switch-ron's own geometry, also the
* placeholder switch inline in design/cdac/cdac_array.sch) measures
* SFDR = 53.8 dB worst-case single-ended (sim/track-switch-thd, corner
* ss_27c_2.97v) -- short of the >= 62 dB spec floor by ~8 dB. Upsizing 4x
* (this schematic) measures 64.8 dB single-ended / 66.0 dB differential
* worst-case -- clears the spec floor with margin; an ideal bootstrap would
* clear it further (76-95 dB) but is NOT chosen because the upsized T-gate
* already meets the target and a real (non-ideal) bootstrap at this supply
* would need either 5/6 V devices or active clamping to keep every
* terminal within V_DD of every other (a boosted node reaches Vin + V_DD,
* up to 6.6 V at full scale -- see the decision record's device-reliability
* section) -- real cost this design does not need to pay.
*
* CHARGE-INJECTION COMPENSATION: MDN/MDP are half-width dummy devices,
* source+drain shorted onto the hold node (vout), gated by the
* COMPLEMENTARY clock phase from the main devices. They address channel
* charge only (not gate-overlap clock feedthrough, which both the main
* and dummy devices inject and this construction does not cancel) --
* sim/track-switch-sampling measures both effects separately with this
* exact topology (branch "tg4dum").
*
* NOT bottom-plate sampling. DR-0006 (CDAC switching scheme) ratifies
* TOP-plate sampling for the MCS/Vcm array, so the delayed-turn-off
* ground-switch charge-injection remedy the prior-art survey lists as
* primary is not available here -- compensation has to come from the
* switch itself, which is why the dummy pair above exists.
*
* One instance samples one side of the differential (or pseudo-
* differential) CDAC array's top plate, replacing the placeholder 10u/20u
* T-gate instantiated inline in design/cdac/cdac_array.sch (samppN/samppP,
* sampnN/sampnP) -- updating that inline placeholder to reference this
* block is left to a follow-up (see DR-0007 Consequences), out of this
* issue's scope.
*
* Evidence: sim/track-switch-thd/ (track-mode SFDR/THD vs topology),
* sim/track-switch-sampling/ (charge injection, settling, droop, and --
* for the alternative considered -- bootstrap terminal-voltage stress).
}
G {}
K {}
V {}
S {}
E {}
C {ipin.sym} -260 -30 0 0 {name=p_vin lab=vin}
C {opin.sym} 320 -30 0 0 {name=p_vout lab=vout}
C {ipin.sym} -260 130 0 0 {name=p_clk lab=clk}
C {ipin.sym} -260 190 0 0 {name=p_clkb lab=clkb}
C {ipin.sym} -260 250 0 0 {name=p_vdd lab=vdd}
C {ipin.sym} -260 310 0 0 {name=p_gnd lab=0}
C {symbols/nfet_03v3.sym} 0 0 0 0 {name=MN L=0.28u W=40u nf=1 m=1}
C {symbols/pfet_03v3.sym} 0 -150 0 0 {name=MP L=0.28u W=80u nf=1 m=1}
C {symbols/nfet_03v3.sym} 200 0 0 0 {name=MDN L=0.28u W=20u nf=1 m=1}
C {symbols/pfet_03v3.sym} 200 -150 0 0 {name=MDP L=0.28u W=40u nf=1 m=1}
C {lab_pin.sym} 20 -30 0 0 {name=l0 lab=vin}
C {lab_pin.sym} -20 0 0 0 {name=l1 lab=clk}
C {lab_pin.sym} 20 30 0 0 {name=l2 lab=vout}
C {lab_pin.sym} 20 0 0 0 {name=l3 lab=0}
C {lab_pin.sym} 20 -120 0 0 {name=l4 lab=vin}
C {lab_pin.sym} -20 -150 0 0 {name=l5 lab=clkb}
C {lab_pin.sym} 20 -180 0 0 {name=l6 lab=vout}
C {lab_pin.sym} 20 -150 0 0 {name=l7 lab=vdd}
C {lab_pin.sym} 220 -30 0 0 {name=l8 lab=vout}
C {lab_pin.sym} 180 0 0 0 {name=l9 lab=clkb}
C {lab_pin.sym} 220 30 0 0 {name=l10 lab=vout}
C {lab_pin.sym} 220 0 0 0 {name=l11 lab=0}
C {lab_pin.sym} 220 -120 0 0 {name=l12 lab=vout}
C {lab_pin.sym} 180 -150 0 0 {name=l13 lab=clk}
C {lab_pin.sym} 220 -180 0 0 {name=l14 lab=vout}
C {lab_pin.sym} 220 -150 0 0 {name=l15 lab=vdd}
C {lab_pin.sym} -260 -30 0 0 {name=l16 lab=vin}
C {lab_pin.sym} 320 -30 0 0 {name=l17 lab=vout}
C {lab_pin.sym} -260 130 0 0 {name=l18 lab=clk}
C {lab_pin.sym} -260 190 0 0 {name=l19 lab=clkb}
C {lab_pin.sym} -260 250 0 0 {name=l20 lab=vdd}
C {lab_pin.sym} -260 310 0 0 {name=l21 lab=0}
T {main NMOS, W=40u -- 4x sim/device-switch-ron geometry, gate=clk, body=0} -20 60 0 0 0.2 0.2 {}
T {main PMOS, W=80u, gate=clkb, body=vdd} -20 -240 0 0 0.2 0.2 {}
T {dummy half-NMOS, W=20u, D=S=vout, gate=clkb (complementary phase)} 180 60 0 0 0.2 0.2 {}
T {dummy half-PMOS, W=40u, D=S=vout, gate=clk (complementary phase)} 180 -240 0 0 0.2 0.2 {}
T {Sample/track switch -- T-gate 40u/80u + dummy charge-injection compensation (DR-0007)} -260 -400 0 0 0.3 0.3 {}
}
