"""run_pilot_shim.py — Pilot-A عبر نقطة OpenAI-compatible (claude-openai-shim).

نفس Pilot-A تمامًا (نفس العقد، نفس الـ adapter المجمّد llm_agent.py)، لكن النقل
مُبدَّل إلى الـ shim بدل api.anthropic.com. الهوية التنفيذية تُسجَّل بصدق:
النموذج الحقيقي + مزوّد "operator claude-cli via openai-compatible shim" + العنوان.

الاستعمال:  python run_pilot_shim.py [n] [model] [base_url]
  n=1  model=claude-sonnet-5  base_url=http://127.0.0.1:8787/v1  (الافتراضات)
المخرجات: provenance/pilot_a_shim_run/ + تقرير العائلات الخمس.
"""

import os
import sys

import run_pilot_a  # نفس نطاق seeds 2000+ (PILOT_SEED_BASE) والتقرير والـ taxonomy
from llm_agent import LLMAgent, MODEL as ADAPTER_MODEL_STRING
from shim_client import ShimClient, ShimError

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(HERE, "provenance", "pilot_a_shim_run")


class ShimLLMAgent(LLMAgent):
    """نفس الـ adapter، مع هوية تنفيذية صادقة عن النقل الفعلي (لا يمسّ parsing العقد)."""

    def __init__(self, seed, client, model_id, endpoint):
        super().__init__(seed, client=client)
        self._model_id = model_id
        self._endpoint = endpoint

    def execution_identity(self):
        idn = super().execution_identity()
        idn.update({
            "model": self._model_id,
            "provider": "operator claude-cli via openai-compatible shim",
            "transport": "openai_chat_completions",
            "shim_endpoint": self._endpoint,
            "adapter_model_string_sent": ADAPTER_MODEL_STRING,
            "note": ("adapter_hash below is the frozen Anthropic-format adapter (unchanged); "
                     "transport swapped to the shim; the shim maps every request to `model` above "
                     "and runs it through the operator's `claude -p` CLI (tools disabled, pure text)"),
        })
        return idn


def main(n=1, model="claude-sonnet-5", base_url="http://127.0.0.1:8787/v1"):
    # صنّف فشل النقل عند الـ shim كـ provider، لا كـ world/session bug (يبقى run_pilot_a مجمّدًا).
    _orig = run_pilot_a.classify_exception

    def classify(e):
        if isinstance(e, ShimError):
            return "PROVIDER_FAILURE"
        return _orig(e)

    run_pilot_a.classify_exception = classify
    try:
        client = ShimClient(base_url=base_url, model=model)
        make_agent = lambda seed: ShimLLMAgent(seed, client, model, base_url)
        return run_pilot_a.main(n, make_agent=make_agent, run_dir=RUN_DIR)
    finally:
        run_pilot_a.classify_exception = _orig


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    model = sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-5"
    base = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8787/v1"
    main(n, model, base)
