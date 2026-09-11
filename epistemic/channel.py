"""channel.py — the automatically verified commitment channel + the Archivist.

The rule (Article 33): anything the Schema Validator does not accept and the Archivist
does not seal has no formal epistemic existence. Sealing = hash chain — altering the past
is technically impossible, not merely procedurally forbidden.

A-003: the blind test has its own independent schema (BLIND_SCHEMA), with the same
strictness as deposits — no coercion and no default values: a malformed reply is rejected
and retried once, then raises AgentProtocolFailure.
"""

import hashlib
import json
import math
import os
import time

SCHEMA_VERSION = "1.1"

COMMIT_SCHEMA = {
    "version": SCHEMA_VERSION,
    # A-009: strictness is part of what the schema MEANS, so it must be reflected in the hash.
    # (The validator was tightened first while the hash stayed fixed — that violates the triple
    #  freeze, which holds that a change of meaning requires a new version even if the JSON shape
    #  is unchanged.)
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

# A-003: the shape of the blind-test reply — frozen and sealed in GENESIS just like COMMIT_SCHEMA.
BLIND_SCHEMA = {
    "version": SCHEMA_VERSION,
    "entry": {"pred": "integer 0 or 1 (bool rejected)", "conf": "number in [0,1]"},
    "coverage": "prediction keys must equal exactly the issued case symbols",
    "policy": "no coercion, no defaults — invalid reply => one neutral retry, then AgentProtocolFailure",
}


def _canon(obj):
    # allow_nan=False: NaN/Infinity are not standard JSON and must never enter a sealed record
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
    """Duplicate JSON key — silently collapsing to the last value is not acceptable in the commitment channel."""


def _no_duplicates(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise DuplicateKeyError(f"duplicate JSON key: {k}")
        seen.add(k)
    return dict(pairs)


def strict_loads(text):
    """Strict json.loads: rejects duplicate keys and NaN/Infinity.

    Reason: standard json.loads keeps the **last** value on duplication, so
        {"H07": 0.2, "H07": 1.0}  ->  {"H07": 1.0}
    becomes a perfectly valid deposit even though the deposited text was never a single
    distribution. Saving the raw text documents the incident but does not stop it from
    driving the session — the rejection has to happen in the parser.
    """
    return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)


def _reject_constant(name):
    raise SchemaError(f"non-finite JSON constant not allowed: {name}")


def _finite_prob(x, where):
    """An acceptable probability value: a finite real number in [0,1], not a bool."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise SchemaError(f"{where}: probability must be a number")
    if not math.isfinite(x):
        raise SchemaError(f"{where}: probability must be finite (got {x})")
    if not (0.0 <= x <= 1.0):
        raise SchemaError(f"{where}: probability out of range [0,1] (got {x})")
    return float(x)


def validate(deposit):
    """Rejects any deposit outside the format. Probabilities must sum to 1.0 (Article 36)."""
    if not isinstance(deposit, dict) or "type" not in deposit:
        raise SchemaError("missing type")
    t = deposit["type"]
    if t not in COMMIT_SCHEMA["types"]:
        raise SchemaError(f"unknown type {t}")
    for field in COMMIT_SCHEMA["types"][t]["required"]:
        if field not in deposit:
            raise SchemaError(f"{t} missing field {field}")
    # exact schema: no fields beyond those declared (the contract claims a specific structure, so let it be exactly that)
    allowed = set(COMMIT_SCHEMA["types"][t]["required"]) | {"type"}
    extra = set(deposit) - allowed
    if extra:
        raise SchemaError(f"unknown field(s) for {t}: {sorted(extra)}")
    if t == "COMMITMENT":
        probs = deposit["hypotheses"]
        if not isinstance(probs, dict) or not probs:
            raise SchemaError("hypotheses must be a non-empty object")
        # each value is checked individually: NaN/Inf/bool cannot be detected from the sum alone
        # (abs(nan - 1.0) > 1e-6 evaluates to False, so the corrupted distribution would pass through)
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
    """A-003: returns None if valid, otherwise the error text. Strict: no coercion (bool is not 0/1)."""
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


try:                                    # portable file locking
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
    """An append-only log with a hash chain. There is no edit or delete function — by construction.

    Integrity note: the chain reveals naive tampering; sophisticated tampering (re-sealing
    the entire tail) is prevented only by anchoring the chain head externally (git commit /
    README) — see ledger.py verify.
    """

    def __init__(self, path, meta=None):
        self.path = path
        self._chain = []
        if os.path.exists(path):                       # resume an existing chain
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
        return h  # the receipt

    def seal(self, kind, payload):
        return self._append({"kind": kind, "ts": time.time(), **payload})

    def head(self):
        return self._chain[-1]["hash"] if self._chain else None

    @staticmethod
    def verify_file(path):
        """Verify any log file: any tampering breaks the chain (mechanical question 4)."""
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
