"""run_pilot_a.py — Pilot-A الرسمي: LLM + depth-2 + إعلان كامل.

السؤال الوحيد: هل يستطيع موديل لغة حقيقي العيش داخل العقد الذي تحقق ميكانيكيًا؟
لا transfer، لا ادعاءات إحصائية. S_pilot = seeds 2000+ (محروقة تأكيديًا بموجب أ.2).

الاستعمال:  python run_pilot_a.py [n_sessions]
  الاعتماد: ANTHROPIC_API_KEY أو أي مصدر اعتماد يعرفه الـ SDK (ant auth login).
المخرجات: جدول امتثال بروتوكولي + E لكل جلسة + سجلات مختومة في provenance/pilot_a_run/.
"""

import json
import os
import sys

from world import generate_accepted_world
from session import Session
from llm_agent import LLMAgent

PILOT_SEED_BASE = 2000
HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(HERE, "provenance", "pilot_a_run")

AGENT_SIDE = ("AGENT_PROTOCOL_FAILURE",)
INFRA_SIDE = ("PROVIDER_FAILURE", "ADAPTER_FAILURE", "SESSION_CRASH")


def classify_exception(e):
    """taxonomy P-001: provider أم adapter أم ماسورة؟ بالأنواع الرسمية للـ SDK لا بأسماء الاستثناءات."""
    try:
        import anthropic
    except ImportError:
        anthropic = None
    if anthropic is not None:
        if isinstance(e, (anthropic.BadRequestError, anthropic.UnprocessableEntityError)):
            return "ADAPTER_FAILURE"          # نحن بنينا طلبًا سيئًا (400/422)
        if isinstance(e, anthropic.APIError):
            return "PROVIDER_FAILURE"         # auth / rate / 5xx / connection / timeout
    return "SESSION_CRASH"                    # world/session bug — الوحيد الذي يبرر لمس الماسورة


def main(n=3, make_agent=None, run_dir=RUN_DIR):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if make_agent is None:
        try:
            import anthropic
            client = anthropic.Anthropic()          # يحل الاعتماد من البيئة أو ملف الـ profile
        except ImportError:
            print("حزمة anthropic غير مثبتة — pip install anthropic")
            return None
        except Exception as e:                      # لا اعتماد متاح
            print(f"لا يمكن إنشاء عميل Anthropic: {type(e).__name__}: {e}")
            print("Pilot-A يحتاج LLM حقيقيًا (ANTHROPIC_API_KEY أو ant auth login).")
            return None
        make_agent = lambda seed: LLMAgent(seed, client=client)

    os.makedirs(run_dir, exist_ok=True)
    rows = []
    for k in range(n):
        seed = PILOT_SEED_BASE + k
        w = generate_accepted_world(seed)
        sess = Session(w, make_agent(seed),
                       os.path.join(run_dir, f"s{seed}.jsonl"),
                       os.path.join(run_dir, f"s{seed}.side"))
        try:
            r = sess.run()
        except Exception as e:
            # taxonomy أولًا — provider أم adapter أم ماسورة؟ لا نعدل شيئًا قبل التصنيف.
            kind = classify_exception(e)
            r = sess.abort(kind, f"{type(e).__name__}: {e}")
        kinds = [x["payload"]["kind"] for x in sess.arch.records()]
        row = {"seed": seed, "result": r,
               "rejects": kinds.count("SCHEMA_REJECT") + kinds.count("PHASE_REJECT")
                          + kinds.count("BLIND_REJECT"),
               "refusals": kinds.count("REFUSED_ACTION") + kinds.count("FREE_OBS_REFUSED"),
               "provenance": (sess.arch.verify_chain_file()
                              and "EXEC_IDENTITY" in kinds and "EXEC_IDENTITY_END" in kinds
                              and ("SESSION_END" in kinds or "SESSION_ABORTED" in kinds))}
        rows.append(row)
        print(f"seed {seed}: {r['outcome']:<30} E={r.get('E')}  "
              f"blind_ID={r.get('blind_ID')}  N_total={r.get('N_total')}  "
              f"D_pred={w.D_pred}  rejects={row['rejects']}  refusals={row['refusals']}")

    # تقرير Pilot-A: العائلات الخمس فقط. E/calibration = diagnostic لا غير.
    total = len(rows)
    outcomes = [row["result"]["outcome"] for row in rows]
    completed = sum(1 for o in outcomes if o not in AGENT_SIDE + INFRA_SIDE)
    compliant = sum(1 for o in outcomes if o not in AGENT_SIDE)
    print("\n--- Pilot-A report: five result families ---")
    print(f"1. contract compliance rate : {compliant}/{total}")
    print(f"2. schema reject/retry rate : {sum(r['rejects'] for r in rows)} rejects / {total} sessions")
    print(f"3. invalid intervention rate: {sum(r['refusals'] for r in rows)} refusals / {total} sessions")
    print(f"4. session completion rate  : {completed}/{total}")
    print(f"5. provenance completeness  : {sum(1 for r in rows if r['provenance'])}/{total} "
          f"(chain valid + exec identity sealed at start and end + terminal record)")
    print("E/calibration مسجلة diagnostic فقط في هذه المرحلة.")

    # taxonomy الفشل (P-001): فقط world/session bug يبرر لمس الماسورة.
    tax = {"adapter_failure": 0, "contract_non_compliance": 0,
           "provider_api_failure": 0, "world_session_bug": 0}
    for o in outcomes:
        if o == "AGENT_PROTOCOL_FAILURE":
            tax["contract_non_compliance"] += 1
        elif o == "PROVIDER_FAILURE":
            tax["provider_api_failure"] += 1
        elif o == "ADAPTER_FAILURE":
            tax["adapter_failure"] += 1
        elif o == "SESSION_CRASH":
            tax["world_session_bug"] += 1
    print("\nfailure taxonomy:", json.dumps(tax))
    print("القاعدة: LLM adapts to the contract, not the contract to the LLM —"
          " تعديل الماسورة مشروع فقط للفئة الأخيرة.")
    return rows


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
