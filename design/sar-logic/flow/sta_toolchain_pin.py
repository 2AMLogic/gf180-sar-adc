"""Enforce `design/sar-logic/flow/toolchain.json` for the extracted-SPEF STA
flow (issue #486). Import-only; runs no tool at import time.

Reuses `layout/toolchain_pin.py` (loader + verb check); adds the two things
that flow needs beyond it: an exact `klt --version` identity match and the
`klt extract` flag list.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import flow_env  # noqa: F401  (puts layout/ on sys.path)
import toolchain_pin as _pin

PIN_PATH = Path(__file__).resolve().with_name("toolchain.json")


def load_pin(path: Path = PIN_PATH) -> dict:
    return _pin.load_toolchain_pin(str(path))


def pin_error(klt: str = "klt", pin: dict | None = None, pin_path: Path = PIN_PATH) -> str | None:
    """Error text if `klt` does not satisfy the pin, else None. Names the install
    command. A malformed pin or absent `klt` is an error, never a pass."""
    try:
        pin = pin if pin is not None else load_pin(pin_path)
        want = pin["klt_version"]
        install = pin["klt_install"]
    except (OSError, ValueError, KeyError) as exc:
        return f"cannot read extract/sta toolchain pin {pin_path}: {exc!r}"
    hint = f'Run under a throwaway env: uvx --from "{install}" klt ... (do not change the host tool).'
    try:
        got = subprocess.run([klt, "--version"], capture_output=True, text=True, check=False)
    except OSError as exc:
        return f"`{klt}` not runnable ({exc}). {hint}"
    ident = (got.stdout + got.stderr).strip()
    if ident != want:
        return f"klt identity {ident!r} does not match pin {want!r}. {hint}"
    err = _pin.klt_capability_error(klt, pin, str(pin_path))
    if err:
        return err
    flags = pin.get("klt_required_extract_flags", [])
    ext = subprocess.run([klt, "extract", "--help"], capture_output=True, text=True, check=False)
    absent = [f for f in flags if f not in ext.stdout]
    if absent:
        return f"klt extract lacks required flag(s) {', '.join(absent)}. {hint}"
    return None
