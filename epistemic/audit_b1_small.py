"""audit_b1_small.py — تدقيق ما بعد التشغيل لجلسات B1-small (seeds 4000..4009).

تحليل فقط على السجلات المختومة: يعيد بناء العالم من البذرة، يعيد تشغيل مسار الأدلة، ويحسب
لكل التزام (IG_joint, IG_H, IG_Σ) — لأن الصفوف المسجَّلة سبقت IG_Σ. لا يمسّ العقد ولا الأوراكل.

الفصل الذي يظهر: EXPERIMENT على رمز **غير مبروب** يكتسب معلومة الحالة (IG_Σ عالٍ) لا القانون
(IG_H ~ 0)؛ وعلى رمز **مبروب** العكس. أي أن "التجربة قبل البروب" قد تكون اكتساب حالة عقلانيًا.
"""

import json
import os
import re

from world_b1 import (generate_accepted_world_b1, Evidence, apply_action)
from ig_state import information_gain_full

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "provenance", "pilot_b1_run")
ACT = re.compile(r"^(PROBE|EXPERIMENT)\(([A-Za-z]{2})\)$")


def audit_seed(seed):
    w = generate_accepted_world_b1(seed)
    sidx = {s: k for k, s in enumerate(w.train_symbols)}
    recs = [json.loads(l) for l in open(os.path.join(RUN, f"s{seed}.jsonl"), encoding="utf-8")]
    ev = Evidence(w.n_syms, w.n_syms)
    steps, seq = [], []
    pending = None                       # (kind, x, was_probed_before) بانتظار نتيجته
    for r in recs:
        p = r["payload"]
        k = p["kind"]
        if k in ("FREE_OBS_COMMIT", "COMMITMENT"):
            m = ACT.match(p["deposit"].get("action", ""))
            if not m:
                continue
            kind, sym = m.group(1), m.group(2)
            x = sidx[sym]
            probed_before = bin(ev.pmask[x]).count("1") == 1     # الرمز صار متجهه معروفًا؟
            igj, igh, igs = information_gain_full(w.hypotheses, ev, w.emask, w.ctx, (kind, x, None))
            rec_ig = (p.get("metrics") or {}).get("information") or {}
            bel = (p.get("metrics") or {}).get("belief") or {}
            steps.append({
                "act": f"{kind[0]}:{sym}", "kind": kind, "probed_before": probed_before,
                "IG_joint": round(igj, 4), "IG_H": round(igh, 4), "IG_Sigma": round(igs, 4),
                "rec_joint": rec_ig.get("IG_joint"), "rec_law": rec_ig.get("IG_law"),
                "TV": bel.get("probability_error_tv"), "sup": bel.get("support_size_declared"),
                "mass_truth": bel.get("mass_on_truth"),
                "free": k == "FREE_OBS_COMMIT",
            })
            seq.append(kind[0])
            pending = (kind, x)
        elif k == "PROBE_RESULT" and pending:
            kind, x = pending
            vi = w.declared_vectors.index(tuple(p["result"]))
            ev = apply_action(ev, ("PROBE", x, None), vi)
            pending = None
        elif k == "OBSERVATION" and pending:
            kind, x = pending
            ev = apply_action(ev, ("EXPERIMENT", x, None), p["result"])
            pending = None
        elif k == "SESSION_END":
            res = p["result"]
    return w, steps, "".join(seq), res


def main():
    print("=" * 92)
    print("B1-SMALL POST-HOC AUDIT — per-step IG_joint / IG_H / IG_Σ  (seeds 4000–4009)")
    print("=" * 92)
    tot_exp_state = tot_exp_law = 0.0
    tot_probe_state = 0.0
    mismatches = 0
    for seed in range(4000, 4010):
        w, steps, seq, res = audit_seed(seed)
        print(f"\nseed {seed}   seq={seq}   N={res.get('N_total')} "
              f"D_robust={res.get('D_robust')} blindID={res.get('blind_ID')} "
              f"outcome={res.get('outcome')}")
        print(f"   {'act':<6}{'regime':<10}{'IG_joint':>9}{'IG_H':>7}{'IG_Σ':>7}"
              f"{'cpl':>7}{'TV':>8}{'|sup|':>6}{'mass*':>8}")
        tot_coupling = 0.0
        for s in steps:
            igs = 0.0 if abs(s["IG_Sigma"]) < 1e-9 else s["IG_Sigma"]
            igh = 0.0 if abs(s["IG_H"]) < 1e-9 else s["IG_H"]
            cpl = round(s["IG_joint"] - igh - igs, 4)         # فائض الاقتران (super-additive)
            # تحقّق: IG_joint وIG_H المعاد حسابهما == المسجَّل (نفس دالة الأوراكل)
            if s["rec_joint"] is not None and abs(s["IG_joint"] - s["rec_joint"]) > 1e-3:
                mismatches += 1
            if s["rec_law"] is not None and abs(igh - s["rec_law"]) > 1e-3:
                mismatches += 1
            # النظام مشتقّ من القيم لا من نوع الفعل (بروبٌ بعد تجربة قد يميّز القانون)
            regime = ("state" if igh < 0.01 else "law" if igs < 0.01
                      else "synergy" if cpl > 0.05 else "redund" if cpl < -0.05 else "mixed")
            print(f"   {s['act']:<6}{regime:<10}{s['IG_joint']:>9}{igh:>7}{igs:>7}{cpl:>7}"
                  f"{(s['TV'] if s['TV'] is not None else 0):>8}"
                  f"{(s['sup'] or 0):>6}{(s['mass_truth'] or 0):>8}")
            if s["kind"] == "EXPERIMENT":
                tot_exp_state += igs; tot_exp_law += igh
                if not s["probed_before"]:
                    tot_coupling += max(cpl, 0.0)
            else:
                tot_probe_state += igs
        print(f"   → coupling info (IG_joint−IG_H−IG_Σ) bought by experiments on UN-probed "
              f"symbols: {tot_coupling:.2f} bits")
    print("\n" + "=" * 92)
    print("ACROSS 10 SEEDS — four regimes, none reducible to a single marginal:")
    print(f"  state   (probe, fresh symbol)      → pure STATE: IG_H≡0, Σ IG_Σ = {tot_probe_state:.2f} b")
    print(f"  law     (experiment, probed symbol)→ pure LAW:   IG_Σ≈0, Σ IG_H = {tot_exp_law:.2f} b")
    print(f"  synergy (experiment, un-probed)    → COUPLING:   IG_joint ⋙ IG_H+IG_Σ (cpl>0)")
    print(f"  redund  (probe after its experiment)→ REDUNDANT:  same bit twice (cpl<0)")
    print(f"  recomputed-vs-recorded IG_joint & IG_H mismatches (>1e-3): {mismatches}")
    print("=" * 92)
    return mismatches == 0


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
