"""adversarial_contract.py — adversarial checks on the contract itself (A-009).

Every case here was a **real vulnerability** found in code review, not a hypothetical test:

- A NaN probability used to pass through because `abs(nan - 1.0) > 1e-6` evaluates to False, so the
  sum check alone can't catch it.
- Duplicate JSON keys used to collapse to the last value, so {"H07":0.2,"H07":1.0} becomes a
  valid-looking deposit: the raw log documents the event, but the parsed deposit was actually
  driving the session.
- Undeclared fields used to pass through even though the contract claims a fixed structure.
- Repeating EXPERIMENT on an already-probed symbol was priced as informative in one IG version and
  zero in the other.

These are called from both mechanical validation suites, so none of them stays a silent
vulnerability.
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
    """Returns [(name, passed?, detail)] — all of them must be rejected except the last one."""
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
    """One authoritative meaning for IG: the two versions must agree, even on repeated actions."""
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
