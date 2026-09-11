# Pilot-B1 — Specification (FROZEN before implementation)

**The single question for B1:**

> When the necessary information is hidden, does the agent know **what it needs to observe?**

**No Frame Expansion, no Blind-X, and no incomplete declaration in B1.** All of these await B2.
The declaration remains complete (`declaration_complete: true`), and the law is always within the declared family.

---

## 1. The World: Latent Properties

In Pilot-A, the property table was visible and the law was hidden. In B1, **both are hidden**:

The agent receives only the symbol names, without vectors:

    symbols: ["Qz", "Vx", "Kr", ...]        # not (p0,p1,p2)

Each symbol has a latent vector `v_x ∈ {0,1}³` that it cannot see. The law `f` is one of the 30 (same grammar depth-2).

## 2. Two Distinct Actions — The Fundamental Separation

    PROBE(sym, p_i)   →  v_sym[i] ∈ {0,1}        acquisition of an observation about the state
    EXPERIMENT(sym)   →  f(v_sym) ∈ {0,1}        testing the law

> **Observation acquisition ≠ causal experimentation**

The Verifier rejects any action outside these two forms before execution (same rule as A-003:
attempt consumed). `p_i ∈ {p0,p1,p2}`, and the symbol must be exclusively within the training region.

## 3. Triple Accounting — Frozen From the Start

    N_total = N_free + N_probe + N_experiment

The three are **always stored separately and never merged in a report**. The reason is pre-registered:

    10 probes + 1 experiment   ≠   2 probes + 9 experiments

epistemically, even if `N_total = 11` is equal. The total budget is a single one, consumed equally by the three.

## 4. Hypothesis Identity Is Semantic, Not Textual — Structurally Prevents the 2005 Defect

**Frozen decision:** `Hypothesis identity should be semantic, not textual.`

Each hypothesis has a single canonical identifier derived from its truth table:

    H00 … H29        and the full catalog is delivered in phase zero:
    {"H07": "(NOT p0 AND p2)", ...}

The deposit places the probability on the **identifier**, not on the text:

    "hypotheses": {"H07": 0.5, "H12": 0.5}

Structural consequences:
- `(NOT p1 XOR p2)` and `(p1 XOR NOT p2)` share the same identifier ⇒ **logical duplication is impossible**
  (a duplicate JSON key collapses into one). The 2005 defect is prevented by construction, not detected after the fact.
- The Schema rejects any identifier outside the catalog (a representation error — prevented).
- The analyzer never parses strings after execution, at all.

## 5. What Is Deliberately Not Prevented — The 2006 Defect

Uneven weighting unsupported by evidence (0.4/0.2/0.2/0.2 over equally-consistent hypotheses)
**is not a representation error but a belief error**. The Schema does not prevent it, and B1 **measures it**.

    2005-type (representation)  →  prevented by the architecture
    2006-type (belief)          →  allowed, and measured

## 6. Posterior Metrics — Formal in B1

The Oracle computes the reference posterior exactly. The joint state (law × latent vector
assignments) is distributed **uniformly** over all triples consistent with the evidence, so:

    P*(h | E) ∝ W(h) = Π_x n_x(h)      where n_x(h) = the number of vectors consistent with symbol x's evidence under h
    H_joint  = log2 Z                   where Z = Σ_h W(h)

At each step t, **three separate metrics that are never merged** are recorded:

| Metric | Question |
|---|---|
| `SupportAccuracy_t` | Are the possible hypotheses present in the declared set? (missing/excess + Jaccard) |
| `ProbabilityError_t` | Are their weights correct? (Total Variation between P_agent and P*) |
| `Calibration` | Brier score on sealed predictions against actual outcomes |

The 2006 defect appears as `SupportAccuracy = 1.0` with `ProbabilityError > 0` — which is exactly
why merging them into a single metric is rejected.

## 7. ProbeQuality — Diagnostic Only, Not a Reward

    IG(a) = H_joint(t) − E_outcome[ H_joint(t+1) | a ]
    ProbeQuality = IG_chosen / IG_max      (over the actions available of the same type)

**Pre-registered warning:** a given probe may have `IG_law = 0` and yet still be **necessary**
(it sets up a useful experiment later). Therefore IG is measured on the **joint** state, not on
the law's marginal alone, and `IG_law` is recorded separately for diagnostic purposes. Neither
one enters any reward — to prevent a new Goodhart effect.

## 8. Floors and the Reference (Extension of A-004 to a Two-Action Space)

The four rulers as sealed in A-004, with a broader action space (probes + experiments):
`D_floor^task` (the audit guard) · `D_floor^strict` (diagnostic) · `D_robust^task` (denominator E) ·
`N_realized`. The audit remains: `TRUE_AUDIT ⇔ N_realized < D_floor^task`.

## 9. The Blind Test

Exactly as in Pilot-A: new symbols **with their vectors given**, and the agent predicts `f`.
Reason: latency in B1 concerns **the learning region** (does it know what to observe?), whereas
the blind test measures **whether it learned the law** — and merging the two would corrupt the
Blind-ID measurement.

## 10. B1-small: Adversarial Checks First

`10–20` worlds from `S_pilot` only. **The goal is not significance** but hunting:

- probe leakage · accounting bugs · oracle mismatch · semantic-ID bugs
- malformed beliefs · probe/experiment confusion · budget exploits · stopping exploits

**First pre-registered adversarial check:** can the agent solve the world **without any probe**
due to information that leaked from the representation? This is tested with the `NoProbeAgent`
bot and by checking that `D_floor^task` itself requires probes.

## 11. B1 Success Condition — Three Layers, Not Blind-ID Alone

`BlindID = 1` alone **is not** success: it can be reached by brute-force probing.

    Outcome                Did it succeed at Blind-ID?
    Belief quality         Are the support and weights reasonable?
    Information acquisition Are the probes useful, or random/excessive?

Here, for the first time, the difference appears between **knowing the answer** and **knowing
how to obtain the knowledge**.

## 12. The Binding Order

    Pilot-A CLOSED/PASSED → A-004 sealed → B1 frozen (this document) → B1-small
    → Review/Amend → B2 freeze

`S_confirmatory` **is not opened**. Any amendment resulting from B1 is sealed before B2.
B2 only, later: incomplete declaration → contradictory/low-probability evidence → detection of
framework inadequacy → Frame Expansion → Blind-X, culminating in the stronger question:
**does it know that it does not know?**
