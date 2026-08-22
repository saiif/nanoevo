"""analyze_b1_a007.py — أربع طبقات + ExcessActionsAfterSufficiency، عبر الدفعات الثلاث.

الفرضيتان المتنافستان بعد اختفاء INCOMPLETE في دفعة A-007:

    H1: A-007 حسّن فهم فضاء الأفعال (تحكّم أفضل)
    H2: A-007 غيّر سياسة الإعلان فقط — صار إعلان النقص مكلفًا فيُتجنّب، بلا تحسّن داخلي

التمييز لا يحتاج تغيير العقد: يكفي أن نسأل **متى** توقف الوكيل بالنسبة إلى اللحظة التي
صار عندها النجاح مضمونًا.

نقطة دقيقة: attainable_within صحيحة **من البداية** (العوالم مقبولة = قابلة للحل)، فلا
تصلح علامةً على "صار النجاح مضمونًا". العلامة الصحيحة هي أول خطوة يصبح فيها المعيار
**محقَّقًا بالفعل** — أي لو توقف عندها لنجح. وهو نفس شرط الإنهاء counterfactual-correct
المستعمل في D_robust: تصويت أغلبية الـ support يحقق tau ضد **أي** عضو لو كان هو الصحيح.

    ExcessActionsAfterSufficiency = (عدد الأفعال حتى التوقف) − (أول خطوة صار المعيار عندها محققًا)

قراءة النتيجة:
    excess ≈ 0 عبر الدفعات        → التحكم لم يتدهور؛ اختفاء INCOMPLETE ليس ثمنه إفراط
    excess يرتفع بعد A-007        → H2: نقلنا الخطأ من premature stopping إلى over-exploration
"""

import json
import os
import re
import sys

from world_b1 import (generate_accepted_world_b1, Evidence, apply_action, support_of,
                      posterior, attainable_within)

HERE = os.path.dirname(os.path.abspath(__file__))
BATCHES = [("pre-A007  ", "pilot_b1_run", range(4000, 4010)),
           ("pre-A007r ", "pilot_b1_replication", range(4010, 4020)),
           ("post-A007 ", "pilot_b1_a007_run", range(4020, 4030))]
ACT = re.compile(r"^(PROBE|EXPERIMENT)\(([A-Za-z]{2})\)$")
BUDGET = 15


def criterion_met(w, support):
    """هل يكفي التوقف الآن؟ (counterfactual-correct: ينجح ضد أي عضو لو كان هو الصحيح)."""
    if not support:
        return True
    bl = [tuple(v) for v in w.blind_ID.values()]
    members = [w.hypotheses[k] for k in support]
    for m in members:
        agree = 0
        for v in bl:
            ones = sum(x.eval(v) for x in members)
            agree += ((1 if 2 * ones >= len(members) else 0) == m.eval(v))
        if agree / len(bl) < w.tau:
            return False
    return True


def walk(seed, run_dir):
    """يعيد المسار خطوةً خطوة مع لحظة تحقّق المعيار."""
    path = os.path.join(HERE, "provenance", run_dir, f"s{seed}.jsonl")
    if not os.path.exists(path):
        return None
    w = generate_accepted_world_b1(seed)
    sidx = {s: k for k, s in enumerate(w.train_symbols)}
    ev, pending, used = Evidence(w.n_syms, w.n_syms), None, 0
    first_ok, decl_kind, decl, res = None, None, None, None
    sup_at_first, budget_at_first = None, None
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
            _s = support_of(w.hypotheses, ev, w.emask, w.ctx)
            if first_ok is None and criterion_met(w, _s):
                first_ok, sup_at_first, budget_at_first = used, len(_s), BUDGET - used
        elif k == "OBSERVATION" and pending:
            ev = apply_action(ev, ("EXPERIMENT", pending[1], None), p["result"])
            pending, used = None, used + 1
            _s = support_of(w.hypotheses, ev, w.emask, w.ctx)
            if first_ok is None and criterion_met(w, _s):
                first_ok, sup_at_first, budget_at_first = used, len(_s), BUDGET - used
        elif k in ("SUFFICIENCY", "INCOMPLETE") and decl_kind is None:
            decl_kind, decl = k, p["deposit"]
        elif k == "SESSION_END":
            res = p["result"]
    sup = support_of(w.hypotheses, ev, w.emask, w.ctx)
    P, Z, _, _ = posterior(w.hypotheses, ev, w.emask, w.ctx)
    attainable, d_rem, best_ig, n_inf = attainable_within(
        w.hypotheses, w.n_syms, w.emask, w.ctx, ev, [tuple(v) for v in w.blind_ID.values()],
        w.tau, BUDGET - used)
    return {"seed": seed, "run": run_dir, "outcome": (res or {}).get("outcome"),
            "N": used, "blindID": (res or {}).get("blind_ID"), "E_rob": (res or {}).get("E"),
            "decl": decl_kind, "claim": (decl or {}).get("claim"),
            "support_at_stop": len(sup),
            "P_truth_at_stop": round(P[w.true_id], 4) if Z else 0.0,
            "criterion_met_at_stop": criterion_met(w, sup),
            # الحقول المطلوبة صراحةً: متى صار الحسم ممكنًا، ومتى توقف، وماذا كان متاحًا حينها
            "t_sufficient": first_ok, "t_stop": used,
            "B_remaining_at_t_sufficient": budget_at_first,
            "support_size_at_t_sufficient": sup_at_first,
            "first_sufficiency_step": first_ok,
            "excess_after_sufficiency": (used - first_ok) if first_ok is not None else None,
            "budget_remaining": BUDGET - used, "D_remaining": d_rem,
            "slack": (BUDGET - used - d_rem) if d_rem is not None else None,
            "still_attainable": attainable}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    allrows, bybatch = [], {}
    for label, run, seeds in BATCHES:
        rows = [r for r in (walk(s, run) for s in seeds) if r]
        bybatch[label] = rows
        allrows += rows

    print("=" * 112)
    print("LAYER 1-2 — OUTCOME and BELIEF AT STOP")
    print("=" * 112)
    print(f"{'batch':<11}{'seed':>5} {'outcome':<28}{'N':>3} {'blindID':>8} "
          f"{'|sup|@stop':>10} {'P(truth)':>9} {'crit met':>9}")
    for label, rows in bybatch.items():
        for r in rows:
            print(f"{label:<11}{r['seed']:>5} {str(r['outcome']):<28}{r['N']:>3} "
                  f"{str(r['blindID']):>8} {r['support_at_stop']:>10} "
                  f"{r['P_truth_at_stop']:>9} {str(r['criterion_met_at_stop']):>9}")

    print("\n" + "=" * 112)
    print("LAYER 3 — ACTIONABILITY JUDGMENT")
    print("=" * 112)
    for label, rows in bybatch.items():
        incs = [r for r in rows if r["decl"] == "INCOMPLETE"]
        wrong = [r for r in incs if r["still_attainable"]
                 and r.get("claim") == "no_decisive_action_remains"]
        prem = [r for r in rows if not r["criterion_met_at_stop"]]
        aer = f"{len(wrong)/len(incs):.3f}" if incs else "n/a (no INCOMPLETE)"
        print(f"  {label}  INCOMPLETE={len(incs):>2}   ActionabilityErrorRate={aer:>18}   "
              f"PrematureStopRate={len(prem)}/{len(rows)}")

    print("\n" + "=" * 112)
    print("LAYER 4 — STOPPING QUALITY:  H1 (better control)  vs  H2 (avoidance -> over-exploration)")
    print("=" * 112)
    print(f"{'batch':<11}{'seed':>5} {'N':>3} {'first suff.':>12} {'EXCESS':>7} "
          f"{'slack@stop':>11} {'D_rem':>6}")
    for label, rows in bybatch.items():
        for r in rows:
            print(f"{label:<11}{r['seed']:>5} {r['N']:>3} {str(r['first_sufficiency_step']):>12} "
                  f"{str(r['excess_after_sufficiency']):>7} {str(r['slack']):>11} "
                  f"{str(r['D_remaining']):>6}")
    print()
    for label, rows in bybatch.items():
        ex = [r["excess_after_sufficiency"] for r in rows
              if r["excess_after_sufficiency"] is not None]
        sl = [r["slack"] for r in rows if r["slack"] is not None]
        if ex:
            print(f"  {label}  ExcessActionsAfterSufficiency: mean={sum(ex)/len(ex):.2f} "
                  f"min={min(ex)} max={max(ex)} | n={len(ex)}"
                  + (f"   slack@stop mean={sum(sl)/len(sl):.2f}" if sl else ""))
    pre = [r["excess_after_sufficiency"] for lb in ("pre-A007  ", "pre-A007r ")
           for r in bybatch.get(lb, []) if r["excess_after_sufficiency"] is not None]
    post = [r["excess_after_sufficiency"] for r in bybatch.get("post-A007 ", [])
            if r["excess_after_sufficiency"] is not None]
    if pre and post:
        mp, mq = sum(pre)/len(pre), sum(post)/len(post)
        print(f"\n  pre-A007 mean excess = {mp:.2f}   post-A007 mean excess = {mq:.2f}"
              f"   delta = {mq-mp:+.2f}")
        print("  reading: a rise means the error moved from premature stopping to over-exploration")
        print("  (H2); a flat or lower value means the disappearance of INCOMPLETE did not cost")
        print("  extra actions (consistent with H1, though not by itself proof of it).")
    p = os.path.join(HERE, "b1_a007_stopping_quality.json")
    json.dump(allrows, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nrows -> {p}")


if __name__ == "__main__":
    main()
