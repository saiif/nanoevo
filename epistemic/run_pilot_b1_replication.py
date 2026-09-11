"""run_pilot_b1_replication.py — R-001 replication batch on seeds 4010-4019.

Does not modify the sealed path at all: it only resets B1_SEED_BASE and RUN_DIR, then calls
run_pilot_b1.main verbatim — same SessionB1, same LLMAgentB1, and the same prompt and adapter
semantics. A separate directory (pilot_b1_replication) so the 4000-4009 provenance is not touched.

The definitions pinned at commit 2441332 are the reference for the analysis after the run — no redefinition.
"""

import os
import sys

import run_pilot_b1

run_pilot_b1.B1_SEED_BASE = 4010
run_pilot_b1.RUN_DIR = os.path.join(
    os.path.dirname(os.path.abspath(run_pilot_b1.__file__)),
    "provenance", "pilot_b1_replication")

if __name__ == "__main__":
    run_pilot_b1.main(
        int(sys.argv[1]) if len(sys.argv) > 1 else 10,
        sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-5",
        sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8787/v1")
