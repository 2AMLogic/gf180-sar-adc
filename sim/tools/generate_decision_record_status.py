#!/usr/bin/env python3
"""Generate and CI-check spec/decision-records/STATUS.md (issue #438).

A read-only, deterministic status index over the `DR-*.md` header fields.
It never modifies a record and does not ratify or reject anything.

    python3 sim/tools/generate_decision_record_status.py             # write
    python3 sim/tools/generate_decision_record_status.py --as-of 2026-10-09
    python3 sim/tools/generate_decision_record_status.py --check     # CI

As-of semantics: the generated file carries an explicit `As of: YYYY-MM-DD`.
Generation defaults it to the current UTC date (``--as-of`` overrides).
``--check`` reads the committed file's As-of value and regenerates with that
same date, never today's, so an unchanged tree stays green as wall-clock time
passes. Refreshing the snapshot date is an explicit generation action.

Stdlib-only; no PDK / ngspice / klt required (headless CI path).
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DR_DIR = REPO_ROOT / "spec" / "decision-records"
STATUS_FILE = DR_DIR / "STATUS.md"

DEFAULT_THRESHOLD_DAYS = 14
STATUS_TOKENS = ("proposed", "ratified", "superseded-by")
REQUIRED_FIELDS = ("Status", "Date", "Supersedes", "Superseded by")

TITLE_RE = re.compile(r"^# (DR-(\d{4})): (\S.*)$")
FIELD_RE = re.compile(r"^- \*\*([^*]+)\*\*:[ \t]*(.*)$")
ASOF_RE = re.compile(r"^As of: (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
SPEC_HEADING = "## Spec lines affected"


class RecordError(Exception):
    """A malformed record; message is `<file>: <field>: <problem>`."""


@dataclass(frozen=True)
class Record:
    number: str          # "DR-0001"
    filename: str
    title: str
    status_token: str
    status_text: str
    date: dt.date
    supersedes: str
    superseded_by: str
    spec_lines: tuple[str, ...]


def _norm(text: str) -> str:
    return " ".join(text.split())


def parse_iso_date(value: str) -> dt.date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"not an ISO YYYY-MM-DD date: {value!r}")
    return dt.date.fromisoformat(value)


def parse_record(path: Path, as_of: dt.date) -> Record:
    name = path.name
    lines = path.read_text(encoding="utf-8").splitlines()

    def err(field: str, msg: str) -> RecordError:
        return RecordError(f"{name}: {field}: {msg}")

    # Title: first Markdown heading.
    first = next((i for i, l in enumerate(lines) if l.startswith("#")), None)
    if first is None:
        raise err("title", "no Markdown heading found")
    m = TITLE_RE.match(lines[first])
    if not m:
        raise err("title", f"malformed, expected '# DR-NNNN: title', got {lines[first]!r}")
    number, digits, title = m.group(1), m.group(2), _norm(m.group(3))
    if not name.startswith(f"DR-{digits}"):
        raise err("title", f"{number} does not match filename")

    # Header block: first heading through next '##' heading.
    fields: dict[str, list[list[str]]] = {}
    current: list[str] | None = None
    end = len(lines)
    for i in range(first + 1, len(lines)):
        line = lines[i]
        if line.startswith("## "):
            end = i
            break
        fm = FIELD_RE.match(line)
        if fm:
            current = [fm.group(2)]
            fields.setdefault(fm.group(1).strip(), []).append(current)
        elif current is not None and line[:1] in (" ", "\t") and line.strip():
            current.append(line)
        else:
            current = None

    values: dict[str, str] = {}
    for f in REQUIRED_FIELDS:
        found = fields.get(f, [])
        if not found:
            raise err(f, "missing required header field")
        if len(found) > 1:
            raise err(f, f"duplicate header field ({len(found)} occurrences)")
        values[f] = _norm(" ".join(found[0]))

    status = values["Status"]
    token = status.split(" ", 1)[0] if status else ""
    if token not in STATUS_TOKENS:
        raise err("Status", f"unknown status token {token!r}; expected one of {', '.join(STATUS_TOKENS)}")

    try:
        date = parse_iso_date(values["Date"])
    except ValueError as e:
        raise err("Date", str(e)) from None
    if date > as_of:
        raise err("Date", f"{date} is after the as-of date {as_of}")

    # Spec lines affected.
    try:
        s = next(i for i in range(end, len(lines)) if lines[i].rstrip() == SPEC_HEADING)
    except StopIteration:
        raise err("Spec lines affected", "section missing") from None
    entries: list[list[str]] = []
    for line in lines[s + 1:]:
        if line.startswith("#"):
            break
        if re.match(r"^[-*] ", line):
            entries.append([line[2:]])
        elif line.strip():
            if entries and line[:1] in (" ", "\t"):
                entries[-1].append(line)
            else:
                entries.append([line])
    spec_lines = tuple(e for e in (_norm(" ".join(x)) for x in entries) if e)
    if not spec_lines:
        raise err("Spec lines affected", "section is empty")

    return Record(number, name, title, token, status, date,
                  values["Supersedes"], values["Superseded by"], spec_lines)


def load_records(dr_dir: Path, as_of: dt.date) -> list[Record]:
    records = [parse_record(p, as_of) for p in sorted(dr_dir.glob("DR-*.md"))]
    records.sort(key=lambda r: (r.number, r.filename))
    return records


def _cell(text: str) -> str:
    return (text or "-").replace("|", "\\|")


def render(records: list[Record], as_of: dt.date,
           threshold_days: int = DEFAULT_THRESHOLD_DAYS) -> str:
    counts = {t: sum(r.status_token == t for r in records) for t in STATUS_TOKENS}
    out = [
        "# Decision record status index",
        "",
        "<!-- GENERATED by sim/tools/generate_decision_record_status.py; do not edit by hand. -->",
        "",
        f"As of: {as_of.isoformat()}",
        "",
        "This is a read-only view of each `DR-*.md` header. It does not ratify,",
        "reject, or modify any record. The as-of date is a committed snapshot:",
        "`--check` reuses it instead of today's date, so age columns and the",
        "aged-proposed section do not go stale as calendar time passes. To",
        "refresh, run `python3 sim/tools/generate_decision_record_status.py`",
        "(defaults to the current UTC date; `--as-of YYYY-MM-DD` overrides) and",
        "commit the result.",
        "",
        f"Records: {len(records)} ("
        + ", ".join(f"{counts[t]} {t}" for t in STATUS_TOKENS) + ")",
        "",
        "## All records",
        "",
        "| DR | Title | Status | Status text | Date | Age (days) | Supersedes | Superseded by | Spec lines affected |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        age = (as_of - r.date).days
        spec = "<br>".join(_cell(x) for x in r.spec_lines)
        out.append(
            f"| {r.number} | [{_cell(r.title)}]({r.filename}) | {r.status_token} "
            f"| {_cell(r.status_text)} | {r.date.isoformat()} | {age} "
            f"| {_cell(r.supersedes)} | {_cell(r.superseded_by)} | {spec} |"
        )
    aged = [r for r in records
            if r.status_token == "proposed" and (as_of - r.date).days >= threshold_days]
    out += [
        "",
        "## Aged proposed records",
        "",
        f"Records whose status token is `proposed` and whose age at the as-of date is "
        f"at least {threshold_days} days. Age and status alone do not show that any "
        "implementation artifact depends on a record; this is not a dependency list.",
        "",
    ]
    if aged:
        out += ["| DR | Title | Date | Age (days) |", "|---|---|---|---|"]
        for r in aged:
            out.append(f"| {r.number} | [{_cell(r.title)}]({r.filename}) "
                       f"| {r.date.isoformat()} | {(as_of - r.date).days} |")
    else:
        out.append("None.")
    return "\n".join(out) + "\n"


def committed_as_of(status_file: Path) -> dt.date:
    if not status_file.exists():
        raise RecordError(f"{status_file.name}: missing; run the generator without --check")
    m = ASOF_RE.search(status_file.read_text(encoding="utf-8"))
    if not m:
        raise RecordError(f"{status_file.name}: As of: no 'As of: YYYY-MM-DD' line")
    try:
        return parse_iso_date(m.group(1))
    except ValueError as e:
        raise RecordError(f"{status_file.name}: As of: {e}") from None


def generate(dr_dir: Path, as_of: dt.date,
             threshold_days: int = DEFAULT_THRESHOLD_DAYS) -> str:
    return render(load_records(dr_dir, as_of), as_of, threshold_days)


def check(dr_dir: Path, status_file: Path,
          threshold_days: int = DEFAULT_THRESHOLD_DAYS) -> str | None:
    """Return None if fresh, else a unified diff / diagnostic string."""
    as_of = committed_as_of(status_file)
    expected = generate(dr_dir, as_of, threshold_days)
    actual = status_file.read_text(encoding="utf-8")
    if actual == expected:
        return None
    return "".join(difflib.unified_diff(
        actual.splitlines(keepends=True), expected.splitlines(keepends=True),
        fromfile=f"{status_file.name} (committed)",
        tofile=f"{status_file.name} (expected)"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="fail if STATUS.md is stale (reuses its committed As-of date)")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="as-of date for generation (default: current UTC date)")
    ap.add_argument("--threshold-days", type=int, default=DEFAULT_THRESHOLD_DAYS)
    ap.add_argument("--dr-dir", type=Path, default=DR_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--status-file", type=Path, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    status_file = args.status_file or (args.dr_dir / "STATUS.md")

    try:
        if args.check:
            if args.as_of:
                ap.error("--as-of cannot be combined with --check")
            diff = check(args.dr_dir, status_file, args.threshold_days)
            if diff is None:
                print(f"ok: {status_file.name} is up to date")
                return 0
            print(f"error: {status_file.name} is stale; regenerate with "
                  "python3 sim/tools/generate_decision_record_status.py "
                  f"--as-of {committed_as_of(status_file).isoformat()} "
                  "(or omit --as-of to refresh the snapshot date)\n" + diff,
                  file=sys.stderr)
            return 1
        if args.as_of:
            try:
                as_of = parse_iso_date(args.as_of)
            except ValueError as e:
                ap.error(f"--as-of: {e}")
        else:
            as_of = dt.datetime.now(dt.timezone.utc).date()
        status_file.write_text(generate(args.dr_dir, as_of, args.threshold_days),
                               encoding="utf-8")
        print(f"wrote {status_file} (as of {as_of.isoformat()})")
        return 0
    except RecordError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
