#!/usr/bin/env python3
"""Spec-level reference model for the SAR control logic.

This module is the **oracle**, not the design. It is written directly from the
ratified records -- DR-0003 (external clock, M = 16), DR-0005 (10-bit parallel
output register, SPI deferred) and DR-0006-cdac-switching-scheme (MCS / Vcm-based
switching, top-plate sampling, mode-dependent switching sequence) -- and knows
nothing about how the
logic is built. ``sar_logic.py`` builds the gate-level structure that the
transistor netlist is generated from; the tests in
``sim/tests/test_sar_logic.py`` check that structure against *this* model over
every reachable decision sequence in both input modes.

Keeping the two apart is the whole point: a model derived from the netlist
would agree with the netlist by construction and prove nothing.

Phase map (M = 16, DR-0003)
---------------------------

One sample period is 16 clock cycles. Cycle indices are counted from the cycle
in which the sequencer's one-hot pointer sits on stage 0:

===========  ==========  =================================================
cycle        phase       what happens
===========  ==========  =================================================
0 .. 5       acquire     ``samp`` asserted, input tracked onto both top
                         plates, every bottom plate released to ``V_cm``
6            trial 1     MSB: decided from the sampled charge with **no**
                         array switching at all (top-plate sampling, per
                         DR-0006-cdac-switching-scheme); the decision is
                         captured at the clock
                         edge that ends this cycle
7 .. 15      trial 2-10  weight ``2**(9-i)`` engaged from the decision
                         captured at the end of trial ``i``
===========  ==========  =================================================

At the clock edge that ends cycle 15 the 10 captured decisions are transferred
into the parallel output register, so a conversion's code is readable for the
whole of the *following* sample period.
"""

from __future__ import annotations

from dataclasses import dataclass, field

N_BITS = 10
"""Resolution. 10 bits (README target specification, ratified in DR-0006-spec-ratification)."""

CLOCK_MULTIPLIER = 16
"""``M`` from DR-0003: clock is ``M * f_s`` -- 16 MHz at 1 MS/s, 32 MHz at the 2 MS/s stretch."""

ACQUIRE_CYCLES = 6
"""Cycles spent tracking the input. ``CLOCK_MULTIPLIER - N_BITS``, one cycle per bit trial."""

WEIGHTS = (256, 128, 64, 32, 16, 8, 4, 2, 1)
"""The nine switched sub-array weights, in the order they are engaged.

DR-0006-cdac-switching-scheme: the array is ``2**(N-1) = 512`` unit positions
per side; 511 of them
are the binary weights ``2**8 .. 2**0`` that resolve bits 2..10, and one is a
terminating unit permanently tied to ``V_cm``. Weight ``WEIGHTS[i-1]`` is
engaged by the decision taken in trial ``i``, so the last weight (1) is engaged
by trial 9's decision and trial 10 needs no weight of its own.
"""

SIDES = ("p", "n")
"""``p`` is the side that samples ``V_in`` in single-ended mode; ``n`` is pinned to ``V_cm``."""

REL, HI, LO = "rel", "hi", "lo"
"""Bottom-plate states: released to ``V_cm``, engaged to ``V_REF``, engaged to ``GND``."""


@dataclass(frozen=True)
class CycleState:
    """Everything the controller drives during one clock cycle."""

    cycle: int
    samp: bool
    trial: int | None                      # 1..N_BITS during a trial, else None
    cells: dict[tuple[str, int], str]      # (side, weight) -> REL | HI | LO
    code: int                              # parallel output register contents
    eoc: bool                              # "new code available" flag (cycle 0)

    @property
    def acquiring(self) -> bool:
        return self.trial is None


def cell_state(weight_index: int, trial: int, bit: int, side: str, mode_diff: bool) -> str:
    """Bottom-plate state of one cell during one trial. The whole scheme, in one function.

    ``weight_index`` is 1-based into :data:`WEIGHTS`; ``trial`` is 1-based;
    ``bit`` is the decision captured at the end of trial ``weight_index``.
    """
    if weight_index >= trial:
        # Not engaged yet: this cell's own trial has not finished.
        return REL
    if side == "p":
        # A '1' decision means the p-side residue was positive, so the p-side
        # top plate must be pulled DOWN -- bottom plate V_cm -> GND
        # (DR-0006-cdac-switching-scheme).
        return LO if bit else HI
    if not mode_diff:
        # Single-ended: the V_cm-pinned side never switches. Driving it would
        # double every step and cost a bit of resolution
        # (DR-0006-cdac-switching-scheme).
        return REL
    return HI if bit else LO


def conversion_cycles(pattern: list[int] | tuple[int, ...], mode_diff: bool, code_in: int) -> list[CycleState]:
    """The 16 cycle states of one conversion.

    ``pattern`` is the sequence of ``N_BITS`` comparator decisions, MSB first.
    ``code_in`` is what the output register already held when the conversion
    started (the previous conversion's code) -- it is *not* updated until the
    edge that ends the last cycle, so it is visible throughout.
    """
    if len(pattern) != N_BITS:
        raise ValueError(f"pattern must be {N_BITS} decisions, got {len(pattern)}")
    if any(b not in (0, 1) for b in pattern):
        raise ValueError("decisions must be 0 or 1")

    states: list[CycleState] = []
    for cycle in range(CLOCK_MULTIPLIER):
        trial = None if cycle < ACQUIRE_CYCLES else cycle - ACQUIRE_CYCLES + 1
        cells: dict[tuple[str, int], str] = {}
        for side in SIDES:
            for index, weight in enumerate(WEIGHTS, start=1):
                if trial is None:
                    cells[(side, weight)] = REL
                else:
                    cells[(side, weight)] = cell_state(
                        index, trial, pattern[index - 1], side, mode_diff
                    )
        states.append(
            CycleState(
                cycle=cycle,
                samp=trial is None,
                trial=trial,
                cells=cells,
                code=code_in,
                eoc=cycle == 0,
            )
        )
    return states


def code_of(pattern: list[int] | tuple[int, ...]) -> int:
    """The parallel output word: the decisions themselves, MSB first.

    No redundancy and no non-binary weighting is used (DR-0009), so no digital
    correction stands between the decisions and the output code: bit 1 is the
    MSB of a straight offset-binary word.
    """
    value = 0
    for bit in pattern:
        value = (value << 1) | bit
    return value


@dataclass
class ReferenceRun:
    """A multi-conversion run, cycle by cycle, as the reference model predicts it."""

    cycles: list[CycleState] = field(default_factory=list)
    codes: list[int] = field(default_factory=list)


def run(patterns: list[tuple[int, ...]], modes: list[bool], code_at_reset: int = 0) -> ReferenceRun:
    """Chain conversions back to back, as the testbench drives them."""
    if len(patterns) != len(modes):
        raise ValueError("one mode per conversion")
    out = ReferenceRun()
    code = code_at_reset
    for pattern, mode_diff in zip(patterns, modes):
        out.cycles.extend(conversion_cycles(pattern, mode_diff, code))
        code = code_of(pattern)
        out.codes.append(code)
    return out
