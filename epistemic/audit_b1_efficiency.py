"""audit_b1_efficiency.py — لماذا بعض مسارات B1-small أكفأ؟ (بنية المعلومة لا عددها).

يبني على audit_b1_small.audit_seed: لكل seed يصنّف كل فعل إلى نظامه المعلوماتي
(state/law/synergy/redund) ويقيس بنية الكفاءة، ثم يقارن أتراب N (8 مقابل 11).

الفرضية المختبَرة: الكفاءة (N منخفض) تنشأ من استغلال synergy (تجربة تحصد الاقتران في فعل
واحد) وتجنّب redundancy (بروب فوق أثر تجربة سابقة)؛ لا من «ترتيب P→E» بحد ذاته.
"""

import statistics as st
from audit_b1_small import audit_seed


def regime_of(igj, igh, igs):
    cpl = igj - (0.0 if abs(igh) < 1e-9 else igh) - (0.0 if abs(igs) < 1e-9 else igs)
    if igh < 0.01:
        return "state", cpl
    if igs < 0.01:
        return "law", cpl
    if cpl > 0.05:
        return "synergy", cpl
    if cpl < -0.05:
        return "redund", cpl
    return "mixed", cpl


def analyze(seed):
    w, steps, seq, res = audit_seed(seed)
    counts = {r: 0 for r in ("state", "law", "synergy", "redund", "mixed")}
    coupling_pos = coupling_neg = 0.0
    ig_joint_sum = 0.0
    hi_joint = 0                          # أفعال بـ IG_joint >= 1.5 (كثيفة معلوماتيًا)
    probed, experimented = set(), set()   # أيّ الرموز نالت كل نوع (لبنية التجهيز)
    for s in steps:
        r, cpl = regime_of(s["IG_joint"], s["IG_H"], s["IG_Sigma"])
        counts[r] += 1
        ig_joint_sum += s["IG_joint"]
        if cpl > 0:
            coupling_pos += cpl
        else:
            coupling_neg += -cpl
        if s["IG_joint"] >= 1.5:
            hi_joint += 1
        kind_c, sym = s["act"].split(":")
        (probed if kind_c == "P" else experimented).add(sym)
    n_paid = len(steps)                   # كل الأفعال المسجَّلة (تشمل الحرّة)
    both = probed & experimented          # رمز جُهِّز بالكامل (بروب + تجربة)
    exp_only = experimented - probed      # قانونٌ استُخرج بتجربة على رمز لم يُبرَب (synergy)
    probe_only = probed - experimented    # بروب لم يُتبَع بتجربة = هدر صريح
    return {
        "seed": seed, "N": res.get("N_total"), "seq": seq,
        "n_actions": n_paid, **counts,
        "fully_instrumented": len(both), "exp_only_symbols": len(exp_only),
        "probe_only_waste": len(probe_only),
        "cost_identity": 2 * len(both) + len(exp_only) + len(probe_only),
        "n_probed": len(probed), "n_experimented": len(experimented),
        "synergy_frac": round(counts["synergy"] / n_paid, 3),
        "redund_n": counts["redund"],
        "coupling_harvested": round(coupling_pos, 2),
        "coupling_wasted": round(coupling_neg, 2),
        "ig_per_action": round(ig_joint_sum / n_paid, 3),
        "hi_joint_frac": round(hi_joint / n_paid, 3),
    }


def main():
    rows = [analyze(s) for s in range(4000, 4010)]
    print("=" * 100)
    print("B1-SMALL EFFICIENCY STRUCTURE — why some paths cost less (D_robust=8 in all)")
    print("=" * 100)
    hdr = ("seed", "N", "seq", "full", "exp-only", "waste", "2·f+e+w")
    print(f"{hdr[0]:<6}{hdr[1]:<4}{hdr[2]:<14}{hdr[3]:>5}{hdr[4]:>9}{hdr[5]:>6}{hdr[6]:>8}")
    ok_identity = True
    for r in sorted(rows, key=lambda x: x["N"]):
        ok_identity &= (r["cost_identity"] == r["N"])
        print(f"{r['seed']:<6}{r['N']:<4}{r['seq']:<14}{r['fully_instrumented']:>5}"
              f"{r['exp_only_symbols']:>9}{r['probe_only_waste']:>6}{r['cost_identity']:>8}")
    print(f"\n  cost identity  N = 2·(fully instrumented) + (exp-only) + (probe waste)  holds: "
          f"{ok_identity} on all 10")

    # مقارنة الأتراب: الأكفأ (N<=9) مقابل الأبطأ (N>=11)
    fast = [r for r in rows if r["N"] <= 9]
    slow = [r for r in rows if r["N"] >= 11]

    def agg(group, key):
        return round(st.mean(r[key] for r in group), 3)

    print("\n" + "-" * 100)
    print(f"COHORT COMPARISON   fast (N≤9, n={len(fast)})   vs   slow (N≥11, n={len(slow)})")
    print("-" * 100)
    for key, label in [("fully_instrumented", "symbols FULLY instrumented (probe+exp)"),
                       ("exp_only_symbols", "symbols resolved by experiment ONLY"),
                       ("n_probed", "distinct symbols probed"),
                       ("synergy", "synergy experiments (count)"),
                       ("ig_per_action", "mean IG_joint per action")]:
        print(f"  {label:<42} fast={agg(fast,key):>7}   slow={agg(slow,key):>7}")
    print("-" * 100)
    print("READING: efficiency is NOT 'probe-first vs experiment-first', and NOT denser info/action")
    print("(1.45 vs 1.39 — nearly equal). The driver is STRUCTURAL: how many symbols get the")
    print("expensive FULL probe+experiment treatment. Slow sessions fully instrument ~every symbol")
    print("they use (a maximally-DECOMPOSED policy); fast sessions leave some symbols probe-free and")
    print("resolve the law by experimenting on them (coupling), spending 1 action where slow spends 2.")
    print("The LLM discovers the law every time, but does NOT consistently exploit the joint structure")
    print("— that inconsistency, not capability, is what the efficiency spread measures.")
    print("=" * 100)


if __name__ == "__main__":
    main()
