"""world.py — Depth-2 world generator + oracle + D_min (exact, minimax).

نطاق التحقق الميكانيكي (الملحق ب): grammar بسيطة قابلة للحساب الكامل.
قرار توثيقي: في هذه المرحلة جدول الخصائص *ظاهر* للوكيل والقانون هو المخفي —
الخصائص الكامنة القابلة للـ probe تدخل في الـ pilot. الهدف هنا اختبار الماسورة.

القانون: صيغة منطقية على خاصيتين من ثلاث: (±p_i OP ±p_j), OP ∈ {AND, OR, XOR}.
التدخل الوحيد: TEST(symbol) → يرجع f(props(symbol)) ∈ {0,1}.
"""

import hashlib
import itertools
import json
import random

GRAMMAR_VERSION = "1.0-mech-depth2"
N_PROPS = 3
OPS = ("AND", "OR", "XOR")


def _op(op, a, b):
    if op == "AND":
        return a & b
    if op == "OR":
        return a | b
    return a ^ b


class Hypothesis:
    """(op, i, neg_i, j, neg_j) — canonicalized by truth-table signature."""

    def __init__(self, op, i, ni, j, nj):
        self.op, self.i, self.ni, self.j, self.nj = op, i, ni, j, nj

    def eval(self, props):
        a = props[self.i] ^ self.ni
        b = props[self.j] ^ self.nj
        return _op(self.op, a, b)

    def signature(self):
        return tuple(self.eval(v) for v in itertools.product((0, 1), repeat=N_PROPS))

    def name(self):
        lit = lambda k, n: f"{'NOT ' if n else ''}p{k}"
        return f"({lit(self.i, self.ni)} {self.op} {lit(self.j, self.nj)})"


def enumerate_hypotheses():
    """كل الصيغ depth-2، منزوعة التكرار بالـ truth table (support الـ grammar)."""
    seen, out = {}, []
    for op in OPS:
        for i, j in itertools.combinations(range(N_PROPS), 2):
            for ni, nj in itertools.product((0, 1), repeat=2):
                h = Hypothesis(op, i, ni, j, nj)
                sig = h.signature()
                if sig not in seen:
                    seen[sig] = h
                    out.append(h)
    return out  # canonical hypothesis space


def grammar_hash():
    spec = {"version": GRAMMAR_VERSION, "n_props": N_PROPS, "ops": OPS,
            "law_family": "binary literal formula over prop pairs",
            "intervention": "TEST(symbol) -> law(props(symbol))"}
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]


# ----------------------------- D_min (minimax, exact) -----------------------------

def d_min(hypotheses, objects):
    """أقل عدد TEST (تكيفي، أسوأ حالة) لتمييز القانون الصحيح — oracle-side فقط."""
    all_ids = frozenset(range(len(hypotheses)))
    memo = {}

    def depth(state):
        if len(state) <= 1:
            return 0
        if state in memo:
            return memo[state]
        best = float("inf")
        for props in objects:
            groups = {}
            for hid in state:
                groups.setdefault(hypotheses[hid].eval(props), set()).add(hid)
            if len(groups) < 2:
                continue  # تجربة غير فاصلة — لا تفيد
            worst = 1 + max(depth(frozenset(g)) for g in groups.values())
            best = min(best, worst)
        memo[state] = best
        return best

    return depth(all_ids)


def equivalence_classes(hypotheses, train_vectors):
    """H_a ~_I H_b ⇔ متطابقتان على كل ما تسمح التدخلات المسموحة بملاحظته (A-002)."""
    groups = {}
    for idx, h in enumerate(hypotheses):
        sig = tuple(h.eval(v) for v in train_vectors)
        groups.setdefault(sig, []).append(idx)
    return list(groups.values())


def split_blind(hypotheses, train_vectors, blind_symbols):
    """قاعدة A-002: هدف الـ Blind-ID يجب أن يكون ثابتًا داخل *كل* فئة تكافؤ رصدية.
    ما لا يحقق الشرط = Blind-X (extrapolation/abstraction) — لا يدخل E."""
    classes = equivalence_classes(hypotheses, train_vectors)
    blind_id, blind_x = {}, {}
    for s, v in blind_symbols.items():
        constant = all(len({hypotheses[h].eval(tuple(v)) for h in cls}) == 1
                       for cls in classes)
        (blind_id if constant else blind_x)[s] = v
    return blind_id, blind_x


def d_pred_inst(hypotheses, objects, true_id, blind_vectors, tau):
    """D_pred-inst (Amendment A-001): تكلفة السياسة المثلى للوصول إلى *معرفة كافية
    لنفس معيار الوكيل* (BlindScore ≥ τ)، لا إلى تعريف القانون كاملًا.

    قيد صارم (يدخل الـ amendment حرفيًا): الـ oracle لا يعرف أي فرضية هي الصحيحة
    عند البداية؛ يعرف hypothesis class/grammar المسموحة فقط، ويختار تدخلاته المثلى
    تحت نفس المعلومات الابتدائية I₀ المتاحة للوكيل. بعد تثبيت السياسة، تُقاس تكلفة
    المسار عندما يكون العالم الحقيقي هو W_i:  D_pred-inst(W_i) = C(π*, W_i | I₀).
    أي معرفة مسبقة بالقانون تجعل التكلفة 0 وتلغي عملية الاكتشاف — ممنوعة بالبناء.
    """
    true_h = hypotheses[true_id]

    def blind_ok(h):
        agree = sum(1 for v in blind_vectors if h.eval(v) == true_h.eval(v))
        return agree / len(blind_vectors) >= tau

    # الحالة النهائية task-aligned (تصحيح ميكانيكي #3): الضمان يجب أن يصمد في كل
    # فرع counterfactual — "الحقيقة" هناك هي فرضية الفرع، لا القانون الفعلي.
    # لذلك المعيار: قاعدة الأغلبية داخل الحالة تحقق العتبة ضد *أي* عضو لو كان هو الصحيح.
    def terminal(state):
        members = [hypotheses[h] for h in state]
        preds = []
        for v in blind_vectors:
            ones = sum(m.eval(v) for m in members)
            preds.append(1 if 2 * ones >= len(members) else 0)
        for m in members:  # أسوأ حالة على هوية العضو الصحيح
            agree = sum(1 for k, v in enumerate(blind_vectors)
                        if preds[k] == m.eval(v))
            if blind_vectors and agree / len(blind_vectors) < tau:
                return False
        return True

    all_ids = frozenset(range(len(hypotheses)))
    memo = {}

    def depth(state):
        if terminal(state):
            return 0
        if state in memo:
            return memo[state]
        memo[state] = float("inf")  # حارس ضد الدورات
        best = float("inf")
        for props in objects:
            groups = {}
            for hid in state:
                groups.setdefault(hypotheses[hid].eval(props), set()).add(hid)
            if len(groups) < 2:
                continue
            best = min(best, 1 + max(depth(frozenset(g)) for g in groups.values()))
        memo[state] = best
        return best

    reachable = depth(all_ids) != float("inf")

    state, steps = all_ids, 0
    while not terminal(state):
        best_props, best_key = None, None
        for props in objects:
            groups = {}
            for hid in state:
                groups.setdefault(hypotheses[hid].eval(props), set()).add(hid)
            if len(groups) < 2:
                continue
            d = 1 + max(depth(frozenset(g)) for g in groups.values())
            worst_group = max(len(g) for g in groups.values())
            key = (d, worst_group)   # الأمثل إن وُجد، وإلا الجشع بأقصى تقسيم
            if best_key is None or key < best_key:
                best_key, best_props = key, props
        if best_props is None:
            break
        out = true_h.eval(best_props)   # الواقع يجيب — لا السياسة تعرف مسبقًا
        state = frozenset(h for h in state if hypotheses[h].eval(best_props) == out)
        steps += 1

    # A-002: لا نخلط oracle optimum بمرجع heuristic —
    # UNREACHABLE يعني "المعلومة غير موجودة في قناة التعلم"، لا "مكلفة".
    if reachable:
        return {"D_pred": steps, "reachable": True, "D_greedy_ref": steps}
    return {"D_pred": None, "reachable": False, "D_greedy_ref": steps}


def d_min_instance(hypotheses, objects, true_id):
    """تكلفة السياسة المثلى على *القانون الحقيقي بالذات* — الـ lower bound الصحيح للجلسة.

    اكتشاف التحقق الميكانيكي: D_min الـ minimax هو worst-case على كل القوانين،
    فالجلسة الفعلية قد تنحسم بأقل منه شرعيًا. E وOracleViolation يقاسان على هذا.
    """
    all_ids = frozenset(range(len(hypotheses)))
    memo = {}

    def depth(state):
        if len(state) <= 1:
            return 0
        if state in memo:
            return memo[state]
        best = float("inf")
        for props in objects:
            groups = {}
            for hid in state:
                groups.setdefault(hypotheses[hid].eval(props), set()).add(hid)
            if len(groups) < 2:
                continue
            best = min(best, 1 + max(depth(frozenset(g)) for g in groups.values()))
        memo[state] = best
        return best

    state, steps = all_ids, 0
    while len(state) > 1:
        # الـ oracle يلعب السياسة المثلى (يختار الفعل الأدنى worst-case)
        best_props, best_d = None, float("inf")
        for props in objects:
            groups = {}
            for hid in state:
                groups.setdefault(hypotheses[hid].eval(props), set()).add(hid)
            if len(groups) < 2:
                continue
            d = 1 + max(depth(frozenset(g)) for g in groups.values())
            if d < best_d:
                best_d, best_props = d, props
        if best_props is None:
            break  # غموض بنيوي متبقٍ
        out = hypotheses[true_id].eval(best_props)
        state = frozenset(h for h in state if hypotheses[h].eval(best_props) == out)
        steps += 1
    return steps


def d_floor_pair(hypotheses, objects, true_id, blind_vectors, tau):
    """A-004: أرضيتا instance-optimal تحت epistemic admissibility — يرجع (task, strict).

    admissibility: السياسة π_t: h_t → a_t لا ترى W إلا عبر ما كشفه التاريخ. على instance
    حتمي مثبَّت تنهار أي admissible policy إلى تسلسل أفعال محدد، وترتيب الاختبارات لا يغيّر
    مجموعة الناجين ⇒ min على السياسات = min على *مجموعات* الاختبارات (قابل للحساب الدقيق).
    الـ min بعد تثبيت W هو lower envelope تشخيصي — ليس سياسة يختارها oracle رشيد قبل معرفة W.

    task  = أرخص مسار يحقق الهدف التشغيلي للـ Primary Endpoint: تصويت أغلبية الناجين
            يحرز BlindScore ≥ tau على Blind-ID ضد الحقيقة المُحقَّقة. هذا هو الحارس الرسمي
            للـ TRUE_AUDIT (المسطرة تُقرَن بالمهمة المقاسة لا بمعرفة القانون كاملًا).
    strict = أرخص مسار يجعل الناجين مُجمِعين وصائبين على كل حالة Blind-ID (الأدلة *حدّدت*
            الأجوبة). diagnostic فقط ما دام strict identification ليس الـ endpoint.
    دائمًا task ≤ strict.
    """
    true_h = hypotheses[true_id]
    blind = [tuple(v) for v in blind_vectors]
    vecs = [tuple(v) for v in objects]
    task = strict = None
    for k in range(len(vecs) + 1):
        for S in itertools.combinations(vecs, k):
            surv = [h for h in hypotheses if all(h.eval(v) == true_h.eval(v) for v in S)]
            if not surv:
                continue
            if strict is None and blind and all(
                    len({h.eval(b) for h in surv}) == 1 and surv[0].eval(b) == true_h.eval(b)
                    for b in blind):
                strict = k
            if task is None and blind:
                agree = 0
                for b in blind:
                    ones = sum(h.eval(b) for h in surv)
                    pred = 1 if 2 * ones >= len(surv) else 0
                    agree += (pred == true_h.eval(b))
                if agree / len(blind) >= tau:
                    task = k
            if task is not None and strict is not None:
                return task, strict
    return task, strict


def d_min_bruteforce_check(hypotheses, objects, limit=8):
    """إعادة حساب مستقلة (BFS على الاستراتيجيات) للتحقق اليدوي — السؤال الميكانيكي 7."""
    all_ids = frozenset(range(len(hypotheses)))

    def solvable_within(state, k):
        if len(state) <= 1:
            return True
        if k == 0:
            return False
        for props in objects:
            groups = {}
            for hid in state:
                groups.setdefault(hypotheses[hid].eval(props), set()).add(hid)
            if len(groups) < 2:
                continue
            if all(solvable_within(frozenset(g), k - 1) for g in groups.values()):
                return True
        return False

    for k in range(limit + 1):
        if solvable_within(all_ids, k):
            return k
    return None


# ----------------------------- World -----------------------------

GLYPH_POOL = ["Qz", "Vx", "Kr", "Jm", "Wt", "Hs", "Nd", "Bf", "Xp", "Ly",
              "Rc", "Tg", "Zn", "Um", "Ok", "Ea"]


class World:
    def __init__(self, seed, dmin_window=(2, 6)):
        self.seed = seed
        rng = random.Random(seed)
        self.hypotheses = enumerate_hypotheses()
        self.true_id = rng.randrange(len(self.hypotheses))

        all_vectors = list(itertools.product((0, 1), repeat=N_PROPS))
        rng.shuffle(all_vectors)
        self.train_vectors = all_vectors[:6]           # ما يراه الوكيل
        self.blind_vectors = list(all_vectors)          # كل الـ 8 (تشمل 2 غير مرئيين)
        rng.shuffle(self.blind_vectors)

        glyphs = GLYPH_POOL[:]
        rng.shuffle(glyphs)
        self.train_symbols = {glyphs[k]: v for k, v in enumerate(self.train_vectors)}
        # الاختبار الأعمى: رموز *جديدة كليًا* (permutation) — نفس البنية العميقة
        self.blind_symbols = {glyphs[8 + k]: v for k, v in enumerate(self.blind_vectors)}

        self.D_min = d_min(self.hypotheses, self.train_vectors)          # worst-case: بوابة توليد فقط
        self.D_inst = d_min_instance(self.hypotheses, self.train_vectors,
                                     self.true_id)                        # identification cost (تقرير)
        # A-002: فصل identification عن extrapolation
        self.blind_ID, self.blind_X = split_blind(self.hypotheses,
                                                  self.train_vectors,
                                                  self.blind_symbols)
        oracle = d_pred_inst(self.hypotheses, self.train_vectors, self.true_id,
                             [tuple(v) for v in self.blind_ID.values()], tau=0.90)
        self.D_pred = oracle["D_pred"]            # None = UNREACHABLE
        self.D_reachable = oracle["reachable"]
        self.D_greedy_ref = oracle["D_greedy_ref"]
        # --- A-004: أربع مساطر مسماة صراحةً بدل D_floor غامضة ---
        # D_robust^task: تكلفة السياسة المثلى التي لا تعرف W مسبقًا وتضمن معيار المهمة.
        self.D_robust = self.D_pred
        # أرضيتا الـ instance تحت epistemic admissibility (lower envelope تشخيصي).
        self.D_floor_task, self.D_floor_strict = d_floor_pair(
            self.hypotheses, self.train_vectors, self.true_id,
            [tuple(v) for v in self.blind_ID.values()], tau=0.90)
        # A-002 invariant: الهدف الأساسي يجب أن يكون identifiable تحت فضاء
        # التدخل المعلَن — عالم UNREACHABLE يُرفض في التوليد نفسه.
        self.accepted = (dmin_window[0] <= self.D_min <= dmin_window[1]
                         and self.D_reachable)

    # --- Oracle API (verifier-side فقط؛ الوكيل لا يلمسها) ---
    def oracle_test(self, symbol):
        table = {**self.train_symbols, **self.blind_symbols}
        if symbol not in table:
            raise KeyError(f"unknown symbol {symbol}")
        return self.hypotheses[self.true_id].eval(table[symbol])

    def true_law_name(self):
        return self.hypotheses[self.true_id].name()

    # --- ما يُسلَّم للوكيل في المرحلة صفر (المادة 34) ---
    def phase_zero_packet(self):
        return {
            "symbols": {s: list(v) for s, v in self.train_symbols.items()},
            "actions": ["TEST(symbol)"],
            "declared_primitives": {
                "law_family": "binary formula (±p_i OP ±p_j), OP in AND/OR/XOR",
                "n_props": N_PROPS,
                # لا primitives مخفية في mechanical — الإعلان المنقوص يدخل في pilot
                "declaration_complete": True,
            },
            # لا D_min، لا seed، لا القانون الحقيقي، لا blind symbols
        }


def classify_region(n_realized, d_floor_task, d_robust):
    """A-004: أي منطقة تقع فيها الحلقة. الحارس الرسمي هو floor المهمة لا الـ strict.

      N < D_floor^task            → TRUE_AUDIT (تناقض: leakage/accounting/oracle bug)
      D_floor^task ≤ N < D_robust → FAVORABLE_TRAJECTORY (طبيعي تمامًا)
      N ≥ D_robust                → AT_OR_ABOVE_ROBUST (لا انتهاك؛ كفاءة أقل من الضمان)
    """
    if n_realized is None or d_floor_task is None or d_robust is None:
        return "UNCLASSIFIED"
    if n_realized < d_floor_task:
        return "TRUE_AUDIT"
    if n_realized < d_robust:
        return "FAVORABLE_TRAJECTORY"
    return "AT_OR_ABOVE_ROBUST"


def generate_accepted_world(seed_base, dmin_window=(2, 6), max_tries=200):
    """التوليد بالرفض: أي عالم خارج نافذة D_min يُرفض (المادة 25)."""
    for k in range(max_tries):
        w = World(seed_base * 1000 + k, dmin_window)
        if w.accepted:
            return w
    raise RuntimeError("no world in D_min window")
