"""shim_client.py — transport محايد: يجعل نقطة OpenAI-compatible تبدو كعميل Anthropic.

هذا ليس جزءًا من الـ adapter المجمّد (llm_agent.py غير مُمَسّ، adapter_hash ثابت). إنه
قناة نقل فقط: تترجم استدعاء LLMAgent._call (بنية Anthropic: messages=[{role,content}])
إلى POST /v1/chat/completions، وتعيد كائنًا بنفس الحقول التي يقرأها الـ adapter
(.content[].text، .id، .stop_reason). لا تفسير، لا إصلاح إيداعات — العقد يبقى الحكم.

بلا اعتمادية خارجية: urllib فقط.
"""

import json
import types
import urllib.request
import urllib.error


class ShimError(RuntimeError):
    """فشل نقل عند الـ shim (HTTP/شبكة) — يميَّز عن أخطاء العقد أو الماسورة."""


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
        # الـ shim يقبل فقط نماذج معروفة ويسقط الباقي إلى الافتراضي بصمت؛ لذلك نرسل
        # النموذج الحقيقي صراحةً (self._model) لا سلسلة الـ adapter المجمّدة، ونسجّله في الهوية.
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
    """عميل يحاكي واجهة anthropic.Anthropic().messages.create بما يكفي للـ adapter.

    base_url: مثل http://127.0.0.1:8787/v1
    model:    نموذج معروف للـ shim (claude-sonnet-5 | claude-opus-5 | claude-haiku-4-5)
    """

    def __init__(self, base_url="http://127.0.0.1:8787/v1",
                 model="claude-sonnet-5", api_key="", timeout=240):
        self.base_url = base_url
        self.model = model
        self.messages = _Messages(base_url, model, api_key, timeout)
