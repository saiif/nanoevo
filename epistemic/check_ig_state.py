"""check_ig_state.py — تحقق ميكانيكي لـ IG_Σ قبل أي اعتماد عليه (على غرار run_mechanical_b1)."""

import itertools
import math
import random

from world import enumerate_hypotheses
from world_b1 import (Evidence, exp_masks, Ctx, _subsets_by_popcount, posterior,
                      apply_action, all_actions, information_gain, ALL_VECTORS)
from ig_state import state_entropy, information_gain_full

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main():
    hyps = enumerate_hypotheses()
    rng = random.Random(11)

    # (1) Z من state_entropy == Z من posterior (نفس المقام المشترك) على أدلة عشوائية
    worstZ, tested = 0, 0
    for _ in range(150):
        n = rng.randint(2, 5)
        declared = rng.sample(ALL_VECTORS, n)
        ctx = Ctx(n, _subsets_by_popcount(n), declared, {})
        em = exp_masks(hyps, declared)
        ev = Evidence(n, n)
        for _ in range(rng.randint(0, 4)):
            a = rng.choice(all_actions(n))
            if a[0] == "PROBE":
                opts = [k for k in range(n) if (ev.pmask[a[1]] >> k) & 1]
                if opts:
                    ev = apply_action(ev, a, rng.choice(opts))
            else:
                ev = apply_action(ev, a, rng.randint(0, 1))
        _, Zp, _, _ = posterior(hyps, ev, em, ctx)
        _, Zs = state_entropy(hyps, ev, ctx, em)
        if Zp:
            tested += 1
            worstZ = max(worstZ, abs(Zp - Zs))
    check("state_entropy Z == posterior Z (shared joint normalizer)",
          worstZ == 0 and tested >= 80, f"{tested} states, max |ΔZ|={worstZ}")

    # (2) الحالة الابتدائية بلا أدلة: H(Σ) == log2(n!)
    okstart = True
    for n in range(2, 6):
        declared = rng.sample(ALL_VECTORS, n)
        ctx = Ctx(n, _subsets_by_popcount(n), declared, {})
        em = exp_masks(hyps, declared)
        H0, _ = state_entropy(hyps, Evidence(n, n), ctx, em)
        okstart &= abs(H0 - math.log2(math.factorial(n))) < 1e-9
    check("H(Σ)=log2(n!) at zero evidence (uniform over permutations)", okstart)

    # (3) بعد تثبيت كل الرموز: H(Σ)==0 وIG_Σ لأي تجربة == 0
    okpin = True
    for _ in range(40):
        n = rng.randint(2, 5)
        declared = rng.sample(ALL_VECTORS, n)
        ctx = Ctx(n, _subsets_by_popcount(n), declared, {})
        em = exp_masks(hyps, declared)
        ev = Evidence(n, n)
        perm = list(range(n))
        rng.shuffle(perm)
        for x in range(n):                       # ثبّت الإسنادات كلها بالـ probes
            ev = apply_action(ev, ("PROBE", x, None), perm[x])
        Hs, _ = state_entropy(hyps, ev, ctx, em)
        okpin &= abs(Hs) < 1e-12
        _, _, igs = information_gain_full(hyps, ev, em, ctx, ("EXPERIMENT", 0, None))
        okpin &= abs(igs) < 1e-12
    check("pinned σ ⇒ H(Σ)=0 and IG_Σ(experiment)=0 (matches empirical IG_joint==IG_law)", okpin)

    # (4) IG_joint/IG_law من information_gain_full == من world_b1.information_gain حرفيًا
    okmatch = True
    for _ in range(80):
        n = rng.randint(2, 5)
        declared = rng.sample(ALL_VECTORS, n)
        ctx = Ctx(n, _subsets_by_popcount(n), declared, {})
        em = exp_masks(hyps, declared)
        ev = Evidence(n, n)
        for _ in range(rng.randint(0, 3)):
            a = rng.choice(all_actions(n))
            if a[0] == "PROBE":
                opts = [k for k in range(n) if (ev.pmask[a[1]] >> k) & 1]
                if opts:
                    ev = apply_action(ev, a, rng.choice(opts))
            else:
                ev = apply_action(ev, a, rng.randint(0, 1))
        act = rng.choice(all_actions(n))
        j1, l1, s1 = information_gain_full(hyps, ev, em, ctx, act)
        if act[0] == "EXPERIMENT" and ev.exp[act[1]] is not None:
            okmatch &= j1 == 0.0 and l1 == 0.0 and s1 == 0.0     # فعل زائد ⇒ أصفار
        else:
            j0, l0 = information_gain(hyps, ev, em, ctx, act)
            okmatch &= abs(j0 - j1) < 1e-12 and abs(l0 - l1) < 1e-12 and s1 >= -1e-12
    check("information_gain_full reproduces (IG_joint, IG_law) exactly; IG_Σ >= 0 "
          "(redundant re-experiment ⇒ all zeros)", okmatch)

    passed = sum(CHECKS)
    print(f"\nIG_Σ VALIDATION: {passed}/{len(CHECKS)} checks passed")
    return passed == len(CHECKS)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
