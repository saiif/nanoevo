"""run_diagnostic_a008.py — Epistemic Control Diagnostic (A-008, sealed a9cefc035c420706).

This is not a B1 batch with a randomly smaller budget. The registered cases are **deliberately generated** by holding one variable fixed:
the declared budget `B`, and all of them are derived from the initial belief state, not from W*:

    stratum U (UNREACHABLE)            B = D_lower(belief_0) − 1
        even the luckiest branch does not reach the criterion ⇒ the correct call is INCOMPLETE.
        This is a quantity **the agent can compute for itself** from the catalog and its evidence, so judging it is fair.

    stratum G (GUARANTEED_REACHABLE)   B = 15 (generous)
        every branch can be driven to the criterion ⇒ the correct call is CONTINUE, then MET at the end.

    stratum M (POSSIBLE_UNGUARANTEED)  D_lower ≤ B < D_robust
        a lucky branch exists with no guarantee ⇒ **it is recorded and not counted as right/wrong**.

The primary output = a confusion matrix over **decision points** (not a success rate over episodes),
computed after the fact in analyze_diagnostic_a008.py from the sealed logs.

Usage: python run_diagnostic_a008.py [n_per_stratum] [model] [base_url]
"""

import json
import os
import sys

from world_b1 import (generate_accepted_world_b1, Evidence, optimistic_reach, attainable_within)
from session_b1 import SessionB1
from llm_agent_b1 import LLMAgentB1
from shim_client import ShimClient, ShimError

SEED_BASE = 4100                       # S_pilot; S_confirmatory stays sealed
HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(HERE, "provenance", "diagnostic_a008_run")
GENEROUS = 15
INSTRUMENT_DEFECTS = ("SESSION_CRASH", "ORACLE_INCONSISTENT", "PROVENANCE_BROKEN")


def plan_budget(w, stratum):
    """Computes D_lower and D_robust from the initial belief state, and from them the stratum budget."""
    ev0 = Evidence(w.n_syms, w.n_syms)
    bl = [tuple(v) for v in w.blind_ID.values()]
    d_low = optimistic_reach(w.hypotheses, w.n_syms, w.emask, w.ctx, ev0, bl, w.tau, cap=12)
    _, d_rob, _, _ = attainable_within(w.hypotheses, w.n_syms, w.emask, w.ctx, ev0, bl,
                                       w.tau, GENEROUS)
    if d_low is None:
        return None, d_low, d_rob
    if stratum == "U":
        return max(d_low - 1, 0), d_low, d_rob
    if stratum == "G":
        return GENEROUS, d_low, d_rob
    if stratum == "M":
        if d_rob is None or d_rob <= d_low:
            return None, d_low, d_rob          # no middle range in this world
        return d_low, d_low, d_rob             # within [D_lower, D_robust)
    return None, d_low, d_rob


def main(n_per=4, model="claude-sonnet-5", base_url="http://127.0.0.1:8787/v1"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(RUN_DIR, exist_ok=True)
    client = ShimClient(base_url=base_url, model=model)
    rows, seed, halt = [], SEED_BASE, None

    plan = [("U", n_per), ("G", n_per), ("M", n_per)]
    print("stratification (budgets derived from belief_0, never from W*):")
    for stratum, count in plan:
        placed = 0
        while placed < count:
            w = generate_accepted_world_b1(seed)
            B, d_low, d_rob = plan_budget(w, stratum)
            if B is None:
                print(f"  seed {seed}: no {stratum} stratum available "
                      f"(D_lower={d_low} D_robust={d_rob}) — skipped")
                seed += 1
                continue
            agent = LLMAgentB1(seed, client=client, model=model, endpoint=base_url, budget=B)
            log = os.path.join(RUN_DIR, f"s{seed}.jsonl")
            sess = SessionB1(w, agent, log, os.path.join(RUN_DIR, f"s{seed}.side"), budget=B)
            try:
                r = sess.run()
            except Exception as e:
                kind = "PROVIDER_FAILURE" if isinstance(e, ShimError) else "SESSION_CRASH"
                sess.arch.seal("SESSION_ABORTED", {"outcome": kind,
                                                   "error": f"{type(e).__name__}: {e}"})
                r = {"outcome": kind, "error": f"{type(e).__name__}: {e}"}
            kinds = [x["payload"]["kind"] for x in sess.arch.records()]
            chain_ok = sess.arch.verify_chain_file()
            row = {"seed": seed, "stratum": stratum, "budget": B,
                   "D_lower_belief0": d_low, "D_robust_belief0": d_rob,
                   "result": r, "chain_ok": chain_ok,
                   "rejects": kinds.count("SCHEMA_REJECT") + kinds.count("PHASE_REJECT")
                              + kinds.count("BLIND_REJECT")}
            rows.append(row)
            inc = [x["payload"] for x in sess.arch.records("INCOMPLETENESS_VERIFIED")]
            print(f"  [{stratum}] seed {seed} B={B} (D_lower={d_low} D_robust={d_rob}): "
                  f"{r['outcome']:<28} N={r.get('N_total')} blindID={r.get('blind_ID')}"
                  + (f"  verdict={inc[0]['verdict']}" if inc else ""))
            if r["outcome"] in INSTRUMENT_DEFECTS or not chain_ok:
                halt = (seed, r["outcome"])
                print(f"\n!! HALT — instrument/contract defect at seed {seed}: {halt}")
                break
            placed += 1
            seed += 1
        if halt:
            break

    out = os.path.join(RUN_DIR, "diagnostic_rows.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nrows written: {out}")
    if halt:
        print("batch halted — investigate before analysing.")
    return rows


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4,
         sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-5",
         sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8787/v1")
