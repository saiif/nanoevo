"""agents.py — scripted agents for mechanical verification (no LLM — the pipeline comes first).

Learner: updates the hypothesis space by elimination, picks the symbol with the most discriminating
        power (worst-case split), declares sufficiency once a single hypothesis remains, and Incomplete
        if the budget runs out under genuine ambiguity.
Control: same update rule, but symbol selection is random — isolates the value of experiment selection.
Violation bots: for testing the violation table and the gate (A.3 + A-003) — each bot violates exactly one rule.
"""

import random

from world import enumerate_hypotheses


class BaseAgent:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.hyps = enumerate_hypotheses()
        self.alive = set(range(len(self.hyps)))
        self.symbols = {}
        self.free_left = 3

    def receive_phase_zero(self, packet):
        self.symbols = {s: tuple(v) for s, v in packet["symbols"].items()}

    def observe(self, action, obs):
        sym = action[5:-1]
        props = self.symbols[sym]
        self.alive = {h for h in self.alive if self.hyps[h].eval(props) == obs}

    def interpret(self, obs):
        return ({"alive_count": len(self.alive),
                 "update_kind": "REWEIGHT"},
                f"free-thought: {len(self.alive)} hypotheses remain")

    def notify(self, msg):
        pass

    def _beliefs(self):
        w = 1.0 / len(self.alive)
        return {self.hyps[h].name(): round(w, 6) for h in sorted(self.alive)}

    def _fix_probs(self, probs):
        s = sum(probs.values())
        keys = list(probs)
        fixed = {k: probs[k] / s for k in keys[:-1]}
        fixed[keys[-1]] = 1.0 - sum(fixed.values())
        return fixed

    def _predictions_for(self, sym):
        props = self.symbols[sym]
        p1 = sum(1 for h in self.alive if self.hyps[h].eval(props) == 1) / len(self.alive)
        return {"outcome=1": round(p1, 6)}

    def blind_predict(self, blind_cases):
        """Prediction + confidence = the mass of remaining hypotheses agreeing on the answer (A-002).
        An agent honest about its own ignorance: confidence automatically drops where the remaining
        hypotheses disagree.
        Returns (predictions, thoughts) — the same contract as deposit (A-003)."""
        out = {}
        for s, v in blind_cases.items():
            if not self.alive:                       # no model: explicit ignorance
                out[s] = {"pred": 0, "conf": 0.5}
                continue
            votes = [self.hyps[h].eval(tuple(v)) for h in self.alive]
            ones = sum(votes) / len(votes)
            pred = 1 if ones >= 0.5 else 0
            out[s] = {"pred": pred, "conf": round(max(ones, 1 - ones), 4)}
        return out, None

    def _sufficiency(self):
        return ({"type": "SUFFICIENCY",
                 "final_hypothesis": self.hyps[min(self.alive)].name(),
                 "confidence": 0.99}, "declaring sufficiency")

    def _incomplete(self):
        return ({"type": "INCOMPLETE",
                 "remaining_hypotheses": [self.hyps[h].name() for h in sorted(self.alive)],
                 "reason": "evidence insufficient to discriminate remaining hypotheses"}, None)

    def _inadequacy(self):
        # no hypothesis in the declared family explains the evidence — the formal declaration (Article 39)
        return ({"type": "INADEQUACY",
                 "reason": "no hypothesis in declared family survives the evidence",
                 "requested_family": "unknown — detection without diagnosis"},
                "declaring model inadequacy")

    def _commitment(self, sym):
        return {"type": "COMMITMENT",
                "hypotheses": self._fix_probs(self._beliefs()),
                "action": f"TEST({sym})",
                "predictions": self._predictions_for(sym),
                "update_kind": "REWEIGHT"}

    def deposit(self):
        raise NotImplementedError


class LearnerAgent(BaseAgent):
    """Epistemic training (scripted version): choosing the maximally discriminating experiment."""

    def _best_symbol(self):
        best, best_score = None, None
        for sym, props in self.symbols.items():
            split = {0: 0, 1: 0}
            for h in self.alive:
                split[self.hyps[h].eval(props)] += 1
            if 0 in (split[0], split[1]):
                continue  # not discriminating
            score = max(split.values())  # minimize worst case
            if best_score is None or score < best_score:
                best, best_score = sym, score
        return best

    def deposit(self):
        if not self.alive:
            return self._inadequacy()
        if len(self.alive) == 1:
            return self._sufficiency()
        sym = self._best_symbol()
        if sym is None:
            # A-002: the agent has exhausted what the evidence permits it to know (no discriminating
            # test remains). The observational class is determined → Blind-ID's answer is guaranteed →
            # it declares sufficiency with honest confidence = the mass of the largest hypothesis,
            # letting the ambiguity show up in conf_X.
            return ({"type": "SUFFICIENCY",
                     "final_hypothesis": self.hyps[min(self.alive)].name(),
                     "confidence": round(1.0 / len(self.alive), 4)},
                    "evidence exhausted; observational class identified; "
                    "residual ambiguity carried honestly into blind confidence")
        if self.free_left > 0:
            self.free_left -= 1
            return ({"type": "FREE_OBS", "action": f"TEST({sym})"},
                    "free exploration on most-splitting symbol")
        return self._commitment(sym), f"choosing discriminative test {sym}"


class ControlAgent(BaseAgent):
    """No training: random selection — same resources, same update rule."""

    def deposit(self):
        if not self.alive:
            return self._inadequacy()
        if len(self.alive) == 1:
            return self._sufficiency()
        sym = self.rng.choice(list(self.symbols))
        if self.free_left > 0:
            self.free_left -= 1
            return ({"type": "FREE_OBS", "action": f"TEST({sym})"}, None)
        return self._commitment(sym), None


# ----------------------------- violation bots (A.3) -----------------------------

class MalformedOnceAgent(LearnerAgent):
    """First deposit has probabilities summing to 1.2 → one retry → valid (A.3 line 1-2).
    On retry the session calls deposit again and the state hasn't changed → the valid version."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self._poisoned = False

    def deposit(self):
        dep, th = super().deposit()
        if not self._poisoned and dep["type"] == "COMMITMENT":
            self._poisoned = True
            bad = dict(dep)
            bad["hypotheses"] = {k: v * 1.2 for k, v in dep["hypotheses"].items()}
            return bad, "malformed on purpose (probs sum to 1.2)"
        return dep, th


class MalformedTwiceAgent(LearnerAgent):
    """Fails the schema twice → AgentProtocolFailure with E=0 (A.3 line 4)."""

    def deposit(self):
        return ({"type": "COMMITMENT", "hypotheses": {"h": 2.0},
                 "action": "TEST(??)", "predictions": {},
                 "update_kind": "REWEIGHT"}, "always malformed")


class LeakProbeAgent(LearnerAgent):
    """Attempts a forbidden action (a symbol outside the training region) → refusal + attempt consumed."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self._probed = False
        self.free_left = 0

    def deposit(self):
        if not self._probed:
            self._probed = True
            dep = self._commitment(next(iter(self.symbols)))
            dep["action"] = "TEST(Zz)"          # symbol that doesn't exist in the allowed region
            dep["predictions"] = {"outcome=1": 0.5}
            return dep, "probing outside allowed region"
        return super().deposit()


# ----------------------------- violation bots (A-003) -----------------------------

class BadActionAgent(LearnerAgent):
    """A malformed action string (passes the schema, gets rejected by the Verifier): once during free
    observation and once during commitment.
    Expected: FREE_OBS_REFUSED + REFUSED_ACTION, the session continues and resolves, no crash."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 1
        self._stage = 0

    def deposit(self):
        if self._stage == 0:
            self._stage = 1
            return ({"type": "FREE_OBS", "action": "TEST(Qz, Vx)"}, "malformed free action")
        if self._stage == 1:
            self._stage = 2
            dep = self._commitment(next(iter(self.symbols)))
            dep["action"] = "test qz"
            return dep, "malformed committed action"
        return super().deposit()


class ExtraFreeObsAgent(LearnerAgent):
    """Sends a fourth FREE_OBS after the observation phase has ended → PHASE_REJECT + a neutral retry,
    then commits. Expected: the session continues (no immediate failure)."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 4

    def notify(self, msg):
        if msg == "TYPE_NOT_ALLOWED_IN_PHASE":
            self.free_left = 0


class InadequacyLoopAgent(LearnerAgent):
    """Declares inadequacy forever → every declaration consumes an attempt → BUDGET_EXHAUSTED, not an infinite loop."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 0

    def deposit(self):
        return self._inadequacy()


class BlindMalformedAgent(LearnerAgent):
    """Malformed blind reply n_bad times, then valid. n_bad=1 → BLIND_REJECT + retry + SOLVED;
    n_bad=2 → AgentProtocolFailure during the blind phase without revealing the truth."""

    def __init__(self, seed=0, n_bad=1):
        super().__init__(seed)
        self.n_bad = n_bad

    def blind_predict(self, blind_cases):
        if self.n_bad > 0:
            self.n_bad -= 1
            return None, "garbled blind reply on purpose"
        return super().blind_predict(blind_cases)


class EarlyStopAgent(LearnerAgent):
    """Declares sufficiency before full identification (once ≤ stop_at hypotheses remain) and predicts
    by majority.

    Its existence is necessary to test A-004: the reference Learner seeks full identification and so
    never drops below D_robust, whereas the LLM actually does (2000#r1). This bot produces a trajectory
    shorter than the guarantee, so it tests: the FAVORABLE_TRAJECTORY region, that E_robust > 1 is
    uncapped, and that the audit does not fire as long as N ≥ D_floor^task. It may sometimes end in
    FALSE_CERTAINTY — and that is legitimate behavior for early stopping.
    """

    def __init__(self, seed=0, stop_at=2):
        super().__init__(seed)
        self.stop_at = stop_at

    def deposit(self):
        if self.alive and len(self.alive) <= self.stop_at:
            return ({"type": "SUFFICIENCY",
                     "final_hypothesis": self.hyps[min(self.alive)].name(),
                     "confidence": round(1.0 / len(self.alive), 4)},
                    "early task-aligned stop (A-004 ruler test)")
        return super().deposit()


class IncompleteClaimAgent(LearnerAgent):
    """After free observation, claims the evidence is insufficient while a discriminating test still
    exists → INCOMPLETENESS_VERIFIED correct=False → INCORRECT_INCOMPLETENESS_CLAIMED, E=0."""

    def deposit(self):
        if self.free_left > 0 or len(self.alive) <= 1:
            return super().deposit()
        return self._incomplete()
