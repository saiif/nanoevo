"""world_b1.py — Pilot-B1: خصائص كامنة + PROBE/EXPERIMENT + هوية فرضية دلالية.

مطابق لـ PILOT_B1_SPEC.md المجمدة (spec_hash b720abb855b59b04، ledger 74f955b935f1d84b).

الفرق البنيوي عن Pilot-A: متجهات الخصائص **كامنة** — الوكيل يستقبل أسماء الرموز فقط.
فعلان متمايزان: PROBE(sym,p_i) لاكتساب ملاحظة، EXPERIMENT(sym) لاختبار القانون.

الـ oracle المرجعي (المادة 6 من الـ spec): الحالة المشتركة (قانون × إسنادات المتجهات
الكامنة) موزعة بانتظام على كل الثلاثيات المتسقة مع الأدلة، لأن كل ثلاثية متسقة لها نفس
الاحتمال تحت prior منتظم. إذن — والرموز مستقلة بشرط القانون —

    W(h) = Π_x n_x(h)      n_x(h) = عدد متجهات الرمز x المتسقة مع أدلته تحت h
    Z    = Σ_h W(h)        P*(h|E) = W(h)/Z        H_joint = log2 Z

دقيق ورخيص (30 قانونًا × رموز × 8 متجهات)، ولا يحتاج تعدادًا للفضاء المشترك.
"""

import hashlib
import itertools
import json
import math
import random

from world import enumerate_hypotheses, N_PROPS, GLYPH_POOL

GRAMMAR_VERSION_B1 = "1.0-b1-latent-depth2"
ALL_VECTORS = list(itertools.product((0, 1), repeat=N_PROPS))


# ----------------------- هوية دلالية للفرضيات (المادة 4) -----------------------

def hypothesis_catalog():
    """H00..H29 — معرّف قانوني واحد لكل جدول حقيقة. التكرار المنطقي مستحيل بالبناء."""
    hyps = enumerate_hypotheses()
    ids = [f"H{i:02d}" for i in range(len(hyps))]
    return hyps, ids, {hid: h.name() for hid, h in zip(ids, hyps)}


def grammar_hash_b1():
    hyps, ids, names = hypothesis_catalog()
    spec = {"version": GRAMMAR_VERSION_B1, "n_props": N_PROPS,
            "law_family": "binary formula (+-p_i OP +-p_j), OP in AND/OR/XOR",
            "latent_properties": True,
            "actions": ["PROBE(symbol,p_i)", "EXPERIMENT(symbol)"],
            "hypothesis_identity": "semantic canonical IDs over truth tables",
            "catalog": names}
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]


# ----------------------- الأدلة والـ posterior المرجعي -----------------------

FULL_MASK = (1 << len(ALL_VECTORS)) - 1
# PROBE_MASK[i][bit] = قناع المتجهات التي v[i]==bit
PROBE_MASK = [[sum(1 << k for k, v in enumerate(ALL_VECTORS) if v[i] == b) for b in (0, 1)]
              for i in range(N_PROPS)]
_POPCOUNT = [bin(m).count("1") for m in range(1 << len(ALL_VECTORS))]


def exp_masks(hyps):
    """EXP_MASK[h][e] = قناع المتجهات التي h(v)==e."""
    return [[sum(1 << k for k, v in enumerate(ALL_VECTORS) if h.eval(v) == e) for e in (0, 1)]
            for h in hyps]


class Evidence:
    """أدلة الجلسة كأقنعة بتات — حالة قانونية قابلة للـ hash ورخيصة الحساب.

    لكل رمز: قناع المتجهات المتوافقة مع الـ probes (مستقل عن القانون) + نتيجة التجربة
    (مرشِّح يعتمد على القانون). لا تحوي أي حقيقة مخفية.
    """

    __slots__ = ("pmask", "exp")

    def __init__(self, n_syms):
        self.pmask = [FULL_MASK] * n_syms
        self.exp = [None] * n_syms

    def copy(self):
        e = Evidence.__new__(Evidence)
        e.pmask = list(self.pmask)
        e.exp = list(self.exp)
        return e

    def key(self):
        return (tuple(self.pmask), tuple(self.exp))


def posterior(hyps, evidence, emask):
    """يرجع (P*(h)، Z، H_joint، support). W(h)=Π_x n_x(h)، والحالة المشتركة منتظمة."""
    W = []
    Z = 0
    for k, h in enumerate(hyps):
        w = 1
        em = emask[k]
        for x, pm in enumerate(evidence.pmask):
            e = evidence.exp[x]
            n = _POPCOUNT[pm if e is None else pm & em[e]]
            if n == 0:
                w = 0
                break
            w *= n
        W.append(w)
        Z += w
    if Z == 0:
        return [0.0] * len(hyps), 0, 0.0, []
    return ([w / Z for w in W], Z, math.log2(Z),
            [k for k, w in enumerate(W) if w > 0])


def support_of(hyps, evidence, emask):
    """الـ support وحده — أرخص من الـ posterior الكامل (يُستعمل داخل البحث)."""
    sup = []
    for k in range(len(hyps)):
        em = emask[k]
        ok = True
        for x, pm in enumerate(evidence.pmask):
            e = evidence.exp[x]
            if _POPCOUNT[pm if e is None else pm & em[e]] == 0:
                ok = False
                break
        if ok:
            sup.append(k)
    return sup


# ----------------------- الأفعال والـ information gain (المادة 7) -----------------------

def all_actions(n_syms):
    """الأفعال بفهرس الرمز: ('PROBE', x, i) و('EXPERIMENT', x, None)."""
    acts = [("PROBE", x, i) for x in range(n_syms) for i in range(N_PROPS)]
    acts += [("EXPERIMENT", x, None) for x in range(n_syms)]
    return acts


def apply_action(evidence, action, out):
    e = evidence.copy()
    kind, x, i = action
    if kind == "PROBE":
        e.pmask[x] &= PROBE_MASK[i][out]
    else:
        e.exp[x] = out
    return e


def information_gain(hyps, evidence, emask, action):
    """IG على الحالة المشتركة = H_joint(t) − E[H_joint(t+1)|a]. يرجع (IG_joint, IG_law).

    ملاحظة مجمدة في الـ spec: قد يكون IG_law = 0 وprobe مع ذلك ضروري (يمهّد لتجربة
    مفيدة لاحقًا) — لذلك القياس على المشترك، وIG_law تشخيصي منفصل.
    """
    P0, Z0, H0, _ = posterior(hyps, evidence, emask)
    if Z0 == 0:
        return 0.0, 0.0
    H0_law = _entropy(P0)
    exp_H, exp_H_law = 0.0, 0.0
    for out in (0, 1):
        P2, Z2, H2, _ = posterior(hyps, apply_action(evidence, action, out), emask)
        if Z2 == 0:
            continue
        p_out = Z2 / Z0          # احتمال النتيجة تحت الـ prior المشترك المنتظم
        exp_H += p_out * H2
        exp_H_law += p_out * _entropy(P2)
    return H0 - exp_H, H0_law - exp_H_law


def _entropy(P):
    return -sum(p * math.log2(p) for p in P if p > 0)


# ----------------------- الأرضيات والمرجع (المادة 8 — امتداد A-004) -----------------------

def _task_ok(hyps, support, blind_vectors, true_h, tau, strict=False):
    if not support or not blind_vectors:
        return False
    members = [hyps[k] for k in support]
    if strict:
        return all(len({m.eval(v) for m in members}) == 1 and members[0].eval(v) == true_h.eval(v)
                   for v in blind_vectors)
    agree = 0
    for v in blind_vectors:
        ones = sum(m.eval(v) for m in members)
        pred = 1 if 2 * ones >= len(members) else 0
        agree += (pred == true_h.eval(v))
    return agree / len(blind_vectors) >= tau


def d_floor_pair_b1(hyps, n_syms, true_vectors_idx, true_id, emask, blind_vectors, tau, cap=8):
    """A-004 على فضاء الفعلين: أرخص مجموعة أفعال admissible تبلغ المعيار.

    على instance حتمي، نتيجة كل فعل محددة سلفًا وترتيب الأفعال لا يغيّر الأدلة الناتجة،
    فـ min على السياسات المقبولة = min على *مجموعات* الأفعال. تعميق تدريجي حتى cap.
    يرجع (task, strict, actions_task) — و None عند تجاوز الـ cap.
    """
    acts = all_actions(n_syms)
    true_h = hyps[true_id]
    outcome = {}
    for a in acts:
        kind, x, i = a
        v = ALL_VECTORS[true_vectors_idx[x]]
        outcome[a] = v[i] if kind == "PROBE" else true_h.eval(v)
    task = strict = task_set = None
    for k in range(cap + 1):
        for S in itertools.combinations(acts, k):
            ev = Evidence(n_syms)
            for a in S:
                ev = apply_action(ev, a, outcome[a])
            support = support_of(hyps, ev, emask)
            if not support:
                continue
            if task is None and _task_ok(hyps, support, blind_vectors, true_h, tau):
                task, task_set = k, S
            if strict is None and _task_ok(hyps, support, blind_vectors, true_h, tau, strict=True):
                strict = k
            if task is not None and strict is not None:
                return task, strict, task_set
        if task is not None and strict is not None:
            break
    return task, strict, task_set


def d_robust_b1(hyps, n_syms, emask, blind_vectors, tau, cap=8):
    """تكلفة السياسة المثلى التي لا تعرف القانون مسبقًا وتضمن المعيار في أسوأ حالة.

    تعميق تكراري (IDA): نسأل "هل يوجد ضمان خلال k؟" لـ k تصاعديًا — أرخص بكثير من بحث
    عميق ثابت لأن أغلب الفروع تنتهي مبكرًا. الضمان counterfactual-correct: الحالة نهائية
    إذا تحقق المعيار ضد كل عضو في الـ support لو كان هو الصحيح (تصحيح #3 من Pilot-A).
    """
    acts = all_actions(n_syms)
    term_memo = {}

    def terminal(support):
        if not support:
            return True
        key = tuple(support)
        if key in term_memo:
            return term_memo[key]
        members = [hyps[k] for k in support]
        ok = True
        for m in members:                      # أسوأ حالة على هوية العضو الصحيح
            agree = 0
            for v in blind_vectors:
                ones = sum(x.eval(v) for x in members)
                pred = 1 if 2 * ones >= len(members) else 0
                agree += (pred == m.eval(v))
            if agree / len(blind_vectors) < tau:
                ok = False
                break
        term_memo[key] = ok
        return ok

    memo = {}

    def solvable(ev, support, budget):
        if terminal(support):
            return True
        if budget == 0:
            return False
        k = (ev.key(), budget)
        if k in memo:
            return memo[k]
        memo[k] = False
        for a in acts:
            branches, useful = [], False
            for out in (0, 1):
                e2 = apply_action(ev, a, out)
                s2 = support_of(hyps, e2, emask)
                if not s2:
                    continue
                if len(s2) != len(support):
                    useful = True
                branches.append((e2, s2))
            if not useful:
                continue                      # فعل غير فاصل على الـ support — لا يفيد
            if all(solvable(e2, s2, budget - 1) for e2, s2 in branches):
                memo[k] = True
                return True
        return False

    ev0 = Evidence(n_syms)
    sup0 = support_of(hyps, ev0, emask)
    for budget in range(cap + 1):
        memo.clear()
        if solvable(ev0, sup0, budget):
            return budget
    return None


# ----------------------- العالم -----------------------

class WorldB1:
    def __init__(self, seed, n_train=5, tau=0.90, cap=8):
        self.seed = seed
        self.tau = tau
        rng = random.Random(seed)
        self.hypotheses, self.hyp_ids, self.catalog = hypothesis_catalog()
        self.id_of = {i: hid for i, hid in enumerate(self.hyp_ids)}
        self.index_of = {hid: i for i, hid in enumerate(self.hyp_ids)}
        self.true_id = rng.randrange(len(self.hypotheses))
        self.true_h = self.hypotheses[self.true_id]

        vecs = list(ALL_VECTORS)
        rng.shuffle(vecs)
        train_vecs = vecs[:n_train]
        glyphs = GLYPH_POOL[:]
        rng.shuffle(glyphs)
        self.train_symbols = list(glyphs[:n_train])
        self.true_vectors = {s: tuple(v) for s, v in zip(self.train_symbols, train_vecs)}
        # الاختبار الأعمى (المادة 9): رموز جديدة **مع متجهاتها معطاة**
        blind_vecs = list(ALL_VECTORS)
        rng.shuffle(blind_vecs)
        self.blind_symbols = {glyphs[n_train + k]: tuple(v)
                              for k, v in enumerate(blind_vecs)}

        # فئات التكافؤ تحت فضاء التدخل (متجهات التدريب) — A-002
        groups = {}
        for k, h in enumerate(self.hypotheses):
            groups.setdefault(tuple(h.eval(v) for v in train_vecs), []).append(k)
        self.classes = list(groups.values())
        self.blind_ID, self.blind_X = {}, {}
        for s, v in self.blind_symbols.items():
            const = all(len({self.hypotheses[k].eval(v) for k in cls}) == 1 for cls in self.classes)
            (self.blind_ID if const else self.blind_X)[s] = v

        self.emask = exp_masks(self.hypotheses)
        self.n_syms = n_train
        self.vec_index = {s: ALL_VECTORS.index(self.true_vectors[s]) for s in self.train_symbols}
        true_idx = [self.vec_index[s] for s in self.train_symbols]
        bl = [tuple(v) for v in self.blind_ID.values()]
        # B1 لا يقبل عوالم فيها Blind-X (تنتظر B2) — نتجنب حساب oracle مكلفًا بلا داعٍ
        if self.blind_X or not bl:
            self.D_floor_task = self.D_floor_strict = self.floor_actions = self.D_robust = None
        else:
            self.D_floor_task, self.D_floor_strict, self.floor_actions = d_floor_pair_b1(
                self.hypotheses, n_train, true_idx, self.true_id, self.emask, bl, tau, cap)
            self.D_robust = d_robust_b1(self.hypotheses, n_train, self.emask, bl, tau, cap)
        # الفحص العدائي المسجَّل (المادة 10): هل الأرضية تستلزم probes أصلًا؟
        self.floor_requires_probe = (bool(self.floor_actions)
                                     and any(a[0] == "PROBE" for a in self.floor_actions))
        self.accepted = (not self.blind_X                 # B1: لا Blind-X (تنتظر B2)
                         and self.D_floor_task is not None
                         and self.D_robust is not None
                         and self.floor_requires_probe)   # عالم بلا حاجة لـ probe لا يختبر B1

    # --- Oracle API (verifier-side فقط) ---
    def probe(self, sym, i):
        return self.true_vectors[sym][i]

    def experiment(self, sym):
        return self.true_h.eval(self.true_vectors[sym])

    def blind_truth(self):
        return {s: self.true_h.eval(v) for s, v in self.blind_symbols.items()}

    def true_law_name(self):
        return self.true_h.name()

    def true_law_id(self):
        return self.hyp_ids[self.true_id]

    def phase_zero_packet(self):
        return {
            "symbols": list(self.train_symbols),        # أسماء فقط — لا متجهات (المادة 1)
            "actions": ["PROBE(symbol,p_i)", "EXPERIMENT(symbol)"],
            "hypothesis_catalog": self.catalog,          # هوية دلالية (المادة 4)
            "declared_primitives": {
                "law_family": "binary formula (±p_i OP ±p_j), OP in AND/OR/XOR",
                "n_props": N_PROPS,
                "latent_properties": True,
                "declaration_complete": True,            # B1: لا إعلان منقوص
            },
        }


def generate_accepted_world_b1(seed_base, n_train=5, tau=0.90, cap=8, max_tries=60):
    for k in range(max_tries):
        w = WorldB1(seed_base * 1000 + k, n_train, tau, cap)
        if w.accepted:
            return w
    raise RuntimeError(f"no accepted B1 world for seed_base {seed_base}")
