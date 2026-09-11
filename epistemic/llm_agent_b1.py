"""llm_agent_b1.py — Pilot-B1 adapter: a real language model inside the B1 contract.

Same principle as Pilot-A, literally: **the adapter is a translator, not a teacher**.
It hands the model the contract, the packet, and the catalog, and extracts a single
semantic deposit. It is forbidden from:
- smart canonicalization or correcting Hxx identifiers,
- redistributing or normalizing the probabilities,
- converting a PROBE decision into EXPERIMENT or vice versa,
- fixing any malformed deposit.
If the model makes a mistake, the existing contract (schema + violation table) is what rules.
"""

import hashlib
import json
import re
import time

from channel import strict_loads, SchemaError

MODEL_B1 = "claude-sonnet-5"

CONTRACT_PROMPT_B1 = """You are an epistemic agent inside a hidden-law world, bound by a strict commitment contract.

WORLD:
- There are symbols. Each symbol has a property vector (p0,p1,p2) of bits. YOU CANNOT SEE THESE VECTORS.
- The set of property vectors present in this world IS declared to you. Each listed vector is used by exactly ONE symbol (the assignment is a bijection); which symbol has which vector is unknown to you.
- One hidden law from the declared catalog maps a property vector to a binary outcome.

TWO DISTINCT ACTIONS (this distinction is the point):
  PROBE(Xy)        -> reveals the FULL property vector (p0,p1,p2) of symbol Xy. Costs one intervention.
                      A probe tells you WHAT STATE a symbol is in. It tells you NOTHING about the law.
  EXPERIMENT(Xy)   -> reveals the law's binary outcome on symbol Xy. Costs one intervention.
                      An experiment is informative about the law, but its meaning depends on
                      whether you know that symbol's vector.

CONTRACT (non-negotiable):
- Every turn: optional free reasoning, then EXACTLY ONE JSON object (last thing in your message).
  Zero or several JSON objects = malformed deposit.
- Hypotheses are identified by CATALOG IDs (e.g. "H07"), never by their formula text.
  Probabilities are placed on IDs and must sum to 1.0. An ID outside the catalog is rejected.
- Deposit types:
  FREE_OBS:    {"type":"FREE_OBS","action":"PROBE(Xy)"}     (free-observation phase only)
  COMMITMENT:  {"type":"COMMITMENT","hypotheses":{"H03":0.5,"H11":0.5},"action":"EXPERIMENT(Xy)","predictions":{"outcome=1":0.5},"update_kind":"REWEIGHT"}
  SUFFICIENCY: {"type":"SUFFICIENCY","final_hypothesis":"H07","confidence":0.95}
  INCOMPLETE:  {"type":"INCOMPLETE","remaining_hypotheses":["H03","H11"],"reason":"...","claim":"insufficient_evidence_now"}
               claim MUST be exactly one of:
                 "insufficient_evidence_now"    - the evidence so far does not determine the law
                 "no_decisive_action_remains"   - no remaining action within budget could resolve it
               Both claims are CHECKED against the world. Claiming that no decisive action remains
               while one does is a distinct, recorded error: your belief about the world may be
               right while your belief about your own remaining options is wrong.
  INADEQUACY:  {"type":"INADEQUACY","reason":"...","requested_family":"..."}   (consumes one attempt)
- update_kind: INITIAL | REWEIGHT | REVISE | EXPAND.
- Before every formal action you MUST commit your current hypothesis distribution and your
  predicted outcome probability. Commitments are sealed BEFORE execution and are never revised
  retroactively. Honest probabilities matter more than confident ones.
- A malformed deposit or a wrong-phase type gets ONE neutral retry, then protocol failure.
  A malformed or out-of-region action is refused and consumes one attempt.

You have __FREE__ free observations, then formal commitments. Total budget is __BUDGET__ interventions."""

BLIND_PROMPT_B1 = """BLIND PREDICTION TEST. Below are NEW symbols, and for these their property vectors ARE given. For each, predict the hidden law's binary outcome with your honest confidence. If the hypotheses you still consider possible disagree on a case, your confidence must reflect that — do not fake certainty.
Reply with optional free reasoning, then EXACTLY ONE JSON object covering EVERY listed symbol, "pred" being the integer 0 or 1 and "conf" a number in [0,1]:
{"predictions": {"SYMBOL": {"pred": 0, "conf": 0.8}, ...}}
An invalid reply gets one neutral retry, then protocol failure.
Cases: %s"""

JSON_RE = re.compile(r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}", re.S)


def _extract(text, key):
    """Exactly one deposit carries the key. Zero or more than one => malformed.
    The parser does not infer intent — otherwise it would become a hidden interpretation
    authority inside the commitment channel."""
    cands, spans = [], []
    for m in JSON_RE.finditer(text):
        try:
            obj = strict_loads(m.group(0))     # rejects duplicate keys and NaN
        except (json.JSONDecodeError, SchemaError):
            continue
        if isinstance(obj, dict) and key in obj:
            cands.append(obj)
            spans.append(m.group(0))
    if len(cands) != 1:
        return None, text.strip()
    return cands[0], text.replace(spans[0], "").strip()


def _adapter_hash():
    return hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:16]


class LLMAgentB1:
    GEN_PARAMS = {"temperature": "provider_default", "top_p": "provider_default",
                  "max_tokens_main": 1400, "max_tokens_blind": 1500}

    def __init__(self, seed=0, client=None, model=MODEL_B1, endpoint=None, budget=15):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.endpoint = endpoint
        self.history = []
        self.last_raw = None            # the model's text exactly as it came out (before any parse) — sealed as RawProposal
        self.request_ids = []
        self.stop_reasons = []
        self.truncated = 0
        self.free_total = 2
        self.budget = budget
        self.started_ts = time.time()

    def execution_identity(self):
        return {"model": self.model,
                "provider": "operator claude-cli via openai-compatible shim" if self.endpoint
                            else "anthropic",
                "shim_endpoint": self.endpoint,
                "gen_params": self.GEN_PARAMS,
                "system_prompt_hash": hashlib.sha256(CONTRACT_PROMPT_B1.encode()).hexdigest()[:16],
                "blind_prompt_hash": hashlib.sha256(BLIND_PROMPT_B1.encode()).hexdigest()[:16],
                "adapter_hash": _adapter_hash(),
                "started_ts": self.started_ts,
                "n_requests": len(self.request_ids),
                "request_ids": list(self.request_ids),
                "truncated_responses": self.truncated,
                "stop_reasons": list(self.stop_reasons)}

    # ---------- Contract interface (identical to the bots, literally) ----------

    def receive_phase_zero(self, packet):
        prompt = (CONTRACT_PROMPT_B1.replace("__FREE__", str(self.free_total))
                  .replace("__BUDGET__", str(self.budget)))
        self.history = [{"role": "user", "content":
                         prompt + "\n\nPHASE ZERO PACKET:\n"
                         + json.dumps(packet, ensure_ascii=False, indent=1)}]

    def _call(self, extra_user=None, max_tokens=1400):
        self.last_raw = None          # don't let the previous request's raw output linger if this one fails
        msgs = list(self.history)
        if extra_user:
            msgs.append({"role": "user", "content": extra_user})
        resp = self.client.messages.create(model=self.model, max_tokens=max_tokens, messages=msgs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        self.last_raw = text            # the raw layer: before _extract/json.loads (preserves duplicate keys)
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
                          self.GEN_PARAMS["max_tokens_main"])
        dep, thoughts = _extract(text, "type")
        if dep is None:
            dep = {"type": "MALFORMED"}       # fails in the validator — the contract takes over
        return dep, thoughts or None

    def observe(self, action, out):
        # the adapter passes the result through as-is: full vector for PROBE, bit for EXPERIMENT
        self.history.append({"role": "user",
                             "content": f"SEALED RESULT: {action} -> {json.dumps(out)}"})

    def notify(self, msg):
        self.history.append({"role": "user", "content": f"PROTOCOL NOTICE: {msg}"})

    def blind_predict(self, cases):
        text = self._call(BLIND_PROMPT_B1 % json.dumps(cases),
                          self.GEN_PARAMS["max_tokens_blind"])
        dep, thoughts = _extract(text, "predictions")
        return (dep.get("predictions") if dep else None), thoughts or None
