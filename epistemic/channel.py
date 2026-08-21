"""channel.py — قناة الالتزام المحققة آليًا + الـ Archivist.

القاعدة (المادة 33): كل ما لم يقبله الـ Schema Validator ويختمه الـ Archivist
لا وجود معرفي رسمي له. الختم = hash chain — تعديل الماضي مستحيل تقنيًا لا ممنوع إجرائيًا.

A-003: الاختبار الأعمى له schema مستقل (BLIND_SCHEMA) بنفس صرامة الإيداعات —
لا coercion ولا قيم افتراضية: الرد المشوه يُرفض ويُعاد مرة واحدة ثم AgentProtocolFailure.
"""

import hashlib
import json
import os
import time

SCHEMA_VERSION = "1.0"

COMMIT_SCHEMA = {
    "version": SCHEMA_VERSION,
    "types": {
        "FREE_OBS":     {"required": ["action"]},
        "COMMITMENT":   {"required": ["hypotheses", "action", "predictions", "update_kind"]},
        "INADEQUACY":   {"required": ["reason", "requested_family"]},
        "SUFFICIENCY":  {"required": ["final_hypothesis", "confidence"]},
        "INCOMPLETE":   {"required": ["remaining_hypotheses", "reason"]},
    },
    "update_kinds": ["INITIAL", "REWEIGHT", "REVISE", "EXPAND"],
}

# A-003: بنية الرد على الاختبار الأعمى — مجمدة ومختومة في GENESIS مثل COMMIT_SCHEMA.
BLIND_SCHEMA = {
    "version": SCHEMA_VERSION,
    "entry": {"pred": "integer 0 or 1 (bool rejected)", "conf": "number in [0,1]"},
    "coverage": "prediction keys must equal exactly the issued case symbols",
    "policy": "no coercion, no defaults — invalid reply => one neutral retry, then AgentProtocolFailure",
}


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def schema_hash():
    return hashlib.sha256(_canon(COMMIT_SCHEMA).encode()).hexdigest()[:16]


def blind_schema_hash():
    return hashlib.sha256(_canon(BLIND_SCHEMA).encode()).hexdigest()[:16]


def protocol_hash(protocol_spec):
    return hashlib.sha256(_canon(protocol_spec).encode()).hexdigest()[:16]


class SchemaError(Exception):
    pass


def validate(deposit):
    """يرفض أي إيداع خارج الصيغة. الاحتمالات يجب أن تجمع إلى 1.0 (المادة 36)."""
    if not isinstance(deposit, dict) or "type" not in deposit:
        raise SchemaError("missing type")
    t = deposit["type"]
    if t not in COMMIT_SCHEMA["types"]:
        raise SchemaError(f"unknown type {t}")
    for field in COMMIT_SCHEMA["types"][t]["required"]:
        if field not in deposit:
            raise SchemaError(f"{t} missing field {field}")
    if t == "COMMITMENT":
        probs = deposit["hypotheses"]
        if not isinstance(probs, dict) or not probs:
            raise SchemaError("hypotheses must be a non-empty object")
        try:
            total = sum(probs.values())
        except TypeError:
            raise SchemaError("hypothesis probabilities must be numbers")
        if abs(total - 1.0) > 1e-6:
            raise SchemaError("hypothesis probabilities must sum to 1.0")
        if deposit["update_kind"] not in COMMIT_SCHEMA["update_kinds"]:
            raise SchemaError("bad update_kind")
        preds = deposit["predictions"]
        if not isinstance(preds, dict):
            raise SchemaError("predictions must be an object")
        for h, p in preds.items():
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not (0.0 <= p <= 1.0):
                raise SchemaError(f"prediction prob out of range for {h}")
    if t == "INCOMPLETE" and not isinstance(deposit["remaining_hypotheses"], list):
        raise SchemaError("remaining_hypotheses must be a list")
    return True


def validate_blind(predictions, cases):
    """A-003: يرجع None إذا صالح، وإلا نص الخطأ. صارم: لا coercion (bool ليس 0/1)."""
    if not isinstance(predictions, dict):
        return "predictions must be an object keyed by case symbol"
    if set(predictions) != set(cases):
        return "prediction symbols must equal exactly the issued cases"
    for s, p in predictions.items():
        if not isinstance(p, dict):
            return f"{s}: entry must be an object"
        pred, conf = p.get("pred"), p.get("conf")
        if isinstance(pred, bool) or pred not in (0, 1):
            return f"{s}: pred must be integer 0 or 1"
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            return f"{s}: conf must be a number in [0,1]"
    return None


class Archivist:
    """سجل append-only بسلسلة hash. لا توجد أي دالة تعديل أو حذف — بالبناء.

    ملاحظة نزاهة: السلسلة تكشف التلاعب الساذج؛ التلاعب المتقن (إعادة ختم الذيل كله)
    يُمنع فقط بتثبيت رأس السلسلة خارجيًا (git commit / README) — انظر ledger.py verify.
    """

    def __init__(self, path, meta=None):
        self.path = path
        self._chain = []
        if os.path.exists(path):                       # استمرار سلسلة موجودة
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._chain.append(json.loads(line))
        else:
            genesis = {"kind": "GENESIS", "meta": meta or {}, "ts": time.time()}
            self._append(genesis)

    def _append(self, payload):
        prev = self._chain[-1]["hash"] if self._chain else "0" * 16
        h = hashlib.sha256((prev + _canon(payload)).encode()).hexdigest()[:16]
        rec = {"index": len(self._chain), "prev": prev, "hash": h, "payload": payload}
        self._chain.append(rec)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canon(rec) + "\n")
        return h  # الوصل (receipt)

    def seal(self, kind, payload):
        return self._append({"kind": kind, "ts": time.time(), **payload})

    def head(self):
        return self._chain[-1]["hash"] if self._chain else None

    @staticmethod
    def verify_file(path):
        """التحقق من أي ملف سجل: أي تلاعب يكسر السلسلة (السؤال الميكانيكي 4)."""
        prev = "0" * 16
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                h = hashlib.sha256((prev + _canon(rec["payload"])).encode()).hexdigest()[:16]
                if h != rec["hash"] or rec["prev"] != prev:
                    return False
                prev = rec["hash"]
        return True

    def verify_chain_file(self, path=None):
        return Archivist.verify_file(path or self.path)

    def records(self, kind=None):
        return [r for r in self._chain if kind is None or r["payload"]["kind"] == kind]
