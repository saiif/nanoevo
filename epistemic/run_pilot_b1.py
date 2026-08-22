"""run_pilot_b1.py — Pilot-B1-small: 10 عوالم من S_pilot عبر الـ shim.

اختبار **هندسة/سلوك استكشافي، لا دراسة أداء**: لا يُغيَّر A-005 ولا الـ Session ولا الـ
oracle أثناء الدفعة، ولا تُستعمل النتائج لاختيار نسخة "أفضل" من العقد.

قاعدة التوقف المسجَّلة مسبقًا:
- عيب **عقد/أداة** (تسريب، تناقض أوراكل، فشل سلسلة/provenance، اختلاف دلالة بين الـ adapter
  والعقد) ⇒ توقف الدفعة وحقّق.
- **سلوك النموذج نفسه** (توزيع سيئ، إفراط في الـ probes، فشل Blind-ID، غباء عام)
  ⇒ لا توقف ولا إصلاح. هذا هو القياس.

الاستعمال: python run_pilot_b1.py [n] [model] [base_url]
"""

import json
import os
import sys

from world_b1 import generate_accepted_world_b1
from session_b1 import SessionB1
from llm_agent_b1 import LLMAgentB1
from shim_client import ShimClient, ShimError

B1_SEED_BASE = 4020                    # S_pilot (>=2000)؛ S_confirmatory تبقى مغلقة
HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(HERE, "provenance", "pilot_b1_a007_run")

# عيوب توقف الدفعة (أداة/عقد) مقابل ما لا يوقفها (سلوك النموذج)
INSTRUMENT_DEFECTS = ("SESSION_CRASH", "ORACLE_INCONSISTENT", "PROVENANCE_BROKEN")
# ملاحظة: INCORRECT_ACTION_EXHAUSTION و ACTIONABLE_INCOMPLETENESS **ليسا** عيبَي أداة —
# هما بالضبط ما جاءت الدفعة لقياسه (سلوك الوكيل). لا يوقفان الدفعة.


def classify(e):
    if isinstance(e, ShimError):
        return "PROVIDER_FAILURE"
    return "SESSION_CRASH"


def action_sequence(recs):
    """التسلسل الخام P/E كما وقع فعلًا (يشمل الاستطلاع الحر)."""
    seq = []
    for r in recs:
        p = r["payload"]
        if p["kind"] in ("FREE_OBS_COMMIT", "COMMITMENT"):
            a = p["deposit"].get("action", "")
            if a.startswith("PROBE"):
                seq.append("P")
            elif a.startswith("EXPERIMENT"):
                seq.append("E")
            else:
                seq.append("?")
    return "".join(seq)


def main(n=10, model="claude-sonnet-5", base_url="http://127.0.0.1:8787/v1"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(RUN_DIR, exist_ok=True)
    client = ShimClient(base_url=base_url, model=model)
    rows, halt = [], None

    for k in range(n):
        seed = B1_SEED_BASE + k
        w = generate_accepted_world_b1(seed)
        agent = LLMAgentB1(seed, client=client, model=model, endpoint=base_url)
        log = os.path.join(RUN_DIR, f"s{seed}.jsonl")
        sess = SessionB1(w, agent, log, os.path.join(RUN_DIR, f"s{seed}.side"))
        try:
            r = sess.run()
        except Exception as e:
            kind = classify(e)
            sess.arch.seal("SESSION_ABORTED", {"outcome": kind, "error": f"{type(e).__name__}: {e}"})
            r = {"outcome": kind, "error": f"{type(e).__name__}: {e}"}
        recs = sess.arch.records()
        kinds = [x["payload"]["kind"] for x in recs]
        chain_ok = sess.arch.verify_chain_file()
        row = {
            "seed": seed, "result": r, "seq": action_sequence(recs),
            "rejects": kinds.count("SCHEMA_REJECT") + kinds.count("PHASE_REJECT")
                       + kinds.count("BLIND_REJECT"),
            "refusals": kinds.count("REFUSED_ACTION"),
            "chain_ok": chain_ok,
            "prov": chain_ok and "EXEC_IDENTITY" in kinds and "EXEC_IDENTITY_END" in kinds,
            "true_audit": r.get("true_audit", 0),
        }
        # A-007: تشخيص التوقف (oracle-side، لا يراه الوكيل)
        inc = [x["payload"] for x in recs if x["payload"]["kind"] == "INCOMPLETENESS_VERIFIED"]
        stop = [x["payload"] for x in recs if x["payload"]["kind"] == "STOPPING_AUDIT"]
        row["incompleteness"] = inc[0] if inc else None
        row["stopping"] = stop[0] if stop else None
        rows.append(row)
        print(f"seed {seed}: {r['outcome']:<24} seq={row['seq']:<12} "
              f"P={r.get('N_probe')} E={r.get('N_experiment')} free={r.get('N_free')} "
              f"N={r.get('N_total')} blindID={r.get('blind_ID')} "
              f"floor={r.get('D_floor_task')} Drob={r.get('D_robust')} E_rob={r.get('E')} "
              f"rej={row['rejects']} ref={row['refusals']}")

        # قاعدة التوقف: عيب أداة/عقد فقط
        if r["outcome"] in INSTRUMENT_DEFECTS or row["true_audit"] or not chain_ok:
            halt = (seed, r["outcome"], "chain" if not chain_ok else "audit/crash")
            print(f"\n!! HALTING BATCH — instrument/contract defect at seed {seed}: {halt}")
            break

    # ---- A-007 metrics: actionability awareness ----
    incs = [r["incompleteness"] for r in rows if r.get("incompleteness")]
    n_inc = len(incs)
    n_wrong_exh = sum(1 for v in incs if v["verdict"] == "INCORRECT_ACTION_EXHAUSTION")
    n_actionable = sum(1 for v in incs if v["verdict"] == "ACTIONABLE_INCOMPLETENESS")
    n_correct_inc = sum(1 for v in incs if v["verdict"] == "CORRECT_INCOMPLETENESS")
    stops = [r["stopping"] for r in rows if r.get("stopping")] + incs
    premature = sum(1 for s_ in stops
                    if s_.get("still_attainable") or s_.get("attainable_within_remaining_budget"))
    print()
    print("--- A-007 actionability metrics ---")
    print(f"INCOMPLETE declarations      : {n_inc}")
    print(f"  CORRECT_INCOMPLETENESS     : {n_correct_inc}")
    print(f"  ACTIONABLE_INCOMPLETENESS  : {n_actionable}")
    print(f"  INCORRECT_ACTION_EXHAUSTION: {n_wrong_exh}")
    print(f"ActionabilityErrorRate       : "
          f"{(n_wrong_exh / n_inc):.3f}" if n_inc else "ActionabilityErrorRate       : n/a (no INCOMPLETE)")
    print(f"PrematureStopRate            : {premature}/{len(stops)} stops still resolvable"
          + (f" ({premature/len(stops):.3f})" if stops else ""))
    slacks = [s_["slack"] for s_ in stops if s_.get("slack") is not None]
    if slacks:
        print(f"slack at stop (B_rem - D_rem): min={min(slacks)} max={max(slacks)} "
              f"mean={sum(slacks)/len(slacks):.2f}")

    out = os.path.join(RUN_DIR, "b1_small_rows.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nrows written: {out}")
    if halt:
        print("batch halted — investigate before any further B1 runs.")
    return rows


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10,
         sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-5",
         sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8787/v1")
