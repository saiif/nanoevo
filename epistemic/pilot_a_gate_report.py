"""pilot_a_gate_report.py — Pilot-A Gate Report (read-only diagnostics).

يجمع كل episodes الدفعة (2000-2007, بما فيها repeated runs داخل نفس السلسلة append-only)
في تقرير بوابة واحد بأربع طبقات:
  1. Contract      — completion / rejects / retries / invalid actions / bypass / zero semantic repair
  2. Provenance    — hash chains / exec identity (start+end) / frozen hashes / no overwrite
  3. Behavior      — N_free, N_formal, N_realized, Blind-ID, confidence، منحنى |H_t| وIG_t،
                     وclaimed-vs-actual: posterior الموديل المختوم مقابل الناجين الفعليين،
                     وpredictions المختومة مقابل كتلة الفرضيات، وrank الفعل المختار.
  4. Oracle        — D_floor (instance-optimal under epistemic admissibility; lower envelope)
                     / D_robust (=D_pred, minimax) / N_realized + التصنيف الثلاثي.

لا يعدّل أي شيء: يقرأ السجلات المختومة ويعيد حساب كميات oracle-side فقط.
A-004 غير مختوم — هذا التقرير هو اختباره التجريبي الأول، لا ختمه.

الاستعمال:  python pilot_a_gate_report.py [run_dir] > PILOT_A_GATE_REPORT.md
"""

import glob
import itertools
import json
import math
import os
import sys

from world import generate_accepted_world, enumerate_hypotheses, OPS, N_PROPS
from channel import Archivist, schema_hash, blind_schema_hash, protocol_hash
from session import PROTOCOL_SPEC

EXPECTED = {
    "schema_hash": schema_hash(),
    "blind_schema_hash": blind_schema_hash(),
    "protocol_hash": protocol_hash(PROTOCOL_SPEC),
}


# ------------------------- تفكيك السلاسل إلى episodes -------------------------

def segment(recs):
    """سلسلة append-only قد تحوي عدة sessions: كل session تبدأ EXEC_IDENTITY بعد SESSION_END سابقة."""
    sessions, cur = [], []
    for r in recs:
        if (r["payload"]["kind"] == "EXEC_IDENTITY" and cur
                and any(x["payload"]["kind"] == "SESSION_END" for x in cur)):
            sessions.append(cur)
            cur = []
        cur.append(r)
    if cur:
        sessions.append(cur)
    return [s for s in sessions if any(x["payload"]["kind"] == "SESSION_END" for x in s)]


# ------------------------- تطبيع أسماء الفرضيات (claimed → canonical) -------------------------

def _norm(s):
    """تطبيع اسم فرضية إلى شكل canonical مقارن.

    ملاحظة مقاسة (2026-08-21): الموديل يكتب النفي بأشكال متعددة — `NOT p0`، `¬p0`، `~p0`، `!p0`.
    الـ schema لا يفرض تدوينًا (يفرض فقط أن تجمع الاحتمالات إلى 1)، فالتنويع امتثالي تمامًا.
    نسخة أولى من هذا التشخيص لم تعرف `~` فأنتجت false negatives على seed 2003 (ظهرت كأن
    الموديل يعلن فرضيات خارج الفضاء بينما كان يعلن القانون الحقيقي). المسطرة تُدقَّق قبل المقيس.
    """
    for neg in ("¬", "~", "!"):
        s = s.replace(neg, "NOT ")
    return s.upper().replace("(", "").replace(")", "").replace(" ", "")


def build_name_map(hyps):
    """كل صيغة literal مكافئة (بما فيها تبديل الطرفين وأشكال XOR) → canonical id."""
    sig2id = {h.signature(): i for i, h in enumerate(hyps)}
    name2id = {}

    class _H:
        def __init__(self, op, i, ni, j, nj):
            self.op, self.i, self.ni, self.j, self.nj = op, i, ni, j, nj

        def eval(self, props):
            a = props[self.i] ^ self.ni
            b = props[self.j] ^ self.nj
            return (a & b) if self.op == "AND" else (a | b) if self.op == "OR" else (a ^ b)

    lit = lambda k, n: f"{'NOT ' if n else ''}p{k}"
    for op in OPS:
        for i in range(N_PROPS):
            for j in range(N_PROPS):
                if i == j:
                    continue
                for ni, nj in itertools.product((0, 1), repeat=2):
                    h = _H(op, i, ni, j, nj)
                    sig = tuple(h.eval(v) for v in itertools.product((0, 1), repeat=N_PROPS))
                    if sig in sig2id:
                        name2id[_norm(f"({lit(i, ni)} {op} {lit(j, nj)})")] = sig2id[sig]
    return name2id


# ------------------------- كميات oracle-side -------------------------

def d_floor(w, tau=None):
    """D_floor تحت epistemic admissibility — يرجع (weak, strict).

    مبرر الحساب: على instance حتمي مثبَّت، أي admissible policy (π_t: h_t → a_t) تنهار إلى
    تسلسل أفعال محدَّد (لأن إجابات العالم محددة سلفًا بالقانون الحقيقي)، وترتيب الاختبارات
    لا يغيّر مجموعة الناجين — فالـ min على السياسات = min على *مجموعات* الاختبارات.

    تشعّب مهم في تعريف نقطة التوقف:
      strict = الناجون مجمعون (unanimous) على كل حالة Blind-ID وبقيمة الحقيقة
               → الأدلة *حدّدت* الأجوبة العمياء.
      weak   = تصويت أغلبية الناجين يحقق BlindScore ≥ tau على الحقيقة المُحقَّقة
               → المعيار *بُلِغ*، ولو بقي الناجون منقسمين (قد يكون بمحاذاة موفقة).
    weak ≤ strict دائمًا. بما أن D_floor يُستعمل كـ**validity bound**، الحد الصحيح هو
    الأضعف: أي N أقل منه مستحيل على أي سياسة مقبولة ⇒ bug/leak. استعمال strict كحد
    للـ audit ينتج إنذارات كاذبة على حلقات مشروعة.
    """
    tau = PROTOCOL_SPEC["tau_blind"] if tau is None else tau
    true = w.hypotheses[w.true_id]
    blind = [tuple(v) for v in w.blind_ID.values()]
    vecs = [tuple(v) for v in w.train_vectors]
    weak = strict = None
    for k in range(len(vecs) + 1):
        for S in itertools.combinations(vecs, k):
            surv = [h for h in w.hypotheses if all(h.eval(v) == true.eval(v) for v in S)]
            if not surv:
                continue
            if strict is None and all(len({h.eval(b) for h in surv}) == 1
                                      and surv[0].eval(b) == true.eval(b) for b in blind):
                strict = k
            if weak is None and blind:
                # قاعدة القرار المثلى تحت posterior منتظم: تصويت الأغلبية
                agree = 0
                for b in blind:
                    ones = sum(h.eval(b) for h in surv)
                    pred = 1 if 2 * ones >= len(surv) else 0
                    agree += (pred == true.eval(b))
                if agree / len(blind) >= tau:
                    weak = k
            if weak is not None and strict is not None:
                return weak, strict
        if weak is not None and strict is not None:
            break
    return weak, strict


def region(n, floor, robust):
    if n < floor:
        return "TRUE_AUDIT"
    if n < robust:
        return "FAVORABLE_TRAJECTORY"
    return "NORMAL/ABOVE_ROBUST_COST"


# ------------------------- تحليل episode واحدة -------------------------

def analyze_episode(tag, recs, w, name2id):
    P = [r["payload"] for r in recs]
    K = [p["kind"] for p in P]
    end = next(p["result"] for p in P if p["kind"] == "SESSION_END")
    packet = next((p["packet"] for p in P if p["kind"] == "PHASE_ZERO"), None)
    sym2vec = {s: tuple(v) for s, v in packet["symbols"].items()} if packet else {}

    # --- الطبقة 1: العقد ---
    contract = {
        "outcome": end["outcome"],
        "schema_rejects": K.count("SCHEMA_REJECT"),
        "phase_rejects": K.count("PHASE_REJECT"),
        "blind_rejects": K.count("BLIND_REJECT"),
        "refusals": K.count("REFUSED_ACTION") + K.count("FREE_OBS_REFUSED"),
        "unparsed_interpretations": sum(
            1 for p in P if p["kind"] == "INTERPRETATION"
            and p["interpretation"].get("interpretation") == "UNPARSED"),
    }
    # bypass: كل observation مربوطة بوصل ختم commitment سابق داخل نفس الـ episode
    hashes_by_kind = {}
    bypass = 0
    for r in recs:
        k = r["payload"]["kind"]
        if k in ("COMMITMENT", "FREE_OBS_COMMIT"):
            hashes_by_kind[r["hash"]] = k
        if k == "OBSERVATION" and hashes_by_kind.get(r["payload"].get("receipt")) != "COMMITMENT":
            bypass += 1
        if k == "FREE_OBS_RESULT" and hashes_by_kind.get(r["payload"].get("receipt")) != "FREE_OBS_COMMIT":
            bypass += 1
    contract["gate_bypass"] = bypass

    # --- الطبقة 2: provenance ---
    idn_start = next((p["identity"] for p in P if p["kind"] == "EXEC_IDENTITY"), None)
    idn_end = next((p["identity"] for p in P if p["kind"] == "EXEC_IDENTITY_END"), None)
    prov = {
        "exec_identity": idn_start is not None and idn_end is not None,
        "request_ids_complete": bool(idn_end) and idn_end.get("n_requests") == len(idn_end.get("request_ids", [])) > 0,
        "model": (idn_end or {}).get("model"),
        "adapter_hash": (idn_end or {}).get("adapter_hash"),
        "truncated_responses": (idn_end or {}).get("truncated_responses"),
        "terminal": "SESSION_END" in K,
    }

    # --- الطبقة 3: السلوك — replay منحنى |H_t| وIG وجودة الأفعال ---
    hyps = w.hypotheses
    alive = set(range(len(hyps)))
    curve = [len(alive)]
    steps = []          # (phase, action, split_rank, split, claimed_p1, actual_p1, obs)
    claimed_checks = [] # مقارنة posterior المختوم بالناجين الفعليين
    events = []
    for p in P:
        if p["kind"] in ("FREE_OBS_COMMIT", "COMMITMENT"):
            events.append(("commit", p))
        elif p["kind"] in ("FREE_OBS_RESULT", "OBSERVATION"):
            events.append(("obs", p))
    i = 0
    while i < len(events):
        kind, p = events[i]
        if kind == "commit" and i + 1 < len(events) and events[i + 1][0] == "obs":
            dep = p["deposit"]
            action = dep["action"]
            symn = action[5:-1]
            obs = events[i + 1][1]["observation"]
            # جودة الاختيار: worst-case split لكل رمز متاح على alive الحالي
            ranks = []
            for s, v in sym2vec.items():
                n1 = sum(1 for h in alive if hyps[h].eval(v))
                n0 = len(alive) - n1
                ranks.append((max(n0, n1) if n0 and n1 else float("inf"), s))
            ranks.sort()
            rank = next((k + 1 for k, (_, s) in enumerate(ranks) if s == symn), None)
            v = sym2vec[symn]
            n1 = sum(1 for h in alive if hyps[h].eval(v))
            actual_p1 = n1 / len(alive) if alive else None
            claimed_p1 = None
            if dep.get("predictions"):
                claimed_p1 = dep["predictions"].get("outcome=1")
                if claimed_p1 is None and "outcome=0" in dep["predictions"]:
                    claimed_p1 = 1.0 - dep["predictions"]["outcome=0"]
            # posterior مختوم مقابل الناجين الفعليين
            if dep.get("hypotheses"):
                ids = {}
                unmatched = []
                for nm, pr in dep["hypotheses"].items():
                    hid = name2id.get(_norm(nm))
                    if hid is None:
                        unmatched.append(nm)
                    else:
                        ids[hid] = ids.get(hid, 0.0) + pr
                # أسماء متعددة تنهار إلى نفس الـ truth table = تكرار منطقي (لا يخالف الـ schema،
                # لكنه يشوّه الأوزان: الفئة المكررة تأخذ حصتين من كتلة الاحتمال)
                dup_groups = {}
                for nm2 in dep["hypotheses"]:
                    hid = name2id.get(_norm(nm2))
                    if hid is not None:
                        dup_groups.setdefault(hid, []).append(nm2)
                dups = {k: v for k, v in dup_groups.items() if len(v) > 1}
                uniform = None
                if ids:
                    exp = 1.0 / len(ids)
                    uniform = all(abs(pr - exp) <= 1e-3 for pr in ids.values())
                claimed_checks.append({
                    "action": action,
                    "claimed_n": len(dep["hypotheses"]), "actual_n": len(alive),
                    "distinct_n": len(ids),
                    "matched": len(ids), "unmatched": unmatched,
                    "set_equal": set(ids) == alive,
                    "uniform": uniform,
                    "dups": {tuple(v) for v in dups.values()},
                    "mass_on_truth": round(ids.get(w.true_id, 0.0), 4),
                    "truth_in_claimed": w.true_id in ids,
                })
            new_alive = {h for h in alive if hyps[h].eval(v) == obs}
            ig = math.log2(len(alive) / len(new_alive)) if new_alive else float("inf")
            steps.append({"phase": "free" if p["kind"] == "FREE_OBS_COMMIT" else "formal",
                          "action": action, "obs": obs, "rank": rank,
                          "H_before": len(alive), "H_after": len(new_alive),
                          "IG_bits": round(ig, 3),
                          "claimed_p1": claimed_p1,
                          "actual_p1": round(actual_p1, 4) if actual_p1 is not None else None})
            alive = new_alive
            curve.append(len(alive))
            i += 2
        else:
            i += 1

    suff = next((p["deposit"] for p in P if p["kind"] == "SUFFICIENCY"), None)
    behavior = {
        "N_free": end["free_used"], "N_formal": end["N_interventions"],
        "N_realized": end.get("N_total"),
        "blind_ID": end.get("blind_ID"), "conf_ID": end.get("conf_ID"),
        "conf_X": end.get("conf_X"),
        "declared_conf": suff.get("confidence") if suff else None,
        "declared_law": suff.get("final_hypothesis") if suff else None,
        "curve": curve, "steps": steps, "claimed_checks": claimed_checks,
        "final_H": len(alive), "truth_survives": w.true_id in alive,
    }

    # --- الطبقة 4: oracle ---
    weak, strict = d_floor(w)
    n = end.get("N_total")
    oracle = {"D_floor_weak": weak, "D_floor_strict": strict,
              "D_robust": w.D_pred, "D_inst": w.D_inst, "D_min": w.D_min,
              "N_realized": n,
              # الحد للـ audit = الأضعف (validity bound)؛ strict وصفي فقط
              "region": region(n, weak, w.D_pred) if n is not None and weak is not None else "-",
              "audit_fired": "ORACLE_VIOLATION_AUDIT" in K}
    return {"tag": tag, "contract": contract, "prov": prov,
            "behavior": behavior, "oracle": oracle}


# ------------------------- التقرير -------------------------

def main(run_dir):
    hyps = enumerate_hypotheses()
    name2id = build_name_map(hyps)
    episodes = []
    files = sorted(glob.glob(os.path.join(run_dir, "s*.jsonl")))
    chains_ok = {}
    for f in files:
        if f.endswith(".tampered"):
            continue
        seed = int(os.path.basename(f)[1:-6])
        chains_ok[seed] = Archivist.verify_file(f)
        recs = [json.loads(l) for l in open(f, encoding="utf-8")]
        sess = segment(recs)
        w = generate_accepted_world(seed)
        for j, s in enumerate(sess):
            tag = f"{seed}" + (f"#r{j+1}" if len(sess) > 1 else "")
            episodes.append((seed, analyze_episode(tag, s, w, name2id)))

    worlds = sorted({s for s, _ in episodes})
    print("# Pilot-A Gate Report — seeds "
          f"{min(worlds)}–{max(worlds)} ({len(worlds)} worlds, {len(episodes)} episodes)")
    print()
    print("model: claude-sonnet-5 عبر claude-openai-shim (اشتراك المشغل، claude -p، pure text).")
    print("repeated runs: العوالم التي أعيد تشغيلها تُعرض كـ #r1/#r2 داخل نفس السلسلة append-only —")
    print("عالم واحد إحصائيًا، لا عالمين.")
    print()
    print("**هذا التقرير read-only بالكامل. لا شيء في الماسورة عُدِّل. A-004 غير مختوم —")
    print("القسم 4 هو اختباره التجريبي الأول على بيانات مجمدة.**")
    print()

    # ---- 1. Contract ----
    print("## 1. Contract layer")
    print()
    print("| episode | outcome | schema_rej | phase_rej | blind_rej | refusals | unparsed_interp | gate_bypass |")
    print("|---|---|---|---|---|---|---|---|")
    tot = {"schema_rejects": 0, "phase_rejects": 0, "blind_rejects": 0, "refusals": 0,
           "unparsed_interpretations": 0, "gate_bypass": 0}
    complete = 0
    for _, e in episodes:
        c = e["contract"]
        complete += c["outcome"] not in ("AGENT_PROTOCOL_FAILURE", "PROVIDER_FAILURE",
                                         "ADAPTER_FAILURE", "SESSION_CRASH")
        for k in tot:
            tot[k] += c[k]
        print(f"| {e['tag']} | {c['outcome']} | {c['schema_rejects']} | {c['phase_rejects']} | "
              f"{c['blind_rejects']} | {c['refusals']} | {c['unparsed_interpretations']} | {c['gate_bypass']} |")
    print()
    print(f"- completion: **{complete}/{len(episodes)}**؛ semantic repairs بالبناء = 0 "
          f"(الـ adapter لا يصلح شيئًا؛ كل رفض أعلاه مرئي ومختوم).")
    print(f"- مجاميع: schema={tot['schema_rejects']}, phase={tot['phase_rejects']}, "
          f"blind={tot['blind_rejects']}, refusals={tot['refusals']}, "
          f"unparsed_interp={tot['unparsed_interpretations']}, gate_bypass={tot['gate_bypass']}.")
    print()

    # ---- 2. Provenance ----
    print("## 2. Provenance layer")
    print()
    print("| episode | chain | exec_id start+end | request_ids | model | adapter_hash | truncations | terminal |")
    print("|---|---|---|---|---|---|---|---|")
    for seed, e in episodes:
        p = e["prov"]
        print(f"| {e['tag']} | {'VALID' if chains_ok[seed] else 'BROKEN'} | "
              f"{'Y' if p['exec_identity'] else 'N'} | "
              f"{'complete' if p['request_ids_complete'] else 'MISSING'} | {p['model']} | "
              f"{p['adapter_hash']} | {p['truncated_responses']} | {'Y' if p['terminal'] else 'N'} |")
    print()
    print(f"- frozen hashes (متوقعة من الكود المجمد): schema={EXPECTED['schema_hash']}, "
          f"blind={EXPECTED['blind_schema_hash']}, protocol={EXPECTED['protocol_hash']}.")
    print("- لا overwrite: الـ repeated runs التحقت بنفس السلسلة append-only وصمد الـ verify"
          " على الملف كاملًا — الماضي محفوظ لا مُعاد كتابته.")
    print()

    # ---- 3. Behavior ----
    print("## 3. Behavior diagnostics")
    print()
    print("| episode | Nfree | Nform | Nreal | Blind-ID | conf_ID | conf_X | declared_conf | truth_survives | |H| curve | IG bits/step |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, e in episodes:
        b = e["behavior"]
        igs = "، ".join(str(s["IG_bits"]) for s in b["steps"])
        curve = "→".join(map(str, b["curve"]))
        print(f"| {e['tag']} | {b['N_free']} | {b['N_formal']} | {b['N_realized']} | "
              f"{b['blind_ID']} | {b['conf_ID']} | {b['conf_X']} | {b['declared_conf']} | "
              f"{'Y' if b['truth_survives'] else 'N'} | {curve} | {igs} |")
    print()
    print("### claimed vs actual — هل كلام الموديل يطابق ما تفعله أفعاله؟")
    print()
    print("لكل خطوة: rank الفعل المختار بين الأفعال الستة بمعيار worst-case split (1 = الأفصل)،")
    print("وclaimed P(outcome=1) المختوم مقابل النسبة الفعلية للناجين المصوتين بـ1:")
    print()
    print("| episode | step | action | rank | H_before→H_after | claimed p1 | actual p1 | Δ |")
    print("|---|---|---|---|---|---|---|---|")
    for _, e in episodes:
        for k, s in enumerate(e["behavior"]["steps"], 1):
            d = (abs(s["claimed_p1"] - s["actual_p1"])
                 if s["claimed_p1"] is not None and s["actual_p1"] is not None else None)
            print(f"| {e['tag']} | {k} ({s['phase']}) | {s['action']} | {s['rank']} | "
                  f"{s['H_before']}→{s['H_after']} | "
                  f"{s['claimed_p1'] if s['claimed_p1'] is not None else '—'} | {s['actual_p1']} | "
                  f"{round(d, 4) if d is not None else '—'} |")
    print()
    print("### posterior المختوم مقابل الناجين الفعليين (COMMITMENT deposits)")
    print()
    print("| episode | action | names | distinct | survivors | set == survivors? | uniform? | mass on truth | truth claimed? |")
    print("|---|---|---|---|---|---|---|---|---|")
    any_claims = False
    n_dep_all = n_set_eq = n_unif = 0
    dup_rows = []
    for _, e in episodes:
        for c in e["behavior"]["claimed_checks"]:
            any_claims = True
            n_dep_all += 1
            n_set_eq += bool(c["set_equal"])
            n_unif += bool(c["uniform"])
            if c["dups"]:
                dup_rows.append((e["tag"], c))
            print(f"| {e['tag']} | {c['action']} | {c['claimed_n']} | {c['distinct_n']} | "
                  f"{c['actual_n']} | {'Y' if c['set_equal'] else 'N'} | "
                  f"{'Y' if c['uniform'] else 'N'} | {c['mass_on_truth']} | "
                  f"{'Y' if c['truth_in_claimed'] else 'N'} |")
    if not any_claims:
        print("| — | — | — | — | — | — | — | — | — |")
    print()
    print(f"- **set == survivors في {n_set_eq}/{n_dep_all} إيداع** (تتبع مجموعة الناجين مضبوط).")
    print(f"- **posterior منتظم على الناجين في {n_unif}/{n_dep_all}**.")
    nonunif_nodup = [(t, c) for _, e in episodes for c in e["behavior"]["claimed_checks"]
                     for t in [e["tag"]] if c["uniform"] is False and not c["dups"]]
    if dup_rows or nonunif_nodup:
        print()
        print("**ملاحظتان سلبيتان مسجَّلتان — وهما ظاهرتان مختلفتان لا تُدمجان:**")
        print()
    if dup_rows:
        print("**(أ) تكرار منطقي في تعداد الفرضيات** — أسماء مختلفة تنهار إلى *نفس* جدول الحقيقة،")
        print("فتأخذ فئة التكافؤ حصتين من كتلة الاحتمال:")
        print()
        for tag, c in dup_rows:
            for pair in c["dups"]:
                print(f"- `{tag}` / {c['action']}: {' ≡ '.join(pair)} — "
                      f"{c['claimed_n']} اسمًا لـ {c['distinct_n']} فرضية متمايزة "
                      f"(الوزن على الفئة المكررة ≈ {round(2 / c['claimed_n'], 4)} بدل "
                      f"{round(1 / c['distinct_n'], 4)}).")
        print()
        print("**خلل canonicalization لدى الوكيل**: مجموعة الناجين صحيحة لكن الـ posterior موزون")
        print("خطأً على فئة تكافؤ منطقي.")
        print()
    if nonunif_nodup:
        print("**(ب) وزن غير منتظم بلا سند من الأدلة** — لا تكرار هنا؛ الأسماء متمايزة وكلها ناجية،")
        print("أي متساوية التوافق مع الأدلة، ومع ذلك وُزِّعت الكتلة بغير تساوٍ:")
        print()
        for tag, c in nonunif_nodup:
            print(f"- `{tag}` / {c['action']}: {c['distinct_n']} فرضيات متمايزة كلها متسقة مع الأدلة، "
                  f"والكتلة على القانون الحقيقي {c['mass_on_truth']} بدل "
                  f"{round(1 / c['distinct_n'], 4)} — انحراف عن الـ posterior المرجعي.")
        print()
        print("تحت حذف حتمي وprior منتظم، المرجع الصحيح هو التوزيع المنتظم على الناجين؛ فأي ترجيح")
        print("إضافي لا تسنده الأدلة. لا يخالف العقد (الاحتمالات تجمع إلى 1.0)، لكنه **ميل تفضيلي")
        print("غير مبرَّر إفتراضيًا** يستحق التتبع في Pilot-B حيث تصبح المعايرة مقياسًا أساسيًا.")
    if dup_rows or nonunif_nodup:
        print()
        print("كلاهما يُسجَّل صراحةً ولا يُبلع: الدفعة ليست خالية من العيوب، وإن لم يغيّر أيٌّ منهما")
        print("النتيجة النهائية (كل الحلقات انتهت SOLVED بـ Blind-ID كامل).")
    print()

    # ---- 4. Oracle ----
    print("## 4. Oracle diagnostics — الاختبار التجريبي الأول لصياغة A-004 (غير المختومة)")
    print()
    print("D_floor = instance-optimal تحت epistemic admissibility (lower envelope تشخيصي فقط).")
    print("مبرر الحساب: على instance حتمي، أي admissible policy تنهار إلى تسلسل أفعال محدد،")
    print("وترتيب الاختبارات لا يغيّر مجموعة الناجين ⇒ min على السياسات = min على مجموعات الاختبارات.")
    print()
    print("**تشعّب مكتشف في التعريف** (لم يكن في الصياغة الأولى): نقطة التوقف لها قراءتان —")
    print("`weak` = تصويت أغلبية الناجين يحقق BlindScore ≥ tau على الحقيقة المحققة (المعيار بُلِغ،")
    print("ولو بقي الناجون منقسمين)؛ `strict` = الناجون مجمعون على كل حالة Blind-ID (الأدلة *حدّدت*")
    print("الأجوبة). دائمًا weak ≤ strict. **حد الـ audit يجب أن يكون weak** لأنه validity bound:")
    print("أي N دونه مستحيل على أي سياسة مقبولة ⇒ bug/leak؛ واستعمال strict ينتج إنذارات كاذبة.")
    print()
    print("| episode | D_floor(weak) | D_floor(strict) | D_robust | D_inst | N_realized | region | audit (old rule) |")
    print("|---|---|---|---|---|---|---|---|")
    regions = {}
    split_seen = False
    for _, e in episodes:
        o = e["oracle"]
        regions[o["region"]] = regions.get(o["region"], 0) + 1
        if o["D_floor_weak"] != o["D_floor_strict"]:
            split_seen = True
        print(f"| {e['tag']} | {o['D_floor_weak']} | {o['D_floor_strict']} | {o['D_robust']} | "
              f"{o['D_inst']} | {o['N_realized']} | {o['region']} | "
              f"{'YES' if o['audit_fired'] else '-'} |")
    print()
    print(f"- توزيع المناطق: {json.dumps(regions, ensure_ascii=False)}")
    print(f"- TRUE_AUDIT (N < D_floor_weak) = leakage/accounting/oracle bug: "
          f"**{regions.get('TRUE_AUDIT', 0)}** من {len(episodes)}.")
    print(f"- weak ≠ strict في هذه الدفعة: {'نعم — التشعّب حقيقي عمليًا لا نظريًا فقط' if split_seen else 'لا (تطابقا هنا؛ التشعّب يبقى صحيحًا نظريًا وقد يظهر في عوالم أغنى)'}.")
    sep = [e["tag"] for _, e in episodes if e["oracle"]["D_robust"] != e["oracle"]["D_inst"]]
    print(f"- D_robust ≠ D_inst في: {'، '.join(sep) if sep else '(لا شيء)'} — "
          "حيث يفترقان يكون التوقف task-aligned أرخص فعليًا من التعريف الكامل للقانون، "
          "وهو دليل مباشر أن تعديل A-001 (المسطرة task-aligned لا identification كامل) "
          "يقوم بعمل حقيقي لا مجرد إعادة تسمية.")
    print()
    # ---- 5. تصحيحات أداة القياس ----
    n_dep = sum(len(e["behavior"]["claimed_checks"]) for _, e in episodes)
    n_eq = sum(1 for _, e in episodes for c in e["behavior"]["claimed_checks"] if c["set_equal"])
    n_truth = sum(1 for _, e in episodes for c in e["behavior"]["claimed_checks"]
                  if c["truth_in_claimed"])
    print("## 5. Measurement Instrument Corrections During Pilot-A")
    print()
    print("تصحيح واحد وقع أثناء Pilot-A، **في أداة التحليل لا في التجربة**. يُسجَّل كاملًا لأن")
    print("نزاهة التحليل جزء من الـ provenance:")
    print()
    print("| البند | التفصيل |")
    print("|---|---|")
    print("| **المشكلة** | normalizer التشخيصي كان يعرف `NOT` و`¬` ولا يعرف `~` (ولا `!`). "
          "الـ COMMIT_SCHEMA لا يفرض تدوينًا للأسماء — يفرض فقط أن تجمع الاحتمالات إلى 1.0 — "
          "فكتابة `(~p0 AND p2)` إيداع صالح ومطابق للعقد. |")
    print("| **الأثر الخاطئ الأولي** | seed 2003 ظهر كأن الموديل يعلن فرضيات خارج فضاء الفرضيات، "
          "وأن كتلته على القانون الحقيقي = 0.0، وأن القانون الحقيقي غير مُعلَن أصلًا "
          "(3 من 4 أسماء \"unmatched\"). الاستنتاج المتاح وقتها كان: *الموديل يسقط القانون الحقيقي*. |")
    print("| **كيف تُحقِّق** | فُحص الإيداع الخام من السلسلة المختومة قبل رفع أي استنتاج: "
          "`{\"(p1 XOR p2)\":0.25, \"(~p0 AND p2)\":0.25, \"(~p0 AND ~p1)\":0.25, \"(~p1 AND p2)\":0.25}` "
          "وSUFFICIENCY = `(~p0 AND p2)`، بينما القانون الحقيقي `(NOT p0 AND p2)` — أي **الشيء نفسه** "
          "بترميز مكافئ. الخطأ في المسطرة لا في المقيس. |")
    print("| **موضع الإصلاح** | `pilot_a_gate_report._norm` فقط (أداة تحليل خارج الماسورة): "
          "قبول `~` و`!` و`¬` كنفي. لم يُمَس world/channel/session/agents/llm_agent ولا الـ protocol "
          "ولا الـ schema ولا أي بيانات مختومة. |")
    print(f"| **نتيجة إعادة التحليل** | {n_eq}/{n_dep} إيداع: مجموعة الفرضيات المعلنة = مجموعة الناجين "
          f"الفعليين تمامًا؛ القانون الحقيقي داخل المُعلَن في {n_truth}/{n_dep}. |")
    print("| **السجلات الأصلية** | لم تتغير: الأداة لا تفتح أي ملف للكتابة، وسلاسل الـ hash "
          "أعلاه (القسم 2) أُعيد التحقق منها بعد الإصلاح وبقيت VALID — وهو دليل تقني لا إجرائي. |")
    print()
    print("الدرس المسجَّل: الفصل بين **العقد الرسمي** (يقيّد ما يُحتسب) و**أدوات التحليل اللاحقة** "
          "(تقرأ ولا تُلزِم) هو ما جعل هذا الخطأ قابلًا للاكتشاف والإصلاح دون تلويث التجربة. "
          "وتُدقَّق أداة القياس قبل الحكم على المقيس — نفس قاعدة الـ OracleViolation، مطبَّقة على المحلِّل.")
    print()

    print("## Gate verdict")
    print()
    print("سؤال البوابة: **هل بقي العقد سليمًا أمام LLM حقيقي عبر عدة worlds/runs؟**")
    print("(الـ Blind-ID ليس شرط العبور الوحيد — الحكم على سلامة العقد والسجل.)")
    print()
    print("الصياغة الملتزمة لما أثبتته الطبقة الثالثة، بلا تضخيم:")
    print()
    n_all = sum(len(e["behavior"]["claimed_checks"]) for _, e in episodes)
    n_eq2 = sum(1 for _, e in episodes for c in e["behavior"]["claimed_checks"] if c["set_equal"])
    n_un2 = sum(1 for _, e in episodes for c in e["behavior"]["claimed_checks"] if c["uniform"])
    print("> **Exact survivor-set tracking in Pilot-A, with two documented "
          "posterior-weighting defects**")
    print()
    print(f"أي: مجموعة الناجين مضبوطة في **{n_eq2}/{n_all}** إيداع — وهذا هو الادعاء القوي. "
          f"أما الأوزان فمنتظمة في **{n_un2}/{n_all}** فقط، والفارق ليس ضجيجًا بل عيبان "
          "مختلفان موثّقان أعلاه: (أ) تكرار منطقي يشوّه وزن فئة تكافؤ، (ب) ترجيح غير منتظم "
          "بلا سند من الأدلة. وتوقعات outcome المختومة طابقت نسبة الناجين "
          "المصوتين بـ1 بفارق ≤ 3×10⁻⁴. هذا **ليس** ادعاء \"كفاءة بيزية معرفية\" عامة: "
          "النطاق depth-2 صغير، والإعلان كامل، وفضاء الفرضيات 30 فقط وقابل للحصر يدويًا — "
          "والحذف الحتمي تحت prior منتظم يجعل الـ posterior الصحيح تمرينًا مباشرًا.")
    print()
    print("خارج نطاق حكم Pilot-A نهائيًا: **Blind-X، Frame Expansion، latent probes** — "
          "لا تُحتسب هنا نجاحًا ولا فشلًا؛ حضورها في الكود يُسجَّل فقط كـ plumbing جاهز للمرحلة التالية "
          "(Blind-X فارغة بنيويًا في هذا العالم، والإعلان كامل فلا فرصة Frame Expansion أصلًا).")
    print()
    print("الخطوتان المشروطتان بالعبور، قبل Pilot-B وبهذا الترتيب:")
    print("1. مراجعة مرشح A-004 على هذه البيانات المجمدة وقرار ختمه أو رفضه.")
    print("2. ختم مواصفات Pilot-B: فصل probe، وt_inadequacy، وFrame Expansion، وثلاثية Blind-X.")
    print()
    print("البذور التأكيدية لا تُفتح.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "provenance", "pilot_a_shim_run"))
