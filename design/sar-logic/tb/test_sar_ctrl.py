"""cocotb testbench for `sar_ctrl_a` (design/sar-logic/rtl/sar_ctrl.v), issue #642.

Run by `klt functional-verification` (request: sar_ctrl.fv_request.json); the
DUT name and port list are the only coupling, so a gate-level netlist with the
same top (`sar_ctrl_a`) can reuse this module by swapping `sources` (#645).

An ideal comparator is modelled in Python: for an input of code T it answers
each successive-approximation trial with `T >= trial level`, so a correct
sequencer must return exactly T. Besides the final code, every output is
checked EVERY CYCLE against an independent cycle-accurate model of the
sequencer written from the documented phase schedule, not from the RTL:

  phase k = k-th clock after the `start` edge (0..15, one-hot ring)
  samp_tp_n = phases 0..2, sel_in_n = phases 0..3, drdy = phase 15
  bit b (9..0) is decided in phase 13-b; the engage flag of the weight whose
  q-index is qi (9..1, weight 2**(qi-1)) is high in phases 14-qi..13
  c9..c0 load at the edge leaving phase 14 and hold until the next load

Sampling discipline: outputs are read on the falling edge (stable, after the
previous rising edge's non-blocking updates) and inputs are driven there too.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

NPHASE = 16
WEIGHTS = [(256, 9), (128, 8), (64, 7), (32, 6), (16, 5), (8, 4), (4, 3), (2, 2), (1, 1)]


def bits(dut, names):
    return {n: getattr(dut, n).value for n in names}


def expected_phase_outputs(phase: int, code: int, mode: int, prev_code: int | None) -> dict:
    """Every checked output of sar_ctrl_a in `phase` of a conversion of `code`."""
    exp = {
        "samp_tp_n": int(phase <= 2),
        "sel_in_n": int(phase <= 3),
        "drdy": int(phase == 15),
    }
    smpb = int(phase >= 4)
    for w, qi in WEIGHTS:
        eng = int(14 - qi <= phase <= 13)
        q = (code >> qi) & 1
        exp[f"rel_n_{w}p"] = int(not eng) & smpb
        exp[f"sel_hi_n_{w}p"] = eng & q
        exp[f"sel_lo_n_{w}p"] = eng & (1 - q)
        exp[f"rel_n_{w}n"] = int((not eng) or (not mode)) & smpb
        exp[f"sel_hi_n_{w}n"] = (eng & mode) & (1 - q)
        exp[f"sel_lo_n_{w}n"] = (eng & mode) & q
    out_code = code if phase == 15 else prev_code
    if out_code is not None:
        for b in range(10):
            exp[f"c{b}"] = (out_code >> b) & 1
    return exp


def trial_cmp(code: int, phase: int, decided: int) -> int:
    """cmp level the ideal comparator presents in `phase` (a trial of bit 13-phase).
    DUT inverts it (dec = ~cmp), so cmp = 0 means "keep this bit"."""
    b = 13 - phase
    level = decided | (1 << b)
    return 0 if code >= level else 1


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 62.5, unit="ns", impl="gpi").start())
    dut.start.value = 0
    dut.cmp.value = 0
    dut.mode.value = 1


async def warm_up(dut):
    """Real hardware has no reset: one start pulse seeds the ring, one full
    conversion clears the engage flags."""
    await FallingEdge(dut.clk)
    dut.start.value = 1
    await FallingEdge(dut.clk)
    dut.start.value = 0
    for _ in range(NPHASE + 1):
        await FallingEdge(dut.clk)


async def run_conversions(dut, codes, mode, *, restart_each: bool, prev_code=None):
    """Convert each code back to back, checking every output every cycle.
    Called on a falling edge with `start` low and the ring in phase 15 -> 0 wrap
    (or any state when restart_each). Returns the last code converted."""
    dut.mode.value = mode
    for code in codes:
        decided = 0
        # phase 0 is the cycle after the start edge (or after the ph15 wrap)
        if restart_each:
            dut.start.value = 1
            await FallingEdge(dut.clk)
            dut.start.value = 0
        else:
            await FallingEdge(dut.clk)
        for phase in range(NPHASE):
            exp = expected_phase_outputs(phase, code, mode, prev_code)
            for name, want in exp.items():
                got = getattr(dut, name).value
                assert got.is_resolvable and int(got) == want, (
                    f"code {code} mode {mode} phase {phase}: {name} = {got}, expected {want}"
                )
            if 4 <= phase <= 13:
                dut.cmp.value = trial_cmp(code, phase, decided)
                if code >= decided | (1 << (13 - phase)):
                    decided |= 1 << (13 - phase)
            if phase != NPHASE - 1:
                await FallingEdge(dut.clk)
        assert decided == code, f"model self-check: decided {decided} != {code}"
        prev_code = code
        if not restart_each:
            pass
    return prev_code


@cocotb.test()
async def test_all_codes_differential(dut):
    """All 1024 codes, differential mode, restarted each conversion."""
    await start_clock(dut)
    await warm_up(dut)
    await run_conversions(dut, range(1024), 1, restart_each=True, prev_code=None)


@cocotb.test()
async def test_all_codes_single_ended(dut):
    """All 1024 codes with `mode` = 0 (n-side gated off)."""
    await start_clock(dut)
    await warm_up(dut)
    await run_conversions(dut, range(1024), 0, restart_each=True, prev_code=None)


@cocotb.test()
async def test_free_running_wrap(dut):
    """No `start` between conversions: ph15 wraps into ph0 on its own."""
    await start_clock(dut)
    await warm_up(dut)
    # warm_up leaves us in phase 1 of a free-running ring; align to phase 15
    # by waiting out the rest of that conversion, then check three wraps.
    for _ in range(NPHASE - 2):
        await FallingEdge(dut.clk)
    await run_conversions(dut, [0x2A5, 0x3FF, 0x000, 0x155], 1, restart_each=False, prev_code=None)


@cocotb.test()
async def test_start_restarts_mid_conversion(dut):
    """`start` asserted mid-conversion forces phase 0 and a single token."""
    await start_clock(dut)
    await warm_up(dut)
    for _ in range(7):
        await FallingEdge(dut.clk)
    dut.start.value = 1
    await FallingEdge(dut.clk)
    dut.start.value = 0
    # ring must be exactly phase 0: sampling window outputs of phase 0
    assert int(dut.samp_tp_n.value) == 1 and int(dut.sel_in_n.value) == 1 and int(dut.drdy.value) == 0
    # a full conversion from here must be bit-exact (start edge already taken)
    dut.mode.value = 1
    code = 0x1B6
    decided = 0
    for phase in range(NPHASE):
        exp = expected_phase_outputs(phase, code, 1, None)
        for name in ("samp_tp_n", "sel_in_n", "drdy"):
            assert int(getattr(dut, name).value) == exp[name], f"restart phase {phase}: {name}"
        if 4 <= phase <= 13:
            dut.cmp.value = trial_cmp(code, phase, decided)
            if code >= decided | (1 << (13 - phase)):
                decided |= 1 << (13 - phase)
        if phase == NPHASE - 1:
            got = sum(int(getattr(dut, f"c{b}").value) << b for b in range(10))
            assert got == code, f"restart conversion returned {got}, expected {code}"
        else:
            await FallingEdge(dut.clk)
