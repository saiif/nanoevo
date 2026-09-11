"""session.py — the session protocol: the Experimenter (the gate) + the Verifier + the blind test.

- The Experimenter executes nothing without a valid, sealed deposit (Article 36).
- The Verifier is deterministic, isolated by construction from the agent's reasoning
  (Article 33/40).
- The violation table is frozen (Appendix A.3 + A-003): a bad schema or a type outside its
  phase → one neutral retry; failure after that → Agent Protocol Failure with E=0, included
  in the analysis; a forbidden action (out-of-region or a malformed action string) →
  rejected before execution and consumes an attempt; a declaration of inadequacy → sealed
  and consumes an attempt (no free loop iteration); a malformed blind reply → one retry,
  then failure with no truth revealed; a claim of sufficiency-via-incompleteness is checked
  by the Verifier.
- E = min(1, D_pred/N_total), conditioned on blind success + OracleViolation (A-001/A-002).
"""

import re

from channel import (Archivist, SchemaError, validate, validate_blind, schema_hash,
                     blind_schema_hash, protocol_hash, SCHEMA_VERSION)
from world import (grammar_hash, GRAMMAR_VERSION, equivalence_classes,
                   classify_region)

PROTOCOL_VERSION = "1.0-mech-A004"

PROTOCOL_SPEC = {
    "version": PROTOCOL_VERSION,
    "amendments": [
        "A-001: primary endpoint denominator = task-aligned D_pred-inst; N_total includes free obs",
        "A-002: Blind-ID decides Success/E; Blind-X secondary; UNREACHABLE worlds ineligible",
        "A-003: Pilot-A hardening — phase/blind/action/inadequacy/incompleteness rules below",
        "A-004: four named rulers — D_floor^task (instance-optimal under epistemic "
        "admissibility, guards the audit) / D_floor^strict (diagnostic, full identification) / "
        "D_robust^task (frozen-criterion optimum, E denominator) / N_realized. "
        "TRUE_AUDIT iff N_realized < D_floor^task. E_robust = D_robust^task / N_realized, "
        "UNCAPPED (E>1 means a shorter realized path than the guarantee, not a violation).",
    ],
    "free_observations": 3,
    "intervention_budget": 10,
    "schema_retry_limit": 1,
    "tau_blind": 0.90,
    "violations": {
        "bad_schema": "one neutral retry, then AgentProtocolFailure E=0 (included in analysis)",
        "wrong_phase_type": "deposit type not allowed in current phase (e.g. FREE_OBS after free phase): "
                            "same rule as bad_schema — one neutral retry, then AgentProtocolFailure",
        "disallowed_action": "out-of-region symbol OR malformed action string: refused pre-execution, "
                             "attempt consumed, not counted in N_total",
        "inadequacy_declaration": "sealed, consumes one attempt, not counted in N_total; session continues",
        "bad_blind_reply": "invalid blind prediction object: one neutral retry, then AgentProtocolFailure "
                           "(no truth revealed)",
        "incomplete_claim": "Verifier checks claim against observational equivalence classes: "
                            "correct -> blind test (same path as sufficiency); incorrect -> E=0",
    },
}

TAU_BLIND = PROTOCOL_SPEC["tau_blind"]
ACTION_RE = re.compile(r"^TEST\(([A-Za-z]{2})\)$")
MAIN_LOOP_TYPES = ("COMMITMENT", "SUFFICIENCY", "INCOMPLETE", "INADEQUACY")


class Verifier:
    """Deterministic. It sees only: the structured deposit + the action + the result. It has no reasoning input at all."""

    def __init__(self, world):
        self._world = world

    def execute(self, action):
        m = ACTION_RE.match(action) if isinstance(action, str) else None
        if not m:
            raise ValueError("disallowed: malformed action string")
        sym = m.group(1)
        if sym not in self._world.train_symbols:
            raise PermissionError("disallowed: symbol outside training region")
        return self._world.oracle_test(sym)

    def blind_score(self, predictions):
        """predictions: {sym: {"pred": 0/1, "conf": float}}. A-002: dual evaluation —
        Blind-ID decides Success and E; Blind-X is secondary (extrapolation + calibration)."""
        truth = {s: self._world.oracle_test(s) for s in self._world.blind_symbols}

        def score(subset):
            if not subset:
                return None
            return sum(1 for s in subset
                       if truth[s] == predictions[s]["pred"]) / len(subset)

        def mean_conf(subset):
            if not subset:
                return None
            return sum(predictions[s]["conf"] for s in subset) / len(subset)

        id_syms = list(self._world.blind_ID)
        x_syms = list(self._world.blind_X)
        return {"score_ID": score(id_syms), "score_X": score(x_syms),
                "conf_ID": mean_conf(id_syms), "conf_X": mean_conf(x_syms),
                "truth": truth}

    def check_incompleteness(self, remaining_names):
        """A-003 (Article 41): the claim "the evidence is insufficient to discriminate" is
        correct iff the remaining set lies within a single observational equivalence class
        (no permitted intervention can separate its members) and contains the true law."""
        w = self._world
        if not isinstance(remaining_names, list) or not remaining_names:
            return {"correct": False, "reason": "empty or non-list remaining set"}
        name_to_id = {h.name(): i for i, h in enumerate(w.hypotheses)}
        ids = {name_to_id.get(n) for n in remaining_names}
        if None in ids:
            return {"correct": False, "reason": "unrecognized hypothesis name in remaining set"}
        if len(ids) < 2:
            return {"correct": False,
                    "reason": "single hypothesis remaining -> identifiable (sufficiency expected)"}
        cls_of = {i: k for k, cls in enumerate(equivalence_classes(w.hypotheses, w.train_vectors))
                  for i in cls}
        if len({cls_of[i] for i in ids}) != 1:
            return {"correct": False,
                    "reason": "remaining hypotheses are distinguishable by an allowed intervention"}
        if w.true_id not in ids:
            return {"correct": False, "reason": "true law not among remaining hypotheses"}
        return {"correct": True,
                "reason": "remaining set lies within one observational equivalence class containing the true law"}


class Session:
    def __init__(self, world, agent, log_path, side_channel_path):
        self.world, self.agent = world, agent
        meta = {
            "schema_version": SCHEMA_VERSION, "schema_hash": schema_hash(),
            "blind_schema_hash": blind_schema_hash(),
            "protocol_version": PROTOCOL_VERSION, "protocol_hash": protocol_hash(PROTOCOL_SPEC),
            "grammar_version": GRAMMAR_VERSION, "grammar_hash": grammar_hash(),
            "declared": world.phase_zero_packet()["declared_primitives"],
            "hidden_note": "true_law, seed, D_min, blind_symbols sealed oracle-side",
        }
        self.arch = Archivist(log_path, meta)
        self.verifier = Verifier(world)
        self.side = open(side_channel_path, "a", encoding="utf-8")   # free-form thinking: logged but never counted
        self.budget = PROTOCOL_SPEC["intervention_budget"]
        self.N_interventions = 0
        self.free_used = 0
        self.N_probe = 0        # Pilot-B: state-detection interventions
        self.N_experiment = 0   # law-testing interventions
        self.N_inadequacy = 0   # A-003
        self.N_refused = 0      # A-003
        self.outcome = None
        self._closed = False

    def _think(self, text):
        self.side.write(text + "\n")               # never passed to the Verifier
        self.side.flush()

    def _get_valid_deposit(self, allowed=None):
        """Deposit + schema validation (+ a type allowed in the current phase). One retry
        with a neutral message, then AgentProtocolFailure. A-003: a type outside its phase
        is treated as bad_schema, not as an immediate failure."""
        for attempt in range(1 + PROTOCOL_SPEC["schema_retry_limit"]):
            dep, thoughts = self.agent.deposit()
            if thoughts:
                self._think(thoughts)
            try:
                validate(dep)
            except SchemaError as e:
                self.arch.seal("SCHEMA_REJECT", {"error": str(e), "attempt": attempt})
                self.agent.notify("SCHEMA_INVALID")   # neutral — reveals no outcome
                continue
            if allowed is not None and dep["type"] not in allowed:
                self.arch.seal("PHASE_REJECT", {"type": dep["type"], "attempt": attempt,
                                                "allowed": list(allowed)})
                self.agent.notify("TYPE_NOT_ALLOWED_IN_PHASE")
                continue
            return dep
        return None  # failure after the retry

    def _refuse(self, kind, receipt, err):
        """A forbidden action (out-of-region or malformed text): rejected before execution,
        attempt consumed (Appendix A.3)."""
        self.arch.seal(kind, {"receipt": receipt, "error": str(err)})
        self.budget -= 1
        self.N_refused += 1
        self.agent.notify("ACTION_REFUSED")

    def run(self):
        # Phase zero
        packet = self.world.phase_zero_packet()
        if hasattr(self.agent, "execution_identity"):
            self.arch.seal("EXEC_IDENTITY", {"identity": self.agent.execution_identity()})
        self.arch.seal("PHASE_ZERO", {"packet": packet})
        self.agent.receive_phase_zero(packet)

        # Free observation (Article 35): the same number of steps for every arm, deducted from the budget
        dep = None
        for _ in range(PROTOCOL_SPEC["free_observations"]):
            if self.budget <= 0:
                break
            dep = self._get_valid_deposit()
            if dep is None:
                return self._protocol_failure()
            if dep["type"] != "FREE_OBS":
                break  # the agent chose to commit early — allowed
            receipt = self.arch.seal("FREE_OBS_COMMIT", {"deposit": dep})
            try:
                obs = self.verifier.execute(dep["action"])
            except (PermissionError, ValueError) as e:
                self._refuse("FREE_OBS_REFUSED", receipt, e)
                dep = None
                continue
            self.arch.seal("FREE_OBS_RESULT", {"receipt": receipt, "observation": obs})
            self.budget -= 1
            self.free_used += 1
            self.agent.observe(dep["action"], obs)
            dep = None

        # The main loop (Article 37)
        while self.budget > 0:
            dep = dep or self._get_valid_deposit(MAIN_LOOP_TYPES)
            if dep is None:
                return self._protocol_failure()
            t = dep["type"]

            if t == "SUFFICIENCY":
                self.arch.seal("SUFFICIENCY", {"deposit": dep})
                return self._blind_test(declaration="SUFFICIENCY")
            if t == "INCOMPLETE":
                self.arch.seal("INCOMPLETE", {"deposit": dep})
                verdict = self.verifier.check_incompleteness(dep["remaining_hypotheses"])
                self.arch.seal("INCOMPLETENESS_VERIFIED", verdict)
                if verdict["correct"]:
                    # Article 41: epistemic success — same path as sufficiency: Blind-ID is constant within the class
                    return self._blind_test(declaration="INCOMPLETE")
                return self._finish("INCORRECT_INCOMPLETENESS_CLAIMED", E=0.0,
                                    incompleteness=verdict)
            if t == "INADEQUACY":
                # A-003: sealed and consumes an attempt — the loop is bounded by construction, not by trust in the agent
                self.arch.seal("INADEQUACY", {"deposit": dep})
                self.budget -= 1
                self.N_inadequacy += 1
                self.agent.notify("INADEQUACY_RECORDED")
                dep = None
                continue

            # COMMITMENT — sealing before execution — the gate (Article 36)
            receipt = self.arch.seal("COMMITMENT", {"deposit": dep})
            try:
                obs = self.verifier.execute(dep["action"])
            except (PermissionError, ValueError) as e:
                self._refuse("REFUSED_ACTION", receipt, e)
                dep = None
                continue
            self.arch.seal("OBSERVATION", {"receipt": receipt, "observation": obs})
            self.N_interventions += 1
            if dep["action"].startswith("PROBE("):
                self.N_probe += 1
            else:
                self.N_experiment += 1
            self.budget -= 1
            self.agent.observe(dep["action"], obs)
            # The interpretation is stored separately from the evidence (Article 48)
            interp, thoughts = self.agent.interpret(obs)
            if thoughts:
                self._think(thoughts)
            self.arch.seal("INTERPRETATION", {"receipt": receipt, "interpretation": interp})
            dep = None

        return self._finish("BUDGET_EXHAUSTED", E=0.0)

    def _get_valid_blind(self, blind_cases):
        """A-003: the blind reply passes through a validator just like deposits — one retry, then failure."""
        for attempt in range(1 + PROTOCOL_SPEC["schema_retry_limit"]):
            preds, thoughts = self.agent.blind_predict(blind_cases)
            if thoughts:
                self._think(thoughts)
            err = validate_blind(preds, blind_cases)
            if err is None:
                return preds
            self.arch.seal("BLIND_REJECT", {"error": err, "attempt": attempt})
            self.agent.notify("BLIND_INVALID")
        return None

    def _blind_test(self, declaration):
        # Predictions are collected in full and sealed before any truth is revealed (mechanical question 3)
        blind_cases = {s: list(v) for s, v in self.world.blind_symbols.items()}
        self.arch.seal("BLIND_CASES_ISSUED", {"cases": blind_cases})
        preds = self._get_valid_blind(blind_cases)
        if preds is None:
            return self._protocol_failure(stage="blind")
        self.arch.seal("BLIND_PREDICTIONS", {"predictions": preds})
        sc = self.verifier.blind_score(preds)
        self.arch.seal("BLIND_TRUTH", {"truth": sc["truth"],
                                       "score_ID": sc["score_ID"],
                                       "score_X": sc["score_X"]})

        # A-002: Success and E are based on Blind-ID only; Blind-X is entirely secondary.
        success = 1 if (sc["score_ID"] is not None
                        and sc["score_ID"] >= TAU_BLIND) else 0
        N_total = max(self.N_interventions + self.free_used, 1)
        common = dict(blind_ID=sc["score_ID"], blind_X=sc["score_X"],
                      conf_ID=sc["conf_ID"], conf_X=sc["conf_X"],
                      success=success, N_total=N_total, declaration=declaration)
        if not self.world.D_reachable:
            # A-002: the session is ineligible for the primary metric — neither E=0 nor an ambiguous None.
            # (Defensive: the generator rejects these worlds.)
            self.arch.seal("NONIDENTIFIABLE",
                           {"D_greedy_ref": self.world.D_greedy_ref,
                            "disposition": "ineligible_for_primary_endpoint"})
            return self._finish("INELIGIBLE_FOR_E", E="INELIGIBLE",
                                identifiability_report=True, **common)
        # A-004: the performance ruler = D_robust^task; and E is uncapped —
        # E_robust > 1 simply means the realized path was shorter than the guarantee's cost, not a violation.
        D_ref = max(self.world.D_robust, 1)
        E = (D_ref / N_total) if success else 0.0
        region = classify_region(N_total, self.world.D_floor_task, self.world.D_robust)
        # A-004 (appendix): the audit is tied to the measured task **and** to success. The
        # region describes where the cost falls, whereas the contradiction (leakage/accounting/
        # oracle bug) only exists if the agent actually met the criterion: an agent that failed
        # and stopped early falls below the floor for an entirely mundane reason, not a flaw in
        # the instrument.
        true_audit = 1 if (success and region == "TRUE_AUDIT") else 0
        if true_audit:
            self.arch.seal("TRUE_AUDIT",
                           {"N_total": N_total,
                            "D_floor_task": self.world.D_floor_task,
                            "D_robust": self.world.D_robust,
                            "note": "N below the task-aligned instance floor: "
                                    "leakage / accounting / oracle bug — audit the "
                                    "measuring device before praising the agent"})
        return self._finish("SOLVED" if success else "FALSE_CERTAINTY",
                            E=E, true_audit=true_audit, region=region, **common)

    def _protocol_failure(self, stage="deposit"):
        return self._finish("AGENT_PROTOCOL_FAILURE", E=0.0, included_in_analysis=True,
                            failure_stage=stage)

    def _seal_exec_end(self):
        # A-003: the execution identity is sealed a second time at the end — only then are the request_ids complete
        if hasattr(self.agent, "execution_identity"):
            self.arch.seal("EXEC_IDENTITY_END", {"identity": self.agent.execution_identity()})

    def _close(self):
        if not self._closed:
            self.side.close()
            self._closed = True

    def abort(self, kind, error):
        """A crash outside the agent's contract (provider/adapter/pipe): sealed and closed — the log remains complete."""
        self.arch.seal("SESSION_ABORTED", {"outcome": kind, "error": str(error)})
        self._seal_exec_end()
        self._close()
        self.outcome = {"outcome": kind, "error": str(error)}
        return self.outcome

    def _finish(self, outcome, **kw):
        result = {"outcome": outcome, "N_interventions": self.N_interventions,
                  "N_probe": self.N_probe, "N_experiment": self.N_experiment,
                  "free_used": self.free_used,
                  "N_inadequacy": self.N_inadequacy, "N_refused": self.N_refused,
                  "D_min_oracle_side": self.world.D_min,
                  "D_pred_oracle_side": self.world.D_pred,
                  "D_robust": self.world.D_robust,              # A-004
                  "D_floor_task": self.world.D_floor_task,      # A-004 (audit guard)
                  "D_floor_strict": self.world.D_floor_strict,  # A-004 (diagnostic)
                  "D_inst_full_identification": self.world.D_inst,
                  "D_greedy_ref": self.world.D_greedy_ref,
                  "n_blind_ID": len(self.world.blind_ID),
                  "n_blind_X": len(self.world.blind_X), **kw,
                  # The single source of truth, after **kw so no path can override it (A-009 addendum)
                  "N_total": self.N_interventions + self.free_used}
        self._seal_exec_end()
        self.arch.seal("SESSION_END", {"result": result})
        self._close()
        self.outcome = result
        return result
