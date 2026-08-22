"""analyze_diagnostic_a008.py — مصفوفة الالتباس على **نقاط القرار** (A-008).

المخرج الأساسي ليس success rate على الحلقات. عند كل خطوة يواجه الوكيل سؤالًا:

    STOP (اكتفاء)  /  CONTINUE  /  DECLARE INCOMPLETE

والحالة الحقيقية تُشتق من **حالة الاعتقاد** وحدها (لا من W*):

    MET                   → الصواب STOP
    GUARANTEED_REACHABLE  → الصواب CONTINUE
    POSSIBLE_UNGUARANTEED → **يُسجَّل ولا يُحتسب** (قاعدة القرار نفسها غير محسومة)
    UNREACHABLE           → الصواب INCOMPLETE

وحدة القياس = نقطة القرار؛ وحدة التجميع = الحلقة/العالم (ج.3، منعًا للـ pseudo-replication).
كل الأرقام تُبلَّغ مع عدد العوالم المساهمة، ولا يُجرى اختبار يعامل الخطوات كمستقلة.

تنبيه مسجَّل: حكم الجلسة (INCOMPLETENESS_VERIFIED) أخشن من تصنيف A-008 — فهو يسمّي النطاق
الأوسط CORRECT_INCOMPLETENESS لأنه يفحص الضمان وحده. **هذا المحلّل هو المرجع** في التصنيف.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict

from world_b1 import (generate_accepted_world_b1, Evidence, apply_action, support_of,
                      decision_state)

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "provenance", "diagnostic_a008_run")
ACT = re.compile(r"^(PROBE|EXPERIMENT)\(([A-Za-z]{2})\)$")
SCORED = {"MET": "STOP", "GUARANTEED_REACHABLE": "CONTINUE", "UNREACHABLE": "INCOMPLETE"}


def decision_points(seed, rows_by_seed):
    """يعيد بناء نقاط القرار: الحالة الحقيقية قبل كل قرار + ما فعله الوكيل."""
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

    out = os.path.join(HERE, "diagnostic_a008_decisions.json")
    json.dump({"episodes": episodes, "excluded": [e["seed"] for e in excluded]},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nrows -> {out}")


if __name__ == "__main__":
    main()
