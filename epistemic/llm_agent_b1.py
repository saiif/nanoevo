"""llm_agent_b1.py — Pilot-B1 adapter: موديل لغة حقيقي داخل عقد B1.

نفس مبدأ Pilot-A حرفيًا: **الـ adapter مترجم لا معلّم**.
يعطي العقد والـ packet والكتالوج، ويستخرج إيداعًا دلاليًا واحدًا. وممنوع عليه:
- canonicalization ذكي أو تصحيح معرّفات Hxx،
- إعادة توزيع الاحتمالات أو تطبيعها،
- تحويل قرار PROBE إلى EXPERIMENT أو العكس،
- إصلاح أي إيداع مشوه.
إن أخطأ النموذج، فالعقد الموجود (schema + جدول الانتهاكات) هو الذي يحكم.
"""

import hashlib
import json
import re
import time

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
  INCOMPLETE:  {"type":"INCOMPLETE","remaining_hypotheses":["H03","H11"],"reason":"..."}
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
    """إيداع واحد بالضبط يحمل المفتاح. صفر أو أكثر من واحد => malformed.
    الـ parser لا يستنتج المقصود — وإلا صار جهة تفسير خفية داخل قناة الالتزام."""
    cands, spans = [], []
    for m in JSON_RE.finditer(text):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
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

    def __init__(self, seed=0, client=None, model=MODEL_B1, endpoint=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.endpoint = endpoint
        self.history = []
        self.request_ids = []
        self.stop_reasons = []
        self.truncated = 0
        self.free_total = 2
        self.budget = 15
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

    # ---------- واجهة العقد (مطابقة للبوتات حرفيًا) ----------

    def receive_phase_zero(self, packet):
        prompt = (CONTRACT_PROMPT_B1.replace("__FREE__", str(self.free_total))
                  .replace("__BUDGET__", str(self.budget)))
        self.history = [{"role": "user", "content":
                         prompt + "\n\nPHASE ZERO PACKET:\n"
                         + json.dumps(packet, ensure_ascii=False, indent=1)}]

    def _call(self, extra_user=None, max_tokens=1400):
        msgs = list(self.history)
        if extra_user:
            msgs.append({"role": "user", "content": extra_user})
        resp = self.client.messages.create(model=self.model, max_tokens=max_tokens, messages=msgs)
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
                          self.GEN_PARAMS["max_tokens_main"])
        dep, thoughts = _extract(text, "type")
        if dep is None:
            dep = {"type": "MALFORMED"}       # يفشل في الـ validator — العقد يتصرف
        return dep, thoughts or None

    def observe(self, action, out):
        # الـ adapter ينقل النتيجة كما هي: متجه كامل للـ PROBE، بت للـ EXPERIMENT
        self.history.append({"role": "user",
                             "content": f"SEALED RESULT: {action} -> {json.dumps(out)}"})

    def notify(self, msg):
        self.history.append({"role": "user", "content": f"PROTOCOL NOTICE: {msg}"})

    def blind_predict(self, cases):
        text = self._call(BLIND_PROMPT_B1 % json.dumps(cases),
                          self.GEN_PARAMS["max_tokens_blind"])
        dep, thoughts = _extract(text, "predictions")
        return (dep.get("predictions") if dep else None), thoughts or None
