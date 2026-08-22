"""world_b1.py — Pilot-B1: خصائص كامنة + PROBE/EXPERIMENT + هوية فرضية دلالية.

مطابق لـ PILOT_B1_SPEC.md المجمدة (spec_hash b720abb855b59b04) بعد Amendment A-005.

الفرق البنيوي عن Pilot-A: متجهات الخصائص **كامنة** — الوكيل يستقبل أسماء الرموز فقط.
فعلان متمايزان: PROBE(sym) يكشف المتجه **كاملًا** بتدخل واحد (A-005)، وEXPERIMENT(sym)
يختبر القانون.

الـ prior المرجعي (A-005 — يصف التنفيذ حرفيًا):
عالم B1 يعلن مجموعة متجهات متمايزة، والإسناد σ من الرموز إليها **تقابل** (bijection)
مجهول للوكيل. الـ prior منتظم على أزواج (قانون، تقابل):

    P(h, σ) ∝ 1     على كل σ تقابلية

ومنه، بعد الأدلة E:

    P*(h | E) = #{σ تقابلية و(h,σ) ⊨ E}  /  Σ_h' #{σ تقابلية و(h',σ) ⊨ E}

عدّاد التقابلات المتسقة = **permanent** لمصفوفة السماح (0/1) — تُحسب بـ DP على المجموعات
الجزئية. وH_joint = log2 Z حيث Z المقام أعلاه (الحالة المشتركة منتظمة على الأزواج المتسقة).

تنبيه مسجَّل: النسخة الأولى افترضت استقلالًا شرطيًا W(h)=Π_x n_x(h)، وهو **prior مختلف**
يسمح بأن تتشارك كل الرموز متجهًا واحدًا — وعندها يستحيل التمييز ويصبح D_robust غير موجود.
شرط التقابل معلَن للوكيل في phase_zero، وهو جزء من بنية العالم لا من القانون المخفي.

ملاحظة أداء: عضوية الـ support تحتاج *وجود* تقابل لا *عدده*، فتُحسب بالتزاوج (Kuhn)؛
والـ permanent يبقى للـ posterior وحده. وحالات البحث تُفهرس بمفتاح قانوني تحت تبديل
الرموز (الرموز متبادلة تحت prior التقابل) — الاثنان مثبتان في run_mechanical_b1.py.
"""

import hashlib
import itertools
from collections import namedtuple
import json
import math
import random

from world import enumerate_hypotheses, N_PROPS, GLYPH_POOL

GRAMMAR_VERSION_B1 = "1.1-b1-latent-fullprobe"

# هوية واحدة صريحة للسياق: لا مكان يظن أنه زوج ومكان آخر يظنه ثلاثيًا.
#   n        عدد رموز التدريب
#   by_pop   المجموعات الجزئية مرتبة بعدد البتات (لحساب الـ permanent)
#   declared كون المتجهات المعلَن — كل mask/index في الملف يفهرس عليه حصرًا
#   cache    ذاكرة support مفتاحها حالة الأدلة (البحث يعيد زيارة الحالات كثيرًا)
Ctx = namedtuple("Ctx", "n by_pop declared cache")
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
            "actions": ["PROBE(symbol)", "EXPERIMENT(symbol)"],
            "probe_semantics": "A-005: PROBE reveals the symbol's FULL property vector "
                               "in one intervention (per-bit probing removed)",
            "latent_assignment": "bijection onto a declared set of distinct vectors",
            "hypothesis_identity": "semantic canonical IDs over truth tables",
            "catalog": names}
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]


# ----------------------- الأدلة والـ posterior المرجعي -----------------------

def exp_masks(hyps, declared):
    """EXP_MASK[h][e] = قناع متجهات **المجموعة المعلنة** التي h(v)==e."""
    return [[sum(1 << k for k, v in enumerate(declared) if h.eval(v) == e) for e in (0, 1)]
            for h in hyps]


class Evidence:
    """أدلة الجلسة كأقنعة بتات — حالة قانونية قابلة للـ hash ورخيصة الحساب.

    لكل رمز: قناع المتجهات المتوافقة مع الـ probes (مستقل عن القانون) + نتيجة التجربة
    (مرشِّح يعتمد على القانون). لا تحوي أي حقيقة مخفية.
    """

    __slots__ = ("pmask", "exp")

    def __init__(self, n_syms, n_vecs=None):
        full = (1 << (n_vecs if n_vecs is not None else n_syms)) - 1
        self.pmask = [full] * n_syms
        self.exp = [None] * n_syms

    def copy(self):
        e = Evidence.__new__(Evidence)
        e.pmask = list(self.pmask)
        e.exp = list(self.exp)
        return e

    def key(self):
        """مفتاح **قانوني** تحت تبديل الرموز.

        الرموز متبادلة a priori (لكلٍّ متجه مجهول متمايز)، ودالتا support/posterior
        ثابتتان تحت تبديل الصفوف — فحالتان تختلفان بترتيب الرموز فقط متكافئتان تمامًا.
        الفرز يطوي هذه الفئات فيقلّص فضاء البحث بشدة.
        """
        return tuple(sorted((pm, -1 if e is None else e)
                            for pm, e in zip(self.pmask, self.exp)))


def _subsets_by_popcount(n):
    by = [[] for _ in range(n + 1)]
    for S in range(1 << n):
        by[bin(S).count("1")].append(S)
    return by


def _permanent(allowed, n, by_pop):
    """عدد الإسنادات **التباينية** (bijection) المتسقة: symbol x → متجه مسموح، بلا تكرار.

    A-005 (invariant معلَن): رموز التدريب تحقق تقابلًا على مجموعة المتجهات المعلنة.
    بدون هذا الشرط يسمح الـ prior بأن تتشارك كل الرموز متجهًا واحدًا، فيستحيل التمييز
    ويصبح D_robust = ∞ — أي أن B1 غير قابل للتشغيل أصلًا. القياس كشف هذا قبل التشغيل.
    """
    dp = [0] * (1 << n)
    dp[0] = 1
    for x in range(n):
        ndp = [0] * (1 << n)
        av = allowed[x]
        for S in by_pop[x]:
            d = dp[S]
            if not d:
                continue
            free = av & ~S
            while free:
                b = free & -free
                ndp[S | b] += d
                free ^= b
        dp = ndp
    return dp[(1 << n) - 1]


def _has_matching(allowed, n):
    """هل يوجد تقابل صالح؟ (Kuhn القياسي) — الـ support يحتاج *وجود* إسناد لا *عدده*.

    حساب الـ permanent الكامل داخل البحث كلّف ~80 ثانية للعالم الواحد، ووجود التقابل
    يكفي تمامًا لتقرير عضوية الفرضية في الـ support. (الـ permanent يبقى للـ posterior.)
    """
    match = [-1] * n                      # فهرس المتجه j -> الرمز المسند إليه

    def augment(x, seen):
        av = allowed[x] & ~seen[0]
        while av:
            b = av & -av
            j = b.bit_length() - 1
            av ^= b
            seen[0] |= b
            if match[j] == -1 or augment(match[j], seen):
                match[j] = x
                return True
        return False

    for x in range(n):
        if not augment(x, [0]):
            return False
    return True


def posterior(hyps, evidence, emask, ctx):
    """يرجع (P*(h)، Z، H_joint، support) تحت الـ prior التقابلي المعلَن."""
    n, by_pop = ctx.n, ctx.by_pop
    W, Z = [], 0
    for k in range(len(hyps)):
        em = emask[k]
        allowed = []
        w = 1
        for x, pm in enumerate(evidence.pmask):
            e = evidence.exp[x]
            a = pm if e is None else pm & em[e]
            if a == 0:
                w = 0
                break
            allowed.append(a)
        if w:
            w = _permanent(allowed, n, by_pop)
        W.append(w)
        Z += w
    if Z == 0:
        return [0.0] * len(hyps), 0, 0.0, []
    return ([w / Z for w in W], Z, math.log2(Z),
            [k for k, w in enumerate(W) if w > 0])


def support_of(hyps, evidence, emask, ctx):
    """الـ support وحده — نفس الشرط التقابلي (إسناد واحد صالح على الأقل)."""
    n = ctx.n
    ekey = evidence.key()
    hit = ctx.cache.get(ekey)
    if hit is not None:
        return hit
    sup = []
    for k in range(len(hyps)):
        em = emask[k]
        allowed = []
        ok = True
        for x, pm in enumerate(evidence.pmask):
            e = evidence.exp[x]
            a = pm if e is None else pm & em[e]
            if a == 0:
                ok = False
                break
            allowed.append(a)
        if ok and _has_matching(allowed, n):
            sup.append(k)
    ctx.cache[ekey] = sup
    return sup


# ----------------------- الأفعال والـ information gain (المادة 7) -----------------------

def all_actions(n_syms):
    """A-005: PROBE(x) يكشف المتجه كاملًا بتدخل واحد؛ EXPERIMENT(x) يختبر القانون.

    درجة الحرية "أي bit أستكشف" حُذفت عمدًا (A-005): القياس أثبت أنها تستهلك الميزانية
    دون أن تختبر سؤال B1. الفرق البنيوي Probe ≠ Experiment محفوظ بالكامل.
    """
    return ([("PROBE", x, None) for x in range(n_syms)]
            + [("EXPERIMENT", x, None) for x in range(n_syms)])


def action_outcomes(evidence, action):
    """نتائج الفعل الممكنة. PROBE يعيد فهرس المتجه (حتى 8 نتائج)، EXPERIMENT يعيد بتًا."""
    kind, x, _ = action
    if kind == "PROBE":
        pm = evidence.pmask[x]
        out = []
        while pm:
            b = pm & -pm
            out.append(b.bit_length() - 1)
            pm ^= b
        return out
    return [0, 1]


def apply_action(evidence, action, out):
    e = evidence.copy()
    kind, x, _ = action
    if kind == "PROBE":
        e.pmask[x] = 1 << out          # المتجه صار معروفًا بالكامل
    else:
        e.exp[x] = out
    return e


def information_gain(hyps, evidence, emask, ctx, action):
    """IG على الحالة المشتركة = H_joint(t) − E[H_joint(t+1)|a]. يرجع (IG_joint, IG_law).

    ملاحظة مجمدة في الـ spec: قد يكون IG_law = 0 وprobe مع ذلك ضروري (يمهّد لتجربة
    مفيدة لاحقًا) — لذلك القياس على المشترك، وIG_law تشخيصي منفصل.
    """
    P0, Z0, H0, _ = posterior(hyps, evidence, emask, ctx)
    if Z0 == 0:
        return 0.0, 0.0
    H0_law = _entropy(P0)
    exp_H, exp_H_law = 0.0, 0.0
    for out in action_outcomes(evidence, action):
        P2, Z2, H2, _ = posterior(hyps, apply_action(evidence, action, out), emask, ctx)
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


def d_floor_pair_b1(hyps, n_syms, true_vectors_idx, true_id, emask, ctx, blind_vectors, tau, cap=8):
    """A-004 على فضاء الفعلين: أرخص مجموعة أفعال admissible تبلغ المعيار.

    على instance حتمي، نتيجة كل فعل محددة سلفًا وترتيب الأفعال لا يغيّر الأدلة الناتجة،
    فـ min على السياسات المقبولة = min على *مجموعات* الأفعال. تعميق تدريجي حتى cap.
    يرجع (task, strict, actions_task) — و None عند تجاوز الـ cap.
    """
    acts = all_actions(n_syms)
    true_h = hyps[true_id]
    declared = ctx.declared
    outcome = {}
    for a in acts:
        kind, x, _ = a
        vi = true_vectors_idx[x]
        outcome[a] = vi if kind == "PROBE" else true_h.eval(declared[vi])
    task = strict = task_set = None
    for k in range(cap + 1):
        for S in itertools.combinations(acts, k):
            ev = Evidence(n_syms, ctx.n)
            for a in S:
                ev = apply_action(ev, a, outcome[a])
            support = support_of(hyps, ev, emask, ctx)
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


def attainable_within(hyps, n_syms, emask, ctx, ev0, blind_vectors, tau, budget):
    """A-007: هل توجد سياسة **مقبولة** تبلغ معيار المهمة من هذه الحالة ضمن هذه الميزانية؟

    نفس منطق d_robust_b1 لكن انطلاقًا من حالة أدلة قائمة وبميزانية متبقية. الضمان
    counterfactual-correct: لا يُسمح للسياسة بمعرفة القانون الحقيقي — يجب أن تنجح ضد أي
    عضو في الـ support لو كان هو الصحيح. هذا يجعل "هل كان بإمكانه الاستمرار؟" سؤالًا
    أوراكليًا حتميًا لا حكمًا على نية الوكيل.

    يرجع (attainable, D_remaining, best_action_ig, n_informative_actions) حيث
    D_remaining = أدنى ميزانية تكفي للضمان من هذه الحالة (None إذا تجاوزت المتاح).
    ومنه Slack = B_remaining − D_remaining: كم من الهامش تركه الوكيل على الطاولة.
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
        for m in members:
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

    fail_upto, ok_from = {}, {}

    def solvable(ev, support, b):
        if terminal(support):
            return True
        if b == 0:
            return False
        ek = ev.key()
        f = fail_upto.get(ek)
        if f is not None and b <= f:
            return False
        o = ok_from.get(ek)
        if o is not None and b >= o:
            return True
        for a in acts:
            branches, useful, changed = [], False, False
            for out in action_outcomes(ev, a):
                e2 = apply_action(ev, a, out)
                if e2.key() != ev.key():
                    changed = True
                s2 = support_of(hyps, e2, emask, ctx)
                if not s2:
                    continue
                if len(s2) != len(support):
                    useful = True
                branches.append((e2, s2))
            if not (useful or changed):
                continue
            if all(solvable(e2, s2, b - 1) for e2, s2 in branches):
                if o is None or b < o:
                    ok_from[ek] = b
                return True
        if f is None or b > f:
            fail_upto[ek] = b
        return False

    sup0 = support_of(hyps, ev0, emask, ctx)
    best_ig, n_inf = 0.0, 0
    for a in acts:
        _, igh = information_gain(hyps, ev0, emask, ctx, a)
        if igh > 1e-9:
            n_inf += 1
            best_ig = max(best_ig, igh)
    # أدنى ميزانية كافية: تعميق تكراري يستفيد من نفس الذاكرة
    d_remaining = None
    for b in range(max(budget, 0) + 1):
        if solvable(ev0, sup0, b):
            d_remaining = b
            break
    return (d_remaining is not None), d_remaining, round(best_ig, 4), n_inf


def optimistic_reach(hyps, n_syms, emask, ctx, ev0, blind_vectors, tau, cap=10):
    """D_lower(belief_t): أقل عدد أفعال يبلغ المعيار على **أوفر الفروع حظًا**، مشتقًا من
    حالة الاعتقاد وحدها — لا من W* ولا من القانون الحقيقي.

    لماذا هذا ضروري: الحكم على الوكيل بأن العالم "غير قابل للحل" اعتمادًا على
    D_floor^task(W*) يحاكمه على حقيقة لا يملك إليها سبيلًا — وهو نفس خطأ 4015/4018 لكن
    معكوسًا. الكمية القابلة للاستنتاج من تاريخه هي: هل يوجد **أي** فرع متسق مع أدلتي
    يبلغ المعيار خلال k فعلًا؟

    بحث بالعرض (BFS) على حالات الأدلة: الفرع = (فعل، نتيجة ممكنة تحت الاعتقاد الحالي).
    يرجع أقل k، أو None إذا تجاوز cap. دائمًا: D_lower ≤ D_robust(belief).
    """
    from collections import deque

    def met(support):
        if not support:
            return True
        members = [hyps[k] for k in support]
        for m in members:
            agree = 0
            for v in blind_vectors:
                ones = sum(x.eval(v) for x in members)
                agree += ((1 if 2 * ones >= len(members) else 0) == m.eval(v))
            if agree / len(blind_vectors) < tau:
                return False
        return True

    start = support_of(hyps, ev0, emask, ctx)
    if met(start):
        return 0
    seen = {ev0.key()}
    q = deque([(ev0, 0)])
    acts = all_actions(n_syms)
    while q:
        ev, d = q.popleft()
        if d >= cap:
            continue
        for a in acts:
            for out in action_outcomes(ev, a):
                e2 = apply_action(ev, a, out)
                k2 = e2.key()
                if k2 in seen:
                    continue
                s2 = support_of(hyps, e2, emask, ctx)
                if not s2:                       # فرع غير متسق مع الأدلة — غير قابل للبلوغ
                    continue
                if met(s2):
                    return d + 1
                seen.add(k2)
                q.append((e2, d + 1))
    return None


def decision_state(hyps, n_syms, emask, ctx, ev, blind_vectors, tau, budget, cap=10):
    """A-008: الحالة التحكمية الحقيقية عند نقطة قرار — **كلها من حالة الاعتقاد**.

        MET                     المعيار متحقق الآن                       الصواب: STOP
        GUARANTEED_REACHABLE    توجد سياسة تضمنه ضمن B                   الصواب: CONTINUE
        POSSIBLE_UNGUARANTEED   يوجد فرع محظوظ يبلغه، بلا ضمان           لا يُسجَّل صوابًا/خطأً
        UNREACHABLE             لا يبلغه حتى أوفر الفروع حظًا ضمن B      الصواب: INCOMPLETE

    الغموض في المنطقة الوسطى ليس في العالم بل في **قاعدة القرار التي لم تُحدَّد بعد**،
    فتُفرد بتحليل مستقل بدل أن تُحتسب خطأً على سلوك معقول.
    """
    sup = support_of(hyps, ev, emask, ctx)
    guaranteed, d_rob, _, _ = attainable_within(hyps, n_syms, emask, ctx, ev,
                                                blind_vectors, tau, budget)
    d_low = optimistic_reach(hyps, n_syms, emask, ctx, ev, blind_vectors, tau, cap)
    if d_low == 0:
        state = "MET"
    elif guaranteed:
        state = "GUARANTEED_REACHABLE"
    elif d_low is not None and d_low <= budget:
        state = "POSSIBLE_UNGUARANTEED"
    else:
        state = "UNREACHABLE"
    return {"state": state, "support_size": len(sup), "budget": budget,
            "D_robust_belief": d_rob, "D_lower_belief": d_low,
            "scored": state != "POSSIBLE_UNGUARANTEED",
            "correct_decision": {"MET": "STOP", "GUARANTEED_REACHABLE": "CONTINUE",
                                 "UNREACHABLE": "INCOMPLETE"}.get(state)}


def d_robust_b1(hyps, n_syms, emask, ctx, blind_vectors, tau, cap=8, start=0):
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

    # ذاكرة عابرة للميزانيات: لكل حالة نحفظ أكبر ميزانية ثبت فشلها وأصغر ميزانية ثبت نجاحها.
    # (مسح الذاكرة عند كل تعميق كان يهدر كل العمل السابق — 84s للعالم الواحد.)
    fail_upto, ok_from = {}, {}

    def solvable(ev, support, budget):
        if terminal(support):
            return True
        if budget == 0:
            return False
        ek = ev.key()
        f = fail_upto.get(ek)
        if f is not None and budget <= f:
            return False
        o = ok_from.get(ek)
        if o is not None and budget >= o:
            return True
        for a in acts:
            branches, useful, changed = [], False, False
            for out in action_outcomes(ev, a):
                e2 = apply_action(ev, a, out)
                if e2.key() != ev.key():
                    changed = True
                s2 = support_of(hyps, e2, emask, ctx)
                if not s2:
                    continue
                if len(s2) != len(support):
                    useful = True
                branches.append((e2, s2))
            # PROBE قد لا يغيّر الـ support (IG_law=0) لكنه يغيّر الحالة ويمهّد لتجربة —
            # لذلك المعيار هنا "غيّر الحالة" لا "غيّر الـ support" (تحذير §7 المجمد).
            if not (useful or changed):
                continue
            if all(solvable(e2, s2, budget - 1) for e2, s2 in branches):
                if o is None or budget < o:
                    ok_from[ek] = budget
                return True
        if f is None or budget > f:
            fail_upto[ek] = budget
        return False

    ev0 = Evidence(n_syms, ctx.n)
    sup0 = support_of(hyps, ev0, emask, ctx)
    for budget in range(start, cap + 1):
        if solvable(ev0, sup0, budget):
            return budget
    return None


# ----------------------- العالم -----------------------

class WorldB1:
    """عالم B1: متجهات كامنة، تقابل معلَن، PROBE كامل المتجه (A-005)."""

    def __init__(self, seed, n_train=6, tau=0.90, cap=14):
        self.seed = seed
        self.tau = tau
        rng = random.Random(seed)
        self.hypotheses, self.hyp_ids, self.catalog = hypothesis_catalog()
        self.index_of = {hid: i for i, hid in enumerate(self.hyp_ids)}
        self.true_id = rng.randrange(len(self.hypotheses))
        self.true_h = self.hypotheses[self.true_id]

        vecs = list(ALL_VECTORS)
        rng.shuffle(vecs)
        # المجموعة المعلَنة: n_train متجهًا متمايزًا، والإسناد إلى الرموز تقابل مجهول للوكيل
        self.declared_vectors = [tuple(v) for v in vecs[:n_train]]
        glyphs = GLYPH_POOL[:]
        rng.shuffle(glyphs)
        self.train_symbols = list(glyphs[:n_train])
        perm = list(range(n_train))
        rng.shuffle(perm)
        self.vec_index = {s: perm[k] for k, s in enumerate(self.train_symbols)}
        self.true_vectors = {s: self.declared_vectors[i] for s, i in self.vec_index.items()}

        blind_vecs = list(ALL_VECTORS)
        rng.shuffle(blind_vecs)
        self.blind_symbols = {glyphs[n_train + k]: tuple(v) for k, v in enumerate(blind_vecs)}

        groups = {}
        for k, h in enumerate(self.hypotheses):
            groups.setdefault(tuple(h.eval(v) for v in self.declared_vectors), []).append(k)
        self.classes = list(groups.values())
        self.blind_ID, self.blind_X = {}, {}
        for s, v in self.blind_symbols.items():
            const = all(len({self.hypotheses[k].eval(v) for k in cls}) == 1 for cls in self.classes)
            (self.blind_ID if const else self.blind_X)[s] = v

        self.n_syms = n_train
        self.emask = exp_masks(self.hypotheses, self.declared_vectors)
        self.ctx = Ctx(n_train, _subsets_by_popcount(n_train),
                       self.declared_vectors, {})
        bl = [tuple(v) for v in self.blind_ID.values()]
        if self.blind_X or not bl:
            self.D_floor_task = self.D_floor_strict = self.floor_actions = self.D_robust = None
        else:
            true_idx = [self.vec_index[s] for s in self.train_symbols]
            self.D_floor_task, self.D_floor_strict, self.floor_actions = d_floor_pair_b1(
                self.hypotheses, n_train, true_idx, self.true_id, self.emask, self.ctx,
                bl, tau, cap)
            # D_robust >= D_floor^task بنيويًا — نبدأ التعميق من الأرضية لا من الصفر
            self.D_robust = d_robust_b1(self.hypotheses, n_train, self.emask, self.ctx,
                                        bl, tau, cap, start=self.D_floor_task or 0)
        self.floor_requires_probe = (bool(self.floor_actions)
                                     and any(a[0] == "PROBE" for a in self.floor_actions))
        self.accepted = (not self.blind_X
                         and self.D_floor_task is not None
                         and self.D_robust is not None
                         and self.floor_requires_probe)

    # --- Oracle API (verifier-side فقط) ---
    def probe(self, sym):
        """A-005: يكشف المتجه كاملًا بتدخل واحد."""
        return list(self.true_vectors[sym])

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
            "symbols": list(self.train_symbols),
            "actions": ["PROBE(symbol)", "EXPERIMENT(symbol)"],
            "hypothesis_catalog": self.catalog,
            "declared_primitives": {
                "law_family": "binary formula (±p_i OP ±p_j), OP in AND/OR/XOR",
                "n_props": N_PROPS,
                "latent_properties": True,
                # invariant معلَن (A-005): بدونه يسمح الـ prior بتشارك كل الرموز متجهًا واحدًا
                # فيستحيل التمييز ويصبح D_robust غير موجود.
                "property_vectors_present": [list(v) for v in self.declared_vectors],
                "assignment": "bijection: each symbol has exactly one of the listed vectors, "
                              "all distinct; which symbol has which is unknown",
                "declaration_complete": True,
            },
        }


def generate_accepted_world_b1(seed_base, n_train=6, tau=0.90, cap=14, max_tries=60):
    for k in range(max_tries):
        w = WorldB1(seed_base * 1000 + k, n_train, tau, cap)
        if w.accepted:
            return w
    raise RuntimeError(f"no accepted B1 world for seed_base {seed_base}")
