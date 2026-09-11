"""world.py — Depth-2 world generator + oracle + D_min (exact, minimax).

The scope of mechanical verification (Appendix B): a simple grammar that is fully
computable. A documented decision: at this stage the property table is *visible* to the
agent and only the law is hidden — latent properties that can be probed belong to the
pilot. The goal here is to test the pipe.

The law: a logical formula over two of three properties: (±p_i OP ±p_j), OP ∈ {AND, OR, XOR}.
The only intervention: TEST(symbol) → returns f(props(symbol)) ∈ {0,1}.
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
    """All depth-2 formulas, deduplicated by truth table (the grammar's support)."""
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
    """The minimum number of TESTs (adaptive, worst case) to identify the correct law — oracle-side only."""
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
                continue  # a non-discriminating test — no use
            worst = 1 + max(depth(frozenset(g)) for g in groups.values())
            best = min(best, worst)
        memo[state] = best
        return best

    return depth(all_ids)


def equivalence_classes(hypotheses, train_vectors):
    """H_a ~_I H_b ⇔ identical on everything the permitted interventions allow to be observed (A-002)."""
    groups = {}
    for idx, h in enumerate(hypotheses):
        sig = tuple(h.eval(v) for v in train_vectors)
        groups.setdefault(sig, []).append(idx)
    return list(groups.values())


def split_blind(hypotheses, train_vectors, blind_symbols):
    """A-002 rule: the Blind-ID target must be constant within *every* observational
    equivalence class. Anything that fails this condition is Blind-X
    (extrapolation/abstraction) — it does not enter E."""
    classes = equivalence_classes(hypotheses, train_vectors)
    blind_id, blind_x = {}, {}
    for s, v in blind_symbols.items():
        constant = all(len({hypotheses[h].eval(tuple(v)) for h in cls}) == 1
                       for cls in classes)
        (blind_id if constant else blind_x)[s] = v
    return blind_id, blind_x


def d_pred_inst(hypotheses, objects, true_id, blind_vectors, tau):
    """D_pred-inst (Amendment A-001): the cost of the optimal policy for reaching *knowledge
    sufficient for the same criterion the agent is held to* (BlindScore ≥ τ), not for fully
    identifying the law.

    A strict constraint (this is the amendment, verbatim): the oracle does not know which
    hypothesis is correct at the start; it knows only the permitted hypothesis class/grammar,
    and chooses its optimal interventions under the same initial information I₀ available to
    the agent. Once the policy is fixed, the path's cost is measured for the case where the
    true world is W_i:  D_pred-inst(W_i) = C(π*, W_i | I₀).
    Any prior knowledge of the law would make the cost 0 and void the discovery process — this
    is forbidden by construction.
    """
    true_h = hypotheses[true_id]

    def blind_ok(h):
        agree = sum(1 for v in blind_vectors if h.eval(v) == true_h.eval(v))
        return agree / len(blind_vectors) >= tau

    # The task-aligned terminal condition (mechanical correction #3): the guarantee must
    # hold in every counterfactual branch — "the truth" there is that branch's hypothesis,
    # not the actual law. So the criterion is: the majority rule within the state meets the
    # threshold against *any* member, were it the correct one.
    def terminal(state):
        members = [hypotheses[h] for h in state]
        preds = []
        for v in blind_vectors:
            ones = sum(m.eval(v) for m in members)
            preds.append(1 if 2 * ones >= len(members) else 0)
        for m in members:  # worst case over which member is the correct one
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
        memo[state] = float("inf")  # guard against cycles
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
            key = (d, worst_group)   # the optimum if one exists, otherwise greedy by the largest split
            if best_key is None or key < best_key:
                best_key, best_props = key, props
        if best_props is None:
            break
        out = true_h.eval(best_props)   # reality answers — the policy does not know in advance
        state = frozenset(h for h in state if hypotheses[h].eval(best_props) == out)
        steps += 1

    # A-002: never conflate the oracle optimum with a heuristic reference —
    # UNREACHABLE means "the information does not exist in the learning channel," not "expensive."
    if reachable:
        return {"D_pred": steps, "reachable": True, "D_greedy_ref": steps}
    return {"D_pred": None, "reachable": False, "D_greedy_ref": steps}


def d_min_instance(hypotheses, objects, true_id):
    """The cost of the optimal policy on *the actual true law* — the correct lower bound for
    the session.

    A finding from mechanical verification: the minimax D_min is the worst case over all
    laws, so an actual session may legitimately resolve in fewer steps than that. E and
    OracleViolation are measured against this value.
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
        # the oracle plays the optimal policy (chooses the action with the lowest worst-case cost)
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
            break  # residual structural ambiguity
        out = hypotheses[true_id].eval(best_props)
        state = frozenset(h for h in state if hypotheses[h].eval(best_props) == out)
        steps += 1
    return steps


def d_floor_pair(hypotheses, objects, true_id, blind_vectors, tau):
    """A-004: the two instance-optimal floors under epistemic admissibility — returns
    (task, strict).

    Admissibility: the policy π_t: h_t → a_t sees W only through what the history has
    revealed. For a fixed, deterministic instance, any admissible policy collapses to a
    specific action sequence, and the order of the tests does not change the set of
    survivors ⇒ the min over policies equals the min over *sets* of tests (exactly
    computable). The min after fixing W is a diagnostic lower envelope — not a policy a
    rational oracle would choose before knowing W.

    task   = the cheapest path that meets the operational goal of the Primary Endpoint: a
             majority vote of the survivors achieves BlindScore ≥ tau on Blind-ID against
             the realized truth. This is the official guard for TRUE_AUDIT (the ruler is
             tied to the measured task, not to fully identifying the law).
    strict = the cheapest path that makes the survivors unanimous and correct on every
             Blind-ID case (the evidence has *determined* the answers). Diagnostic only,
             since strict identification is not the endpoint.
    Always task ≤ strict.
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
    """An independent recomputation (BFS over strategies) for manual verification — mechanical question 7."""
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
        self.train_vectors = all_vectors[:6]           # what the agent sees
        self.blind_vectors = list(all_vectors)          # all 8 (including 2 unseen)
        rng.shuffle(self.blind_vectors)

        glyphs = GLYPH_POOL[:]
        rng.shuffle(glyphs)
        self.train_symbols = {glyphs[k]: v for k, v in enumerate(self.train_vectors)}
        # the blind test: *entirely new* symbols (a permutation) — the same underlying structure
        self.blind_symbols = {glyphs[8 + k]: v for k, v in enumerate(self.blind_vectors)}

        self.D_min = d_min(self.hypotheses, self.train_vectors)          # worst-case: a generation gate only
        self.D_inst = d_min_instance(self.hypotheses, self.train_vectors,
                                     self.true_id)                        # identification cost (reporting)
        # A-002: separating identification from extrapolation
        self.blind_ID, self.blind_X = split_blind(self.hypotheses,
                                                  self.train_vectors,
                                                  self.blind_symbols)
        oracle = d_pred_inst(self.hypotheses, self.train_vectors, self.true_id,
                             [tuple(v) for v in self.blind_ID.values()], tau=0.90)
        self.D_pred = oracle["D_pred"]            # None = UNREACHABLE
        self.D_reachable = oracle["reachable"]
        self.D_greedy_ref = oracle["D_greedy_ref"]
        # --- A-004: four explicitly named rulers instead of an ambiguous D_floor ---
        # D_robust^task: the cost of the optimal policy that does not know W in advance and guarantees the task criterion.
        self.D_robust = self.D_pred
        # The two instance floors under epistemic admissibility (a diagnostic lower envelope).
        self.D_floor_task, self.D_floor_strict = d_floor_pair(
            self.hypotheses, self.train_vectors, self.true_id,
            [tuple(v) for v in self.blind_ID.values()], tau=0.90)
        # A-002 invariant: the primary target must be identifiable under the declared
        # intervention space — an UNREACHABLE world is rejected during generation itself.
        self.accepted = (dmin_window[0] <= self.D_min <= dmin_window[1]
                         and self.D_reachable)

    # --- Oracle API (verifier-side only; the agent never touches it) ---
    def oracle_test(self, symbol):
        table = {**self.train_symbols, **self.blind_symbols}
        if symbol not in table:
            raise KeyError(f"unknown symbol {symbol}")
        return self.hypotheses[self.true_id].eval(table[symbol])

    def true_law_name(self):
        return self.hypotheses[self.true_id].name()

    # --- What is handed to the agent in phase zero (Article 34) ---
    def phase_zero_packet(self):
        return {
            "symbols": {s: list(v) for s, v in self.train_symbols.items()},
            "actions": ["TEST(symbol)"],
            "declared_primitives": {
                "law_family": "binary formula (±p_i OP ±p_j), OP in AND/OR/XOR",
                "n_props": N_PROPS,
                # no hidden primitives in the mechanical stage — an incomplete declaration belongs to the pilot
                "declaration_complete": True,
            },
            # no D_min, no seed, no true law, no blind symbols
        }


def classify_region(n_realized, d_floor_task, d_robust):
    """A-004: which region the run falls into. The official guard is the task floor, not the strict one.

      N < D_floor^task            → TRUE_AUDIT (a contradiction: leakage/accounting/oracle bug)
      D_floor^task ≤ N < D_robust → FAVORABLE_TRAJECTORY (perfectly normal)
      N ≥ D_robust                → AT_OR_ABOVE_ROBUST (no violation; efficiency below the guarantee)
    """
    if n_realized is None or d_floor_task is None or d_robust is None:
        return "UNCLASSIFIED"
    if n_realized < d_floor_task:
        return "TRUE_AUDIT"
    if n_realized < d_robust:
        return "FAVORABLE_TRAJECTORY"
    return "AT_OR_ABOVE_ROBUST"


def generate_accepted_world(seed_base, dmin_window=(2, 6), max_tries=200):
    """Rejection sampling: any world outside the D_min window is rejected (Article 25)."""
    for k in range(max_tries):
        w = World(seed_base * 1000 + k, dmin_window)
        if w.accepted:
            return w
    raise RuntimeError("no world in D_min window")
