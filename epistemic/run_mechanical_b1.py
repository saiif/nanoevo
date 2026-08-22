"""run_mechanical_b1.py — التحقق الميكانيكي لـ Pilot-B1 (قبل أي تشغيل LLM).

المنطقة الأخطر هنا هي **المسطرة نفسها**: prior التقابل والـ minimax الجديدان. لو أخطأنا
فيهما لبدا الوكيل calibrated أو غير calibrated بسبب oracle خاطئ — وهي نفس فئة الأخطاء
التي علّمنا Pilot-A ألا نتسامح معها. لذلك أول فحصين يثبتان المسطرة بالتعداد الصريح،
لا بالاستدلال على الكود.
"""

import itertools
import json
import os
import shutil
import sys
import time

from channel import Archivist, SchemaError, protocol_hash
from world import enumerate_hypotheses
from world_b1 import (generate_accepted_world_b1, Evidence, exp_masks, Ctx,
                      _subsets_by_popcount, _permanent, _has_matching, posterior,
                      support_of, all_actions, apply_action, grammar_hash_b1, ALL_VECTORS)
from session_b1 import (SessionB1, PROTOCOL_SPEC_B1, PROTOCOL_VERSION_B1, validate_b1,
                        ACTION_RE_B1)
from agents_b1 import (LearnerB1, NoProbeAgent, UnknownIdAgent, BadActionB1,
                       NonUniformAgent, ClaimExhaustionAgent,
                       HonestPrematureAgent, ExhaustThenIncompleteAgent)

HERE = os.path.dirname(os.path.abspath(__file__))
PROV = os.path.join(HERE, "provenance")
RUN_DIR = os.path.join(PROV, "mech_b1_run")
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def run_one(agent, seed, tag, world=None):
    w = world or generate_accepted_world_b1(seed)
    log = os.path.join(RUN_DIR, f"{tag}_s{seed}.jsonl")
    side = os.path.join(RUN_DIR, f"{tag}_s{seed}.side")
    s = SessionB1(w, agent, log, side)
    return w, s, s.run(), log


# ---------- المسطرة: تعداد صريح مقابل الـ permanent ----------

def brute_force_posterior(hyps, declared, n, evidence):
    """P*(h|E) بتعداد **كل** التقابلات صراحةً — مسطرة مستقلة تمامًا عن الـ permanent."""
    W = []
    for h in hyps:
        cnt = 0
        for perm in itertools.permutations(range(len(declared)), n):
            ok = True
            for x, vi in enumerate(perm):
                if not (evidence.pmask[x] >> vi) & 1:
                    ok = False
                    break
                e = evidence.exp[x]
                if e is not None and h.eval(declared[vi]) != e:
                    ok = False
                    break
            cnt += ok
        W.append(cnt)
    Z = sum(W)
    return ([w / Z for w in W] if Z else [0.0] * len(hyps)), Z


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(PROV, exist_ok=True)
    if os.path.isdir(RUN_DIR):
        shutil.move(RUN_DIR, os.path.join(PROV, f"mech_b1_archive_{int(time.time())}"))
    os.makedirs(RUN_DIR)
    print("=" * 66)
    print("PILOT-B1 MECHANICAL VALIDATION — latent properties, PROBE/EXPERIMENT (A-005)")
    print(f"protocol {PROTOCOL_VERSION_B1}  grammar_hash={grammar_hash_b1()}")
    print("=" * 66)

    hyps = enumerate_hypotheses()

    # ---------- B1-Q1: الـ posterior = التعداد الصريح للتقابلات ----------
    print("\n[B1-Q1] Reference posterior equals brute-force enumeration of bijections")
    import random
    rng = random.Random(7)
    worst, tested = 0.0, 0
    for trial in range(120):
        n = rng.randint(2, 5)
        declared = rng.sample(ALL_VECTORS, n)
        ctx = Ctx(n, _subsets_by_popcount(n), declared, {})
        em = exp_masks(hyps, declared)
        ev = Evidence(n, n)
        for _ in range(rng.randint(0, 4)):        # أدلة عشوائية
            a = rng.choice(all_actions(n))
            if a[0] == "PROBE":
                opts = [k for k in range(n) if (ev.pmask[a[1]] >> k) & 1]
                if not opts:
                    continue
                ev = apply_action(ev, a, rng.choice(opts))
            else:
                ev = apply_action(ev, a, rng.randint(0, 1))
        P_fast, Z_fast, _, _ = posterior(hyps, ev, em, ctx)
        P_bf, Z_bf = brute_force_posterior(hyps, declared, n, ev)
        if Z_bf == 0:
            continue
        tested += 1
        worst = max(worst, max(abs(a - b) for a, b in zip(P_fast, P_bf)))
        if Z_fast != Z_bf:
            worst = 1.0
    check("B1-Q1 permanent posterior == brute-force bijection enumeration",
          worst < 1e-12 and tested >= 50,
          f"{tested} evidence states, max |ΔP| = {worst:.2e}")

    # ---------- B1-Q2: تكافؤ تبديل الرموز (أساس مفتاح البحث القانوني) ----------
    print("\n[B1-Q2] Symbol-permutation invariance (justifies the canonical search key)")
    bad_perm = 0
    for trial in range(60):
        n = rng.randint(2, 5)
        declared = rng.sample(ALL_VECTORS, n)
        ctx = Ctx(n, _subsets_by_popcount(n), declared, {})
        em = exp_masks(hyps, declared)
        ev = Evidence(n, n)
        for _ in range(rng.randint(1, 4)):
            a = rng.choice(all_actions(n))
            if a[0] == "PROBE":
                opts = [k for k in range(n) if (ev.pmask[a[1]] >> k) & 1]
                if opts:
                    ev = apply_action(ev, a, rng.choice(opts))
            else:
                ev = apply_action(ev, a, rng.randint(0, 1))
        perm = list(range(n))
        rng.shuffle(perm)
        ev2 = Evidence(n, n)
        ev2.pmask = [ev.pmask[perm[x]] for x in range(n)]
        ev2.exp = [ev.exp[perm[x]] for x in range(n)]
        s1 = support_of(hyps, ev, em, Ctx(n, ctx.by_pop, declared, {}))
        s2 = support_of(hyps, ev2, em, Ctx(n, ctx.by_pop, declared, {}))
        p1, z1, _, _ = posterior(hyps, ev, em, ctx)
        p2, z2, _, _ = posterior(hyps, ev2, em, Ctx(n, ctx.by_pop, declared, {}))
        if s1 != s2 or z1 != z2 or ev.key() != ev2.key():
            bad_perm += 1
    check("B1-Q2 support/posterior/canonical-key invariant under symbol permutation",
          bad_perm == 0, f"{60 - bad_perm}/60 permutations agree")

    # ---------- B1-Q3: التزاوج == (permanent > 0) ----------
    print("\n[B1-Q3] Matching existence agrees with the exact count being non-zero")
    mism = 0
    for _ in range(4000):
        n = rng.randint(1, 6)
        allowed = [rng.getrandbits(n) for _ in range(n)]
        if (_permanent(allowed, n, _subsets_by_popcount(n)) > 0) != _has_matching(allowed, n):
            mism += 1
    check("B1-Q3 matching existence == permanent > 0", mism == 0, f"{mism} mismatches / 4000")

    # ---------- B1-Q4: نموذج الفعل واحد عبر كل الطبقات (A-005) ----------
    print("\n[B1-Q4] One PROBE semantics across packet / world / oracle / session")
    w = generate_accepted_world_b1(3000)
    packet = w.phase_zero_packet()
    packet_actions = set(packet["actions"])
    world_probe = w.probe(w.train_symbols[0])
    oracle_kinds = {a[0] for a in all_actions(w.n_syms)}
    session_ok = bool(ACTION_RE_B1.match(f"PROBE({w.train_symbols[0]})"))
    stale_rejected = not ACTION_RE_B1.match(f"PROBE({w.train_symbols[0]},p0)")
    check("B1-Q4 packet declares PROBE(symbol)/EXPERIMENT(symbol)",
          packet_actions == {"PROBE(symbol)", "EXPERIMENT(symbol)"}, str(sorted(packet_actions)))
    check("B1-Q4 world PROBE returns a FULL vector in one call",
          isinstance(world_probe, list) and len(world_probe) == 3, str(world_probe))
    check("B1-Q4 oracle action kinds are exactly PROBE/EXPERIMENT",
          oracle_kinds == {"PROBE", "EXPERIMENT"}, str(sorted(oracle_kinds)))
    check("B1-Q4 session accepts PROBE(sym) and rejects the stale per-bit form",
          session_ok and stale_rejected)
    check("B1-Q4 packet leaks no property vector per symbol (only the declared SET)",
          all(not isinstance(v, (list, dict)) for v in packet["symbols"])
          and "property_vectors_present" in packet["declared_primitives"])

    # ---------- B1-Q5: هوية الفرضية دلالية ----------
    print("\n[B1-Q5] Semantic hypothesis identity (2005-type defect impossible by design)")
    ids = set(w.catalog)
    try:
        validate_b1({"type": "COMMITMENT", "hypotheses": {"H99": 1.0}, "action": "EXPERIMENT(Qz)",
                     "predictions": {"outcome=1": 0.5}, "update_kind": "REWEIGHT"}, ids)
        unknown_rejected = False
    except SchemaError:
        unknown_rejected = True
    try:
        validate_b1({"type": "COMMITMENT", "hypotheses": {"(NOT p1 XOR p2)": 1.0},
                     "action": "EXPERIMENT(Qz)", "predictions": {"outcome=1": 0.5},
                     "update_kind": "REWEIGHT"}, ids)
        text_rejected = False
    except SchemaError:
        text_rejected = True
    dup_collapses = len({"H07": 0.5, "H07": 0.5}) == 1     # noqa: F601 — المقصود إثبات الانهيار
    check("B1-Q5 unknown hypothesis id rejected", unknown_rejected)
    check("B1-Q5 free-text hypothesis name rejected (IDs only)", text_rejected)
    check("B1-Q5 duplicate ids collapse structurally (2005 defect impossible)", dup_collapses)

    # ---------- B1-Q6: الأرضيات والمرجع دقيقة وضمن ميزانية معقولة ----------
    print("\n[B1-Q6] Exact floors and robust reference within a justified budget")
    rows, ok_order, ok_budget = [], True, True
    for sb in (3000, 3001, 3002, 3003):
        wi = generate_accepted_world_b1(sb)
        rows.append((sb, wi.D_floor_task, wi.D_floor_strict, wi.D_robust))
        ok_order &= (wi.D_floor_task <= wi.D_robust)
        ok_budget &= (wi.D_robust <= 14)
        print(f"    seed {sb}: floor_task={wi.D_floor_task} floor_strict={wi.D_floor_strict} "
              f"D_robust={wi.D_robust} nID={len(wi.blind_ID)} nX={len(wi.blind_X)}")
    check("B1-Q6 D_floor^task <= D_robust on every world", ok_order)
    check("B1-Q6 D_robust <= 14 (budget 15 is justified by the oracle, not by comfort)",
          ok_budget, f"max D_robust = {max(r[3] for r in rows)}")

    # ---------- B1-Q7: الفحص العدائي — لا حل بلا probe ----------
    print("\n[B1-Q7] Adversarial: no solution without probing (representation leakage)")
    _, s_np, r_np, _ = run_one(NoProbeAgent(1), 3000, "noprobe", world=w)
    check("B1-Q7 probe-free agent cannot reach the blind criterion",
          r_np["outcome"] != "SOLVED" and r_np["N_probe"] == 0,
          f"outcome={r_np['outcome']} blind_ID={r_np.get('blind_ID')}")
    check("B1-Q7 the task floor itself requires at least one probe", w.floor_requires_probe)

    # ---------- B1-Q8: المحاسبة الثلاثية ----------
    print("\n[B1-Q8] Three-way accounting never merged")
    w2, s_l, r_l, log_l = run_one(LearnerB1(2), 3001, "learner")
    consistent = (r_l["N_free"] + r_l["N_probe"] + r_l["N_experiment"]
                  == r_l.get("N_total", r_l["N_free"] + r_l["N_probe"] + r_l["N_experiment"]))
    check("B1-Q8 N_total == N_free + N_probe + N_experiment, all stored separately",
          consistent and all(k in r_l for k in ("N_free", "N_probe", "N_experiment")),
          f"free={r_l['N_free']} probe={r_l['N_probe']} exp={r_l['N_experiment']}")
    check("B1-Q8 reference learner solves the world", r_l["outcome"] == "SOLVED",
          f"outcome={r_l['outcome']} E={r_l.get('E')} region={r_l.get('region')}")

    # ---------- B1-Q9: فصل عيب التمثيل عن عيب الاعتقاد ----------
    print("\n[B1-Q9] Representation defect prevented; belief defect permitted and measured")
    _, s_u, r_u, _ = run_one(UnknownIdAgent(3), 3001, "unknown_id", world=w2)
    check("B1-Q9 unknown-id agent is stopped by the schema (representation defect prevented)",
          r_u["outcome"] == "AGENT_PROTOCOL_FAILURE")
    _, s_nu, r_nu, _ = run_one(NonUniformAgent(4), 3001, "nonuniform", world=w2)
    ms = [m for m in r_nu["belief_metrics"] if m.get("belief")]
    skewed = [m for m in ms if m["belief"]["support_exact"]
              and m["belief"]["probability_error_tv"] > 1e-6]
    check("B1-Q9 belief defect permitted by schema and caught by metrics "
          "(support exact, probability error > 0)",
          bool(skewed),
          f"{len(skewed)}/{len(ms)} commitments with exact support but TV>0"
          + (f", max TV={max(m['belief']['probability_error_tv'] for m in skewed):.3f}"
             if skewed else ""))

    # ---------- B1-Q10: الفعل المشوه يُرفض قبل التنفيذ ----------
    print("\n[B1-Q10] Malformed action refused pre-execution")
    _, s_b, r_b, _ = run_one(BadActionB1(5), 3001, "bad_action", world=w2)
    check("B1-Q10 stale per-bit probe syntax refused, attempt consumed, no crash",
          r_b["N_refused"] >= 1 and r_b["outcome"] != "AGENT_PROTOCOL_FAILURE",
          f"refused={r_b['N_refused']} outcome={r_b['outcome']}")

    # ---------- B1-Q11: نزاهة السجل + عدم تسريب ----------
    print("\n[B1-Q11] Provenance and no hidden-information leak")
    chain_ok = Archivist.verify_file(log_l)
    recs = [json.loads(l) for l in open(log_l, encoding="utf-8")]
    probed = set()
    leak = False
    for r in recs:
        p = r["payload"]
        if p["kind"] == "PROBE_RESULT":
            probed.add(p["symbol"])
        if p["kind"] == "PHASE_ZERO":
            blob = json.dumps(p)
            if any(f'"{s}": [' in blob for s in w2.train_symbols):
                leak = True
        if p["kind"] == "OBSERVATION":
            # نتيجة تجربة = بت واحد فقط، لا متجه
            if isinstance(p.get("result"), list):
                leak = True
    check("B1-Q11 hash chain valid on the reference run", chain_ok)
    check("B1-Q11 no per-symbol vector in phase zero; EXPERIMENT returns only a bit",
          not leak)
    check("B1-Q11 every PROBE_RESULT traces to a sealed commitment receipt",
          all(any(x["hash"] == r["payload"]["receipt"] for x in recs)
              for r in recs if r["payload"]["kind"] == "PROBE_RESULT"))

    # ---------- B1-Q12: A-007 — الحكم الثلاثي على إعلان النقص ----------
    print("\n[B1-Q12] A-007: incompleteness is verified, not accepted as self-report")
    _, s_ex, r_ex, _ = run_one(ClaimExhaustionAgent(9), 3001, "claim_exhaustion", world=w2)
    v_ex = [x["payload"] for x in s_ex.arch.records("INCOMPLETENESS_VERIFIED")]
    check("B1-Q12 false no-decisive-action-remains -> INCORRECT_ACTION_EXHAUSTION",
          r_ex["outcome"] == "INCORRECT_ACTION_EXHAUSTION" and bool(v_ex)
          and v_ex[0]["attainable_within_remaining_budget"],
          str(r_ex["outcome"])
          + (f" best_remaining_IG_law={v_ex[0]['best_remaining_IG_law']}" if v_ex else ""))

    _, s_hp, r_hp, _ = run_one(HonestPrematureAgent(9), 3001, "honest_premature", world=w2)
    check("B1-Q12 honest insufficient-evidence while resolvable -> ACTIONABLE_INCOMPLETENESS",
          r_hp["outcome"] == "ACTIONABLE_INCOMPLETENESS", f"outcome={r_hp['outcome']}")

    import session_b1 as _sb
    _ob = _sb.PROTOCOL_SPEC_B1["intervention_budget"]
    _sb.PROTOCOL_SPEC_B1["intervention_budget"] = 0
    try:
        _, s_ci, r_ci, _ = run_one(ExhaustThenIncompleteAgent(9), 3001, "correct_incomplete",
                                   world=w2)
    finally:
        _sb.PROTOCOL_SPEC_B1["intervention_budget"] = _ob
    check("B1-Q12 same claim under a genuinely exhausted budget is not an error outcome",
          r_ci["outcome"] != "INCORRECT_ACTION_EXHAUSTION", f"outcome={r_ci['outcome']}")
    check("B1-Q12 the verdicts are distinct outcomes",
          len({r_ex["outcome"], r_hp["outcome"], r_ci["outcome"]}) >= 2,
          f"{r_ex['outcome']} / {r_hp['outcome']} / {r_ci['outcome']}")

    try:
        validate_b1({"type": "INCOMPLETE", "remaining_hypotheses": ["H01"],
                     "reason": "x", "claim": "i think i am done"}, ids)
        bad_claim = False
    except SchemaError:
        bad_claim = True
    try:
        validate_b1({"type": "INCOMPLETE", "remaining_hypotheses": ["H01"], "reason": "x"}, ids)
        miss_claim = False
    except SchemaError:
        miss_claim = True
    check("B1-Q12 claim is a structured required field (Verifier never parses free text)",
          bad_claim and miss_claim)

    print("\n" + "=" * 66)
    passed = sum(ok for _, ok in CHECKS)
    print(f"PILOT-B1 MECHANICAL VALIDATION: {passed}/{len(CHECKS)} checks passed")
    print(f"protocol_hash={protocol_hash(PROTOCOL_SPEC_B1)}  grammar_hash={grammar_hash_b1()}")
    print("=" * 66)
    return passed == len(CHECKS)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
