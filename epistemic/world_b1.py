"""world_b1.py — Pilot-B1: latent properties + PROBE/EXPERIMENT + semantic hypothesis identity.

Conforms to the frozen PILOT_B1_SPEC.md (spec_hash b720abb855b59b04) after Amendment A-005.

Structural difference from Pilot-A: the property vectors are **latent** — the agent only
receives symbol names. Two distinct actions: PROBE(sym) reveals the vector **fully** in
one intervention (A-005), and EXPERIMENT(sym) tests the law.

Reference prior (A-005 — describes the implementation literally):
World B1 declares a set of distinct vectors, and the assignment σ from symbols to them is
a **bijection** unknown to the agent. The prior is uniform over pairs (law, bijection):

    P(h, σ) ∝ 1     over every bijective σ

Hence, after evidence E:

    P*(h | E) = #{bijective σ such that (h,σ) ⊨ E}  /  Σ_h' #{bijective σ such that (h',σ) ⊨ E}

The count of consistent bijections = the **permanent** of the (0/1) allowance matrix —
computed by DP over subsets. And H_joint = log2 Z where Z is the denominator above (the
joint state is uniform over consistent pairs).

Logged caveat: the first version assumed conditional independence W(h)=Π_x n_x(h), which is
a **different prior** that allows every symbol to share a single vector — at which point
discrimination becomes impossible and D_robust ceases to exist. The bijection condition is
declared to the agent in phase_zero, and it is part of the world's structure, not of the
hidden law.

Performance note: support membership needs the *existence* of a bijection, not its *count*,
so it is computed via matching (Kuhn); the permanent remains reserved for the posterior
alone. Search states are indexed by a canonical key under permutation of symbols (symbols
are interchangeable under the bijection prior) — both facts are pinned down in
run_mechanical_b1.py.
"""

import hashlib
import itertools
from collections import namedtuple
import json
import math
import random

from world import enumerate_hypotheses, N_PROPS, GLYPH_POOL

GRAMMAR_VERSION_B1 = "1.1-b1-latent-fullprobe"

# One explicit identity for the context: no place should assume it's a pair while another
# assumes it's a triple.
#   n        number of training symbols
#   by_pop   subsets ordered by bit count (for computing the permanent)
#   declared the declared universe of vectors — every mask/index in the file indexes into it exclusively
#   cache    support memo keyed by evidence state (the search revisits states a lot)
Ctx = namedtuple("Ctx", "n by_pop declared cache")
ALL_VECTORS = list(itertools.product((0, 1), repeat=N_PROPS))


# ----------------------- Semantic identity for hypotheses (Article 4) -----------------------

def hypothesis_catalog():
    """H00..H29 — one canonical identifier per truth table. Logical duplication is impossible by construction."""
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


# ----------------------- Evidence and the reference posterior -----------------------

def exp_masks(hyps, declared):
    """EXP_MASK[h][e] = mask of vectors in the **declared set** for which h(v)==e."""
    return [[sum(1 << k for k, v in enumerate(declared) if h.eval(v) == e) for e in (0, 1)]
            for h in hyps]


class Evidence:
    """Session evidence as bit masks — a canonical, hashable, cheap-to-compute state.

    For each symbol: a mask of vectors compatible with the probes (independent of the law) +
    the experiment outcome (a filter that depends on the law). Contains no hidden ground
    truth.
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
        """A **canonical** key under permutation of symbols.

        Symbols are interchangeable a priori (each has an unknown, distinct vector), and the
        support/posterior functions are invariant under row permutation — so two states that
        differ only in symbol order are fully equivalent. Sorting collapses these equivalence
        classes, which sharply shrinks the search space.
        """
        return tuple(sorted((pm, -1 if e is None else e)
                            for pm, e in zip(self.pmask, self.exp)))


def _subsets_by_popcount(n):
    by = [[] for _ in range(n + 1)]
    for S in range(1 << n):
        by[bin(S).count("1")].append(S)
    return by


def _permanent(allowed, n, by_pop):
    """The number of consistent **injective** assignments (bijection): symbol x → an allowed
    vector, with no repeats.

    A-005 (declared invariant): training symbols satisfy a bijection onto the declared set of
    vectors. Without this condition the prior would allow every symbol to share a single
    vector, making discrimination impossible and D_robust = ∞ — i.e., B1 would not be
    runnable at all. Measurement uncovered this before the run.
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
    """Does a valid bijection exist? (standard Kuhn matching) — support needs the *existence*
    of an assignment, not its *count*.

    Computing the full permanent inside the search cost ~80 seconds per world, and the
    existence of a matching is entirely sufficient to decide a hypothesis's membership in the
    support. (The permanent remains reserved for the posterior.)
    """
    match = [-1] * n                      # index of vector j -> the symbol assigned to it

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
    """Returns (P*(h), Z, H_joint, support) under the declared bijective prior."""
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
    """Support alone — the same bijective condition (at least one valid assignment)."""
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


# ----------------------- Actions and information gain (Article 7) -----------------------

def all_actions(n_syms):
    """A-005: PROBE(x) reveals the vector fully in one intervention; EXPERIMENT(x) tests the
    law.

    The degree of freedom "which bit to explore" was deliberately removed (A-005):
    measurement showed it consumes the budget without testing B1's actual question. The
    structural distinction Probe ≠ Experiment is fully preserved.
    """
    return ([("PROBE", x, None) for x in range(n_syms)]
            + [("EXPERIMENT", x, None) for x in range(n_syms)])


def action_outcomes(evidence, action):
    """Possible outcomes of the action. PROBE returns the vector index (up to 8 outcomes), EXPERIMENT returns a bit."""
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
        e.pmask[x] = 1 << out          # the vector is now fully known
    else:
        e.exp[x] = out
    return e


def information_gain(hyps, evidence, emask, ctx, action):
    """IG on the joint state = H_joint(t) − E[H_joint(t+1)|a]. Returns (IG_joint, IG_law).

    Note frozen in the spec: IG_law can be 0 while the probe is nonetheless necessary (it
    sets up a useful experiment later) — hence the measurement is on the joint, and IG_law is
    a separate diagnostic.
    """
    # Repeated action: an experiment on a symbol whose outcome is already recorded =
    # re-observing a determined quantity ⇒ zero information. apply_action would overwrite
    # exp[x], generating a spurious counterfactual branch that breaks Σ p_out = 1, mispricing
    # the information. It is zeroed here so the project keeps **one single meaning for IG**
    # throughout (information_gain and information_gain_full used to disagree on exactly this
    # case).
    kind, x, _ = action
    if kind == "EXPERIMENT" and evidence.exp[x] is not None:
        return 0.0, 0.0
    if kind == "PROBE" and _POPCOUNT_SMALL(evidence.pmask[x]) == 1:
        return 0.0, 0.0          # the vector is fully known — re-exploring adds nothing
    P0, Z0, H0, _ = posterior(hyps, evidence, emask, ctx)
    if Z0 == 0:
        return 0.0, 0.0
    H0_law = _entropy(P0)
    exp_H, exp_H_law = 0.0, 0.0
    for out in action_outcomes(evidence, action):
        P2, Z2, H2, _ = posterior(hyps, apply_action(evidence, action, out), emask, ctx)
        if Z2 == 0:
            continue
        p_out = Z2 / Z0          # probability of the outcome under the uniform joint prior
        exp_H += p_out * H2
        exp_H_law += p_out * _entropy(P2)
    return H0 - exp_H, H0_law - exp_H_law


def _POPCOUNT_SMALL(m):
    return bin(m).count("1")


def _entropy(P):
    return -sum(p * math.log2(p) for p in P if p > 0)


# ----------------------- Floors and the reference (Article 8 — extension of A-004) -----------------------

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
    """A-004 over the two-action space: the cheapest admissible set of actions that reaches
    the criterion.

    On a deterministic instance, each action's outcome is predetermined and the order of
    actions does not change the resulting evidence, so min over admissible policies = min
    over *sets* of actions. Iterative deepening up to cap.
    Returns (task, strict, actions_task) — and None when the cap is exceeded.
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
    """A-007: does an **admissible** policy exist that reaches the task criterion from this
    state within this budget?

    Same logic as d_robust_b1 but starting from an existing evidence state and a remaining
    budget. The guarantee is counterfactual-correct: the policy is not allowed to know the
    true law — it must succeed against any member of the support, were that member the true
    one. This makes "could it have continued?" a deterministic oracle question, not a
    judgment on the agent's intent.

    Returns (attainable, D_remaining, best_action_ig, n_informative_actions) where
    D_remaining = the minimum budget sufficient to guarantee from this state (None if it
    exceeds what's available). Hence Slack = B_remaining − D_remaining: how much margin the
    agent left on the table.
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
    # Minimum sufficient budget: iterative deepening reusing the same memo
    d_remaining = None
    for b in range(max(budget, 0) + 1):
        if solvable(ev0, sup0, b):
            d_remaining = b
            break
    return (d_remaining is not None), d_remaining, round(best_ig, 4), n_inf


def optimistic_reach(hyps, n_syms, emask, ctx, ev0, blind_vectors, tau, cap=10):
    """D_lower(belief_t): the fewest actions that reach the criterion on the **luckiest
    branch**, derived solely from the belief state — not from W*, and not from the true law.

    Why this is necessary: judging the agent as facing an "unsolvable" world based on
    D_floor^task(W*) holds it accountable to a fact it has no access to — the same error as
    4015/4018, but inverted. The quantity that CAN be inferred from its history is: does
    **any** branch consistent with my evidence reach the criterion within k actions?

    Breadth-first search (BFS) over evidence states: a branch = (action, an outcome possible
    under the current belief). Returns the smallest k, or None if it exceeds cap. Always:
    D_lower ≤ D_robust(belief).
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
                if not s2:                       # branch inconsistent with the evidence — unreachable
                    continue
                if met(s2):
                    return d + 1
                seen.add(k2)
                q.append((e2, d + 1))
    return None


def decision_state(hyps, n_syms, emask, ctx, ev, blind_vectors, tau, budget, cap=10):
    """A-008: the true control-relevant state at a decision point — **entirely derived from
    the belief state**.

        MET                     the criterion is satisfied now                Correct: STOP
        GUARANTEED_REACHABLE    a policy exists that guarantees it within B    Correct: CONTINUE
        POSSIBLE_UNGUARANTEED   a lucky branch reaches it, with no guarantee   Not scored right/wrong
        UNREACHABLE             not even the luckiest branch reaches it within B  Correct: INCOMPLETE

    The ambiguity in the middle region is not in the world but in the **decision rule that
    has not yet been fixed**, so it is broken out as an independent analysis instead of being
    counted as an error against reasonable behavior.
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
    """The cost of the optimal policy that does not know the law in advance and guarantees
    the criterion in the worst case.

    Iterative deepening (IDA): we ask "does a guarantee exist within k?" for increasing k —
    much cheaper than a fixed deep search because most branches terminate early. The
    guarantee is counterfactual-correct: a state is terminal if the criterion holds against
    every member of the support, were that member the true one (correction #3 from Pilot-A).
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
        for m in members:                      # worst case over the identity of the true member
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

    # A memo shared across budgets: for each state we cache the largest budget proven to
    # fail and the smallest budget proven to succeed.
    # (Clearing the memo on every deepening pass used to waste all prior work — 84s per world.)
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
            # PROBE may not change the support (IG_law=0) but it changes the state and sets
            # up an experiment — hence the criterion here is "changed the state," not
            # "changed the support" (frozen caveat §7).
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


# ----------------------- The world -----------------------

class WorldB1:
    """World B1: latent vectors, a declared bijection, full-vector PROBE (A-005)."""

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
        # The declared set: n_train distinct vectors, and the assignment to symbols is a
        # bijection unknown to the agent
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
            # D_robust >= D_floor^task structurally — we start deepening from the floor, not
            # from zero
            self.D_robust = d_robust_b1(self.hypotheses, n_train, self.emask, self.ctx,
                                        bl, tau, cap, start=self.D_floor_task or 0)
        self.floor_requires_probe = (bool(self.floor_actions)
                                     and any(a[0] == "PROBE" for a in self.floor_actions))
        self.accepted = (not self.blind_X
                         and self.D_floor_task is not None
                         and self.D_robust is not None
                         and self.floor_requires_probe)

    # --- Oracle API (verifier-side only) ---
    def probe(self, sym):
        """A-005: reveals the vector fully in one intervention."""
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
                # declared invariant (A-005): without it the prior would allow every symbol
                # to share a single vector, making discrimination impossible and D_robust
                # nonexistent.
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
