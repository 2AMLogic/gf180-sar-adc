import sys, dataclasses
sys.path.insert(0, '.')
from harness import testbench, pdk as pdkm, corners, runner
tb = testbench.load('adc-rail-current/testbench')
tmax = sys.argv[1]; tstop = sys.argv[2]; out = sys.argv[3]
an = [f"tran 1n {tstop} 0 {tmax}",
      "let isum = i(vddc)+i(vddd)+i(vddt)",
      "meas tran pk MIN isum FROM=6.99u TO=7.10u",
      "meas tran pkd MIN i(vddd) FROM=6.99u TO=7.10u",
      "meas tran qa INTEG isum FROM=6.999u TO=7.0615u",
      "meas tran qad INTEG i(vddd) FROM=6.999u TO=7.0615u",
      "meas tran qb INTEG isum FROM=7.249u TO=7.3115u",
      "meas tran mx MAX isum FROM=3u TO=" + tstop,
      "meas tran mxd MAX i(vddd) FROM=3u TO=" + tstop,
      "let npts = length(time)",
      "print npts",
      "wrdata " + out + ".dat isum i(vddd)",
     ]
tb = dataclasses.replace(tb, analyses=tuple(an), measure={})
p = pdkm.find_pdk()
c = corners.resolve_corners(['ff'])[0]
pt = corners.PvtPoint(corner=c, temp_c=-40.0, vdd=3.63)
deck = runner.compose_deck(tb, p, pt, num_threads=1)
deck = deck.replace('.include "' + str(tb.netlist), '.include "' + str(tb.netlist.resolve()))
open(out,'w').write(deck)
