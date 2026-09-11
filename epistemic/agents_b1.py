"""agents_b1.py — B1 scripted agents (no LLM — pipeline first).

LearnerB1: computes the joint posterior from its own evidence (not from the oracle), and picks the action with the highest IG.
NoProbeAgent: never explores — the first adversarial check recorded in spec §10.
Violation bots: test the violation table and the semantic hypothesis identity.
"""

import random

from world_b1 import (Evidence, all_actions, apply_action, posterior, information_gain)


class BaseB1:
    """Agent that keeps its own evidence state and computes the posterior only from information available to it."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.free_left = 2

    def receive_phase_zero(self, packet):
        self.symbols = list(packet["symbols"])
        self.catalog = packet["hypothesis_catalog"]
        self.ids = list(self.catalog)
        self.declared = [tuple(v) for v in
                         packet["declared_primitives"]["property_vectors_present"]]
        # Build the agent's own copy of the hypothesis space from the declared catalog (not from the oracle)
        from world import enumerate_hypotheses
        self.hyps = enumerate_hypotheses()
        from world_b1 import exp_masks, _subsets_by_popcount, Ctx
        self.emask = exp_masks(self.hyps, self.declared)
        self.n = len(self.symbols)
        self.ctx = Ctx(self.n, _subsets_by_popcount(self.n), self.declared, {})
        self.ev = Evidence(self.n, self.n)
        self.idx = {s: k for k, s in enumerate(self.symbols)}

    def observe(self, action, out):
        kind = action.split("(")[0]
        sym = action[action.index("(") + 1:-1]
        x = self.idx[sym]
        if kind == "PROBE":
            self.ev = apply_action(self.ev, ("PROBE", x, None),
                                   self.declared.index(tuple(out)))
        else:
            self.ev = apply_action(self.ev, ("EXPERIMENT", x, None), out)

    def notify(self, msg):
        pass

    def _post(self):
        return posterior(self.hyps, self.ev, self.emask, self.ctx)

    def _beliefs(self):
        P, _, _, sup = self._post()
        if not sup:
            return {self.ids[0]: 1.0}
        d = {self.ids[k]: P[k] for k in sup}
        keys = list(d)
        fixed = {k: d[k] for k in keys[:-1]}
        fixed[keys[-1]] = 1.0 - sum(fixed.values())
        return fixed

    def _best_action(self):
        best, best_ig = None, -1.0
        for a in all_actions(self.n):
            ig, _ = information_gain(self.hyps, self.ev, self.emask, self.ctx, a)
            if ig > best_ig + 1e-12:
                best, best_ig = a, ig
        return best, best_ig

    def _act_str(self, a):
        return f"{a[0]}({self.symbols[a[1]]})"

    def _predictions_for(self, a):
        """Sealed prediction before execution: probability of outcome=1 for an experiment, or a flat distribution for exploration."""
        if a[0] == "EXPERIMENT":
            _, Z, _, _ = self._post()
            _, Z1, _, _ = posterior(self.hyps, apply_action(self.ev, a, 1),
                                    self.emask, self.ctx)
            # P(outcome=1) = mass of consistent pairs giving 1 ÷ total mass
            return {"outcome=1": round(Z1 / Z, 6) if Z else 0.5}
        return {"vector_known_after": 1.0}

    def blind_predict(self, cases):
        P, _, _, sup = self._post()
        out = {}
        for s, v in cases.items():
            if not sup:
                out[s] = {"pred": 0, "conf": 0.5}
                continue
            ones = sum(P[k] for k in sup if self.hyps[k].eval(tuple(v)) == 1)
            pred = 1 if ones >= 0.5 else 0
            out[s] = {"pred": pred, "conf": round(max(ones, 1 - ones), 4)}
        return out, None

    def _sufficiency(self):
        P, _, _, sup = self._post()
        top = max(sup, key=lambda k: P[k]) if sup else 0
        return ({"type": "SUFFICIENCY", "final_hypothesis": self.ids[top],
                 "confidence": round(P[top], 4) if sup else 0.5}, "declaring sufficiency")

    def deposit(self):
        raise NotImplementedError


class LearnerB1(BaseB1):
    """Explores, then experiments according to the highest joint IG; declares sufficiency when only one hypothesis remains."""

    def deposit(self):
        _, _, _, sup = self._post()
        if len(sup) <= 1:
            return self._sufficiency()
        a, ig = self._best_action()
        if a is None or ig <= 1e-12:
            return self._sufficiency()
        act = self._act_str(a)
        if self.free_left > 0:
            self.free_left -= 1
            return {"type": "FREE_OBS", "action": act}, f"free {act}"
        return ({"type": "COMMITMENT", "hypotheses": self._beliefs(), "action": act,
                 "predictions": self._predictions_for(a), "update_kind": "REWEIGHT"},
                f"IG-max {act}")


class NoProbeAgent(BaseB1):
    """Adversarial check (§10): never explores at all — only experiments.

    If it can still reach the criterion, that means information about the state leaked from the representation,
    or the world isn't testing the B1 question at all.
    """

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 0

    def deposit(self):
        _, _, _, sup = self._post()
        if len(sup) <= 1:
            return self._sufficiency()
        best, best_ig = None, -1.0
        for a in all_actions(self.n):
            if a[0] == "PROBE":
                continue
            ig, _ = information_gain(self.hyps, self.ev, self.emask, self.ctx, a)
            if ig > best_ig + 1e-12:
                best, best_ig = a, ig
        if best is None or best_ig <= 1e-12:
            return self._sufficiency()
        return ({"type": "COMMITMENT", "hypotheses": self._beliefs(),
                 "action": self._act_str(best),
                 "predictions": self._predictions_for(best), "update_kind": "REWEIGHT"},
                "experiments only (no probes)")


class UnknownIdAgent(LearnerB1):
    """Deposits a hypothesis id outside the catalog → a representation error the schema must reject."""

    def deposit(self):
        dep, th = super().deposit()
        if dep["type"] == "COMMITMENT":
            bad = dict(dep)
            bad["hypotheses"] = {"H99": 0.5, "(p0 AND p1)": 0.5}   # unknown id + free text
            return bad, "unknown hypothesis id on purpose"
        return dep, th


class BadActionB1(LearnerB1):
    """Action outside the syntax (passes the schema, rejected by the Verifier) → attempt consumed."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 0
        self._done = False

    def deposit(self):
        if not self._done:
            self._done = True
            dep, _ = super().deposit()
            if dep["type"] != "COMMITMENT":
                dep = {"type": "COMMITMENT", "hypotheses": self._beliefs(),
                       "action": "x", "predictions": {"outcome=1": 0.5},
                       "update_kind": "REWEIGHT"}
            dep = dict(dep)
            dep["action"] = "PROBE(Qz, p0)"      # old A-005 syntax — must be rejected
            return dep, "stale per-bit probe syntax"
        return super().deposit()


class NonUniformAgent(LearnerB1):
    """Distorts the weights (keeps the support correct) — a type-2006 belief defect.

    **The schema must not block it**; the belief metrics must measure it (ProbabilityError>0
    with SupportAccuracy=1.0). Its existence proves the separation between the two types works.
    """

    def deposit(self):
        dep, th = super().deposit()
        if dep["type"] == "COMMITMENT" and len(dep["hypotheses"]) >= 2:
            keys = list(dep["hypotheses"])
            skew = dict.fromkeys(keys, 0.0)
            head = 0.6
            skew[keys[0]] = head
            rest = (1.0 - head) / (len(keys) - 1)
            for k in keys[1:]:
                skew[k] = rest
            skew[keys[-1]] = 1.0 - sum(skew[k] for k in keys[:-1])
            dep = dict(dep)
            dep["hypotheses"] = skew
            return dep, "deliberately skewed weights (belief defect, not representation)"
        return dep, th


# ----------------------- A-007: bots for the three INCOMPLETE states -----------------------

class ClaimExhaustionAgent(LearnerB1):
    """Explores a little, then claims "no decisive action remains" while actions are still available.

    This is the 4015/4018 pattern: a correct belief about the world combined with a **false belief about its remaining actions**.
    Expected: INCORRECT_ACTION_EXHAUSTION.
    """

    def __init__(self, seed=0, after=4):
        super().__init__(seed)
        self.after = after
        self.n = 0

    def deposit(self):
        self.n += 1
        if self.n <= self.after:
            return super().deposit()
        _, _, _, sup = self._post()
        return ({"type": "INCOMPLETE",
                 "remaining_hypotheses": [self.ids[k] for k in sup][:8],
                 "reason": "believes no further useful action exists",
                 "claim": "no_decisive_action_remains"}, "false exhaustion claim")


class HonestPrematureAgent(ClaimExhaustionAgent):
    """Same timing but with an honest claim: "the evidence isn't sufficient yet" (no claim of action exhaustion).
    Expected: ACTIONABLE_INCOMPLETENESS — an early stop honestly described."""

    def deposit(self):
        dep, th = super().deposit()
        if dep["type"] == "INCOMPLETE":
            dep = dict(dep)
            dep["claim"] = "insufficient_evidence_now"
            dep["reason"] = "evidence does not determine the law yet"
        return dep, th


class ExhaustThenIncompleteAgent(LearnerB1):
    """Actually exhausts the budget, then declares incompleteness — expected: CORRECT_INCOMPLETENESS."""

    def __init__(self, seed=0, declare_at=1):
        super().__init__(seed)
        self.declare_at = declare_at

    def deposit(self):
        _, _, _, sup = self._post()
        return ({"type": "INCOMPLETE",
                 "remaining_hypotheses": [self.ids[k] for k in sup][:8],
                 "reason": "declared under an exhausted budget",
                 "claim": "no_decisive_action_remains"}, "incomplete at exhausted budget")
