#!/usr/bin/env python3
"""Machine-check the evidence citations in `sim/characterization-summary.md`
(issue #437).

`signoff/run_signoff.py --check` proves the summary's bytes are the bytes that
were graded. It cannot prove the records the summary cites are still the
current ones. This checker closes that gap for the one table T1 item 8 grades
-- the `Source (dated)` column of the table under `## Per-spec-row status` --
and for nothing else (narrative, history prose and other sections are out of
scope on purpose).

Contract (the summary's side)
-----------------------------
Every link in that column whose destination is a `sim/` record
(`<campaign>/records/<YYYYMMDD-HHMMSS-hash>.md`, relative to `sim/`) must be
followed *immediately* by exactly one citation-local marker:

    <!-- evidence role=<governing|current|historical> mode=<schematic|extracted|other> -->

* `role` is the author's statement of what the citation is for: `governing`
  (the result the row's verdict rests on), `current` (a still-current
  companion result, e.g. the schematic side next to a governing extraction)
  or `historical` (retained history; never a freshness failure).
* `mode` must equal the mode the cited record declares in its own
  `**Netlist provenance**` field (`schematic...` / `extracted...`; anything
  else is `other`). Roles are never inferred from link order, bold text or
  prose such as "supersedes" in the cell.

Rows with no sim-record link are valid. Links to anything other than a sim
record (decision records, READMEs, layout records, ...) are outside the check.

Freshness rule (governing/current citations only)
-------------------------------------------------
Records are grouped by campaign (`sim/<campaign>/records/`) and by the mode
their own provenance declares; schematic results are never compared with
extracted ones.

1. **Successor chain.** Follow record-declared `- **Supersedes**:` edges
   (bare record IDs, resolved within the same campaign) forward from the
   cited record. Every reachable same-mode record with no same-mode successor
   of its own is a *successor*: the citation is stale.
2. **Unlinked newer candidate.** Every same-campaign, same-mode record whose
   filename timestamp is newer than the cited record's, that is not on the
   cited record's successor chain and has no same-mode successor of its own,
   is reported as an *unresolved candidate* -- unless that record is itself
   linked in the same row, where its own marker already classifies it (the
   paired-arm rows cite both arms). A newer filename does not prove
   comparable coverage (it may be a candidate design, a different scope, a
   paired-arm experiment...), so the checker never calls it a replacement --
   but it also never lets it pass silently.

Either finding fails unless `sim/tools/characterization_citation_exceptions.json`
holds an entry for the exact tuple (spec row label, mode, cited record path,
newer record path) with a non-empty reason. There are no wildcards: an
exception authorizes retaining that one citation against that one newer
record, nothing else, and it never authorizes weakening a verdict or a
ratified spec. Unused, duplicate, malformed or dangling exceptions fail too.

Also fails on: a missing/duplicate section heading or column header, a row
whose width differs from the header, an unescaped pipe inside inline code
(GitHub splits cells there, naive readers do not -- ambiguous), a link that
does not parse, a non-canonical destination for a sim record (`./x`,
`../sim/x`, absolute, URL, fragment), a missing/malformed/orphan/duplicate
marker, contradictory markers for one record in one row, a record that does
not exist, a malformed record filename, a dangling or ambiguous
`Supersedes` reference, a `Supersedes` cycle, and a table that parses to zero
rows.

Ordering uses the timestamp prefix of committed filenames, never mtime. No
numbers are re-derived and no verdict is changed by this tool.

Stdlib-only, no PDK / ngspice / klt / network, so it belongs on the headless
CI path (.github/workflows/ci.yml) and in `npm run check:ci`.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_REL = "sim/characterization-summary.md"
EXCEPTIONS_REL = "sim/tools/characterization_citation_exceptions.json"

SECTION_HEADING = "## Per-spec-row status"
EXPECTED_HEADER = [
    "Spec row (README target)",
    "Target",
    "Latest verified value",
    "Verdict",
    "Source (dated)",
]
SOURCE_COL = EXPECTED_HEADER.index("Source (dated)")

ROLES = ("governing", "current", "historical")
MODES = ("schematic", "extracted", "other")

RECORD_NAME_RE = re.compile(r"^(?P<ts>\d{8}-\d{6})-[0-9a-f]{7,40}\.md$")
CANONICAL_DEST_RE = re.compile(r"^(?P<campaign>[A-Za-z0-9][A-Za-z0-9._-]*)/records/(?P<name>[^/]+)$")
LINK_RE = re.compile(r"\[(?P<text>[^\[\]]*)\]\((?P<dest>[^()\s]*)\)")
MARKER_ANY_RE = re.compile(r"<!--\s*evidence\b.*?-->", re.S)
MARKER_EXACT_RE = re.compile(r"<!-- evidence role=(?P<role>[a-z]+) mode=(?P<mode>[a-z]+) -->")
SUPERSEDES_FIELD_RE = re.compile(r"^- \*\*Supersedes\*\*:\s*(?P<value>.*)$")
PROVENANCE_FIELD_RE = re.compile(r"^- \*\*Netlist provenance\*\*:\s*(?P<value>.*)$")
ID_TOKEN = r"`?(?P<id>\d{8}-\d{6}(?:-[0-9a-f]+)?)(?:\.md)?`?"
SUPERSEDES_LIST_RE = re.compile(
    r"^\s*" + ID_TOKEN.replace("?P<id>", "") + r"(?:\s*(?:,|\+|\band\b)\s*" + ID_TOKEN.replace("?P<id>", "") + r")*"
)
ID_FIND_RE = re.compile(r"\d{8}-\d{6}(?:-[0-9a-f]+)?")
# What may follow the ID list in a Supersedes value: end, or prose introduced
# by a clear separator.
SUPERSEDES_TAIL_RE = re.compile(r"^\s*(?:$|—|–|--|-|\(|;|:|\.|,)")


class CheckError(Exception):
    """A structural problem that makes further checking meaningless."""


# --------------------------------------------------------------------------
# Markdown table parsing
# --------------------------------------------------------------------------

def split_row(line: str, lineno: int) -> list[str]:
    """Split one GFM table row into raw cell strings.

    `\\|` is a literal pipe. An unescaped `|` inside an inline code span is
    rejected: GitHub ends the cell there, a code-span-aware reader does not,
    so the row means different things to different readers.
    """
    s = line.rstrip()
    if not (s.startswith("|") and s.endswith("|")) or len(s) < 2:
        raise CheckError(f"{SUMMARY_REL}:{lineno}: table row must start and end with '|'")
    cells: list[str] = []
    buf: list[str] = []
    i, n = 0, len(s)
    code_run = 0  # backtick-run length of the open code span, 0 = none
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n:
            buf.append(s[i:i + 2])
            i += 2
            continue
        if ch == "`":
            j = i
            while j < n and s[j] == "`":
                j += 1
            run = j - i
            if code_run == 0:
                code_run = run
            elif run == code_run:
                code_run = 0
            buf.append(s[i:j])
            i = j
            continue
        if ch == "|":
            if code_run:
                raise CheckError(
                    f"{SUMMARY_REL}:{lineno}: unescaped '|' inside inline code is ambiguous "
                    "(GitHub splits the cell there); escape it as '\\|'"
                )
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if code_run:
        raise CheckError(f"{SUMMARY_REL}:{lineno}: unterminated inline code span in table row")
    if buf and "".join(buf).strip():
        raise CheckError(f"{SUMMARY_REL}:{lineno}: text after the closing '|'")
    # cells[0] is the empty string before the leading pipe.
    return cells[1:]


@dataclass
class Row:
    lineno: int
    label: str
    cells: list[str]


def parse_table(text: str) -> list[Row]:
    lines = text.splitlines()
    heads = [i for i, l in enumerate(lines) if l.rstrip() == SECTION_HEADING]
    near = [i for i, l in enumerate(lines)
            if l.lstrip("#").strip().lower() == SECTION_HEADING.lstrip("#").strip().lower()
            and l.startswith("#")]
    if len(near) > 1 or len(heads) > 1:
        raise CheckError(f"{SUMMARY_REL}: section heading '{SECTION_HEADING}' appears more than once")
    if not heads:
        raise CheckError(f"{SUMMARY_REL}: section heading '{SECTION_HEADING}' not found")
    i = heads[0] + 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not lines[i].startswith("|"):
        raise CheckError(f"{SUMMARY_REL}:{i + 1}: no table directly under '{SECTION_HEADING}'")
    header = [c.strip() for c in split_row(lines[i], i + 1)]
    if len(set(header)) != len(header):
        raise CheckError(f"{SUMMARY_REL}:{i + 1}: duplicate column header in {header}")
    if header != EXPECTED_HEADER:
        raise CheckError(
            f"{SUMMARY_REL}:{i + 1}: table header {header} != expected {EXPECTED_HEADER}"
        )
    i += 1
    if i >= len(lines):
        raise CheckError(f"{SUMMARY_REL}: table header has no separator row")
    sep = [c.strip() for c in split_row(lines[i], i + 1)]
    if len(sep) != len(header) or not all(re.fullmatch(r":?-{3,}:?", c) for c in sep):
        raise CheckError(f"{SUMMARY_REL}:{i + 1}: malformed separator row under the table header")
    i += 1
    rows: list[Row] = []
    while i < len(lines) and lines[i].startswith("|"):
        cells = split_row(lines[i], i + 1)
        if len(cells) != len(header):
            raise CheckError(
                f"{SUMMARY_REL}:{i + 1}: row has {len(cells)} cells, header has {len(header)}"
            )
        label = cells[0].strip()
        if not label:
            raise CheckError(f"{SUMMARY_REL}:{i + 1}: empty spec-row label")
        rows.append(Row(i + 1, label, cells))
        i += 1
    # Nothing else in this section may look like a table: a second table
    # (or a row split off by a blank line) would otherwise be skipped.
    while i < len(lines) and not lines[i].startswith("## "):
        if lines[i].lstrip().startswith("|"):
            raise CheckError(
                f"{SUMMARY_REL}:{i + 1}: table-like line after the end of the "
                f"'{SECTION_HEADING}' table (blank line inside the table, or a second table)"
            )
        i += 1
    if not rows:
        raise CheckError(f"{SUMMARY_REL}: '{SECTION_HEADING}' table has zero rows")
    labels = [r.label for r in rows]
    dups = sorted({l for l in labels if labels.count(l) > 1})
    if dups:
        raise CheckError(f"{SUMMARY_REL}: duplicate spec-row label(s): {dups}")
    return rows


# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------

@dataclass
class Citation:
    row: str
    lineno: int
    path: str  # repo-relative, e.g. sim/adc-power/records/<id>.md
    campaign: str
    role: str
    mode: str


def parse_citations(rows: list[Row], problems: list[str]) -> list[Citation]:
    out: list[Citation] = []
    for row in rows:
        cell = row.cells[SOURCE_COL]
        where = f"{SUMMARY_REL}:{row.lineno} [{row.label}]"
        consumed: list[tuple[int, int]] = []
        used_markers: set[int] = set()
        seen: dict[str, tuple[str, str]] = {}
        for m in LINK_RE.finditer(cell):
            consumed.append(m.span())
            dest = m.group("dest")
            rec = classify_destination(dest, where, problems)
            if rec is None:
                continue
            campaign, name = rec
            path = f"sim/{campaign}/records/{name}"
            rest = cell[m.end():]
            lead = len(rest) - len(rest.lstrip(" "))
            mk = MARKER_ANY_RE.match(rest, lead)
            if not mk:
                problems.append(f"{where}: {path}: missing '<!-- evidence role=... mode=... -->' marker "
                                "immediately after the link")
                continue
            used_markers.add(m.end() + mk.start())
            exact = MARKER_EXACT_RE.fullmatch(mk.group(0))
            if not exact:
                problems.append(f"{where}: {path}: malformed evidence marker {mk.group(0)!r}")
                continue
            role, mode = exact.group("role"), exact.group("mode")
            bad = False
            if role not in ROLES:
                problems.append(f"{where}: {path}: unknown role {role!r} (expected one of {ROLES})")
                bad = True
            if mode not in MODES:
                problems.append(f"{where}: {path}: unknown mode {mode!r} (expected one of {MODES})")
                bad = True
            if bad:
                continue
            if path in seen and seen[path] != (role, mode):
                problems.append(f"{where}: {path}: contradictory markers in one row "
                                f"({seen[path]} vs {(role, mode)})")
                continue
            seen[path] = (role, mode)
            out.append(Citation(row.label, row.lineno, path, campaign, role, mode))
        # Every evidence marker must belong to a sim-record link.
        for mk in MARKER_ANY_RE.finditer(cell):
            if mk.start() not in used_markers:
                problems.append(f"{where}: evidence marker {mk.group(0)!r} does not immediately "
                                "follow a sim-record link (orphan or duplicate marker)")
        # Anything link-shaped the link regex did not consume is unparseable.
        stripped = list(cell)
        for a, b in consumed:
            stripped[a:b] = [" "] * (b - a)
        leftover = "".join(stripped)
        for bad in ("](", "]["):
            if bad in leftover:
                problems.append(f"{where}: unparseable or unsupported Markdown link near "
                                f"{leftover[max(0, leftover.find(bad) - 40):leftover.find(bad) + 40]!r}")
                break
        if re.search(r"<a\s", leftover, re.I):
            problems.append(f"{where}: raw HTML links are not supported in the source column")
    return out


def classify_destination(dest: str, where: str, problems: list[str]) -> tuple[str, str] | None:
    """Return (campaign, filename) for a sim-record destination, None for
    any other document. Non-canonical spellings of a sim record fail."""
    if not dest:
        problems.append(f"{where}: empty link destination")
        return None
    looks_like_record = "/records/" in dest
    if "://" in dest or dest.startswith(("/", "#", "mailto:")):
        if looks_like_record and "sim/" in dest:
            problems.append(f"{where}: unsupported destination {dest!r} for a sim record "
                            "(use '<campaign>/records/<id>.md', relative to sim/)")
        return None
    bare = dest.split("#", 1)[0].split("?", 1)[0]
    norm = posixpath.normpath(posixpath.join("sim", bare))
    parts = norm.split("/")
    if len(parts) >= 3 and parts[0] == "sim" and "records" in parts[2:]:
        m = CANONICAL_DEST_RE.fullmatch(dest)
        if not m or norm != f"sim/{dest}" or len(parts) != 4:
            problems.append(f"{where}: non-canonical destination {dest!r} for a sim record "
                            f"(resolves to {norm}; write it as '<campaign>/records/<id>.md')")
            return None
        if not RECORD_NAME_RE.fullmatch(m.group("name")):
            problems.append(f"{where}: malformed record filename in {dest!r} "
                            "(expected YYYYMMDD-HHMMSS-<hash>.md)")
            return None
        return m.group("campaign"), m.group("name")
    return None


# --------------------------------------------------------------------------
# Record graph
# --------------------------------------------------------------------------

@dataclass
class Record:
    path: str
    stem: str
    ts: str
    mode: str
    supersedes: list[str] = field(default_factory=list)  # resolved stems


def record_mode(text: str) -> str:
    for line in text.splitlines():
        m = PROVENANCE_FIELD_RE.match(line)
        if m:
            v = m.group("value").lstrip("*` ").lower()
            if v.startswith("schematic"):
                return "schematic"
            if v.startswith("extracted"):
                return "extracted"
            return "other"
    return "other"


def parse_supersedes_value(value: str) -> list[str] | None:
    """Return the ID tokens named by a Supersedes value ([] for none), or
    None when the value is not a recognizable form."""
    v = value.strip()
    if not v or v.startswith("(none") or v.lower().startswith("none"):
        return []
    m = SUPERSEDES_LIST_RE.match(v)
    if not m or not SUPERSEDES_TAIL_RE.match(v[m.end():]):
        return None
    return ID_FIND_RE.findall(m.group(0))


class Campaign:
    def __init__(self, repo: Path, name: str, problems: list[str]):
        self.name = name
        self.records: dict[str, Record] = {}
        rdir = repo / "sim" / name / "records"
        raw: dict[str, list[str]] = {}
        for p in sorted(rdir.iterdir()) if rdir.is_dir() else []:
            rel = f"sim/{name}/records/{p.name}"
            if not p.is_file():
                continue
            m = RECORD_NAME_RE.fullmatch(p.name)
            if not m:
                problems.append(f"{rel}: malformed record filename (expected "
                                "YYYYMMDD-HHMMSS-<hash>.md); cannot order it")
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            stem = p.name[:-3]
            self.records[stem] = Record(rel, stem, m.group("ts"), record_mode(text))
            vals = [mm.group("value") for mm in map(SUPERSEDES_FIELD_RE.match, text.splitlines()) if mm]
            if len(vals) > 1:
                problems.append(f"{rel}: more than one '- **Supersedes**:' field (ambiguous)")
                continue
            if vals:
                ids = parse_supersedes_value(vals[0])
                if ids is None:
                    problems.append(f"{rel}: unparseable Supersedes value {vals[0][:80]!r} "
                                    "(expected '(none...)' or bare record ID(s))")
                    continue
                raw[stem] = ids
        for stem, ids in raw.items():
            rec = self.records[stem]
            for tok in ids:
                hits = [s for s in self.records if s == tok] or [s for s in self.records if s.startswith(tok)]
                if not hits:
                    problems.append(f"{rec.path}: Supersedes {tok!r} does not resolve to a record "
                                    f"in sim/{name}/records/ (dangling)")
                elif len(hits) > 1:
                    problems.append(f"{rec.path}: Supersedes {tok!r} is ambiguous in "
                                    f"sim/{name}/records/: {sorted(hits)}")
                elif hits[0] == stem:
                    problems.append(f"{rec.path}: Supersedes names itself (cycle)")
                else:
                    rec.supersedes.append(hits[0])
        # successor (reverse) edges
        self.successors: dict[str, list[str]] = {s: [] for s in self.records}
        for stem, rec in self.records.items():
            for pred in rec.supersedes:
                self.successors[pred].append(stem)
        self.cyclic = self._find_cycles(problems)

    def _find_cycles(self, problems: list[str]) -> bool:
        WHITE, GREY, BLACK = 0, 1, 2
        color = {s: WHITE for s in self.records}
        found = False

        def visit(s: str, stack: list[str]) -> None:
            nonlocal found
            color[s] = GREY
            stack.append(s)
            for t in self.records[s].supersedes:
                if color[t] == GREY:
                    cyc = stack[stack.index(t):] + [t]
                    problems.append(f"sim/{self.name}/records/: Supersedes cycle: {' -> '.join(cyc)}")
                    found = True
                elif color[t] == WHITE:
                    visit(t, stack)
            stack.pop()
            color[s] = BLACK

        for s in sorted(self.records):
            if color[s] == WHITE:
                visit(s, [])
        return found

    def reachable(self, stem: str) -> dict[str, list[str]]:
        """All records reachable forward along successor edges, with one path each."""
        seen: dict[str, list[str]] = {}
        frontier = [(stem, [stem])]
        while frontier:
            cur, path = frontier.pop()
            for nxt in sorted(self.successors[cur]):
                if nxt not in seen and nxt != stem:
                    seen[nxt] = path + [nxt]
                    frontier.append((nxt, path + [nxt]))
        return seen

    def has_same_mode_successor(self, stem: str) -> bool:
        mode = self.records[stem].mode
        return any(self.records[s].mode == mode for s in self.reachable(stem))


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

EXC_KEYS = {"row", "mode", "cited", "newer", "reason"}


def load_exceptions(data: object, repo: Path, row_labels: set[str], problems: list[str]) -> dict[tuple, str]:
    where = EXCEPTIONS_REL
    if not isinstance(data, dict) or not isinstance(data.get("exceptions"), list):
        problems.append(f"{where}: top level must be an object with an 'exceptions' list")
        return {}
    extra = set(data) - {"exceptions", "_comment"}
    if extra:
        problems.append(f"{where}: unknown top-level key(s) {sorted(extra)}")
    out: dict[tuple, str] = {}
    for n, e in enumerate(data["exceptions"]):
        tag = f"{where}: exceptions[{n}]"
        if not isinstance(e, dict) or set(e) != EXC_KEYS:
            problems.append(f"{tag}: must have exactly the keys {sorted(EXC_KEYS)}")
            continue
        if not all(isinstance(e[k], str) for k in EXC_KEYS):
            problems.append(f"{tag}: every field must be a string")
            continue
        if not e["reason"].strip():
            problems.append(f"{tag}: empty reason")
            continue
        ok = True
        for k in ("row", "mode", "cited", "newer"):
            if not e[k].strip() or any(ch in e[k] for ch in "*?[]"):
                problems.append(f"{tag}: {k} {e[k]!r} is empty or a wildcard; exceptions are exact")
                ok = False
        if not ok:
            continue
        if e["row"] not in row_labels:
            problems.append(f"{tag}: row {e['row']!r} is not a spec-row label in the table")
            ok = False
        if e["mode"] not in MODES:
            problems.append(f"{tag}: mode {e['mode']!r} not one of {MODES}")
            ok = False
        camps = []
        for k in ("cited", "newer"):
            m = re.fullmatch(r"sim/([^/]+)/records/([^/]+)", e[k])
            if not m or not RECORD_NAME_RE.fullmatch(m.group(2)):
                problems.append(f"{tag}: {k} {e[k]!r} is not a 'sim/<campaign>/records/<id>.md' path")
                ok = False
            elif not (repo / e[k]).is_file():
                problems.append(f"{tag}: {k} {e[k]!r} does not exist")
                ok = False
            else:
                camps.append(m.group(1))
        if ok and camps[0] != camps[1]:
            problems.append(f"{tag}: cited and newer are in different campaigns")
            ok = False
        if ok and e["cited"] == e["newer"]:
            problems.append(f"{tag}: cited and newer are the same record")
            ok = False
        if not ok:
            continue
        key = (e["row"], e["mode"], e["cited"], e["newer"])
        if key in out:
            problems.append(f"{tag}: duplicate exception for {key}")
            continue
        out[key] = e["reason"]
    return out


# --------------------------------------------------------------------------
# Main check
# --------------------------------------------------------------------------

def check(repo: Path, summary_text: str, exceptions_data: object) -> list[str]:
    problems: list[str] = []
    try:
        rows = parse_table(summary_text)
    except CheckError as exc:
        return [str(exc)]
    cites = parse_citations(rows, problems)

    campaigns: dict[str, Campaign] = {}
    for c in cites:
        if c.campaign not in campaigns:
            campaigns[c.campaign] = Campaign(repo, c.campaign, problems)

    exceptions = load_exceptions(exceptions_data, repo, {r.label for r in rows}, problems)
    used: set[tuple] = set()
    linked_in_row: dict[str, set[str]] = {}
    for c in cites:
        linked_in_row.setdefault(c.row, set()).add(c.path)

    for c in cites:
        where = f"{SUMMARY_REL}:{c.lineno} [{c.row}]"
        camp = campaigns[c.campaign]
        stem = posixpath.basename(c.path)[:-3]
        rec = camp.records.get(stem)
        if rec is None:
            problems.append(f"{where}: cited record {c.path} does not exist")
            continue
        if rec.mode != c.mode:
            problems.append(f"{where}: {c.path}: marker says mode={c.mode} but the record's own "
                            f"Netlist provenance says {rec.mode}")
            continue
        if c.role == "historical" or camp.cyclic:
            continue
        reach = camp.reachable(stem)
        succ = {s: p for s, p in reach.items()
                if camp.records[s].mode == c.mode and not camp.has_same_mode_successor(s)}
        cands = sorted(
            s for s, r in camp.records.items()
            if s != stem and s not in reach and r.mode == c.mode and r.ts > rec.ts
            and not camp.has_same_mode_successor(s)
            # Linked in this same row: its own marker already classifies it.
            and r.path not in linked_in_row[c.row]
        )
        for s in sorted(succ):
            newer = camp.records[s].path
            key = (c.row, c.mode, c.path, newer)
            if key in exceptions:
                used.add(key)
                continue
            problems.append(
                f"{where}: STALE {c.role} {c.mode} citation {c.path} -- superseded via "
                f"{' -> '.join(succ[s])}; successor {newer}"
            )
        for s in cands:
            newer = camp.records[s].path
            key = (c.row, c.mode, c.path, newer)
            if key in exceptions:
                used.add(key)
                continue
            problems.append(
                f"{where}: UNCLASSIFIED newer {c.mode} record {newer} for {c.role} citation "
                f"{c.path} (not on its Supersedes chain) -- cite it, or add an exact exception "
                f"to {EXCEPTIONS_REL} explaining why it is not a replacement"
            )
    for key in sorted(set(exceptions) - used):
        problems.append(f"{EXCEPTIONS_REL}: unused exception {key} -- remove it")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--summary", type=Path, help="summary to check (default: %s)" % SUMMARY_REL)
    ap.add_argument("--exceptions", type=Path, help="exception file (default: %s)" % EXCEPTIONS_REL)
    ap.add_argument("--list", action="store_true", help="print every classified citation")
    args = ap.parse_args(argv)
    repo = args.repo
    summary = args.summary or repo / SUMMARY_REL
    exc_path = args.exceptions or repo / EXCEPTIONS_REL
    text = summary.read_text(encoding="utf-8")
    try:
        data = json.loads(exc_path.read_text(encoding="utf-8")) if exc_path.exists() else {"exceptions": []}
    except json.JSONDecodeError as exc:
        print(f"FAIL: {EXCEPTIONS_REL}: invalid JSON: {exc}")
        return 1
    if args.list:
        probs: list[str] = []
        try:
            for c in parse_citations(parse_table(text), probs):
                print(f"{c.lineno}\t{c.row}\t{c.role}\t{c.mode}\t{c.path}")
        except CheckError as exc:
            print(exc)
    problems = check(repo, text, data)
    if problems:
        print(f"FAIL: {SUMMARY_REL} evidence citations: {len(problems)} problem(s):")
        for p in problems:
            print(f"  {p}")
        return 1
    n = len(parse_citations(parse_table(text), []))
    print(f"ok: {n} sim-record citation(s) in '{SECTION_HEADING}' classified; no stale or "
          "unclassified governing/current evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
