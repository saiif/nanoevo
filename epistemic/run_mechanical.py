"""run_mechanical.py — التحقق الميكانيكي (الملحق ب): هل الآلة تعمل كما يقول الورق؟

سبعة أسئلة ميكانيكية + جدول الانتهاكات (أ.3) + قواعد A-003، كلها PASS/FAIL.
بلا ادعاءات إحصائية. S_mechanical = seeds 1..20 (محروقة تأكيديًا إلى الأبد بموجب أ.2).

المخرجات: provenance/mech_run/ (التشغيل الأخير)؛ أي تشغيل سابق يُؤرشف إلى
provenance/mech_run_archive_<ts>/ — لا يُمسح الفشل الذي أدى إلى تعديل (A-001).
"""

import json
import os
import shutil
import sys
import time

from world import generate_accepted_world, d_min_bruteforce_check, World, equivalence_classes
from channel import schema_hash, blind_schema_hash, protocol_hash, validate, Archivist
from session import Session, Verifier, PROTOCOL_SPEC, PROTOCOL_VERSION
from agents import (LearnerAgent, ControlAgent, MalformedOnceAgent,
                    MalformedTwiceAgent, LeakProbeAgent, BadActionAgent,
                    ExtraFreeObsAgent, InadequacyLoopAgent, BlindMalformedAgent,
                    IncompleteClaimAgent)

HERE = os.path.dirname(os.path.abspath(__file__))
PROV_DIR = os.path.join(HERE, "provenance")
RUN_DIR = os.path.join(PROV_DIR, "mech_run")
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def fresh(name):
    return os.path.join(RUN_DIR, name + ".jsonl"), os.path.join(RUN_DIR, name + ".side")


def run_one(agent, seed, tag):
    w = generate_accepted_world(seed)
    log, side = fresh(f"{tag}_s{seed}")
    s = Session(w, agent, log, side)
    result = s.run()
    return w, s, result, log, side


def kinds_of(session):
    return [r["payload"]["kind"] for r in session.arch.records()]


def main():
    # Windows consoles default to cp1252 — the Arabic/arrow strings below must not crash the run
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # provenance: لا نمسح الفشل الذي أدى للتعديل — نؤرشفه (A-001)
    os.makedirs(PROV_DIR, exist_ok=True)
    if os.path.isdir(RUN_DIR):
        shutil.move(RUN_DIR, os.path.join(PROV_DIR, f"mech_run_archive_{int(time.time())}"))
    os.makedirs(RUN_DIR)
    print("=" * 62)
    print("MECHANICAL VALIDATION — depth-2, two arms, frozen model-free bots")
    print(f"protocol {PROTOCOL_VERSION}  run_dir={os.path.relpath(RUN_DIR, HERE)}")
    print("=" * 62)

    # ---------- Q7: D_min صحيح (إعادة حساب مستقلة + قابل للفحص اليدوي) ----------
    print("\n[Q7] D_min correctness (independent recomputation)")
    ok7 = True
    for seed in (1, 2, 3):
        w = generate_accepted_world(seed)
        bf = d_min_bruteforce_check(w.hypotheses, w.train_vectors)
        ok7 &= (bf == w.D_min)
        print(f"    seed {seed}: minimax D_min={w.D_min}, bruteforce={bf}, "
              f"law={w.true_law_name()}")
    check("Q7 D_min matches independent brute-force", ok7)

    # ---------- تشغيل مرجعي: Learner ----------
    print("\n[RUN] Learner on seed 1")
    w1, s1, r1, log1, side1 = run_one(LearnerAgent(1), 1, "learner")
    print(f"    outcome={r1['outcome']}  N_total={r1.get('N_total','-')}  "
          f"D_pred={r1['D_pred_oracle_side']}  E={r1.get('E')}  "
          f"blind_ID={r1.get('blind_ID')}  blind_X={r1.get('blind_X')}  "
          f"conf_X={r1.get('conf_X')}")

    # ---------- Q1: لا تسريب — hidden info لا تظهر في أي payload يراه الوكيل ----------
    print("\n[Q1] No hidden-information leak to agent-visible channel")
    agent_visible_kinds = {"PHASE_ZERO", "FREE_OBS_RESULT", "OBSERVATION"}
    leaked = False
    secret_markers = [w1.true_law_name(), "D_min", "D_pred", "D_inst", "seed", "true_id",
                      *w1.blind_symbols]
    for rec in s1.arch.records():
        if rec["payload"]["kind"] in agent_visible_kinds:
            blob = json.dumps(rec["payload"])
            if any(m in blob for m in secret_markers):
                leaked = True
    # واختبار السلوك: فعل خارج المنطقة يُرفض قبل التنفيذ
    _, s_leak, r_leak, _, _ = run_one(LeakProbeAgent(4), 4, "leakprobe")
    refused = any(r["payload"]["kind"] == "REFUSED_ACTION" for r in s_leak.arch.records())
    check("Q1 no secrets in agent-visible payloads", not leaked)
    check("Q1 out-of-region action refused pre-execution, attempt consumed",
          refused and r_leak["N_refused"] == 1
          and r_leak["outcome"] in ("SOLVED", "BUDGET_EXHAUSTED", "FALSE_CERTAINTY"))

    # ---------- Q2: البوابة — لا تنفيذ بلا إيداع صالح مختوم ----------
    print("\n[Q2] Experimenter gate")
    gate_ok = True
    for rec in s1.arch.records():
        if rec["payload"]["kind"] == "OBSERVATION":
            ridx = rec["index"]
            prior = [r for r in s1.arch.records()[:ridx]
                     if r["payload"]["kind"] == "COMMITMENT"
                     and r["hash"] == rec["payload"]["receipt"]]
            gate_ok &= len(prior) == 1  # كل observation مربوطة بوصل ختم سابق لها
    check("Q2 every observation traces to a prior sealed commitment", gate_ok)

    # ---------- Q3: الاختبار الأعمى أعمى فعلًا ----------
    print("\n[Q3] Blind test blindness")
    kinds = kinds_of(s1)
    blind_ok = ("BLIND_PREDICTIONS" in kinds and "BLIND_TRUTH" in kinds
                and kinds.index("BLIND_PREDICTIONS") < kinds.index("BLIND_TRUTH"))
    issue_idx = kinds.index("BLIND_CASES_ISSUED")
    early = json.dumps([r["payload"] for r in s1.arch.records()[:issue_idx]])
    blind_syms_hidden = not any(s in early for s in w1.blind_symbols)
    check("Q3 predictions sealed strictly before truth revealed", blind_ok)
    check("Q3 blind symbols absent from all earlier records", blind_syms_hidden)

    # ---------- Q4: صمود السلسلة + كشف التلاعب ----------
    print("\n[Q4] Hash chain integrity + tamper detection")
    check("Q4 chain verifies on honest log", s1.arch.verify_chain_file())
    tampered = log1 + ".tampered"
    with open(log1, encoding="utf-8") as f:
        lines = f.readlines()
    rec = json.loads(lines[3])
    rec["payload"]["kind"] = "FORGED"
    lines[3] = json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n"
    with open(tampered, "w", encoding="utf-8") as f:
        f.writelines(lines)
    check("Q4 tampered log detected", not Archivist.verify_file(tampered))

    # ---------- Q5: فصل Evidence/Interpretation + عزل الـ reasoning ----------
    print("\n[Q5] Evidence/Interpretation separation, reasoning isolation")
    has_obs = "OBSERVATION" in kinds
    has_interp = "INTERPRETATION" in kinds
    side_text = open(side1, encoding="utf-8").read()
    reasoning_in_chain = any("free-thought" in json.dumps(r["payload"])
                             for r in s1.arch.records())
    check("Q5 evidence and interpretation stored as distinct sealed kinds",
          has_obs and has_interp)
    check("Q5 free reasoning lives only in side channel",
          len(side_text) > 0 and not reasoning_in_chain)

    # ---------- Q6: إعلانات القصور/الاكتفاء تمر عبر القناة بلا غموض ----------
    print("\n[Q6] Declarations via the channel")
    inad_ok = validate({"type": "INADEQUACY", "reason": "all H low likelihood",
                        "requested_family": "time-guarded"})
    check("Q6 sufficiency declaration sealed in reference run", "SUFFICIENCY" in kinds)
    check("Q6 inadequacy declaration validates under schema", inad_ok)

    # ---------- جدول الانتهاكات (أ.3) ----------
    print("\n[A.3] Violation table behaviour")
    _, s_m1, r_m1, _, _ = run_one(MalformedOnceAgent(5), 5, "malformed_once")
    retried = "SCHEMA_REJECT" in kinds_of(s_m1)
    check("A.3 malformed once → neutral retry → session continues",
          retried and r_m1["outcome"] != "AGENT_PROTOCOL_FAILURE")
    _, s_m2, r_m2, _, _ = run_one(MalformedTwiceAgent(6), 6, "malformed_twice")
    check("A.3 malformed twice → AgentProtocolFailure, E=0, included",
          r_m2["outcome"] == "AGENT_PROTOCOL_FAILURE" and r_m2["E"] == 0.0
          and r_m2.get("included_in_analysis") is True)

    # ---------- A-003: تصليب العقد قبل Pilot-A ----------
    print("\n[A-003] Pilot-A hardening rules")
    _, s_ba, r_ba, _, _ = run_one(BadActionAgent(12), 12, "bad_action")
    k_ba = kinds_of(s_ba)
    check("A-003 malformed FREE_OBS action refused (no crash), session continues",
          "FREE_OBS_REFUSED" in k_ba and r_ba["outcome"] != "AGENT_PROTOCOL_FAILURE")
    check("A-003 malformed COMMITMENT action refused pre-execution, attempt consumed",
          "REFUSED_ACTION" in k_ba and r_ba["N_refused"] == 2
          and r_ba["outcome"] == "SOLVED"
          and r_ba["N_total"] == r_ba["free_used"] + r_ba["N_interventions"])

    _, s_xf, r_xf, _, _ = run_one(ExtraFreeObsAgent(13), 13, "extra_free_obs")
    check("A-003 FREE_OBS after free phase → PHASE_REJECT → neutral retry → continues",
          "PHASE_REJECT" in kinds_of(s_xf) and r_xf["outcome"] == "SOLVED")

    _, s_in, r_in, _, _ = run_one(InadequacyLoopAgent(14), 14, "inadequacy_loop")
    check("A-003 INADEQUACY consumes an attempt → loop terminates at budget",
          r_in["outcome"] == "BUDGET_EXHAUSTED"
          and r_in["N_inadequacy"] == PROTOCOL_SPEC["intervention_budget"])

    _, s_b1, r_b1, _, _ = run_one(BlindMalformedAgent(15, n_bad=1), 15, "blind_malformed_once")
    check("A-003 malformed blind reply once → BLIND_REJECT → retry → SOLVED",
          "BLIND_REJECT" in kinds_of(s_b1) and r_b1["outcome"] == "SOLVED")
    _, s_b2, r_b2, _, _ = run_one(BlindMalformedAgent(16, n_bad=2), 16, "blind_malformed_twice")
    k_b2 = kinds_of(s_b2)
    check("A-003 malformed blind reply twice → AgentProtocolFailure, truth never revealed",
          r_b2["outcome"] == "AGENT_PROTOCOL_FAILURE" and r_b2.get("failure_stage") == "blind"
          and "BLIND_TRUTH" not in k_b2 and "BLIND_PREDICTIONS" not in k_b2)

    _, s_ic, r_ic, _, _ = run_one(IncompleteClaimAgent(17), 17, "incomplete_claim")
    ver = [r["payload"] for r in s_ic.arch.records("INCOMPLETENESS_VERIFIED")]
    check("A-003 false incompleteness claim detected → INCORRECT_INCOMPLETENESS_CLAIMED, E=0",
          r_ic["outcome"] == "INCORRECT_INCOMPLETENESS_CLAIMED" and r_ic["E"] == 0.0
          and ver and ver[0]["correct"] is False)
    # الحالة الصحيحة: لا تظهر في عالم مقبول (كل الفئات مفردة) — تُختبر على عالم مرفوض
    correct_case = None
    for k in range(200):
        w_rej = World(99 * 1000 + k)
        if w_rej.accepted:
            continue
        classes = equivalence_classes(w_rej.hypotheses, w_rej.train_vectors)
        cls = next((c for c in classes if len(c) >= 2 and w_rej.true_id in c), None)
        if cls:
            names = [w_rej.hypotheses[i].name() for i in cls]
            correct_case = Verifier(w_rej).check_incompleteness(names)["correct"]
            break
    check("A-003 Verifier accepts a genuinely non-identifiable remaining set",
          correct_case is True)

    # ---------- عرض Learner vs Control (بلا إحصاء — ماسورة فقط) ----------
    print("\n[DEMO] Learner vs Control on mechanical seeds (no statistical claims)")
    print(f"    {'seed':>4} {'Dpred':>5} {'nID/nX':>6} | "
          f"{'E_L':>5} {'IDL':>4} {'XL':>4} {'cfX_L':>5} | "
          f"{'E_C':>5} {'IDC':>4} {'XC':>4}")
    for seed in (7, 8, 9, 10, 11):
        wl, _, rl, _, _ = run_one(LearnerAgent(seed), seed, "L")
        wc, _, rc, _, _ = run_one(ControlAgent(seed), seed, "C")
        ov = "  <AUDIT>" if rl.get("oracle_violation") or rc.get("oracle_violation") else ""
        fmt = lambda x: "  - " if x is None else f"{x:4.2f}"
        print(f"    {seed:>4} {str(wl.D_pred):>5} {len(wl.blind_ID)}/{len(wl.blind_X):<4} | "
              f"{fmt(rl.get('E'))} {fmt(rl.get('blind_ID'))} {fmt(rl.get('blind_X'))} "
              f"{fmt(rl.get('conf_X')):>5} | "
              f"{fmt(rc.get('E'))} {fmt(rc.get('blind_ID'))} {fmt(rc.get('blind_X'))}{ov}")

    # ---------- الحصيلة ----------
    print("\n" + "=" * 62)
    passed = sum(ok for _, ok in CHECKS)
    print(f"MECHANICAL VALIDATION: {passed}/{len(CHECKS)} checks passed")
    print(f"schema_hash={schema_hash()}  blind_schema_hash={blind_schema_hash()}  "
          f"protocol_hash={protocol_hash(PROTOCOL_SPEC)}")
    print("=" * 62)
    return passed == len(CHECKS)


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)
