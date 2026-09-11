# Epistemic Control Diagnostic — Design Draft (Unsealed)

**Status: DRAFT.** Do not seal or run before 4020–4029 is complete and you have decided on the two open points.

## The Question

B1 measured **the economics of acquisition**. This diagnostic measures **discrimination in epistemic control**:

> Does the agent know, at every moment, which epistemic state it is in?

$$\text{I do not know now} \;\neq\; \text{I could know if I continued} \;\neq\; \text{I cannot, within the remaining resources}$$

## 1. Four decision states — all derived from the belief state (settled)

The middle range **is not experimental noise** but a real difference between a worst-case guarantee and the possibility of success on
a specific instance. So it is called by its own name and given its own analysis, not eliminated:

| State | Condition (from belief alone) | Correct decision |
|---|---|---|
| `MET` | the criterion is satisfied now | **STOP / SUFFICIENCY** |
| `GUARANTEED_REACHABLE` | every branch can be driven to the criterion within `B` | **CONTINUE** |
| `POSSIBLE_UNGUARANTEED` | a lucky branch reaches it, with no guarantee | **not scored as either correct or incorrect** |
| `UNREACHABLE` | no branch reaches it within `B` | **INCOMPLETE** |

The ambiguity in the middle is not in the world but in the **decision rule that has not yet been fixed** (robust-only versus
expected-value). So it remains in the report under the name `POSSIBLE_UNGUARANTEED` and is analyzed independently — and there
the question becomes: *what does the agent do when success is possible but not guaranteed?* — which may reveal
**risk attitude** later.

## 2. Substantive correction: `B < D_floor^task(W*)` was wrong twice

The first formulation in this draft was:

    UNREACHABLE  ⇔  B < D_floor^task(W)

and it is flawed in two respects, the second of which appeared only at implementation time:

1. **clairvoyant**: `D_floor^task(W*)` is known to the oracle after the truth is known. Judging
   the agent by it holds it accountable for something it has no access to — the same error as 4015/4018, **reversed**.
2. **on the weak criterion**: `d_floor_pair_b1` measures voting against **the true law**, whereas what
   the agent can guarantee is agreement against **every member** of the support. Measured on world 3000:

       D_floor^task(W*) = 2      versus      D_lower(belief) = 6

   So the two quantities are not comparable to begin with. (This is the weak/strict bifurcation from A-004 recurring in a new place.)

**The implemented alternative** — `optimistic_reach()`: a breadth-first search from the current evidence state for the shortest
path to a state at which stopping is **guaranteed to succeed**, via any branch consistent with the evidence. Derived from
belief alone, and it does not touch `W*`. And the ordering holds: `D_lower ≤ D_robust` (6 ≤ 8 on 3000).

> **World-instance unreachable  ≠  Epistemically knowable as unreachable**

And the one used in scoring is exclusively the second.

## 3. Unit of measurement (settled)

**The decision point is the unit of measurement, and the episode/world is the clustering unit** (to prevent pseudo-replication
per C.3). No test is run as if 150 steps from 20 worlds were independent; the confirmatory analysis will later be
cluster-aware or will summarize per-world before comparison.

And a practical advantage: `MET` and `GUARANTEED_REACHABLE` can be extracted **retroactively from existing batches**
without a new run. New generation is required only for `UNREACHABLE`, via a single controlled variable:
the declared budget `B < D_lower(belief_0)` — a quantity **the agent can compute for itself** from
the catalog and its own evidence, so judging it by this is fair.

## 4. The Matrix

| True state \ Decision | STOP (sufficiency) | CONTINUE | INCOMPLETE |
|---|---|---|---|
| **MET** | ✓ | over-exploration | error |
| **POSSIBLE_UNGUARANTEED** | — | — | — (outside the matrix, separate analysis) |
| **GUARANTEED_REACHABLE** | premature stop | ✓ | **action-space misjudgment** |
| **UNREACHABLE** | error | wasted resources | ✓ |

With a breakdown of the `REACHABLE × INCOMPLETE` cell according to the structured claim:
`no_decisive_action_remains` → `INCORRECT_ACTION_EXHAUSTION`;
`insufficient_evidence_now` → `ACTIONABLE_INCOMPLETENESS`.

## 5. Why this is stronger than any scalar

`ExcessActionsAfterSufficiency` has proven its limitations: in B1, `criterion met ⇔ |support|=1`,
and the agent naturally declares sufficiency at the singleton, so `t_sufficient = t_stop` is almost
structurally forced (0.00 in 18/18 sessions). So it is **a detector of negative deviation, not positive evidence of efficiency**. The matrix
measures the thing actually wanted, directly: does the agent know its own state?

## 6. What remains frozen

grammar · schema · the contract visible to the agent (except the budget value) · the four rulers · τ_ID ·
the audit rule. The only controlled variable is the declared budget.

## 7. The Sequence

    Complete 4020-4029 → resolve the narrow question (should A-007 over-exploration be introduced?)
    → decide the two points above → seal A-008 → run the diagnostic

`S_confirmatory` remains closed.
