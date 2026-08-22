"""compare_efficiency_vs_undersampling.py — الحد الفاصل بين الكفاءة والتهور.

تحليل read-only على الدفعتين المكتملتين:
    4000-4009  (10/10 solved)      مقابل   4010-4019  (8/10 + 2 FALSE_CERTAINTY)

السؤال: جلسات N=8 الناجحة وجلستا الفشل كلتاهما "قليلة الـ probes". فهل الفرق **اقتصاد**
أم **نقص أدلة**؟ الفرضية المختبَرة:

    Epistemic efficiency  ≠  Epistemic under-sampling
    الوكيل الجيد لا يجمع أقل معلومات ممكنة، بل **أقل معلومات كافية**.

المحك الحاسم: حالة الـ posterior المرجعي **لحظة إعلان الاكتفاء**. الاقتصادي يعلن وقد
حسم (support = 1)؛ المتهور يعلن والغموض قائم (support > 1) فيقامر على فرع.

لا يمسّ العقد ولا الأوراكل ولا يعيد تعريف أي مقياس مثبّت.
"""

import json
import os
import sys

import audit_b1_small
from audit_b1_small import audit_seed

from world_b1 import Evidence, apply_action, posterior, support_of

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "provenance", "pilot_b1_run")
REPL = os.path.join(HERE, "provenance", "pilot_b1_replication")


def state_at_declaration(seed, run_dir):
    """يعيد تشغيل مسار الأدلة حتى إعلان الاكتفاء، ويقرأ الـ posterior المرجعي هناك.

    هذا هو المحك: كم فرضية كانت لا تزال حية لحظة قال الوكيل "يكفي"؟
    """
    audit_b1_small.RUN = run_dir
    w, steps, seq, res = audit_seed(seed)
    sidx = {s: k for k, s in enumerate(w.train_symbols)}
    recs = [json.loads(l) for l in open(os.path.join(run_dir, f"s{seed}.jsonl"),
                                        encoding="utf-8")]
    ev = Evidence(w.n_syms, w.n_syms)
    pending, decl = None, None
    import re
    ACT = re.compile(r"^(PROBE|EXPERIMENT)\(([A-Za-z]{2})\)$")
    for r in recs:
        p = r["payload"]
        k = p["kind"]
        if k in ("FREE_OBS_COMMIT", "COMMITMENT"):
            m = ACT.match(p["deposit"].get("action", ""))
            if m:
                pending = (m.group(1), sidx[m.group(2)])
        elif k == "PROBE_RESULT" and pending:
            ev = apply_action(ev, ("PROBE", pending[1], None),
                              w.declared_vectors.index(tuple(p["result"])))
            pending = None
        elif k == "OBSERVATION" and pending:
            ev = apply_action(ev, ("EXPERIMENT", pending[1], None), p["result"])
            pending = None
        elif k in ("SUFFICIENCY", "INCOMPLETE") and decl is None:
            sup = support_of(w.hypotheses, ev, w.emask, w.ctx)
            P, Z, _, _ = posterior(w.hypotheses, ev, w.emask, w.ctx)
            decl = {
                "declared_conf": p["deposit"].get("confidence"),
                "declared_law": p["deposit"].get("final_hypothesis"),
                "support_at_declaration": len(sup),
                "truth_in_support": w.true_id in sup,
                "P_truth_at_declaration": round(P[w.true_id], 4) if Z else 0.0,
                "true_law_id": w.true_law_id(),
            }
    return w, steps, seq, res, decl


def structure(steps):
    """F / E_only / P_only بنفس تعريفات commit 2441332 (لا إعادة تعريف)."""
    probed, exped = set(), set()
    for s in steps:
        sym = s["act"].split(":")[1]
        (probed if s["kind"] == "PROBE" else exped).add(sym)
    F = len(probed & exped)
    return {"F": F, "E_only": len(exped - probed), "P_only": len(probed - exped),
            "n_probe_actions": sum(1 for s in steps if s["kind"] == "PROBE"),
            "n_paid_probes": sum(1 for s in steps if s["kind"] == "PROBE" and not s["free"])}


def row(seed, run_dir):
    w, steps, seq, res, decl = state_at_declaration(seed, run_dir)
    st = structure(steps)
    return {"seed": seed, "seq": seq, "outcome": res["outcome"],
            "N": res.get("N_total"), "blindID": res.get("blind_ID"),
            "E_rob": res.get("E"), "D_robust": res.get("D_robust"),
            "D_floor": res.get("D_floor_task"), **st, **(decl or {})}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main_rows = [row(s, MAIN) for s in range(4000, 4010)]
    repl_rows = [row(s, REPL) for s in range(4010, 4020)]
    allr = main_rows + repl_rows

    print("=" * 108)
    print("LAYER 1 — OUTCOME")
    print("=" * 108)
    print(f"{'seed':>5} {'batch':>6} {'seq':<13} {'N':>3} {'blindID':>8} {'E_rob':>6} "
          f"{'floor':>5} {'Drob':>5}  outcome")
    for r in allr:
        b = "main" if r["seed"] < 4010 else "repl"
        e = "-" if r["E_rob"] is None else f"{r['E_rob']:.2f}"
        print(f"{r['seed']:>5} {b:>6} {r['seq']:<13} {r['N']:>3} {r['blindID']:>8} {e:>6} "
              f"{r['D_floor']:>5} {r['D_robust']:>5}  {r['outcome']}")
    ms = sum(1 for r in main_rows if r["outcome"] == "SOLVED")
    rs = sum(1 for r in repl_rows if r["outcome"] == "SOLVED")
    print(f"\n  4000-4009: {ms}/10 SOLVED     4010-4019: {rs}/10 SOLVED")

    print("\n" + "=" * 108)
    print("LAYER 2 — BELIEF: the state of the posterior AT THE MOMENT 'enough' WAS DECLARED")
    print("=" * 108)
    print(f"{'seed':>5} {'outcome':<16} {'|support|@decl':>14} {'P(truth)@decl':>13} "
          f"{'truth in sup':>12} {'declared conf':>13}")
    for r in allr:
        print(f"{r['seed']:>5} {r['outcome']:<16} {r['support_at_declaration']:>14} "
              f"{r['P_truth_at_declaration']:>13} {str(r['truth_in_support']):>12} "
              f"{str(r['declared_conf']):>13}")
    solved = [r for r in allr if r["outcome"] == "SOLVED"]
    failed = [r for r in allr if r["outcome"] != "SOLVED"]
    print(f"\n  SOLVED   (n={len(solved)}): |support|@declaration = "
          f"{sorted({r['support_at_declaration'] for r in solved})}")
    print(f"  FAILED   (n={len(failed)}): |support|@declaration = "
          f"{sorted({r['support_at_declaration'] for r in failed})}")

    print("\n" + "=" * 108)
    print("LAYER 3 — ACQUISITION POLICY: cost structure  N = 2F + E_only + P_only")
    print("=" * 108)
    print(f"{'seed':>5} {'outcome':<16} {'N':>3} {'F':>3} {'E_only':>7} {'P_only':>7} "
          f"{'paid probes':>12} {'2F+Eo+Po':>9}")
    for r in allr:
        print(f"{r['seed']:>5} {r['outcome']:<16} {r['N']:>3} {r['F']:>3} {r['E_only']:>7} "
              f"{r['P_only']:>7} {r['n_paid_probes']:>12} "
              f"{2*r['F']+r['E_only']+r['P_only']:>9}")

    print("\n" + "=" * 108)
    print("THE DECISIVE PAIR — same cost, opposite epistemic status")
    print("=" * 108)
    cheap_ok = [r for r in allr if r["outcome"] == "SOLVED" and r["N"] <= 8]
    cheap_bad = [r for r in allr if r["outcome"] != "SOLVED"]
    for label, group in (("ECONOMICAL (cheap AND correct)", cheap_ok),
                         ("UNDER-SAMPLED (cheap AND wrong)", cheap_bad)):
        print(f"\n  {label}")
        for r in group:
            print(f"    seed {r['seed']}  N={r['N']}  F={r['F']}  E_only={r['E_only']}  "
                  f"paid_probes={r['n_paid_probes']}  |support|@decl={r['support_at_declaration']}"
                  f"  P(truth)@decl={r['P_truth_at_declaration']}  blindID={r['blindID']}")
    if cheap_ok and cheap_bad:
        f_ok = sum(r["F"] for r in cheap_ok) / len(cheap_ok)
        f_bad = sum(r["F"] for r in cheap_bad) / len(cheap_bad)
        s_ok = sum(r["support_at_declaration"] for r in cheap_ok) / len(cheap_ok)
        s_bad = sum(r["support_at_declaration"] for r in cheap_bad) / len(cheap_bad)
        print(f"\n  mean F:                  economical={f_ok:.1f}   under-sampled={f_bad:.1f}")
        print(f"  mean |support|@decl:     economical={s_ok:.1f}   under-sampled={s_bad:.1f}")
        print("\n  READING: cost alone does not separate them. What separates them is whether the")
        print("  evidence had actually RESOLVED the question when 'enough' was declared.")
        print("  Efficiency = stopping at sufficiency. Under-sampling = stopping before it.")
    out = os.path.join(HERE, "b1_efficiency_vs_undersampling.json")
    json.dump(allr, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nrows -> {out}")


if __name__ == "__main__":
    main()
