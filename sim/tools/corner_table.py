"""Read the harness's Markdown per-corner results, including archived ERROR cells."""

from __future__ import annotations

import re
from pathlib import Path


def _cells(line: str) -> list[str]:
    body = line.strip().removeprefix("|").removesuffix("|")
    return [cell.strip().strip("`") for cell in body.split("|")]


def parse_record(path: Path) -> dict[str, dict[str, float | str]]:
    """Read the first corner-id table. Keep verdicts and nonnumeric cells as text."""
    lines = enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
    for _, line in lines:
        if line.lstrip().startswith("|") and _cells(line)[0] == "corner-id":
            header = _cells(line)
            break
    else:
        raise ValueError(f"{path}: no per-corner Result table found")

    rows = {}
    for number, line in lines:
        if not line.lstrip().startswith("|"):
            break
        cells = _cells(line)
        if len(cells) != len(header):
            raise ValueError(
                f"{path}: row {number} has {len(cells)} cells, header has {len(header)}"
            )
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue

        # The harness appended the closing pipe after the simulator's last line.
        if (
            header[-1] == "pass/fail"
            and cells[-1].startswith("ERROR")
            and not line.rstrip().endswith("|")
        ):
            diagnostic = [cells[-1]]
            for _, continuation in lines:
                if (
                    continuation.lstrip().startswith("|")
                    and continuation.strip() != "|"
                ):
                    raise ValueError(
                        f"{path}: unterminated ERROR verdict in row {number}"
                    )
                if continuation.rstrip().endswith("|"):
                    diagnostic.append(continuation.rstrip()[:-1].rstrip())
                    break
                diagnostic.append(continuation)
            else:
                raise ValueError(f"{path}: unterminated ERROR verdict in row {number}")
            cells[-1] = "\n".join(diagnostic)

        row: dict[str, float | str] = {}
        for name, cell in zip(header[1:], cells[1:]):
            try:
                row[name] = float(cell)
            except ValueError:
                row[name] = cell
        rows[cells[0]] = row
    if not rows:
        raise ValueError(f"{path}: Result table has a header but no corner rows")
    return rows


def numeric_points(
    rows: dict[str, dict[str, float | str]],
) -> dict[str, dict[str, float | None]]:
    """Project measurement cells to numbers, retaining explicit gaps in the grid."""
    return {
        corner: {
            name: value if isinstance(value, float) else None
            for name, value in row.items()
            if name not in ("pass/fail", "verdict")
            and (isinstance(value, float) or value in ("", "n/a", "—"))
        }
        for corner, row in rows.items()
    }


def common_measurements(
    left: dict[str, dict[str, float | None]],
    right: dict[str, dict[str, float | None]],
    corners: list[str],
) -> list[str]:
    """Common measurement names in record order, including sparse columns."""
    names = dict.fromkeys(name for c in corners for name in left[c])
    other = {name for c in corners for name in right[c]}
    return [name for name in names if name in other]
