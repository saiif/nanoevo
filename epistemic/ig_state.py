"""ig_state.py — IG_Σ (state / assignment information gain) — analysis only, outside the frozen contract.

Decision made after B1-small (does not touch A-005, world_b1, or oracle search):
information_gain() in world_b1 returns (IG_joint, IG_law) where IG_law ≡ IG_H = I(H;Y|E).
The missing quantity is IG_Σ = I(Σ;Y|E) — how much the action pins down **the assignment**
(which symbol owns which vector).

The new distinction (emerged from the point that "EXPERIMENT before PROBE can be rational"):

    information about state (Σ)  ≠  information about law (H)

Even though a single action can carry both: an experiment on a symbol whose state is
unknown may rule out (h,σ) pairs and raise IG_Σ and IG_H together. So the three
quantities are diagnostic, not additive: IG_H + IG_Σ ≠ IG_joint in general.

**Why outside world_b1 and not on evidence.key():** Σ is exactly what the symbol-permutation
equivalence folds away (the canonical key). So IG_Σ is computed on the **labeled** evidence
(self.ev in the session), and enumerating the permutations (≤ n!) is cheap here because the
call happens ≤ once per commitment — not inside the hot search loop.
"""

import itertools
import math

from world_b1 import posterior, apply_action, action_outcomes, information_gain


def state_entropy(hyps, evidence, ctx, emask):
    """H(Σ | E) = entropy of the labeled assignment marginal, and the normalizer Z
    (must match posterior).

    The joint marginal is uniform over consistent (h, σ) pairs, so the weight of
    permutation σ is c(σ) = the number of laws compatible with σ's experiments:

        P(σ) ∝ c(σ),   Z = Σ_σ c(σ) = Σ_h W(h)   (same Z as in posterior)
        H(Σ) = -Σ_σ (c/Z) log2(c/Z) = log2 Z − (Σ_σ c·log2 c)/Z

    σ ranges only over permutations compatible with the probe masks; the experiment
    constraint enters via c(σ).
    """
    declared = ctx.declared
    n_syms, n_vecs = ctx.n, len(declared)
    pmask = evidence.pmask
    constraints = [(x, e) for x, e in enumerate(evidence.exp) if e is not None]
    Z = 0
    clogc = 0.0
    for perm in itertools.permutations(range(n_vecs), n_syms):
        ok = True
        for x in range(n_syms):
            if not (pmask[x] >> perm[x]) & 1:      # this assignment violates the probe of symbol x
                ok = False
                break
        if not ok:
            continue
        c = 0
        for k in range(len(hyps)):                 # count the laws compatible with this σ's experiments
            good = True
            for x, e in constraints:
                if not (emask[k][e] >> perm[x]) & 1:
                    good = False
                    break
            if good:
                c += 1
        if c:
            Z += c
            clogc += c * math.log2(c)
    if Z == 0:
        return 0.0, 0
    return math.log2(Z) - clogc / Z, Z


def information_gain_full(hyps, evidence, emask, ctx, action):
    """(IG_joint, IG_H, IG_Σ) for a single action. IG_joint/IG_H come verbatim from world_b1
    (full agreement with the previous rows), and IG_Σ is added here. p(out) = Z2/Z0 jointly
    — the same weighting as world_b1.

    IG_Σ can be 0 while IG_H > 0 (an experiment after the assignment is already pinned
    down), or IG_Σ > 0 (an experiment/probe rules out assignment pairs). Initial state:
    H(Σ) = log2(n!), and once every symbol is pinned down, H(Σ) = 0.
    """
    # Redundant action: an experiment on a symbol whose outcome is already recorded =
    # re-observing a determined quantity ⇒ zero information.
    # (apply_action overwrites exp[x], which spuriously generates a counterfactual branch
    #  that breaks Σ p_out = 1; the frozen world_b1.information_gain also mis-prices this
    #  case — we zero it out here safely.)
    kind, x, _ = action
    if kind == "EXPERIMENT" and evidence.exp[x] is not None:
        return 0.0, 0.0, 0.0
    ig_joint, ig_law = information_gain(hyps, evidence, emask, ctx, action)
    _, Z0, _, _ = posterior(hyps, evidence, emask, ctx)
    if Z0 == 0:
        return 0.0, 0.0, 0.0
    H0_state, _ = state_entropy(hyps, evidence, ctx, emask)
    exp_state = 0.0
    for out in action_outcomes(evidence, action):
        e2 = apply_action(evidence, action, out)
        _, Z2, _, _ = posterior(hyps, e2, emask, ctx)
        if Z2 == 0:
            continue
        Hs2, _ = state_entropy(hyps, e2, ctx, emask)
        exp_state += (Z2 / Z0) * Hs2
    return ig_joint, ig_law, H0_state - exp_state
