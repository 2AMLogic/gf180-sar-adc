# gf180-sar-adc -- one-command entry points for independent verification.
#
# Written for the Chipalooza schematic-review bar: "It must be possible for
# me to independently run simulations to verify the performance of the
# circuit ... in the form of a shell script or a Makefile target such that
# full characterization can be done from a single command-line command."
#
# See README.md#independent-verification-chipalooza for prerequisites,
# expected wall-clock, core count, and how each target's output maps to
# docs/chipalooza/challenge-3-proposal.md Sec 4's spec-row table. All three
# targets exit non-zero on any failure.
#
#   make check         Unit tests + syntax checks + toolchain/PDK env check.
#                       No PDK required to PASS this target (it reports
#                       whether one is installed); seconds.
#   make smoke          One nominal PVT corner (tt / 27 C / nominal supply)
#                       across every characterization campaign behind the
#                       Chipalooza proposal's spec table, writing no
#                       evidence. Needs ngspice + the gf180mcu PDK. Minutes,
#                       not hours.
#   make characterize    The full PVT/corner campaign behind every spec row
#                       in docs/chipalooza/challenge-3-proposal.md Sec 4,
#                       minting a new, dated sim/<experiment>/records/ entry
#                       per campaign (append-only, per sim/README.md). Needs
#                       ngspice + the gf180mcu PDK. Hours -- see README.md
#                       for the current wall-clock estimate.

.PHONY: help check smoke characterize

help:
	@echo "make check         unit tests + syntax + env check (seconds, no PDK required to run)"
	@echo "make smoke          one nominal corner, every campaign, writes no evidence (minutes, needs PDK)"
	@echo "make characterize    full PVT campaign, mints sim/ evidence records (hours, needs PDK)"
	@echo "See README.md#independent-verification-chipalooza"

check:
	@npm run --silent check:ci
	@status=0; python3 sim/run_corners.py --check-env || status=$$?; \
	if [ "$$status" -eq 1 ]; then \
		echo "FAIL: installed toolchain drifted from sim/toolchain.json (see docs/environment-setup.md)"; \
		exit 1; \
	elif [ "$$status" -ne 0 ]; then \
		echo "SKIP: ngspice and/or the gf180mcu PDK are not installed -- 'make smoke' / 'make characterize' need them."; \
		echo "      See README.md#independent-verification-chipalooza."; \
	else \
		echo "env check: OK (ngspice + gf180mcu PDK present, toolchain pins match sim/toolchain.json)"; \
	fi

smoke:
	bash sim/characterize.sh smoke

characterize:
	bash sim/characterize.sh characterize
