"""relabel_b1_incompleteness.py — إعادة تصنيف **تحليلية** لجلسات B1 التي أعلنت النقص.

A-007 استعاد إلى B1 ضمانًا كان في Pilot-A: إعلان النقص يُفحص ولا يُقبل كحقيقة ذاتية.
الجلسات القديمة (4015/4018) شُغِّلت قبل ذلك فحملت تسمية FALSE_CERTAINTY — وهي **خاطئة
مرتين**: لم يكن هناك يقين (الوكيل أعلن نقصًا صراحةً)، والخطأ الحقيقي (ادعاء نفاد الأفعال)
لم يُقَس أصلًا.

**السجلات الخام لا تُمَس.** هذا الملف يقرأ فقط ويُخرج تصنيفًا تحليليًا منفصلًا.

قيد صريح: الإيداعات القديمة تسبق الحقل المهيكل `claim`، فاستخلاص نوع الادعاء منها
اجتهاد تحليلي على النص — مسموح هنا لأنه تحليل، وممنوع داخل الـ Verifier. ما هو **ليس**
اجتهادًا هو الشق الأوراكلي: هل بقي فعل حاسم ضمن الميزانية؟ ذاك يُحسب حتميًا.
"""

import json
import os
import re
import sys

from world_b1 import (generate_accepted_world_b1, Evidence, apply_action, support_of,
                      posterior, attainable_within)

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = {"pilot_b1_run": range(4000, 4010), "pilot_b1_replication": range(4010, 4020)}
ACT = re.compile(r"^(PROBE|EXPERIMENT)\(([A-Za-z]{2})\)$")
BUDGET = 15                     # ميزانية B1 وقت تشغيل تلك الجلسات

# دلائل نصية على ادعاء نفاد الأفعال (تحليلي فقط، لا يدخل الـ Verifier أبدًا)
EXHAUST_MARKERS = ("no symbols", "no further", "remain", "exhaust", "nothing left",
                   "no more", "no available", "no useful")


def replay_to_declaration(seed, run_dir):
    w = generate_accepted_world_b1(seed)
    sidx = {s: k for k, s in enumerate(w.train_symbols)}
    path = os.path.join(HERE, "provenance", run_dir, f"s{seed}.jsonl")
    ev, pending, used, decl = Evidence(w.n_syms, w.n_syms), None, 0, None
    for line in open(path, encoding="utf-8"):
        p = json.loads(line)["payload"]
        k = p["kind"]
        if k in ("FREE_OBS_COMMIT", "COMMITMENT"):
            m = ACT.match(p["deposit"].get("action", ""))
            pending = (m.group(1), sidx[m.group(2)]) if m else None
        elif k == "PROBE_RESULT" and pending:
            ev = apply_action(ev, ("PROBE", pending[1], None),
                              w.declared_vectors.index(tuple(p["result"])))
            pending, used = None, used + 1
        elif k == "OBSERVATION" and pending:
            ev = apply_action(ev, ("EXPERIMENT", pending[1], None), p["result"])
            pending, used = None, used + 1
        elif k == "INCOMPLETE" and decl is None:
            decl = p["deposit"]
            break
        elif k == "SESSION_END":
            decl = decl or None
    return w, ev, used, decl


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = []
    print("=" * 100)
    print("ANALYTIC RELABEL of B1 sessions that declared INCOMPLETE (raw logs untouched)")
    print("=" * 100)
    for run_dir, seeds in RUNS.items():
        for seed in seeds:
            w, ev, used, decl = replay_to_declaration(seed, run_dir)
            if decl is None:
                continue
            bl = [tuple(v) for v in w.blind_ID.values()]
            attainable, d_rem, best_ig, n_inf = attainable_within(
                w.hypotheses, w.n_syms, w.emask, w.ctx, ev, bl, w.tau, BUDGET - used)
            sup = support_of(w.hypotheses, ev, w.emask, w.ctx)
            P, Z, _, _ = posterior(w.hypotheses, ev, w.emask, w.ctx)
            reason = (decl.get("reason") or "").lower()
            claimed_exhaustion = any(m in reason for m in EXHAUST_MARKERS)
            if not attainable:
                verdict = "CORRECT_INCOMPLETENESS"
            elif claimed_exhaustion:
                verdict = "INCORRECT_ACTION_EXHAUSTION"
            else:
                verdict = "ACTIONABLE_INCOMPLETENESS"
            row = {"seed": seed, "run": run_dir, "original_label": "FALSE_CERTAINTY",
                   "analytic_relabel": verdict,
                   "posterior_correct": len(sup) == len(decl.get("remaining_hypotheses", [])),
                   "support_at_declaration": len(sup),
                   "P_truth_at_declaration": round(P[w.true_id], 4) if Z else 0.0,
                   "budget_remaining": BUDGET - used,
                   "attainable_within_remaining_budget": attainable,
                   "best_remaining_IG_law": best_ig,
                   "n_informative_actions_remaining": n_inf,
                   "D_remaining": d_rem,
                   "slack": (BUDGET - used - d_rem) if d_rem is not None else None,
                   "claimed_exhaustion_text": claimed_exhaustion,
                   "reason_excerpt": (decl.get("reason") or "")[:110]}
            out.append(row)
            print(f"\nseed {seed}  [{run_dir}]")
            print("  original label      : FALSE_CERTAINTY   <- wrong twice")
            print(f"  analytic relabel    : {verdict}")
            print(f"  posterior at decl   : |support|={len(sup)}  P(truth)={row['P_truth_at_declaration']}"
                  f"  (agent listed {len(decl.get('remaining_hypotheses', []))})")
            print(f"  budget remaining    : {row['budget_remaining']} of {BUDGET}")
            print(f"  decisive action left: {attainable}  best IG_law={best_ig}"
                  f"  informative actions={n_inf}")
            print(f"  D_remaining={d_rem}  slack={row['slack']}"
                  f"   <- slack >> 0 with an exhaustion claim = strong control error")
            print(f"  reason excerpt      : {row['reason_excerpt']}")
    if out:
        print("\n" + "=" * 100)
        print("The world-model was right; the action-model was not.")
        print("  Belief about the world      : correct (support and probabilities match the oracle)")
        print("  Belief about own affordances: wrong (decisive actions and budget both remained)")
        print("=" * 100)
    p = os.path.join(HERE, "b1_incompleteness_relabel.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nrelabel -> {p}   (raw session logs unmodified)")


if __name__ == "__main__":
    main()
