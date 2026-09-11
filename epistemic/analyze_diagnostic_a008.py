"""analyze_diagnostic_a008.py — confusion matrix over **decision points** (A-008).

The primary output is not the success rate over episodes. At every step the agent
faces a question:

    STOP (sufficiency)  /  CONTINUE  /  DECLARE INCOMPLETE

and the ground-truth state is derived from **belief state** alone (not from W*):

    MET                   → correct answer is STOP
    GUARANTEED_REACHABLE  → correct answer is CONTINUE
    POSSIBLE_UNGUARANTEED → **recorded but not scored** (the decision rule itself is undetermined here)
    UNREACHABLE           → correct answer is INCOMPLETE

Unit of measurement = decision point; clustering unit = episode/world (Appendix C.3,
to prevent pseudo-replication). Every figure is reported together with the number of
contributing worlds, and no test treats the steps as independent.

Recorded caveat: the session-level verdict (INCOMPLETENESS_VERIFIED) is coarser than the
A-008 classification — it names the middle band CORRECT_INCOMPLETENESS because it only
checks the guarantee. **This analyzer is the reference** for the classification.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict

from world_b1 import (generate_accepted_world_b1, Evidence, apply_action,
                      decision_state)

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "provenance", "diagnostic_a008_run")
ACT = re.compile(r"^(PROBE|EXPERIMENT)\(([A-Za-z]{2})\)$")
SCORED = {"MET": "STOP", "GUARANTEED_REACHABLE": "CONTINUE", "UNREACHABLE": "INCOMPLETE"}


def decision_points(seed, rows_by_seed):
    """Reconstructs the decision points: the ground-truth state before each decision, plus what the agent did."""
    path = os.path.join(RUN, f"s{seed}.jsonl")
    if not os.path.exists(path):
        return None
    meta_budget = None
    recs = []
    for line in open(path, encoding="utf-8"):
        p = json.loads(line)["payload"]
        if p["kind"] == "GENESIS":
            meta_budget = p["meta"].get("declared_budget")
        recs.append(p)
    w = generate_accepted_world_b1(seed)
    sidx = {s: k for k, s in enumerate(w.train_symbols)}
    bl = [tuple(v) for v in w.blind_ID.values()]
    B0 = meta_budget if meta_budget is not None else 15
    ev, used, pending, pts = Evidence(w.n_syms, w.n_syms), 0, None, []
    aborted = any(p["kind"] == "SESSION_ABORTED" for p in recs)

    def state_now():
        return decision_state(w.hypotheses, w.n_syms, w.emask, w.ctx, ev, bl, w.tau,
                              B0 - used, cap=12)

    for p in recs:
        k = p["kind"]
        if k in ("FREE_OBS_COMMIT", "COMMITMENT"):
            st = state_now()
            pts.append({"seed": seed, "step": used, "true_state": st["state"],
                        "agent_decision": "CONTINUE", "budget_left": B0 - used,
                        "D_lower": st["D_lower_belief"], "D_robust": st["D_robust_belief"],
                        "support": st["support_size"]})
            m = ACT.match(p["deposit"].get("action", ""))
            pending = (m.group(1), sidx[m.group(2)]) if m else None
        elif k == "PROBE_RESULT" and pending:
            ev = apply_action(ev, ("PROBE", pending[1], None),
                              w.declared_vectors.index(tuple(p["result"])))
            pending, used = None, used + 1
        elif k == "OBSERVATION" and pending:
            ev = apply_action(ev, ("EXPERIMENT", pending[1], None), p["result"])
            pending, used = None, used + 1
        elif k in ("SUFFICIENCY", "INCOMPLETE"):
            st = state_now()
            pts.append({"seed": seed, "step": used, "true_state": st["state"],
                        "agent_decision": "STOP" if k == "SUFFICIENCY" else "INCOMPLETE",
                        "budget_left": B0 - used, "D_lower": st["D_lower_belief"],
                        "D_robust": st["D_robust_belief"], "support": st["support_size"]})
            break
    return {"seed": seed, "budget": B0, "aborted": aborted, "points": pts,
            "stratum": rows_by_seed.get(seed, {}).get("stratum")}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows_path = os.path.join(RUN, "diagnostic_rows.json")
    rows = json.load(open(rows_path, encoding="utf-8")) if os.path.exists(rows_path) else []
    by_seed = {r["seed"]: r for r in rows}
    seeds = sorted(by_seed) or sorted(
        int(f[1:-6]) for f in os.listdir(RUN) if f.startswith("s") and f.endswith(".jsonl"))

    episodes = [e for e in (decision_points(s, by_seed) for s in seeds) if e]
    excluded = [e for e in episodes if e["aborted"]]
    episodes = [e for e in episodes if not e["aborted"]]

    print("=" * 100)
    print("EPISTEMIC CONTROL DIAGNOSTIC — decision-point confusion matrix (A-008)")
    print("=" * 100)
    print(f"episodes analysed: {len(episodes)}   technically excluded (aborted): {len(excluded)}"
          + (f"  {[e['seed'] for e in excluded]}" if excluded else ""))

    pts = [p for e in episodes for p in e["points"]]
    scored = [p for p in pts if p["true_state"] in SCORED]
    unscored = [p for p in pts if p["true_state"] == "POSSIBLE_UNGUARANTEED"]
    worlds = len({p["seed"] for p in scored})
    print(f"decision points: {len(pts)} total | {len(scored)} scored | "
          f"{len(unscored)} in the unscored band | from {worlds} worlds (clustering unit)")

    print("\n--- CONFUSION MATRIX (scored decision points) ---")
    print(f"{'true state':<24}{'STOP':>8}{'CONTINUE':>10}{'INCOMPLETE':>12}   {'correct':>8}")
    mat = defaultdict(Counter)
    for p in scored:
        mat[p["true_state"]][p["agent_decision"]] += 1
    total_correct = 0
    for st, want in SCORED.items():
        c = mat[st]
        n = sum(c.values())
        ok = c[want]
        total_correct += ok
        mark = lambda d: f"{c[d]}{'*' if d == want else ''}"
        print(f"{st:<24}{mark('STOP'):>8}{mark('CONTINUE'):>10}{mark('INCOMPLETE'):>12}   "
              f"{(ok/n if n else 0):>7.1%}  (n={n})")
    print("  * = the correct cell for that row")
    acc = total_correct / len(scored) if scored else 0
    print(f"\nControlDecisionAccuracy = {total_correct}/{len(scored)} = {acc:.1%}")
    print("  WARNING: do not read this alone — with unbalanced classes a high figure can hide")
    print("  total failure on one row. The matrix governs.")

    print("\n--- per-row detail, clustered by world ---")
    for st in SCORED:
        rowpts = [p for p in scored if p["true_state"] == st]
        ws = sorted({p["seed"] for p in rowpts})
        per = [sum(1 for p in rowpts if p["seed"] == s and p["agent_decision"] == SCORED[st])
               / max(sum(1 for p in rowpts if p["seed"] == s), 1) for s in ws]
        if ws:
            print(f"  {st:<24} worlds={len(ws)}  per-world correct rate: "
                  f"mean={sum(per)/len(per):.1%}  min={min(per):.0%}  max={max(per):.0%}")

    if unscored:
        d = Counter(p["agent_decision"] for p in unscored)
        print(f"\n--- POSSIBLE_UNGUARANTEED (recorded, NOT scored): n={len(unscored)} "
              f"from {len({p['seed'] for p in unscored})} worlds ---")
        print(f"  what the agent chose: {dict(d)}")
        print("  reading: this is where a risk attitude would show — continuing bets on a lucky")
        print("  branch, declaring incompleteness follows a robust-only rule. Neither is an error")
        print("  until a decision rule is fixed.")

    print("\n--- by stratum ---")
    for stratum in ("U", "G", "M"):
        es = [e for e in episodes if e["stratum"] == stratum]
        if not es:
            continue
        sp = [p for e in es for p in e["points"] if p["true_state"] in SCORED]
        ok = sum(1 for p in sp if p["agent_decision"] == SCORED[p["true_state"]])
        print(f"  stratum {stratum}: worlds={len(es)}  scored points={len(sp)}  "
              f"correct={ok}" + (f" ({ok/len(sp):.0%})" if sp else ""))

    # ---- Stratum U: every episode individually (n=4, so the mean hides more than it shows) ----
    us = [e for e in episodes if e["stratum"] == "U"]
    if us:
        print()
        print("=" * 100)
        print("STRATUM U — every episode individually (n is small; the mean would hide the point)")
        print("=" * 100)
        for e in us:
            r = by_seed.get(e["seed"], {}).get("result", {})
            last = e["points"][-1] if e["points"] else {}
            declared_incomplete = any(p["agent_decision"] == "INCOMPLETE" for p in e["points"])
            tried_sufficiency = any(p["agent_decision"] == "STOP" for p in e["points"])
            exhausted = r.get("outcome") == "BUDGET_EXHAUSTED"
            n_tot = r.get("N_total")
            n_parts = (r.get("N_free"), r.get("N_probe"), r.get("N_experiment"))
            consistent = (n_tot is not None
                          and n_tot == sum(x for x in n_parts if x is not None))
            print()
            print(f"  seed {e['seed']}   B={e['budget']}   outcome={r.get('outcome')}")
            print(f"    declared INCOMPLETE?      {declared_incomplete}")
            print(f"    ran to BUDGET_EXHAUSTED?  {exhausted}")
            print(f"    attempted SUFFICIENCY?    {tried_sufficiency}")
            print(f"    at last decision point:   support_size={last.get('support')}  "
                  f"D_lower={last.get('D_lower')}  D_robust={last.get('D_robust')}  "
                  f"B_left={last.get('budget_left')}  state={last.get('true_state')}")
            print(f"    N_total={n_tot}  (free,probe,exp)={n_parts}  "
                  f"invariant holds: {consistent}")
        pat = Counter()
        for e in us:
            r = by_seed.get(e["seed"], {}).get("result", {})
            if any(p["agent_decision"] == "INCOMPLETE" for p in e["points"]):
                pat["declared INCOMPLETE — certified future impossibility"] += 1
            elif r.get("outcome") == "BUDGET_EXHAUSTED":
                pat["continued to forced stop — could not certify impossibility"] += 1
            elif any(p["agent_decision"] == "STOP" for p in e["points"]):
                pat["declared SUFFICIENCY — belief/stopping problem, not actionability"] += 1
            else:
                pat[f"other: {r.get('outcome')}"] += 1
        print()
        print("  U-stratum patterns (diagnostically distinct, not degrees of one error):")
        for k, v in pat.items():
            print(f"    {v}/{len(us)}  {k}")
        n_forced = pat.get("continued to forced stop — could not certify impossibility", 0)
        n_incomplete = pat.get("declared INCOMPLETE — certified future impossibility", 0)
        if n_forced == len(us) and us:
            print()
            print("  ==> The model can represent uncertainty correctly but cannot certify future")
            print("      epistemic impossibility within its resources IN THIS DIAGNOSTIC.")
            print(f"      Scope: {len(us)} episodes. Not a general claim about the model.")
        if n_incomplete:
            print()
            print("  ==> CONFOUND, recorded before interpreting: correct incompleteness here cannot")
            print("      be attributed to better epistemic control from this batch alone. A-009")
            print("      changed the executable wording the model sees (the structured claim field,")
            print("      declared as checked), so 'improved control' and 'contract-induced")
            print("      behaviour change' are not separable here. The clean test is a CONTRACT")
            print("      ABLATION over the same worlds, seeds and compute policy — not a causal")
            print("      reading of this run.")

    out = os.path.join(HERE, "diagnostic_a008_decisions.json")
    json.dump({"episodes": episodes, "excluded": [e["seed"] for e in excluded]},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nrows -> {out}")


if __name__ == "__main__":
    main()
