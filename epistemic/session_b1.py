"""session_b1.py — بروتوكول جلسة Pilot-B1 (spec b720abb855b59b04 + A-005).

الفروق عن جلسة Pilot-A:
- فعلان: PROBE(sym) كامل المتجه (A-005) وEXPERIMENT(sym) — والـ Verifier يرفض ما عداهما.
- محاسبة ثلاثية: N_total = N_free + N_probe + N_experiment، تُخزَّن **منفصلة دائمًا**.
- هوية الفرضية دلالية: الاحتمالات على معرّفات H00..H29، والمعرّف المجهول يُرفض
  (خطأ تمثيل يُمنع) — بينما الوزن غير المنتظم **يُسمح به ويُقاس** (خطأ اعتقاد).
- مقاييس اعتقاد منفصلة لكل التزام: SupportAccuracy / ProbabilityError / ProbeQuality.
"""

import re

from channel import Archivist, SchemaError, validate_blind, blind_schema_hash, protocol_hash
from world import classify_region
from world_b1 import (Evidence, all_actions, apply_action, posterior,
                      information_gain, grammar_hash_b1, GRAMMAR_VERSION_B1)
from ig_state import information_gain_full     # IG_Σ تشخيصي (تحليل فقط، لا يمسّ العقد)

PROTOCOL_VERSION_B1 = "1.0-b1-A005"
SCHEMA_VERSION_B1 = "1.1-b1"

COMMIT_SCHEMA_B1 = {
    "version": SCHEMA_VERSION_B1,
    "types": {
        "FREE_OBS":    {"required": ["action"]},
        "COMMITMENT":  {"required": ["hypotheses", "action", "predictions", "update_kind"]},
        "SUFFICIENCY": {"required": ["final_hypothesis", "confidence"]},
        "INCOMPLETE":  {"required": ["remaining_hypotheses", "reason"]},
        "INADEQUACY":  {"required": ["reason", "requested_family"]},
    },
    "update_kinds": ["INITIAL", "REWEIGHT", "REVISE", "EXPAND"],
    "hypothesis_identity": "semantic IDs from the declared catalog; unknown IDs rejected",
    "actions": "PROBE(symbol) | EXPERIMENT(symbol)",
}

PROTOCOL_SPEC_B1 = {
    "version": PROTOCOL_VERSION_B1,
    "amendments": ["A-004 rulers", "A-005 full-vector PROBE (observation interface only)"],
    "free_observations": 2,
    "intervention_budget": 15,          # يُبرَّر بحساب الأوراكل، لا بمنح مساحة مريحة
    "schema_retry_limit": 1,
    "tau_blind": 0.90,
    "accounting": "N_total = N_free + N_probe + N_experiment (never merged)",
    "violations": {
        "bad_schema": "one neutral retry then AgentProtocolFailure",
        "unknown_hypothesis_id": "representation error -> schema reject (prevented by design)",
        "disallowed_action": "refused pre-execution, attempt consumed",
        "bad_blind_reply": "one neutral retry then AgentProtocolFailure, no truth revealed",
    },
}

TAU_BLIND_B1 = PROTOCOL_SPEC_B1["tau_blind"]
ACTION_RE_B1 = re.compile(r"^(PROBE|EXPERIMENT)\(([A-Za-z]{2})\)$")


def validate_b1(deposit, catalog_ids):
    """نفس صرامة Pilot-A + هوية الفرضية دلالية (معرّف من الكتالوج حصرًا)."""
    if not isinstance(deposit, dict) or "type" not in deposit:
        raise SchemaError("missing type")
    t = deposit["type"]
    if t not in COMMIT_SCHEMA_B1["types"]:
        raise SchemaError(f"unknown type {t}")
    for f in COMMIT_SCHEMA_B1["types"][t]["required"]:
        if f not in deposit:
            raise SchemaError(f"{t} missing field {f}")
    if t == "COMMITMENT":
        probs = deposit["hypotheses"]
        if not isinstance(probs, dict) or not probs:
            raise SchemaError("hypotheses must be a non-empty object")
        for hid in probs:
            if hid not in catalog_ids:
                raise SchemaError(f"unknown hypothesis id {hid}")
        try:
            total = sum(probs.values())
        except TypeError:
            raise SchemaError("hypothesis probabilities must be numbers")
        if abs(total - 1.0) > 1e-6:
            raise SchemaError("hypothesis probabilities must sum to 1.0")
        if deposit["update_kind"] not in COMMIT_SCHEMA_B1["update_kinds"]:
            raise SchemaError("bad update_kind")
        preds = deposit["predictions"]
        if not isinstance(preds, dict):
            raise SchemaError("predictions must be an object")
        for k, p in preds.items():
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not (0.0 <= p <= 1.0):
                raise SchemaError(f"prediction prob out of range for {k}")
    if t == "SUFFICIENCY" and deposit["final_hypothesis"] not in catalog_ids:
        raise SchemaError("final_hypothesis must be a catalog id")
    if t == "INCOMPLETE":
        rem = deposit["remaining_hypotheses"]
        if not isinstance(rem, list) or any(h not in catalog_ids for h in rem):
            raise SchemaError("remaining_hypotheses must be catalog ids")
    return True


class VerifierB1:
    """حتمي؛ يرى الإيداع المهيكل والفعل والنتيجة فقط. الحقيقة تبقى verifier-side."""

    def __init__(self, world):
        self._w = world

    def parse(self, action):
        m = ACTION_RE_B1.match(action) if isinstance(action, str) else None
        if not m:
            raise ValueError("disallowed: malformed action string")
        kind, sym = m.group(1), m.group(2)
        if sym not in self._w.train_symbols:
            raise PermissionError("disallowed: symbol outside training region")
        return kind, sym

    def execute(self, action):
        kind, sym = self.parse(action)
        return (kind, self._w.probe(sym) if kind == "PROBE" else self._w.experiment(sym))

    def blind_score(self, predictions):
        truth = self._w.blind_truth()
        ids = list(self._w.blind_ID)
        if not ids:
            return {"score_ID": None, "conf_ID": None, "truth": truth}
        return {"score_ID": sum(1 for s in ids if truth[s] == predictions[s]["pred"]) / len(ids),
                "conf_ID": sum(predictions[s]["conf"] for s in ids) / len(ids),
                "truth": truth}


class SessionB1:
    def __init__(self, world, agent, log_path, side_path):
        self.world, self.agent = world, agent
        self.catalog_ids = set(world.catalog)
        meta = {"schema_version": SCHEMA_VERSION_B1,
                "protocol_version": PROTOCOL_VERSION_B1,
                "protocol_hash": protocol_hash(PROTOCOL_SPEC_B1),
                "blind_schema_hash": blind_schema_hash(),
                "grammar_version": GRAMMAR_VERSION_B1, "grammar_hash": grammar_hash_b1(),
                "declared": world.phase_zero_packet()["declared_primitives"],
                "hidden_note": "true law, true symbol->vector assignment, blind truth sealed oracle-side"}
        self.arch = Archivist(log_path, meta)
        self.verifier = VerifierB1(world)
        self.side = open(side_path, "a", encoding="utf-8")
        self.budget = PROTOCOL_SPEC_B1["intervention_budget"]
        self.N_free = self.N_probe = self.N_experiment = self.N_refused = 0
        self.ev = Evidence(world.n_syms, world.n_syms)     # حالة الأدلة المرجعية (oracle-side)
        self.sym_index = {s: k for k, s in enumerate(world.train_symbols)}
        self.metrics = []
        self.outcome = None
        self._closed = False

    # ---------------- أدوات داخلية ----------------

    def _think(self, text):
        self.side.write(text + "\n")
        self.side.flush()

    def _deposit(self, allowed=None):
        for attempt in range(1 + PROTOCOL_SPEC_B1["schema_retry_limit"]):
            dep, thoughts = self.agent.deposit()
            if thoughts:
                self._think(thoughts)
            try:
                validate_b1(dep, self.catalog_ids)
            except SchemaError as e:
                self.arch.seal("SCHEMA_REJECT", {"error": str(e), "attempt": attempt})
                self.agent.notify("SCHEMA_INVALID")
                continue
            if allowed is not None and dep["type"] not in allowed:
                self.arch.seal("PHASE_REJECT", {"type": dep["type"], "attempt": attempt})
                self.agent.notify("TYPE_NOT_ALLOWED_IN_PHASE")
                continue
            return dep
        return None

    def _belief_metrics(self, dep):
        """مقاييس منفصلة لا تُدمج (المادة 6 من الـ spec)."""
        w = self.world
        P_star, _, _, support = posterior(w.hypotheses, self.ev, w.emask, w.ctx)
        sup_ids = {w.hyp_ids[k] for k in support}
        declared = {h: float(p) for h, p in dep["hypotheses"].items()}
        dec_ids = set(declared)
        inter = sup_ids & dec_ids
        union = sup_ids | dec_ids
        tv = 0.5 * sum(abs(declared.get(w.hyp_ids[k], 0.0) - P_star[k])
                       for k in range(len(w.hyp_ids)))
        return {
            "support_size_oracle": len(sup_ids), "support_size_declared": len(dec_ids),
            "missing": sorted(sup_ids - dec_ids), "extra": sorted(dec_ids - sup_ids),
            "support_jaccard": round(len(inter) / len(union), 4) if union else None,
            "support_exact": sup_ids == dec_ids,
            "probability_error_tv": round(tv, 6),
            "mass_on_truth": round(declared.get(w.true_law_id(), 0.0), 6),
        }

    def _probe_quality(self, action):
        """IG على الحالة المشتركة، ونسبته إلى أفضل فعل **من نفس النوع** (diagnostic فقط)."""
        w = self.world
        kind, sym = self.verifier.parse(action)
        x = self.sym_index[sym]
        a = (kind, x, None)
        # IG_law ≡ IG_H = I(H;Y|E)؛ IG_state = IG_Σ = I(Σ;Y|E) — تشخيص غير جمعي.
        ig, ig_law, ig_state = information_gain_full(w.hypotheses, self.ev, w.emask, w.ctx, a)
        same = [b for b in all_actions(w.n_syms) if b[0] == kind]
        best = 0.0
        for b in same:
            g, _ = information_gain(w.hypotheses, self.ev, w.emask, w.ctx, b)
            best = max(best, g)
        return {"IG_joint": round(ig, 4), "IG_law": round(ig_law, 4),
                "IG_state": round(ig_state, 4),
                "IG_max_same_type": round(best, 4),
                "probe_quality": round(ig / best, 4) if best > 1e-12 else None}

    # ---------------- الحلقة ----------------

    def run(self):
        packet = self.world.phase_zero_packet()
        if hasattr(self.agent, "execution_identity"):
            self.arch.seal("EXEC_IDENTITY", {"identity": self.agent.execution_identity()})
        self.arch.seal("PHASE_ZERO", {"packet": packet})
        self.agent.receive_phase_zero(packet)

        dep = None
        for _ in range(PROTOCOL_SPEC_B1["free_observations"]):
            if self.budget <= 0:
                break
            dep = self._deposit()
            if dep is None:
                return self._fail()
            if dep["type"] != "FREE_OBS":
                break
            if not self._act(dep, free=True):
                dep = None
                continue
            self.N_free += 1
            dep = None

        while self.budget > 0:
            dep = dep or self._deposit(("COMMITMENT", "SUFFICIENCY", "INCOMPLETE", "INADEQUACY"))
            if dep is None:
                return self._fail()
            t = dep["type"]
            if t == "SUFFICIENCY":
                self.arch.seal("SUFFICIENCY", {"deposit": dep})
                return self._blind()
            if t == "INCOMPLETE":
                self.arch.seal("INCOMPLETE", {"deposit": dep})
                return self._blind(declaration="INCOMPLETE")
            if t == "INADEQUACY":
                self.arch.seal("INADEQUACY", {"deposit": dep})
                self.budget -= 1
                self.agent.notify("INADEQUACY_RECORDED")
                dep = None
                continue
            self._act(dep, free=False)
            dep = None
        return self._finish("BUDGET_EXHAUSTED", E=0.0)

    def _act(self, dep, free):
        """يختم الالتزام ثم ينفذ. يرجع True إذا نُفّذ الفعل فعلًا."""
        metrics = None
        if not free:
            metrics = {"belief": self._belief_metrics(dep)}
            try:
                metrics["information"] = self._probe_quality(dep["action"])
            except (ValueError, PermissionError):
                metrics["information"] = None
        receipt = self.arch.seal("FREE_OBS_COMMIT" if free else "COMMITMENT",
                                 {"deposit": dep, **({"metrics": metrics} if metrics else {})})
        if metrics:
            self.metrics.append({"action": dep["action"], **metrics})
        try:
            kind, out = self.verifier.execute(dep["action"])
        except (ValueError, PermissionError) as e:
            self.arch.seal("REFUSED_ACTION", {"receipt": receipt, "error": str(e)})
            self.budget -= 1
            self.N_refused += 1
            self.agent.notify("ACTION_REFUSED")
            return False
        _, sym = self.verifier.parse(dep["action"])
        x = self.sym_index[sym]
        if kind == "PROBE":
            self.ev = apply_action(self.ev, ("PROBE", x, None),
                                   self.world.declared_vectors.index(tuple(out)))
            if not free:
                self.N_probe += 1
        else:
            self.ev = apply_action(self.ev, ("EXPERIMENT", x, None), out)
            if not free:
                self.N_experiment += 1
        self.budget -= 1
        self.arch.seal("PROBE_RESULT" if kind == "PROBE" else "OBSERVATION",
                       {"receipt": receipt, "symbol": sym, "result": out})
        self.agent.observe(dep["action"], out)
        return True

    def _blind(self, declaration="SUFFICIENCY"):
        cases = {s: list(v) for s, v in self.world.blind_symbols.items()}
        self.arch.seal("BLIND_CASES_ISSUED", {"cases": cases})
        preds = None
        for attempt in range(1 + PROTOCOL_SPEC_B1["schema_retry_limit"]):
            p, thoughts = self.agent.blind_predict(cases)
            if thoughts:
                self._think(thoughts)
            err = validate_blind(p, cases)
            if err is None:
                preds = p
                break
            self.arch.seal("BLIND_REJECT", {"error": err, "attempt": attempt})
            self.agent.notify("BLIND_INVALID")
        if preds is None:
            return self._fail(stage="blind")
        self.arch.seal("BLIND_PREDICTIONS", {"predictions": preds})
        sc = self.verifier.blind_score(preds)
        self.arch.seal("BLIND_TRUTH", {"truth": sc["truth"], "score_ID": sc["score_ID"]})
        success = 1 if (sc["score_ID"] is not None and sc["score_ID"] >= TAU_BLIND_B1) else 0
        # N_total يُبلَّغ صادقًا (قد يكون 0 لوكيل لم يتدخل)؛ الحارس ضد القسمة داخل E فقط
        N_total = self.N_free + self.N_probe + self.N_experiment
        D_rob = self.world.D_robust
        E = (max(D_rob, 1) / max(N_total, 1)) if (success and D_rob) else 0.0
        region = classify_region(N_total, self.world.D_floor_task, D_rob)
        if success and region == "TRUE_AUDIT":
            self.arch.seal("TRUE_AUDIT", {"N_total": N_total,
                                          "D_floor_task": self.world.D_floor_task,
                                          "note": "below the task floor: leakage/accounting/oracle bug"})
        return self._finish("SOLVED" if success else "FALSE_CERTAINTY", E=E,
                            blind_ID=sc["score_ID"], conf_ID=sc["conf_ID"], success=success,
                            N_total=N_total, region=region,
                            true_audit=1 if (success and region == "TRUE_AUDIT") else 0,
                            declaration=declaration)

    def _fail(self, stage="deposit"):
        return self._finish("AGENT_PROTOCOL_FAILURE", E=0.0, included_in_analysis=True,
                            failure_stage=stage)

    def _finish(self, outcome, **kw):
        w = self.world
        res = {"outcome": outcome,
               "N_free": self.N_free, "N_probe": self.N_probe,
               "N_experiment": self.N_experiment, "N_refused": self.N_refused,
               "D_floor_task": w.D_floor_task, "D_floor_strict": w.D_floor_strict,
               "D_robust": w.D_robust,
               "n_blind_ID": len(w.blind_ID), "n_blind_X": len(w.blind_X),
               "belief_metrics": self.metrics, **kw}
        if hasattr(self.agent, "execution_identity"):
            self.arch.seal("EXEC_IDENTITY_END", {"identity": self.agent.execution_identity()})
        self.arch.seal("SESSION_END", {"result": res})
        if not self._closed:
            self.side.close()
            self._closed = True
        self.outcome = res
        return res
