#!/usr/bin/env python3
"""Reduce a probe deck's `wrdata` dump (time, isum, time, i(vddd)) -- issue #386.

Independent of ngspice's own `.meas` evaluation: integrates the SAVED points
by the trapezoid rule, so it is a check on `.meas INTEG` as well as on the
timestep. Prints (1) every excursion of the summed vdd current beyond
3 mA after 3 us, (2) the three event-window charges and the ph1..ph2 baseline
the record uses, and (3) the time the summed current spends beyond half its
window peak (a FWHM-style width, for comparison with t_eq = dQ / I_pk).

    python3 analyze_probe.py /tmp/probe386/p10p.cir.dat
"""

import sys


def load(path):
    t, v = [], []
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) >= 2:
                t.append(float(parts[0]))
                v.append(float(parts[1]))
    return t, v


def integ(t, v, lo, hi):
    q = 0.0
    for i in range(1, len(t)):
        a, b = max(t[i - 1], lo), min(t[i], hi)
        if b <= a:
            continue
        span = t[i] - t[i - 1]
        va = v[i - 1] + (v[i] - v[i - 1]) * (a - t[i - 1]) / span
        vb = v[i - 1] + (v[i] - v[i - 1]) * (b - t[i - 1]) / span
        q += (b - a) * (va + vb) / 2
    return q


def width_below(t, v, lo, hi):
    idx = [i for i in range(len(t)) if lo <= t[i] <= hi]
    pk = min(v[i] for i in idx)
    half = pk / 2
    w = 0.0
    for j in range(1, len(idx)):
        i0, i1 = idx[j - 1], idx[j]
        dt = t[i1] - t[i0]
        in0, in1 = v[i0] < half, v[i1] < half
        if in0 and in1:
            w += dt
        elif in0 or in1:
            f = (half - v[i0]) / (v[i1] - v[i0])
            w += dt * (1 - f) if in1 else dt * f
    return -pk, w, len(idx)


def main(path):
    t, v = load(path)
    print("excursions beyond 3 mA after 3 us:")
    inside, mn, tm, t0 = False, 0.0, 0.0, 0.0
    for ti, vi in zip(t, v):
        if ti <= 3e-6:
            continue
        if vi < -3e-3:
            if not inside:
                inside, mn, tm, t0 = True, vi, ti, ti
            elif vi < mn:
                mn, tm = vi, ti
        elif inside:
            inside = False
            k = int(tm * 1e6 + 1e-9)
            print(f"  t={tm*1e6:.5f} us  (t_k + {(tm-k*1e-6)*1e9:.2f} ns)  peak {-mn*1e3:.2f} mA")
    windows = {"A k=7": (6.999e-6, 7.0615e-6), "B k=7": (7.249e-6, 7.3115e-6),
               "C k=5": (5.874e-6, 5.9365e-6)}
    bases = {"A k=7": (7.0615e-6, 7.1865e-6), "B k=7": (7.0615e-6, 7.1865e-6),
             "C k=5": (5.0615e-6, 5.1865e-6)}
    for name, (lo, hi) in windows.items():
        q = -integ(t, v, lo, hi)
        blo, bhi = bases[name]
        ib = -integ(t, v, blo, bhi) / (bhi - blo)
        dq = q - ib * (hi - lo)
        ipk, w, n = width_below(t, v, lo, hi)
        print(f"{name}: window charge {q*1e12:.4f} pC, I_static {ib*1e6:.3f} uA, "
              f"dQ_event {dq*1e12:.4f} pC, I_pk {ipk*1e3:.3f} mA, t_eq {dq/ipk*1e9:.4f} ns, "
              f"time beyond half-peak {w*1e9:.4f} ns, {n} points in window")


if __name__ == "__main__":
    main(sys.argv[1])
