"""channel.py — قناة الالتزام المحققة آليًا + الـ Archivist.

القاعدة (المادة 33): كل ما لم يقبله الـ Schema Validator ويختمه الـ Archivist
لا وجود معرفي رسمي له. الختم = hash chain — تعديل الماضي مستحيل تقنيًا لا ممنوع إجرائيًا.

A-003: الاختبار الأعمى له schema مستقل (BLIND_SCHEMA) بنفس صرامة الإيداعات —
لا coercion ولا قيم افتراضية: الرد المشوه يُرفض ويُعاد مرة واحدة ثم AgentProtocolFailure.
"""

import hashlib
import json
import math
import os
import time

SCHEMA_VERSION = "1.1"

COMMIT_SCHEMA = {
    "version": SCHEMA_VERSION,
    # A-009: الصرامة جزء من معنى الـ schema، فيجب أن تنعكس في الـ hash.
    # (شُدِّد الـ validator أولًا بينما بقي الـ hash ثابتًا — وذلك يخالف التجميد الثلاثي
    #  الذي يقول إن تغيّر المعنى يوجب إصدارًا جديدًا حتى لو ظل شكل الـ JSON نفسه.)
    "strictness": {
        "probabilities": "each value must be a finite real in [0,1]; bool rejected; "
                         "NaN/Infinity rejected value-by-value, not merely via the sum",
        "json": "duplicate keys rejected at every level; NaN/Infinity literals rejected",
        "fields": "exact: no field outside type+required is accepted",
    },
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
    # allow_nan=False: NaN/Infinity ليست JSON قياسيًا ولا يجوز أن تدخل سجلًا مختومًا
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def schema_hash():
    return hashlib.sha256(_canon(COMMIT_SCHEMA).encode()).hexdigest()[:16]


def blind_schema_hash():
    return hashlib.sha256(_canon(BLIND_SCHEMA).encode()).hexdigest()[:16]


def protocol_hash(protocol_spec):
    return hashlib.sha256(_canon(protocol_spec).encode()).hexdigest()[:16]


class SchemaError(Exception):
    pass


class DuplicateKeyError(SchemaError):
    """مفتاح JSON مكرر — الانهيار الصامت إلى آخر قيمة غير مقبول في قناة الالتزام."""


def _no_duplicates(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise DuplicateKeyError(f"duplicate JSON key: {k}")
        seen.add(k)
    return dict(pairs)


def strict_loads(text):
    """json.loads صارم: يرفض المفاتيح المكررة و NaN/Infinity.

    السبب: json.loads القياسي يُبقي **آخر** قيمة عند التكرار، فـ
        {"H07": 0.2, "H07": 1.0}  ->  {"H07": 1.0}
    يصير إيداعًا صالحًا تمامًا رغم أن النص المُودَع لم يكن توزيعًا واحدًا. حفظ الخام
    يوثّق الواقعة لكنه لا يمنعها من قيادة الجلسة — فالمنع يجب أن يكون في الـ parser.
    """
    return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)


def _reject_constant(name):
    raise SchemaError(f"non-finite JSON constant not allowed: {name}")


def _finite_prob(x, where):
    """قيمة احتمال مقبولة: عدد حقيقي منتهٍ في [0,1]، وليست bool."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise SchemaError(f"{where}: probability must be a number")
    if not math.isfinite(x):
        raise SchemaError(f"{where}: probability must be finite (got {x})")
    if not (0.0 <= x <= 1.0):
        raise SchemaError(f"{where}: probability out of range [0,1] (got {x})")
    return float(x)


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
    # exact schema: لا حقول خارج المعلَن (العقد يدّعي بنية محددة، فليكن كذلك)
    allowed = set(COMMIT_SCHEMA["types"][t]["required"]) | {"type"}
    extra = set(deposit) - allowed
    if extra:
        raise SchemaError(f"unknown field(s) for {t}: {sorted(extra)}")
    if t == "COMMITMENT":
        probs = deposit["hypotheses"]
        if not isinstance(probs, dict) or not probs:
            raise SchemaError("hypotheses must be a non-empty object")
        # كل قيمة تُفحص منفردة: NaN/Inf/bool لا تُكتشف من المجموع وحده
        # (abs(nan - 1.0) > 1e-6 تساوي False فيمر التوزيع الفاسد)
        total = 0.0
        for h, p in probs.items():
            total += _finite_prob(p, f"hypothesis {h}")
        if abs(total - 1.0) > 1e-6:
            raise SchemaError("hypothesis probabilities must sum to 1.0")
        if deposit["update_kind"] not in COMMIT_SCHEMA["update_kinds"]:
            raise SchemaError("bad update_kind")
        preds = deposit["predictions"]
        if not isinstance(preds, dict):
            raise SchemaError("predictions must be an object")
        for h, p in preds.items():
            _finite_prob(p, f"prediction {h}")
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
        extra = set(p) - {"pred", "conf"}
        if extra:
            return f"{s}: unknown field(s) {sorted(extra)}"
        pred, conf = p.get("pred"), p.get("conf")
        if isinstance(pred, bool) or pred not in (0, 1):
            return f"{s}: pred must be integer 0 or 1"
        try:
            _finite_prob(conf, f"{s} conf")
        except SchemaError as e:
            return str(e)
    return None


try:                                    # قفل ملفات محمول
    import fcntl

    def _lock(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def _unlock(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
except ImportError:                     # Windows
    import msvcrt

    def _lock(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        except OSError:
            pass

    def _unlock(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


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
