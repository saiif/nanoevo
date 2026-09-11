"""llm_agent.py — Pilot-A: a real language model as an epistemic agent inside the contract.

Founding rule: LLM → Deposit Interface → Schema Validator → Archivist →
Experimenter → World. The LLM adapts to the contract; the contract does not change for it.

Design:
- The model writes free-form reasoning, then a single JSON block. The adapter extracts
  the last JSON block as the deposit (it passes through the Schema Validator like any
  agent), and everything else goes to the side channel — the separation between
  reasoning and commitment is preserved by construction.
- A malformed deposit is not fixed here: the contract itself (one retry, then
  AgentProtocolFailure) is what handles it. The adapter does not shield the model
  from the constitution.
- A-003: the blind reply is subject to the same rule (no default values); blind-test
  reasoning goes to the side channel; request_ids and the truncation counter
  (max_tokens) are sealed at the end of the session.
"""

import hashlib
import json
import re
import time

from channel import strict_loads, SchemaError

MODEL = "claude-sonnet-4-6"

CONTRACT_PROMPT = """You are an epistemic agent inside a hidden-law world, bound by a strict commitment contract.

WORLD: symbols with visible property vectors. One hidden law from the declared family maps properties to a binary TEST outcome. Your only intervention: TEST(symbol), written exactly as TEST(Xy) with a symbol from the packet.

CONTRACT (non-negotiable):
- Every turn, output free reasoning if you wish, then EXACTLY ONE JSON object (last thing in your message). Zero or several JSON objects = malformed deposit.
- Before any formal test you MUST commit: your current hypotheses with probabilities summing to 1.0, the chosen action, and predicted outcome probabilities. Commitments are sealed BEFORE execution and can never be revised retroactively.
- Deposit types:
  FREE_OBS:    {"type":"FREE_OBS","action":"TEST(Xy)"}   (ONLY during the free-observation phase; sending it later is a phase violation)
  COMMITMENT:  {"type":"COMMITMENT","hypotheses":{"(p0 AND p1)":0.5,"...":0.5},"action":"TEST(Xy)","predictions":{"outcome=1":0.7},"update_kind":"REWEIGHT"}
  INADEQUACY:  {"type":"INADEQUACY","reason":"...","requested_family":"..."}  (declare when NO hypothesis in the declared family can explain the evidence; each declaration consumes one attempt of your budget)
  SUFFICIENCY: {"type":"SUFFICIENCY","final_hypothesis":"(p0 OR p2)","confidence":0.95}  (declare when evidence suffices)
  INCOMPLETE:  {"type":"INCOMPLETE","remaining_hypotheses":["(p0 AND p1)","(p0 AND p2)"],"reason":"..."}  (declare ONLY if no allowed test can distinguish the remaining hypotheses; the verifier checks this claim)
- update_kind: INITIAL | REWEIGHT | REVISE | EXPAND.
- Violations: malformed deposit or wrong-phase type => one neutral retry, then protocol failure. A malformed or out-of-region action is refused and consumes one attempt.
- Honest probabilities matter: your calibration is scored against sealed commitments. Confident-and-wrong is worse than uncertain-and-honest.
- Do not keep testing after the law is determined; do not stop while real ambiguity remains and discriminating tests exist.

You have __FREE__ free observations (no commitment needed), then formal commitments. Budget is limited."""

BLIND_PROMPT = """BLIND PREDICTION TEST. New symbols with property vectors below. For each, predict the TEST outcome with your honest confidence. If surviving hypotheses disagree on a case, your confidence should reflect that (posterior mixture) — do not fake certainty.
Reply with free reasoning if you wish, then EXACTLY ONE JSON object covering EVERY listed symbol, with "pred" the integer 0 or 1 and "conf" a number in [0,1]:
{"predictions": {"SYMBOL": {"pred": 0, "conf": 0.8}, ...}}
An invalid reply gets one neutral retry, then protocol failure.
Cases: %s"""

JSON_RE = re.compile(r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}", re.S)


def _extract_deposit(text, key="type"):
    """Adapter protocol (frozen): exactly one deposit matching the deposit structure
    (carries key). Zero candidates or more than one => malformed. The parser does not
    "infer intent" — otherwise it would become a hidden interpretive authority inside
    the commitment channel."""
    candidates, spans = [], []
    for m in JSON_RE.finditer(text):
        try:
            obj = strict_loads(m.group(0))     # rejects duplicate keys and NaN
        except (json.JSONDecodeError, SchemaError):
            continue
        if isinstance(obj, dict) and key in obj:
            candidates.append(obj)
            spans.append(m.group(0))
    if len(candidates) != 1:
        return None, text.strip()   # malformed — the contract acts, not the adapter
    thoughts = text.replace(spans[0], "").strip()
    return candidates[0], thoughts


def _adapter_hash():
    return hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:16]


class LLMAgent:
    GEN_PARAMS = {"temperature": "provider_default", "top_p": "provider_default",
                  "max_tokens_main": 1200, "max_tokens_interp": 200, "max_tokens_blind": 1500}

    def __init__(self, seed=0, client=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.history = []
        self.request_ids = []
        self.stop_reasons = []
        self.truncated = 0          # responses cut by max_tokens (adapter-side cap, not the model)
        self.free_total = 3
        self.symbols = {}
        self.started_ts = time.time()

    def execution_identity(self):
        """Sealed at the start (EXEC_IDENTITY) and at the end (EXEC_IDENTITY_END):
        the same commercial name a week later may not be the same system; and
        request_ids are only complete at the end."""
        return {"model": MODEL, "provider": "anthropic",
                "gen_params": self.GEN_PARAMS,
                "system_prompt_hash": hashlib.sha256(CONTRACT_PROMPT.encode()).hexdigest()[:16],
                "blind_prompt_hash": hashlib.sha256(BLIND_PROMPT.encode()).hexdigest()[:16],
                "adapter_hash": _adapter_hash(),
                "started_ts": self.started_ts,
                "n_requests": len(self.request_ids),
                "request_ids": list(self.request_ids),
                "truncated_responses": self.truncated,
                "stop_reasons": list(self.stop_reasons)}

    # ---------- Contract interface (identical to the bots, literally) ----------

    def receive_phase_zero(self, packet):
        self.symbols = packet["symbols"]
        self.history = [{"role": "user", "content":
            CONTRACT_PROMPT.replace("__FREE__", str(self.free_total))
            + "\n\nPHASE ZERO PACKET:\n" + json.dumps(packet, ensure_ascii=False)}]

    def _call(self, extra_user=None, max_tokens=1200):
        msgs = list(self.history)
        if extra_user:
            msgs.append({"role": "user", "content": extra_user})
        resp = self.client.messages.create(model=MODEL, max_tokens=max_tokens,
                                           messages=msgs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        rid = getattr(resp, "id", None)
        if rid:
            self.request_ids.append(rid)
        stop = getattr(resp, "stop_reason", None)
        self.stop_reasons.append(stop)
        if stop == "max_tokens":
            self.truncated += 1
        if extra_user:
            self.history.append({"role": "user", "content": extra_user})
        self.history.append({"role": "assistant", "content": text})
        return text

    def deposit(self):
        text = self._call("Your next deposit (reasoning optional, then ONE JSON):",
                          max_tokens=self.GEN_PARAMS["max_tokens_main"])
        dep, thoughts = _extract_deposit(text, key="type")
        if dep is None:
            dep = {"type": "MALFORMED"}    # fails in the validator — the contract acts
        return dep, thoughts or None

    def observe(self, action, obs):
        self.history.append({"role": "user",
                             "content": f"SEALED OBSERVATION: {action} -> {obs}"})

    def interpret(self, obs):
        text = self._call(
            "One-line interpretation of that observation. "
            'Reply ONLY: {"interpretation": "...", "update_kind": "REWEIGHT|REVISE|EXPAND"}',
            max_tokens=self.GEN_PARAMS["max_tokens_interp"])
        dep, thoughts = _extract_deposit(text, key="interpretation")
        # Interpretation is not scored (Article 48): the unparsed case is marked explicitly and its text stays in the side channel
        return (dep or {"interpretation": "UNPARSED", "update_kind": "UNPARSED"},
                thoughts or None)

    def notify(self, msg):
        self.history.append({"role": "user", "content": f"PROTOCOL NOTICE: {msg}"})

    def blind_predict(self, blind_cases):
        """Returns (predictions | None, thoughts). No coercion: the validator in the session decides."""
        text = self._call(BLIND_PROMPT % json.dumps(blind_cases),
                          max_tokens=self.GEN_PARAMS["max_tokens_blind"])
        dep, thoughts = _extract_deposit(text, key="predictions")
        preds = dep.get("predictions") if dep else None
        return preds, thoughts or None
