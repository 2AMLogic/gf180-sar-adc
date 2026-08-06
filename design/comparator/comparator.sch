v {xschem version=3.4.7 file_version=1.2
* Comparator: static preamplifier -> StrongARM latch -> isolation
* inverters -> NOR SR output latch.  Topology, sizing and offset-
* cancellation tier are ratified in
* spec/decision-records/DR-0015-comparator-topology.md; the derivation
* is spec/comparator-budget-memo.md.
*
* THE SIMULATION SOURCE OF TRUTH IS design/comparator/comparator.spice,
* NOT THIS FILE.  The corner runner consumes self-contained netlist
* fragments with no `.include` (sim/harness/README.md), so every
* testbench embeds a verbatim copy of that file's device block, and
* sim/tests/test_comparator_netlist.py fails if any copy drifts.  This
* schematic is the drawn view of the same circuit, and
* sim/tests/test_comparator_schematic.py fails if ITS device inventory
* (instance name, model, W, L, and every net connection) differs from
* the .spice file's -- so the two views cannot silently disagree even
* though neither is generated from the other.
*
* Connectivity is expressed with net labels rather than drawn wires,
* the same convention design/cdac/cdac_array.sch uses: one lab_pin per
* device terminal, placed at that terminal.  It keeps a 29-device
* schematic readable as a device list and keeps the file diffable.
*
* THE ISOLATION INVERTERS (Msp/Msn, Mrp2/Mrn2) ARE NOT DECORATION.
* Wiring a NAND SR latch straight to outp/outn was built first and
* measured ~10 mV (3 LSB) of hysteresis, because the SR latch's held
* state loads the two regeneration nodes asymmetrically.  See the
* comment in design/comparator/comparator.spice and DR-0007.
*
* Bias generation is out of scope (DR-0007): ibias is a pin, and the
* contract is 10 uA INTO it.  The block's own static draw is ~20 uA,
* because Mb sinks the forced bias while Mt mirrors it.
}
G {}
K {}
V {}
S {}
E {}
T {static preamplifier (40/1 input pair, 150 kohm poly loads, 10 uA tail)} -40 -90 0 0 0.4 0.4 {}
C {symbols/nfet_03v3.sym} 0 0 0 0 {name=Mb L=2u W=20u nf=1 m=1}
C {lab_pin.sym} 20 -30 0 0 {name=l1 lab=ibias}
C {lab_pin.sym} -20 0 0 0 {name=l2 lab=ibias}
C {lab_pin.sym} 20 30 0 0 {name=l3 lab=0}
C {lab_pin.sym} 20 0 0 0 {name=l4 lab=0}
C {symbols/nfet_03v3.sym} 200 0 0 0 {name=Mt L=2u W=20u nf=1 m=1}
C {lab_pin.sym} 220 -30 0 0 {name=l5 lab=ptail}
C {lab_pin.sym} 180 0 0 0 {name=l6 lab=ibias}
C {lab_pin.sym} 220 30 0 0 {name=l7 lab=0}
C {lab_pin.sym} 220 0 0 0 {name=l8 lab=0}
C {symbols/nfet_03v3.sym} 400 0 0 0 {name=Mip L=1u W=40u nf=1 m=1}
C {lab_pin.sym} 420 -30 0 0 {name=l9 lab=pon}
C {lab_pin.sym} 380 0 0 0 {name=l10 lab=vinp}
C {lab_pin.sym} 420 30 0 0 {name=l11 lab=ptail}
C {lab_pin.sym} 420 0 0 0 {name=l12 lab=0}
C {symbols/nfet_03v3.sym} 600 0 0 0 {name=Min L=1u W=40u nf=1 m=1}
C {lab_pin.sym} 620 -30 0 0 {name=l13 lab=pop}
C {lab_pin.sym} 580 0 0 0 {name=l14 lab=vinn}
C {lab_pin.sym} 620 30 0 0 {name=l15 lab=ptail}
C {lab_pin.sym} 620 0 0 0 {name=l16 lab=0}
C {symbols/ppolyf_u_1k.sym} 800 0 0 0 {name=Rlp W=1u L=150u model=ppolyf_u_1k spiceprefix=X m=1}
C {lab_pin.sym} 800 -30 0 0 {name=l17 lab=vdd}
C {lab_pin.sym} 800 30 0 0 {name=l18 lab=pop}
C {lab_pin.sym} 780 0 0 0 {name=l19 lab=0}
C {symbols/ppolyf_u_1k.sym} 1000 0 0 0 {name=Rln W=1u L=150u model=ppolyf_u_1k spiceprefix=X m=1}
C {lab_pin.sym} 1000 -30 0 0 {name=l20 lab=vdd}
C {lab_pin.sym} 1000 30 0 0 {name=l21 lab=pon}
C {lab_pin.sym} 980 0 0 0 {name=l22 lab=0}
T {StrongARM latch (8/0.5 input pair, single clock phase)} -40 210 0 0 0.4 0.4 {}
C {symbols/nfet_03v3.sym} 0 300 0 0 {name=Mlt L=0.35u W=16u nf=1 m=1}
C {lab_pin.sym} 20 270 0 0 {name=l23 lab=ltail}
C {lab_pin.sym} -20 300 0 0 {name=l24 lab=clk}
C {lab_pin.sym} 20 330 0 0 {name=l25 lab=0}
C {lab_pin.sym} 20 300 0 0 {name=l26 lab=0}
C {symbols/nfet_03v3.sym} 200 300 0 0 {name=Mlp L=0.5u W=8u nf=1 m=1}
C {lab_pin.sym} 220 270 0 0 {name=l27 lab=dip}
C {lab_pin.sym} 180 300 0 0 {name=l28 lab=pop}
C {lab_pin.sym} 220 330 0 0 {name=l29 lab=ltail}
C {lab_pin.sym} 220 300 0 0 {name=l30 lab=0}
C {symbols/nfet_03v3.sym} 400 300 0 0 {name=Mln L=0.5u W=8u nf=1 m=1}
C {lab_pin.sym} 420 270 0 0 {name=l31 lab=din}
C {lab_pin.sym} 380 300 0 0 {name=l32 lab=pon}
C {lab_pin.sym} 420 330 0 0 {name=l33 lab=ltail}
C {lab_pin.sym} 420 300 0 0 {name=l34 lab=0}
C {symbols/nfet_03v3.sym} 600 300 0 0 {name=Mnp L=0.35u W=6u nf=1 m=1}
C {lab_pin.sym} 620 270 0 0 {name=l35 lab=outn}
C {lab_pin.sym} 580 300 0 0 {name=l36 lab=outp}
C {lab_pin.sym} 620 330 0 0 {name=l37 lab=dip}
C {lab_pin.sym} 620 300 0 0 {name=l38 lab=0}
C {symbols/nfet_03v3.sym} 800 300 0 0 {name=Mnn L=0.35u W=6u nf=1 m=1}
C {lab_pin.sym} 820 270 0 0 {name=l39 lab=outp}
C {lab_pin.sym} 780 300 0 0 {name=l40 lab=outn}
C {lab_pin.sym} 820 330 0 0 {name=l41 lab=din}
C {lab_pin.sym} 820 300 0 0 {name=l42 lab=0}
C {symbols/pfet_03v3.sym} 1000 300 0 0 {name=Mpp L=0.35u W=8u nf=1 m=1}
C {lab_pin.sym} 1020 330 0 0 {name=l43 lab=outn}
C {lab_pin.sym} 980 300 0 0 {name=l44 lab=outp}
C {lab_pin.sym} 1020 270 0 0 {name=l45 lab=vdd}
C {lab_pin.sym} 1020 300 0 0 {name=l46 lab=vdd}
C {symbols/pfet_03v3.sym} 0 460 0 0 {name=Mpn L=0.35u W=8u nf=1 m=1}
C {lab_pin.sym} 20 490 0 0 {name=l47 lab=outp}
C {lab_pin.sym} -20 460 0 0 {name=l48 lab=outn}
C {lab_pin.sym} 20 430 0 0 {name=l49 lab=vdd}
C {lab_pin.sym} 20 460 0 0 {name=l50 lab=vdd}
C {symbols/pfet_03v3.sym} 200 460 0 0 {name=Mrp L=0.35u W=4u nf=1 m=1}
C {lab_pin.sym} 220 490 0 0 {name=l51 lab=outn}
C {lab_pin.sym} 180 460 0 0 {name=l52 lab=clk}
C {lab_pin.sym} 220 430 0 0 {name=l53 lab=vdd}
C {lab_pin.sym} 220 460 0 0 {name=l54 lab=vdd}
C {symbols/pfet_03v3.sym} 400 460 0 0 {name=Mrn L=0.35u W=4u nf=1 m=1}
C {lab_pin.sym} 420 490 0 0 {name=l55 lab=outp}
C {lab_pin.sym} 380 460 0 0 {name=l56 lab=clk}
C {lab_pin.sym} 420 430 0 0 {name=l57 lab=vdd}
C {lab_pin.sym} 420 460 0 0 {name=l58 lab=vdd}
C {symbols/pfet_03v3.sym} 600 460 0 0 {name=Mrd L=0.35u W=2u nf=1 m=1}
C {lab_pin.sym} 620 490 0 0 {name=l59 lab=dip}
C {lab_pin.sym} 580 460 0 0 {name=l60 lab=clk}
C {lab_pin.sym} 620 430 0 0 {name=l61 lab=vdd}
C {lab_pin.sym} 620 460 0 0 {name=l62 lab=vdd}
C {symbols/pfet_03v3.sym} 800 460 0 0 {name=Mre L=0.35u W=2u nf=1 m=1}
C {lab_pin.sym} 820 490 0 0 {name=l63 lab=din}
C {lab_pin.sym} 780 460 0 0 {name=l64 lab=clk}
C {lab_pin.sym} 820 430 0 0 {name=l65 lab=vdd}
C {lab_pin.sym} 820 460 0 0 {name=l66 lab=vdd}
T {isolation inverters -- remove the SR latch's asymmetric load on outp/outn} -40 670 0 0 0.4 0.4 {}
C {symbols/pfet_03v3.sym} 0 760 0 0 {name=Msp L=0.35u W=2u nf=1 m=1}
C {lab_pin.sym} 20 790 0 0 {name=l67 lab=sset}
C {lab_pin.sym} -20 760 0 0 {name=l68 lab=outn}
C {lab_pin.sym} 20 730 0 0 {name=l69 lab=vdd}
C {lab_pin.sym} 20 760 0 0 {name=l70 lab=vdd}
C {symbols/nfet_03v3.sym} 200 760 0 0 {name=Msn L=0.35u W=1u nf=1 m=1}
C {lab_pin.sym} 220 730 0 0 {name=l71 lab=sset}
C {lab_pin.sym} 180 760 0 0 {name=l72 lab=outn}
C {lab_pin.sym} 220 790 0 0 {name=l73 lab=0}
C {lab_pin.sym} 220 760 0 0 {name=l74 lab=0}
C {symbols/pfet_03v3.sym} 400 760 0 0 {name=Mrp2 L=0.35u W=2u nf=1 m=1}
C {lab_pin.sym} 420 790 0 0 {name=l75 lab=srst}
C {lab_pin.sym} 380 760 0 0 {name=l76 lab=outp}
C {lab_pin.sym} 420 730 0 0 {name=l77 lab=vdd}
C {lab_pin.sym} 420 760 0 0 {name=l78 lab=vdd}
C {symbols/nfet_03v3.sym} 600 760 0 0 {name=Mrn2 L=0.35u W=1u nf=1 m=1}
C {lab_pin.sym} 620 730 0 0 {name=l79 lab=srst}
C {lab_pin.sym} 580 760 0 0 {name=l80 lab=outp}
C {lab_pin.sym} 620 790 0 0 {name=l81 lab=0}
C {lab_pin.sym} 620 760 0 0 {name=l82 lab=0}
T {NOR SR output latch -- holds the decision through the next reset} -40 970 0 0 0.4 0.4 {}
C {symbols/pfet_03v3.sym} 0 1060 0 0 {name=Mq1 L=0.35u W=8u nf=1 m=1}
C {lab_pin.sym} 20 1090 0 0 {name=l83 lab=ps1}
C {lab_pin.sym} -20 1060 0 0 {name=l84 lab=srst}
C {lab_pin.sym} 20 1030 0 0 {name=l85 lab=vdd}
C {lab_pin.sym} 20 1060 0 0 {name=l86 lab=vdd}
C {symbols/pfet_03v3.sym} 200 1060 0 0 {name=Mq2 L=0.35u W=8u nf=1 m=1}
C {lab_pin.sym} 220 1090 0 0 {name=l87 lab=dout}
C {lab_pin.sym} 180 1060 0 0 {name=l88 lab=doutb}
C {lab_pin.sym} 220 1030 0 0 {name=l89 lab=ps1}
C {lab_pin.sym} 220 1060 0 0 {name=l90 lab=vdd}
C {symbols/nfet_03v3.sym} 400 1060 0 0 {name=Mq3 L=0.35u W=4u nf=1 m=1}
C {lab_pin.sym} 420 1030 0 0 {name=l91 lab=dout}
C {lab_pin.sym} 380 1060 0 0 {name=l92 lab=srst}
C {lab_pin.sym} 420 1090 0 0 {name=l93 lab=0}
C {lab_pin.sym} 420 1060 0 0 {name=l94 lab=0}
C {symbols/nfet_03v3.sym} 600 1060 0 0 {name=Mq4 L=0.35u W=4u nf=1 m=1}
C {lab_pin.sym} 620 1030 0 0 {name=l95 lab=dout}
C {lab_pin.sym} 580 1060 0 0 {name=l96 lab=doutb}
C {lab_pin.sym} 620 1090 0 0 {name=l97 lab=0}
C {lab_pin.sym} 620 1060 0 0 {name=l98 lab=0}
C {symbols/pfet_03v3.sym} 800 1060 0 0 {name=Mqb1 L=0.35u W=8u nf=1 m=1}
C {lab_pin.sym} 820 1090 0 0 {name=l99 lab=ps2}
C {lab_pin.sym} 780 1060 0 0 {name=l100 lab=sset}
C {lab_pin.sym} 820 1030 0 0 {name=l101 lab=vdd}
C {lab_pin.sym} 820 1060 0 0 {name=l102 lab=vdd}
C {symbols/pfet_03v3.sym} 1000 1060 0 0 {name=Mqb2 L=0.35u W=8u nf=1 m=1}
C {lab_pin.sym} 1020 1090 0 0 {name=l103 lab=doutb}
C {lab_pin.sym} 980 1060 0 0 {name=l104 lab=dout}
C {lab_pin.sym} 1020 1030 0 0 {name=l105 lab=ps2}
C {lab_pin.sym} 1020 1060 0 0 {name=l106 lab=vdd}
C {symbols/nfet_03v3.sym} 0 1220 0 0 {name=Mqb3 L=0.35u W=4u nf=1 m=1}
C {lab_pin.sym} 20 1190 0 0 {name=l107 lab=doutb}
C {lab_pin.sym} -20 1220 0 0 {name=l108 lab=sset}
C {lab_pin.sym} 20 1250 0 0 {name=l109 lab=0}
C {lab_pin.sym} 20 1220 0 0 {name=l110 lab=0}
C {symbols/nfet_03v3.sym} 200 1220 0 0 {name=Mqb4 L=0.35u W=4u nf=1 m=1}
C {lab_pin.sym} 220 1190 0 0 {name=l111 lab=doutb}
C {lab_pin.sym} 180 1220 0 0 {name=l112 lab=dout}
C {lab_pin.sym} 220 1250 0 0 {name=l113 lab=0}
C {lab_pin.sym} 220 1220 0 0 {name=l114 lab=0}
C {ipin.sym} -300 0 0 0 {name=p0 lab=vinp}
C {ipin.sym} -300 40 0 0 {name=p1 lab=vinn}
C {ipin.sym} -300 80 0 0 {name=p2 lab=clk}
C {ipin.sym} -300 120 0 0 {name=p3 lab=ibias}
C {ipin.sym} -300 160 0 0 {name=p4 lab=vdd}
C {opin.sym} -300 200 0 0 {name=p5 lab=dout}
C {opin.sym} -300 240 0 0 {name=p6 lab=doutb}
