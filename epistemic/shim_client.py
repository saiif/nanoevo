"""shim_client.py — a neutral transport: makes an OpenAI-compatible endpoint look like an Anthropic client.

This is not part of the frozen adapter (llm_agent.py is untouched, adapter_hash is fixed). It is
just a transport channel: it translates the LLMAgent._call invocation (Anthropic shape: messages=[{role,content}])
into a POST /v1/chat/completions, and returns an object with the same fields the adapter reads
(.content[].text, .id, .stop_reason). No interpretation, no fixing of submissions — the contract remains the judge.

No external dependency: urllib only.
"""

import json
import types
import urllib.request
import urllib.error


class ShimError(RuntimeError):
    """A transport failure at the shim (HTTP/network) — distinguished from contract or pipeline errors."""


_FINISH_MAP = {"stop": "end_turn", "length": "max_tokens", "content_filter": "refusal"}


class _Response:
    def __init__(self, text, rid, finish_reason):
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.id = rid
        self.stop_reason = _FINISH_MAP.get(finish_reason, finish_reason or "end_turn")


class _Messages:
    def __init__(self, base_url, model, api_key, timeout):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._key = api_key
        self._timeout = timeout

    @staticmethod
    def _flatten(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
        return str(content)

    def create(self, model, max_tokens, messages):
        # The shim only accepts known models and silently drops the rest to the default; so we send
        # the real model explicitly (self._model), not the frozen adapter string, and record it in the identity.
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "stream": False,
            "messages": [{"role": m["role"], "content": self._flatten(m["content"])}
                         for m in messages],
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        req = urllib.request.Request(self._url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise ShimError(f"HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise ShimError(f"transport: {e.reason}") from e
        try:
            choice = body["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ShimError(f"unexpected response shape: {json.dumps(body)[:300]}") from e
        return _Response(text, body.get("id"), choice.get("finish_reason"))


class ShimClient:
    """A client that mimics the anthropic.Anthropic().messages.create interface well enough for the adapter.

    base_url: e.g. http://127.0.0.1:8787/v1
    model:    a model known to the shim (claude-sonnet-5 | claude-opus-5 | claude-haiku-4-5)
    """

    def __init__(self, base_url="http://127.0.0.1:8787/v1",
                 model="claude-sonnet-5", api_key="", timeout=240):
        self.base_url = base_url
        self.model = model
        self.messages = _Messages(base_url, model, api_key, timeout)
