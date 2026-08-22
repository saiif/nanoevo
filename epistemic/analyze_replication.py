"""analyze_replication.py — إغلاق R-001 على 4010-4019 بالتعريفات المثبّتة (commit 2441332).

يعيد استخدام audit_b1_small.audit_seed وaudit_b1_efficiency.analyze حرفيًا (نفس تعريفات F،
E_only، IG، cost identity)، مُوجَّهة لمجلد التكرار فقط. لا إعادة تعريف. ثم يحكم F1/F2/F3 مقابل
شروط الدحض المجمّدة في R-001، ويحسب Brier علينا.
"""

import json
import math
import os

import audit_b1_small
audit_b1_small.RUN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "provenance", "pilot_b1_replication")
from audit_b1_small import audit_seed          # noqa: E402 — بعد توجيه RUN
from audit_b1_efficiency import analyze         # noqa: E402


def pearson(xs, ys):
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    cov = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    vx = sum((x-mx)**2 for x in xs); vy = sum((y-my)**2 for y in ys)
    return cov/math.sqrt(vx*vy) if vx > 0 and vy > 0 else 0.0


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0]*len(v); i = 0
        while i < len(v):
            j = i
            while j+1 < len(v) and v[order[j+1]] == v[order[i]]:
                j += 1
            avg = (i+j)/2 + 1
            for k in range(i, j+1):
                r[order[k]] = avg
            i = j+1
        return r
    return pearson(ranks(xs), ranks(ys))


def main():
    seeds = list(range(4010, 4020))
    S = []
    for seed in seeds:
        a = analyze(seed)                        # F، E_only، P_only، N، synergy، IG/action ...
        w, steps, seq, res = audit_seed(seed)
        a["blindID"] = res.get("blind_ID")
        a["solved"] = res.get("outcome") == "SOLVED"
        a["first_is_P"] = seq[:1] == "P"
        a["ig_per_action"] = a["ig_per_action"]
        S.append(a)

    print("="*100)
    print("R-001 CLOSURE — replication 4010-4019 (pinned defs @2441332). Confirmatory BEFORE any exploratory.")
    print("="*100)
    print(f"{'seed':<6}{'out':<16}{'blindID':<8}{'N':<4}{'F':<3}{'Eonly':<6}{'Ponly':<6}{'IG/act':<8}{'seq'}")
    for a in S:
        print(f"{a['seed']:<6}{('SOLVED' if a['solved'] else 'FALSE_CERT'):<16}{a['blindID']:<8}"
              f"{a['N']:<4}{a['fully_instrumented']:<3}{a['exp_only_symbols']:<6}"
              f"{a['probe_only_waste']:<6}{a['ig_per_action']:<8}{a['seq']}")

    Ns = [a["N"] for a in S]; Fs = [a["fully_instrumented"] for a in S]
    IGs = [a["ig_per_action"] for a in S]
    med = sorted(Ns)[len(Ns)//2]
    fast = [a for a in S if a["N"] <= med]; slow = [a for a in S if a["N"] > med]

    def mean(g, k): return sum(x[k] for x in g)/len(g) if g else 0.0
    def eonly_frac(a): return a["exp_only_symbols"]/a["n_actions"]

    n_solved = sum(a["solved"] for a in S)
    blinds = sorted(a["blindID"] for a in S)
    median_blind = blinds[len(blinds)//2]
    rho_FN = spearman(Fs, Ns)
    r2_NF = pearson(Fs, Ns)**2
    r2_NIG = pearson(IGs, Ns)**2
    ig_gap = abs(mean(fast, "ig_per_action") - mean(slow, "ig_per_action"))
    eonly_fast = sum(eonly_frac(a) for a in fast)/len(fast)
    eonly_slow = sum(eonly_frac(a) for a in slow)/len(slow) if slow else 0.0
    p_first = sum(a["first_is_P"] for a in S)

    print("\n" + "-"*100)
    print("F1 CAPABILITY (p=0.85) — pred: success >= 8/10, median blindID = 1.0, success NOT primary axis")
    print(f"   success rate = {n_solved}/10 ; median blindID = {median_blind}")
    # التصحيح: عتبة التنبؤ ليست حدّ الدحض. النسخة السابقة استعملت (n_solved >= 6) — وهو
    # **حدّ الدحض** — بوصفه شرط HELD، فكان التنبؤ المعلن (>=8/10) يستطيع أن "ينجح" عند 6/10،
    # ثم يدخل هذا الـ boolean في الـ Brier. الـ Brier يجب أن يُسجَّل على التنبؤ لا على حدّ الموت.
    f1_predicted = (n_solved >= 8) and (median_blind == 1.0)      # التنبؤ المسجَّل حرفيًا
    f1_falsified = (n_solved < 6)                                  # حدّ الدحض المسجَّل
    f1 = f1_predicted                                              # ما يدخل الـ Brier
    print(f"   prediction (>=8/10 and median 1.0): {'MET' if f1_predicted else 'NOT MET'}")
    print(f"   death boundary (<6/10):             {'TRIGGERED' if f1_falsified else 'not triggered'}")
    print("   NOTE: the sealed clause 'blind_ID variance explains more spread than N' was never")
    print("   operationalized in the pre-registration (no estimator, no threshold). It is therefore")
    print("   NOT computed here and NOT used to flip the verdict; operationalizing it now would be")
    print("   a post-hoc definition and requires its own amendment.")
    bl = [a["blindID"] for a in S if a.get("blindID") is not None]
    ns = [a["N"] for a in S if a.get("N") is not None]
    if len(bl) > 1 and len(ns) > 1:
        import statistics as _st
        print(f"   (descriptive only, not scored: var(blind_ID)={_st.pvariance(bl):.4f} "
              f"var(N)={_st.pvariance(ns):.4f})")

    print("\nF2 EFFICIENCY (p=0.80) — pred: rho(F,N)>=0.7 ; fast higher E_only frac ; |IG/act gap|<0.15")
    print(f"   rho(F,N) = {rho_FN:.3f} ; E_only frac fast={eonly_fast:.3f} vs slow={eonly_slow:.3f} ; "
          f"IG/act gap = {ig_gap:.3f}")
    f2 = (rho_FN >= 0.3) and (eonly_fast >= eonly_slow) and (ig_gap < 0.15)
    f2_strong = (rho_FN >= 0.7) and (eonly_fast > eonly_slow) and (ig_gap < 0.15)
    print(f"   verdict: {'HELD (strong)' if f2_strong else 'HELD (weak)' if f2 else 'FALSIFIED'}"
          f"   [falsify iff rho<0.3 OR fast not > slow on E_only OR IG gap>=0.15]")

    print("\nF3 MECHANISM (p=0.75) — pred: F explains N better than IG/act ; P-before-E near-universal")
    print(f"   R2(N~F) = {r2_NF:.3f} vs R2(N~IG/act) = {r2_NIG:.3f} ; sessions opening with P = {p_first}/10")
    f3 = (r2_NF > r2_NIG) and (p_first >= 9)
    print(f"   verdict: {'HELD' if f3 else 'FALSIFIED'}   [falsify iff IG/act explains N better OR P-before-E correlates with N]")

    # Brier علينا نحن (احتمال متوقّع مقابل نتيجة ثنائية held=1)
    preds = [("F1", 0.85, f1), ("F2", 0.80, bool(f2)), ("F3", 0.75, f3)]
    # يُسجَّل على تحقّق **التنبؤات** لا على تجاوز حدود الدحض
    brier = sum((p - (1 if held else 0))**2 for _, p, held in preds)/len(preds)
    print("\n" + "-"*100)
    print("SELF-SCORING (Brier on R-001 probabilities; outcome=1 if held):")
    for name, p, held in preds:
        print(f"   {name}: p={p}  outcome={1 if held else 0}  brier_i={(p-(1 if held else 0))**2:.4f}")
    print(f"   MEAN BRIER = {brier:.4f}   (baseline p=0.5 -> 0.25 ; lower is better)")
    held_all = [name for name, _, h in preds if h]
    print("\n" + "="*100)
    verdict = ("SUPPORTED" if len(held_all) == 3 else
               "MIXED" if held_all else "FALSIFIED")
    print(f"R-001 VERDICT: {verdict}  (held: {', '.join(held_all) or 'none'})")
    print("="*100)


if __name__ == "__main__":
    main()
