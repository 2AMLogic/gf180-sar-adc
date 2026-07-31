v {xschem version=3.4.7 file_version=1.2
* Environment-bootstrap smoke test -- NOT a SAR ADC design.
*
* A throwaway sample-and-hold primitive used only to prove the
* xschem -> ngspice -> gf180mcu toolchain works end to end:
*   VIN (1.0V) drives the source of a gf180mcu 3.3V nfet (nfet_03v3_dss)
*   acting as a sampling switch; VSAMPLE (3.3V) holds its gate on; the
*   drain (vhold) charges an ideal 1p hold capacitor.
*   R1 (10k) from VDD to vhold provides a DC path so the operating point
*   is well defined without needing a transient.
*
* This is the *installation* check. It is deliberately independent of the
* PVT corner harness: device-level corner coverage lives in the harness
* experiments under sim/<experiment-slug>/, which sweep the real model
* sections. See docs/environment-setup.md for how the two differ.
*
* See sim/smoke_test/run_smoke_test.sh for how this gets netlisted and run.
}
G {}
K {}
V {}
S {}
E {}
N 0 -60 0 -30 {}
N 0 30 0 60 {}
N 200 -60 200 -30 {}
N 200 30 200 60 {}
N 400 -60 400 -30 {}
N 400 30 400 60 {}
N 600 -60 600 -30 {}
N 600 30 600 60 {}
N 800 -60 800 -30 {}
N 800 30 800 60 {}
C {vsource.sym} 0 0 0 0 {name=VDD value="dc 3.3"}
C {lab_pin.sym} 0 -60 0 0 {name=p1 lab=vdd}
C {lab_pin.sym} 0 60 0 0 {name=p2 lab=0}
C {vsource.sym} 200 0 0 0 {name=VSAMPLE value="dc 3.3"}
C {lab_pin.sym} 200 -60 0 0 {name=p3 lab=vsample}
C {lab_pin.sym} 200 60 0 0 {name=p4 lab=0}
C {vsource.sym} 400 0 0 0 {name=VIN value="dc 1.0"}
C {lab_pin.sym} 400 -60 0 0 {name=p5 lab=vin}
C {lab_pin.sym} 400 60 0 0 {name=p6 lab=0}
C {res.sym} 600 0 0 0 {name=R1 value=10k footprint=1206 device=resistor m=1}
C {lab_pin.sym} 600 -60 0 0 {name=p7 lab=vdd}
C {lab_pin.sym} 600 60 0 0 {name=p8 lab=vhold}
C {capa.sym} 800 0 0 0 {name=C1 value=1p footprint=1206 device="ceramic capacitor" m=1}
C {lab_pin.sym} 800 -60 0 0 {name=p9 lab=vhold}
C {lab_pin.sym} 800 60 0 0 {name=p10 lab=0}
C {code_shown.sym} 1000 0 0 0 {name=s1 only_toplevel=false value="
* pdk_include.spice is generated at run time by run_smoke_test.sh from
* $PDK_ROOT / $PDK -- kept out of this schematic so it has no hardcoded,
* machine-specific path (see docs/environment-setup.md).
.include pdk_include.spice
XSW vhold vsample vin 0 nfet_03v3_dss w=20u l=0.28u

.control
op
print v(vdd) v(vsample) v(vin) v(vhold)
quit
.endc
"}
