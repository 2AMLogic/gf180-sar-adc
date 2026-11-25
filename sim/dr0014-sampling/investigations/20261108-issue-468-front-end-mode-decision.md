# Investigation 20261108-issue-468-front-end-mode-decision

Not a `sim/run_corners.py` evidence record; scores no PVT grid. No simulation
was run for this note.

- **Issue**: #468 (follows #459 and #623).
- **Decision**: ngspice's front-end mode stays **host-controlled**. The harness
  does not write a `.spiceinit`, and no simulation default changes, so no
  `spec/` decision record is needed.
- **Reason**: the controlled one-binary A/B this issue asked for was already
  run by #623 and committed in
  [`20261021-issue-623-compat-probe.txt`](20261021-issue-623-compat-probe.txt)
  (summary in [`20261021-issue-623-tp-inj-host-offset.md`](20261021-issue-623-tp-inj-host-offset.md)).
  Same ngspice-46 binary on `loom-worker-1` (full banner in the probe file), same
  composed deck (`ff_-40c_3.63v`, extracted), one PDK install; arm 1 had no
  `ngbehavior`, arm 2 `set ngbehavior=hsa`. Output differed only in the
  `Note: ... compatibility mode ...` line, so the whole `m_*` set, including
  `tp_inj_signal_dep_lsb`, was identical. Pinning the mode therefore would not
  remove the Linux/macOS gap; the remaining suspects (macOS build/platform,
  other init state, PDK bytes) are what the new record provenance exposes.
- **Not re-run here.** This issue's live-A/B criterion is satisfied only by
  citing #623's evidence, not by a new run; that probe was one corner on one
  worker and is diagnostic. I did not re-compare the five sampled top-plate
  values or accepted-timepoint counts beyond what #623's diff shows (identical
  output apart from the note). The macOS-side run #623 named remains undone.
- **What changed instead**: records now carry platform, hostname, the full
  banner and the per-point observed compatibility note (see
  `sim/harness/README.md`, "Execution-environment provenance").
