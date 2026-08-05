#!/usr/bin/env python3
"""Build a schematic-vs-extracted delta table from two `sim/` records.

Issue #89 Scope item 3 asks for "for every spec line, schematic result vs
extracted result vs delta". This computes that table *from the committed
records themselves* rather than from numbers transcribed by hand, so an
outside reader can re-derive every cell of the published summary:

    python3 sim/tools/schematic_vs_extracted.py adc-inl-dnl \
        --schematic 20260802-141402-1224e11 \
        --extracted  20260805-131914-94522ce

Both record ids must name records under `sim/<experiment>/records/`. The
tool reads each record's per-corner Result table (the wide markdown table
`sim/harness/report.py` renders, one row per corner), intersects the two
corner sets, and reports, per measurement:

  * the schematic and extracted **worst** value over the shared corners,
    "worst" meaning largest magnitude (these are error terms — the sign is
    reported, the ranking is on |x|), and the corner each occurred at;
  * the delta (extracted worst − schematic worst at the *same* measurement),
    both absolute and as a percentage of the schematic worst;
  * the largest **per-corner** delta, i.e. max over shared corners of
    |extracted(c) − schematic(c)|, which is what actually bounds the
    layout-induced change (a worst-vs-worst delta can hide a large
    per-corner swing that moves the worst corner around).

It also derives the two reduced spec-line quantities the ratified table
names but the record does not carry as its own column — worst |INL| and
worst |DNL| over the probed transitions — from the `inl_t*_lsb` /
`dnl_*_lsb` columns.

Stdlib-only, no PDK / ngspice needed: it reads committed markdown.

**This tool does not adjudicate pass/fail.** The records' own `pass/fail`
column and the manifest's checks do that; a delta table that re-derived
limits here could disagree with the record it summarises. Per-corner
verdicts are read out of the records, never recomputed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Reduced spec-line quantities derived from a group of per-transition
#: columns: name -> (regex matching the source columns, human description).
DERIVED = {
    "inl_worst_lsb": (re.compile(r"^inl_t\d+_lsb$"), "worst |INL| over the probed transitions"),
    "dnl_worst_lsb": (re.compile(r"^dnl_t\d+_t\d+_lsb$"), "worst |DNL| over the probed pairs"),
}


def record_path(experiment: str, record_id: str) -> Path:
    return REPO_ROOT / "sim" / experiment / "records" / f"{record_id}.md"


def _split_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip().strip("`") for c in cells]


def _as_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def parse_record(path: Path) -> dict[str, dict[str, float | str]]:
    """Return {corner_id: {measurement: value}} from a record's Result table.

    The per-corner Result table is the first markdown table in the record
    whose header's first cell is `corner-id`. Its rows run until the first
    line that is not a table row. Values that do not parse as floats (the
    `pass/fail` column) are kept as strings.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    header: list[str] | None = None
    rows: dict[str, dict[str, float | str]] = {}
    for idx, line in enumerate(lines):
        if header is None:
            if line.strip().startswith("|") and _split_row(line)[:1] == ["corner-id"]:
                header = _split_row(line)
            continue
        if not line.strip().startswith("|"):
            break
        cells = _split_row(line)
        if set("".join(cells)) <= {"-", ""}:  # the |---|---| separator
            continue
        if len(cells) != len(header):
            raise ValueError(
                f"{path}: row {idx} has {len(cells)} cells, header has {len(header)}"
            )
        corner = cells[0]
        row: dict[str, float | str] = {}
        for name, raw in zip(header[1:], cells[1:]):
            value = _as_float(raw)
            row[name] = raw if value is None else value
        rows[corner] = row
    if header is None:
        raise ValueError(f"{path}: no per-corner Result table found")
    if not rows:
        raise ValueError(f"{path}: Result table has a header but no corner rows")
    return rows


def add_derived(rows: dict[str, dict[str, float | str]]) -> None:
    """Add the reduced spec-line columns (worst |INL|, worst |DNL|) in place."""
    for name, (pattern, _) in DERIVED.items():
        for corner, row in rows.items():
            sources = [
                v for k, v in row.items() if pattern.match(k) and isinstance(v, float)
            ]
            if sources:
                row[name] = max(sources, key=abs)


def _worst(rows: dict[str, dict[str, float | str]], corners: list[str], name: str):
    """(value, corner) of the largest-magnitude value of `name`, or None."""
    candidates = [
        (row[name], c)
        for c in corners
        for row in [rows[c]]
        if isinstance(row.get(name), float)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda vc: abs(vc[0]))


def _fmt(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) < 1e-4 or abs(value) >= 1e5:
        return f"{value:.3e}"
    return f"{value:.6g}"


def build_table(
    schematic: dict[str, dict[str, float | str]],
    extracted: dict[str, dict[str, float | str]],
    only: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return (markdown lines, shared corner ids)."""
    shared = sorted(set(schematic) & set(extracted))
    if not shared:
        raise SystemExit(
            "error: the two records share no corner: "
            f"schematic={sorted(schematic)}, extracted={sorted(extracted)}"
        )
    names = [
        n
        for n in schematic[shared[0]]
        if isinstance(schematic[shared[0]][n], float)
        and any(isinstance(extracted[c].get(n), float) for c in shared)
    ]
    if only:
        wanted = set(only)
        missing = wanted - set(names)
        if missing:
            raise SystemExit(f"error: no such measurement(s): {sorted(missing)}")
        names = [n for n in names if n in wanted]

    out = [
        "| measurement | schematic worst | extracted worst | delta (worst) | delta % | max per-corner delta |",
        "|---|---|---|---|---|---|",
    ]
    for name in names:
        sw = _worst(schematic, shared, name)
        ew = _worst(extracted, shared, name)
        if sw is None or ew is None:
            continue
        delta = ew[0] - sw[0]
        pct = "n/a" if sw[0] == 0 else f"{100.0 * delta / abs(sw[0]):+.4g}"
        per_corner = max(
            (
                abs(extracted[c][name] - schematic[c][name])
                for c in shared
                if isinstance(extracted[c].get(name), float)
                and isinstance(schematic[c].get(name), float)
            ),
            default=float("nan"),
        )
        out.append(
            f"| `{name}` | {_fmt(sw[0])} (`{sw[1]}`) | {_fmt(ew[0])} (`{ew[1]}`) "
            f"| {delta:+.6g} | {pct} | {_fmt(per_corner)} |"
        )
    return out, shared


def verdicts(rows: dict[str, dict[str, float | str]], corners: list[str]) -> dict[str, str]:
    """PASS/FAIL per corner, read from the record's own `pass/fail` column.

    A FAIL cell carries the failing checks inline ("FAIL — inl_t128_lsb
    min=-1 (got ...); ..."), which is the right level of detail *in a
    record* and far too much in a cross-record summary — so only the
    leading verdict token is kept here. The record remains the place to
    read which check failed and by how much.
    """
    out = {}
    for c in corners:
        cell = str(rows[c].get("pass/fail", "?"))
        out[c] = cell.split("—")[0].split(" - ")[0].strip() or "?"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("experiment", help="experiment slug under sim/")
    ap.add_argument("--schematic", required=True, metavar="RECORD_ID")
    ap.add_argument("--extracted", required=True, metavar="RECORD_ID")
    ap.add_argument(
        "--only",
        nargs="+",
        metavar="NAME",
        help="restrict the table to these measurement columns",
    )
    args = ap.parse_args(argv)

    paths = {}
    for label, rid in (("schematic", args.schematic), ("extracted", args.extracted)):
        path = record_path(args.experiment, rid)
        if not path.is_file():
            print(f"error: no such record: {path}", file=sys.stderr)
            return 2
        paths[label] = path

    schematic = parse_record(paths["schematic"])
    extracted = parse_record(paths["extracted"])
    add_derived(schematic)
    add_derived(extracted)

    table, shared = build_table(schematic, extracted, args.only)

    print(f"# {args.experiment}: schematic vs extracted")
    print()
    print(f"- schematic record: `{args.schematic}`")
    print(f"- extracted record: `{args.extracted}`")
    print(f"- shared corners ({len(shared)}): {', '.join('`' + c + '`' for c in shared)}")
    sv, ev = verdicts(schematic, shared), verdicts(extracted, shared)
    print(
        f"- per-corner verdicts (read from the records, not recomputed): "
        f"schematic {sorted(set(sv.values()))}, extracted {sorted(set(ev.values()))}"
    )
    disagree = [c for c in shared if sv[c] != ev[c]]
    print(
        "- corners whose verdict CHANGED schematic -> extracted: "
        + (", ".join(f"`{c}` ({sv[c]} -> {ev[c]})" for c in disagree) if disagree else "none")
    )
    print()
    print("\n".join(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
