"""adversarial_contract.py — فحوص عدائية على العقد نفسه (A-009).

كل حالة هنا كانت **ثغرة حقيقية** في مراجعة الكود، لا اختبارًا افتراضيًا:

- احتمال NaN كان يعبر لأن `abs(nan - 1.0) > 1e-6` تساوي False، فالمجموع وحده لا يكشفه.
- مفاتيح JSON مكررة كانت تنهار إلى آخر قيمة، فـ {"H07":0.2,"H07":1.0} تصير إيداعًا صالحًا:
  الخام يوثّق الواقعة، لكن الإيداع المُحلَّل كان يقود الجلسة فعلًا.
- حقول غير معلَنة كانت تمر رغم أن العقد يدّعي بنية محددة.
- إعادة EXPERIMENT على رمز مجرَّب كانت تُسعَّر معلومةً في نسخة IG وصفرًا في الأخرى.

تُستدعى من مجموعتي التحقق الميكانيكي فلا تعود أي منها ثغرة صامتة.
"""

import json
import math

from channel import (validate, validate_blind, strict_loads, SchemaError, _canon)


def _rejects(fn):
    try:
        fn()
        return False
    except (SchemaError, ValueError, json.JSONDecodeError):
        return True


def _commit(**over):
    d = {"type": "COMMITMENT", "hypotheses": {"a": 0.5, "b": 0.5}, "action": "TEST(Qz)",
         "predictions": {"outcome=1": 0.5}, "update_kind": "REWEIGHT"}
    d.update(over)
    return d


def contract_checks():
    """يرجع [(اسم, نجح؟, تفصيل)] — كلها يجب أن تُرفض عدا الأخيرة."""
    out = []

    def add(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    add("NaN probability rejected",
        _rejects(lambda: validate(_commit(hypotheses={"a": float("nan")}))),
        "abs(nan-1.0)>1e-6 is False, so the sum test alone cannot catch it")
    add("Infinity probability rejected",
        _rejects(lambda: validate(_commit(hypotheses={"a": float("inf"), "b": float("-inf")}))))
    add("bool as probability rejected",
        _rejects(lambda: validate(_commit(hypotheses={"a": True}))))
    add("negative probability rejected",
        _rejects(lambda: validate(_commit(hypotheses={"a": -0.5, "b": 1.5}))))
    add("NaN prediction rejected",
        _rejects(lambda: validate(_commit(predictions={"outcome=1": float("nan")}))))
    add("unknown field rejected (exact schema)",
        _rejects(lambda: validate(_commit(sneaky="x"))))
    add("duplicate JSON keys rejected before parsing",
        _rejects(lambda: strict_loads('{"hypotheses": {"H07": 0.2, "H07": 1.0}}')),
        "standard json.loads keeps the LAST value, yielding a valid-looking deposit")
    add("duplicate keys at top level rejected",
        _rejects(lambda: strict_loads('{"type": "FREE_OBS", "type": "COMMITMENT"}')))
    add("JSON NaN literal rejected", _rejects(lambda: strict_loads('{"p": NaN}')))
    add("JSON Infinity literal rejected", _rejects(lambda: strict_loads('{"p": Infinity}')))
    add("canonical form refuses non-finite", _rejects(lambda: _canon({"p": float("inf")})))
    add("blind extra field rejected",
        validate_blind({"Qz": {"pred": 1, "conf": 0.5, "x": 1}}, {"Qz": [0, 0, 0]}) is not None)
    add("blind NaN confidence rejected",
        validate_blind({"Qz": {"pred": 1, "conf": float("nan")}}, {"Qz": [0, 0, 0]}) is not None)
    add("blind bool pred rejected",
        validate_blind({"Qz": {"pred": True, "conf": 0.5}}, {"Qz": [0, 0, 0]}) is not None)
    add("a well-formed deposit still passes", validate(_commit()) is True)
    add("a well-formed blind reply still passes",
        validate_blind({"Qz": {"pred": 1, "conf": 0.5}}, {"Qz": [0, 0, 0]}) is None)
    return out


def ig_consistency_checks(seed=3000):
    """دلالة واحدة للـ IG: النسختان يجب أن تتفقا حتى على الأفعال المعادة."""
    import random
    from world_b1 import (generate_accepted_world_b1, Evidence, apply_action, all_actions,
                          information_gain)
    from ig_state import information_gain_full
    w = generate_accepted_world_b1(seed)
    rng = random.Random(3)
    ev = Evidence(w.n_syms, w.n_syms)
    for _ in range(4):
        a = rng.choice(all_actions(w.n_syms))
        outs = ([k for k in range(w.n_syms) if (ev.pmask[a[1]] >> k) & 1]
                if a[0] == "PROBE" else [0, 1])
        if outs:
            ev = apply_action(ev, a, rng.choice(outs))
    mism, repeated = 0, 0
    for a in all_actions(w.n_syms):
        ij, ih = information_gain(w.hypotheses, ev, w.emask, w.ctx, a)
        fj, fh, _ = information_gain_full(w.hypotheses, ev, w.emask, w.ctx, a)
        repeated += (a[0] == "EXPERIMENT" and ev.exp[a[1]] is not None)
        if not (math.isclose(ij, fj, abs_tol=1e-9) and math.isclose(ih, fh, abs_tol=1e-9)):
            mism += 1
    return [("IG has one authoritative meaning (old == corrected, incl. repeated actions)",
             mism == 0, f"{len(all_actions(w.n_syms))} actions, {repeated} repeated, {mism} mismatches")]


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = contract_checks() + ig_consistency_checks()
    for name, ok, detail in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    bad = sum(1 for _, ok, _ in rows if not ok)
    print(f"\nadversarial contract checks: {len(rows) - bad}/{len(rows)} passed")
    raise SystemExit(0 if bad == 0 else 1)
