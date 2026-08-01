v {xschem version=3.4.7 file_version=1.2
* CDAC array (MCS / Vcm-based switching scheme, DR-0011).
* Representative schematic: shows the two structurally-worst/
* boundary bit positions per side (weight=256, the sub-array's
* own MSB and the worst settling case per
* sim/cdac-bit-settling/, and weight=1, the LSB) plus each side's
* terminating dummy unit and its input sampling switch.
* The 7 omitted weighted positions (128,64,32,16,8,4,2) are
* IDENTICAL copies of the bit-cell pattern shown (cap + release/
* hi/lo T-gates), differing only in the cap's m= (weight)
* parameter and their own per-bit SEL_HI/SEL_LO control pins --
* see spec/decision-records/DR-0011-cdac-switching-scheme.md and
* spec/cdac-sizing-memo.md Sec 4 for the full 9-bit-per-side
* array this generalizes to. SAR decision logic driving
* SEL_HI/SEL_LO/REL/SAMP is issue #11's scope, not this one's.
*
* MODE-DEPENDENT CONTROL (DR-0011 Decision): the two sides' cells
* are separately controlled on purpose. In DIFFERENTIAL mode the
* weight-w cells on both sides switch together each trial (one to
* VREF, its mirror to GND). In SINGLE-ENDED mode only the side
* that sampled Vin switches; every cell on the Vcm-pinned side
* stays released to Vcm for the whole conversion. Driving both
* sides single-ended would double every step and cost a bit of
* resolution. rel_n/rel_p are drawn here as one shared pair for
* drawing economy across this two-cell excerpt; the real array
* needs REL decoded per weight (and, single-ended, per side).
}
G {}
K {}
V {}
S {}
E {}
C {lab_pin.sym} 0 -30 0 0 {name=l0 lab=top_p}
C {lab_pin.sym} 0 30 0 0 {name=l1 lab=p256_bot}
C {lab_pin.sym} 220 -180 0 0 {name=l2 lab=vcm}
C {lab_pin.sym} 220 -120 0 0 {name=l3 lab=p256_bot}
C {lab_pin.sym} 180 -150 0 0 {name=l4 lab=rel_n}
C {lab_pin.sym} 220 -150 0 0 {name=l5 lab=0}
C {lab_pin.sym} 340 -120 0 0 {name=l6 lab=vcm}
C {lab_pin.sym} 340 -180 0 0 {name=l7 lab=p256_bot}
C {lab_pin.sym} 300 -150 0 0 {name=l8 lab=rel_p}
C {lab_pin.sym} 340 -150 0 0 {name=l9 lab=vdd}
C {lab_pin.sym} 220 -30 0 0 {name=l10 lab=vref}
C {lab_pin.sym} 220 30 0 0 {name=l11 lab=p256_bot}
C {lab_pin.sym} 180 0 0 0 {name=l12 lab=sel_hi_n_256p}
C {lab_pin.sym} 220 0 0 0 {name=l13 lab=0}
C {lab_pin.sym} 340 30 0 0 {name=l14 lab=vref}
C {lab_pin.sym} 340 -30 0 0 {name=l15 lab=p256_bot}
C {lab_pin.sym} 300 0 0 0 {name=l16 lab=sel_hi_p_256p}
C {lab_pin.sym} 340 0 0 0 {name=l17 lab=vdd}
C {lab_pin.sym} 220 120 0 0 {name=l18 lab=0}
C {lab_pin.sym} 220 180 0 0 {name=l19 lab=p256_bot}
C {lab_pin.sym} 180 150 0 0 {name=l20 lab=sel_lo_n_256p}
C {lab_pin.sym} 220 150 0 0 {name=l21 lab=0}
C {lab_pin.sym} 340 180 0 0 {name=l22 lab=0}
C {lab_pin.sym} 340 120 0 0 {name=l23 lab=p256_bot}
C {lab_pin.sym} 300 150 0 0 {name=l24 lab=sel_lo_p_256p}
C {lab_pin.sym} 340 150 0 0 {name=l25 lab=vdd}
C {lab_pin.sym} 0 670 0 0 {name=l26 lab=top_p}
C {lab_pin.sym} 0 730 0 0 {name=l27 lab=p1_bot}
C {lab_pin.sym} 220 520 0 0 {name=l28 lab=vcm}
C {lab_pin.sym} 220 580 0 0 {name=l29 lab=p1_bot}
C {lab_pin.sym} 180 550 0 0 {name=l30 lab=rel_n}
C {lab_pin.sym} 220 550 0 0 {name=l31 lab=0}
C {lab_pin.sym} 340 580 0 0 {name=l32 lab=vcm}
C {lab_pin.sym} 340 520 0 0 {name=l33 lab=p1_bot}
C {lab_pin.sym} 300 550 0 0 {name=l34 lab=rel_p}
C {lab_pin.sym} 340 550 0 0 {name=l35 lab=vdd}
C {lab_pin.sym} 220 670 0 0 {name=l36 lab=vref}
C {lab_pin.sym} 220 730 0 0 {name=l37 lab=p1_bot}
C {lab_pin.sym} 180 700 0 0 {name=l38 lab=sel_hi_n_1p}
C {lab_pin.sym} 220 700 0 0 {name=l39 lab=0}
C {lab_pin.sym} 340 730 0 0 {name=l40 lab=vref}
C {lab_pin.sym} 340 670 0 0 {name=l41 lab=p1_bot}
C {lab_pin.sym} 300 700 0 0 {name=l42 lab=sel_hi_p_1p}
C {lab_pin.sym} 340 700 0 0 {name=l43 lab=vdd}
C {lab_pin.sym} 220 820 0 0 {name=l44 lab=0}
C {lab_pin.sym} 220 880 0 0 {name=l45 lab=p1_bot}
C {lab_pin.sym} 180 850 0 0 {name=l46 lab=sel_lo_n_1p}
C {lab_pin.sym} 220 850 0 0 {name=l47 lab=0}
C {lab_pin.sym} 340 880 0 0 {name=l48 lab=0}
C {lab_pin.sym} 340 820 0 0 {name=l49 lab=p1_bot}
C {lab_pin.sym} 300 850 0 0 {name=l50 lab=sel_lo_p_1p}
C {lab_pin.sym} 340 850 0 0 {name=l51 lab=vdd}
C {lab_pin.sym} 0 1370 0 0 {name=l52 lab=top_p}
C {lab_pin.sym} 0 1430 0 0 {name=l53 lab=vcm}
C {lab_pin.sym} 20 2070 0 0 {name=l54 lab=vinp}
C {lab_pin.sym} 20 2130 0 0 {name=l55 lab=top_p}
C {lab_pin.sym} -20 2100 0 0 {name=l56 lab=samp_n}
C {lab_pin.sym} 20 2100 0 0 {name=l57 lab=0}
C {lab_pin.sym} 140 2130 0 0 {name=l58 lab=vinp}
C {lab_pin.sym} 140 2070 0 0 {name=l59 lab=top_p}
C {lab_pin.sym} 100 2100 0 0 {name=l60 lab=samp_p}
C {lab_pin.sym} 140 2100 0 0 {name=l61 lab=vdd}
C {lab_pin.sym} 900 -30 0 0 {name=l62 lab=top_n}
C {lab_pin.sym} 900 30 0 0 {name=l63 lab=n256_bot}
C {lab_pin.sym} 1120 -180 0 0 {name=l64 lab=vcm}
C {lab_pin.sym} 1120 -120 0 0 {name=l65 lab=n256_bot}
C {lab_pin.sym} 1080 -150 0 0 {name=l66 lab=rel_n}
C {lab_pin.sym} 1120 -150 0 0 {name=l67 lab=0}
C {lab_pin.sym} 1240 -120 0 0 {name=l68 lab=vcm}
C {lab_pin.sym} 1240 -180 0 0 {name=l69 lab=n256_bot}
C {lab_pin.sym} 1200 -150 0 0 {name=l70 lab=rel_p}
C {lab_pin.sym} 1240 -150 0 0 {name=l71 lab=vdd}
C {lab_pin.sym} 1120 -30 0 0 {name=l72 lab=vref}
C {lab_pin.sym} 1120 30 0 0 {name=l73 lab=n256_bot}
C {lab_pin.sym} 1080 0 0 0 {name=l74 lab=sel_hi_n_256n}
C {lab_pin.sym} 1120 0 0 0 {name=l75 lab=0}
C {lab_pin.sym} 1240 30 0 0 {name=l76 lab=vref}
C {lab_pin.sym} 1240 -30 0 0 {name=l77 lab=n256_bot}
C {lab_pin.sym} 1200 0 0 0 {name=l78 lab=sel_hi_p_256n}
C {lab_pin.sym} 1240 0 0 0 {name=l79 lab=vdd}
C {lab_pin.sym} 1120 120 0 0 {name=l80 lab=0}
C {lab_pin.sym} 1120 180 0 0 {name=l81 lab=n256_bot}
C {lab_pin.sym} 1080 150 0 0 {name=l82 lab=sel_lo_n_256n}
C {lab_pin.sym} 1120 150 0 0 {name=l83 lab=0}
C {lab_pin.sym} 1240 180 0 0 {name=l84 lab=0}
C {lab_pin.sym} 1240 120 0 0 {name=l85 lab=n256_bot}
C {lab_pin.sym} 1200 150 0 0 {name=l86 lab=sel_lo_p_256n}
C {lab_pin.sym} 1240 150 0 0 {name=l87 lab=vdd}
C {lab_pin.sym} 900 670 0 0 {name=l88 lab=top_n}
C {lab_pin.sym} 900 730 0 0 {name=l89 lab=n1_bot}
C {lab_pin.sym} 1120 520 0 0 {name=l90 lab=vcm}
C {lab_pin.sym} 1120 580 0 0 {name=l91 lab=n1_bot}
C {lab_pin.sym} 1080 550 0 0 {name=l92 lab=rel_n}
C {lab_pin.sym} 1120 550 0 0 {name=l93 lab=0}
C {lab_pin.sym} 1240 580 0 0 {name=l94 lab=vcm}
C {lab_pin.sym} 1240 520 0 0 {name=l95 lab=n1_bot}
C {lab_pin.sym} 1200 550 0 0 {name=l96 lab=rel_p}
C {lab_pin.sym} 1240 550 0 0 {name=l97 lab=vdd}
C {lab_pin.sym} 1120 670 0 0 {name=l98 lab=vref}
C {lab_pin.sym} 1120 730 0 0 {name=l99 lab=n1_bot}
C {lab_pin.sym} 1080 700 0 0 {name=l100 lab=sel_hi_n_1n}
C {lab_pin.sym} 1120 700 0 0 {name=l101 lab=0}
C {lab_pin.sym} 1240 730 0 0 {name=l102 lab=vref}
C {lab_pin.sym} 1240 670 0 0 {name=l103 lab=n1_bot}
C {lab_pin.sym} 1200 700 0 0 {name=l104 lab=sel_hi_p_1n}
C {lab_pin.sym} 1240 700 0 0 {name=l105 lab=vdd}
C {lab_pin.sym} 1120 820 0 0 {name=l106 lab=0}
C {lab_pin.sym} 1120 880 0 0 {name=l107 lab=n1_bot}
C {lab_pin.sym} 1080 850 0 0 {name=l108 lab=sel_lo_n_1n}
C {lab_pin.sym} 1120 850 0 0 {name=l109 lab=0}
C {lab_pin.sym} 1240 880 0 0 {name=l110 lab=0}
C {lab_pin.sym} 1240 820 0 0 {name=l111 lab=n1_bot}
C {lab_pin.sym} 1200 850 0 0 {name=l112 lab=sel_lo_p_1n}
C {lab_pin.sym} 1240 850 0 0 {name=l113 lab=vdd}
C {lab_pin.sym} 900 1370 0 0 {name=l114 lab=top_n}
C {lab_pin.sym} 900 1430 0 0 {name=l115 lab=vcm}
C {lab_pin.sym} 920 2070 0 0 {name=l116 lab=vinn}
C {lab_pin.sym} 920 2130 0 0 {name=l117 lab=top_n}
C {lab_pin.sym} 880 2100 0 0 {name=l118 lab=samp_n}
C {lab_pin.sym} 920 2100 0 0 {name=l119 lab=0}
C {lab_pin.sym} 1040 2130 0 0 {name=l120 lab=vinn}
C {lab_pin.sym} 1040 2070 0 0 {name=l121 lab=top_n}
C {lab_pin.sym} 1000 2100 0 0 {name=l122 lab=samp_p}
C {lab_pin.sym} 1040 2100 0 0 {name=l123 lab=vdd}
C {symbols/cap_mim_2f0fF.sym} 0 0 0 0 {name=Cp256 W=2.71u L=2.71u model=cap_mim_2f0fF m=256}
C {symbols/nfet_03v3.sym} 200 -150 0 0 {name=p256relN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 320 -150 0 0 {name=p256relP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 200 0 0 0 {name=p256hiN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 320 0 0 0 {name=p256hiP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 200 150 0 0 {name=p256loN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 320 150 0 0 {name=p256loP L=0.28u W=20u nf=1 m=1}
C {symbols/cap_mim_2f0fF.sym} 0 700 0 0 {name=Cp1 W=2.71u L=2.71u model=cap_mim_2f0fF m=1}
C {symbols/nfet_03v3.sym} 200 550 0 0 {name=p1relN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 320 550 0 0 {name=p1relP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 200 700 0 0 {name=p1hiN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 320 700 0 0 {name=p1hiP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 200 850 0 0 {name=p1loN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 320 850 0 0 {name=p1loP L=0.28u W=20u nf=1 m=1}
C {symbols/cap_mim_2f0fF.sym} 0 1400 0 0 {name=Cpdum W=2.71u L=2.71u model=cap_mim_2f0fF m=1}
C {symbols/nfet_03v3.sym} 0 2100 0 0 {name=samppN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 120 2100 0 0 {name=samppP L=0.28u W=20u nf=1 m=1}
C {symbols/cap_mim_2f0fF.sym} 900 0 0 0 {name=Cn256 W=2.71u L=2.71u model=cap_mim_2f0fF m=256}
C {symbols/nfet_03v3.sym} 1100 -150 0 0 {name=n256relN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 1220 -150 0 0 {name=n256relP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 1100 0 0 0 {name=n256hiN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 1220 0 0 0 {name=n256hiP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 1100 150 0 0 {name=n256loN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 1220 150 0 0 {name=n256loP L=0.28u W=20u nf=1 m=1}
C {symbols/cap_mim_2f0fF.sym} 900 700 0 0 {name=Cn1 W=2.71u L=2.71u model=cap_mim_2f0fF m=1}
C {symbols/nfet_03v3.sym} 1100 550 0 0 {name=n1relN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 1220 550 0 0 {name=n1relP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 1100 700 0 0 {name=n1hiN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 1220 700 0 0 {name=n1hiP L=0.28u W=20u nf=1 m=1}
C {symbols/nfet_03v3.sym} 1100 850 0 0 {name=n1loN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 1220 850 0 0 {name=n1loP L=0.28u W=20u nf=1 m=1}
C {symbols/cap_mim_2f0fF.sym} 900 1400 0 0 {name=Cndum W=2.71u L=2.71u model=cap_mim_2f0fF m=1}
C {symbols/nfet_03v3.sym} 900 2100 0 0 {name=sampnN L=0.28u W=10u nf=1 m=1}
C {symbols/pfet_03v3.sym} 1020 2100 0 0 {name=sampnP L=0.28u W=20u nf=1 m=1}
C {ipin.sym} 0 2500 0 0 {name=p_vinp lab=vinp}
C {ipin.sym} 120 2500 0 0 {name=p_vinn lab=vinn}
C {ipin.sym} 240 2500 0 0 {name=p_vdd lab=vdd}
C {ipin.sym} 360 2500 0 0 {name=p_vref lab=vref}
C {ipin.sym} 480 2500 0 0 {name=p_vcm lab=vcm}
C {ipin.sym} 600 2500 0 0 {name=p_rel_n lab=rel_n}
C {ipin.sym} 720 2500 0 0 {name=p_rel_p lab=rel_p}
C {ipin.sym} 840 2500 0 0 {name=p_samp_n lab=samp_n}
C {ipin.sym} 960 2500 0 0 {name=p_samp_p lab=samp_p}
C {ipin.sym} 0 2600 0 0 {name=p_sel_hi_n_256p lab=sel_hi_n_256p}
C {ipin.sym} 120 2600 0 0 {name=p_sel_hi_p_256p lab=sel_hi_p_256p}
C {ipin.sym} 240 2600 0 0 {name=p_sel_lo_n_256p lab=sel_lo_n_256p}
C {ipin.sym} 360 2600 0 0 {name=p_sel_lo_p_256p lab=sel_lo_p_256p}
C {ipin.sym} 480 2600 0 0 {name=p_sel_hi_n_1p lab=sel_hi_n_1p}
C {ipin.sym} 600 2600 0 0 {name=p_sel_hi_p_1p lab=sel_hi_p_1p}
C {ipin.sym} 720 2600 0 0 {name=p_sel_lo_n_1p lab=sel_lo_n_1p}
C {ipin.sym} 840 2600 0 0 {name=p_sel_lo_p_1p lab=sel_lo_p_1p}
C {ipin.sym} 0 2700 0 0 {name=p_sel_hi_n_256n lab=sel_hi_n_256n}
C {ipin.sym} 120 2700 0 0 {name=p_sel_hi_p_256n lab=sel_hi_p_256n}
C {ipin.sym} 240 2700 0 0 {name=p_sel_lo_n_256n lab=sel_lo_n_256n}
C {ipin.sym} 360 2700 0 0 {name=p_sel_lo_p_256n lab=sel_lo_p_256n}
C {ipin.sym} 480 2700 0 0 {name=p_sel_hi_n_1n lab=sel_hi_n_1n}
C {ipin.sym} 600 2700 0 0 {name=p_sel_hi_p_1n lab=sel_hi_p_1n}
C {ipin.sym} 720 2700 0 0 {name=p_sel_lo_n_1n lab=sel_lo_n_1n}
C {ipin.sym} 840 2700 0 0 {name=p_sel_lo_p_1n lab=sel_lo_p_1n}
C {opin.sym} -200 0 0 0 {name=p_top_p lab=top_p}
C {opin.sym} 700 0 0 0 {name=p_top_n lab=top_n}
T {weight=256} -60 -45 0 0 0.2 0.2 {}
T {weight=1} -60 655 0 0 0.2 0.2 {}
T {dummy, weight=1, fixed to Vcm} -60 1355 0 0 0.2 0.2 {}
T {weight=256} 840 -45 0 0 0.2 0.2 {}
T {weight=1} 840 655 0 0 0.2 0.2 {}
T {dummy, weight=1, fixed to Vcm} 840 1355 0 0 0.2 0.2 {}

