# Pilot-A Gate Report — seeds 2000–2007 (8 worlds, 9 episodes)

model: claude-sonnet-5 via claude-openai-shim (operator's subscription, claude -p, pure text).
repeated runs: worlds that were re-run are shown as #r1/#r2 within the same append-only chain —
one world statistically, not two.

**This report is entirely read-only. Nothing in the pipeline was modified. A-004 is not sealed —
Section 4 is its first empirical test on frozen data.**

## 1. Contract layer

| episode | outcome | schema_rej | phase_rej | blind_rej | refusals | unparsed_interp | gate_bypass |
|---|---|---|---|---|---|---|---|
| 2000#r1 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2000#r2 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2001 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2002 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2003 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2004 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2005 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2006 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |
| 2007 | SOLVED | 0 | 0 | 0 | 0 | 0 | 0 |

- completion: **9/9**; semantic repairs by construction = 0 (the adapter does not fix anything; every rejection above is visible and sealed).
- totals: schema=0, phase=0, blind=0, refusals=0, unparsed_interp=0, gate_bypass=0.

## 2. Provenance layer

| episode | chain | exec_id start+end | request_ids | model | adapter_hash | truncations | terminal |
|---|---|---|---|---|---|---|---|
| 2000#r1 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2000#r2 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2001 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2002 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2003 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2004 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2005 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2006 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |
| 2007 | VALID | Y | complete | claude-sonnet-5 | bd2a2c04778cfe57 | 0 | Y |

- frozen hashes (expected from the frozen code): schema=0043f752a119c0c8, blind=dd7a56a0e3e93e1c, protocol=710f896b96544e0b.
- no overwrite: the repeated runs joined the same append-only chain, and the verify held on the file in full — the past is preserved, not rewritten.

## 3. Behavior diagnostics

| episode | Nfree | Nform | Nreal | Blind-ID | conf_ID | conf_X | declared_conf | truth_survives | |H| curve | IG bits/step |
|---|---|---|---|---|---|---|---|---|---|---|
| 2000#r1 | 3 | 1 | 4 | 1.0 | 0.9500000000000001 | None | 0.97 | Y | 30→15→7→4→1 | 1.0, 1.1, 0.807, 2.0 |
| 2000#r2 | 3 | 2 | 5 | 1.0 | 0.9699999999999999 | None | 0.97 | Y | 30→15→7→4→3→1 | 1.0, 1.1, 0.807, 0.415, 1.585 |
| 2001 | 3 | 2 | 5 | 1.0 | 0.9500000000000001 | None | 0.95 | Y | 30→15→9→4→2→1 | 1.0, 0.737, 1.17, 1.0, 1.0 |
| 2002 | 3 | 2 | 5 | 1.0 | 0.9699999999999999 | None | 0.97 | Y | 30→15→8→4→2→1 | 1.0, 0.907, 1.0, 1.0, 1.0 |
| 2003 | 3 | 3 | 6 | 1.0 | 0.9574999999999999 | None | 0.97 | Y | 30→15→7→4→3→2→1 | 1.0, 1.1, 0.807, 0.415, 0.585, 1.0 |
| 2004 | 3 | 3 | 6 | 1.0 | 0.9299999999999999 | None | 0.95 | Y | 30→15→8→4→3→2→1 | 1.0, 0.907, 1.0, 0.415, 0.585, 1.0 |
| 2005 | 3 | 2 | 5 | 1.0 | 0.9500000000000001 | None | 0.95 | Y | 30→15→9→5→3→1 | 1.0, 0.737, 0.848, 0.737, 1.585 |
| 2006 | 3 | 2 | 5 | 1.0 | 0.9299999999999999 | None | 0.95 | Y | 30→15→6→4→2→1 | 1.0, 1.322, 0.585, 1.0, 1.0 |
| 2007 | 3 | 2 | 5 | 1.0 | 0.9500000000000001 | None | 0.97 | Y | 30→15→8→4→2→1 | 1.0, 0.907, 1.0, 1.0, 1.0 |

### claimed vs actual — does what the model says match what its actions do?

For each step: the rank of the chosen action among the six actions by the worst-case split criterion (1 = best),
and the sealed claimed P(outcome=1) versus the actual proportion of survivors voting for 1:

| episode | step | action | rank | H_before→H_after | claimed p1 | actual p1 | Δ |
|---|---|---|---|---|---|---|---|
| 2000#r1 | 1 (free) | TEST(Kr) | 3 | 30→15 | — | 0.5 | — |
| 2000#r1 | 2 (free) | TEST(Ea) | 1 | 15→7 | — | 0.4667 | — |
| 2000#r1 | 3 (free) | TEST(Ok) | 1 | 7→4 | — | 0.4286 | — |
| 2000#r1 | 4 (formal) | TEST(Xp) | 2 | 4→1 | 0.75 | 0.75 | 0.0 |
| 2000#r2 | 1 (free) | TEST(Kr) | 3 | 30→15 | — | 0.5 | — |
| 2000#r2 | 2 (free) | TEST(Ea) | 1 | 15→7 | — | 0.4667 | — |
| 2000#r2 | 3 (free) | TEST(Ok) | 1 | 7→4 | — | 0.4286 | — |
| 2000#r2 | 4 (formal) | TEST(Hs) | 1 | 4→3 | 0.75 | 0.75 | 0.0 |
| 2000#r2 | 5 (formal) | TEST(Xp) | 1 | 3→1 | 0.6667 | 0.6667 | 0.0 |
| 2001 | 1 (free) | TEST(Um) | 5 | 30→15 | — | 0.5 | — |
| 2001 | 2 (free) | TEST(Bf) | 3 | 15→9 | — | 0.6 | — |
| 2001 | 3 (free) | TEST(Rc) | 2 | 9→4 | — | 0.5556 | — |
| 2001 | 4 (formal) | TEST(Nd) | 1 | 4→2 | 0.5 | 0.5 | 0.0 |
| 2001 | 5 (formal) | TEST(Tg) | 1 | 2→1 | 0.5 | 0.5 | 0.0 |
| 2002 | 1 (free) | TEST(Bf) | 1 | 30→15 | — | 0.5 | — |
| 2002 | 2 (free) | TEST(Xp) | 2 | 15→8 | — | 0.4667 | — |
| 2002 | 3 (free) | TEST(Zn) | 4 | 8→4 | — | 0.5 | — |
| 2002 | 4 (formal) | TEST(Nd) | 1 | 4→2 | 0.5 | 0.5 | 0.0 |
| 2002 | 5 (formal) | TEST(Wt) | 1 | 2→1 | 0.5 | 0.5 | 0.0 |
| 2003 | 1 (free) | TEST(Um) | 5 | 30→15 | — | 0.5 | — |
| 2003 | 2 (free) | TEST(Hs) | 1 | 15→7 | — | 0.5333 | — |
| 2003 | 3 (free) | TEST(Xp) | 1 | 7→4 | — | 0.5714 | — |
| 2003 | 4 (formal) | TEST(Ok) | 3 | 4→3 | 0.25 | 0.25 | 0.0 |
| 2003 | 5 (formal) | TEST(Ea) | 1 | 3→2 | 0.3333 | 0.3333 | 0.0 |
| 2003 | 6 (formal) | TEST(Ly) | 1 | 2→1 | 0.5 | 0.5 | 0.0 |
| 2004 | 1 (free) | TEST(Jm) | 2 | 30→15 | — | 0.5 | — |
| 2004 | 2 (free) | TEST(Hs) | 1 | 15→8 | — | 0.5333 | — |
| 2004 | 3 (free) | TEST(Kr) | 1 | 8→4 | — | 0.5 | — |
| 2004 | 4 (formal) | TEST(Tg) | 3 | 4→3 | 0.75 | 0.75 | 0.0 |
| 2004 | 5 (formal) | TEST(Nd) | 1 | 3→2 | 0.667 | 0.6667 | 0.0003 |
| 2004 | 6 (formal) | TEST(Rc) | 1 | 2→1 | 0.5 | 0.5 | 0.0 |
| 2005 | 1 (free) | TEST(Wt) | 6 | 30→15 | — | 0.5 | — |
| 2005 | 2 (free) | TEST(Jm) | 3 | 15→9 | — | 0.6 | — |
| 2005 | 3 (free) | TEST(Rc) | 2 | 9→5 | — | 0.5556 | — |
| 2005 | 4 (formal) | TEST(Bf) | 1 | 5→3 | 0.5 | 0.6 | 0.1 |
| 2005 | 5 (formal) | TEST(Vx) | 2 | 3→1 | 0.334 | 0.3333 | 0.0007 |
| 2006 | 1 (free) | TEST(Um) | 6 | 30→15 | — | 0.5 | — |
| 2006 | 2 (free) | TEST(Hs) | 3 | 15→6 | — | 0.6 | — |
| 2006 | 3 (free) | TEST(Nd) | 3 | 6→4 | — | 0.6667 | — |
| 2006 | 4 (formal) | TEST(Jm) | 1 | 4→2 | 0.4 | 0.5 | 0.1 |
| 2006 | 5 (formal) | TEST(Kr) | 1 | 2→1 | 0.5 | 0.5 | 0.0 |
| 2007 | 1 (free) | TEST(Ea) | 1 | 30→15 | — | 0.5 | — |
| 2007 | 2 (free) | TEST(Vx) | 2 | 15→8 | — | 0.4667 | — |
| 2007 | 3 (free) | TEST(Wt) | 4 | 8→4 | — | 0.5 | — |
| 2007 | 4 (formal) | TEST(Kr) | 1 | 4→2 | 0.5 | 0.5 | 0.0 |
| 2007 | 5 (formal) | TEST(Um) | 2 | 2→1 | 0.5 | 0.5 | 0.0 |

### sealed posterior versus actual survivors (COMMITMENT deposits)

| episode | action | names | distinct | survivors | set == survivors? | uniform? | mass on truth | truth claimed? |
|---|---|---|---|---|---|---|---|---|
| 2000#r1 | TEST(Xp) | 4 | 4 | 4 | Y | Y | 0.25 | Y |
| 2000#r2 | TEST(Hs) | 4 | 4 | 4 | Y | Y | 0.25 | Y |
| 2000#r2 | TEST(Xp) | 3 | 3 | 3 | Y | Y | 0.3334 | Y |
| 2001 | TEST(Nd) | 4 | 4 | 4 | Y | Y | 0.25 | Y |
| 2001 | TEST(Tg) | 2 | 2 | 2 | Y | Y | 0.5 | Y |
| 2002 | TEST(Nd) | 4 | 4 | 4 | Y | Y | 0.25 | Y |
| 2002 | TEST(Wt) | 2 | 2 | 2 | Y | Y | 0.5 | Y |
| 2003 | TEST(Ok) | 4 | 4 | 4 | Y | Y | 0.25 | Y |
| 2003 | TEST(Ea) | 3 | 3 | 3 | Y | Y | 0.3333 | Y |
| 2003 | TEST(Ly) | 2 | 2 | 2 | Y | Y | 0.5 | Y |
| 2004 | TEST(Tg) | 4 | 4 | 4 | Y | Y | 0.25 | Y |
| 2004 | TEST(Nd) | 3 | 3 | 3 | Y | Y | 0.333 | Y |
| 2004 | TEST(Rc) | 2 | 2 | 2 | Y | Y | 0.5 | Y |
| 2005 | TEST(Bf) | 6 | 5 | 5 | Y | N | 0.1667 | Y |
| 2005 | TEST(Vx) | 3 | 3 | 3 | Y | Y | 0.334 | Y |
| 2006 | TEST(Jm) | 4 | 4 | 4 | Y | N | 0.2 | Y |
| 2006 | TEST(Kr) | 2 | 2 | 2 | Y | Y | 0.5 | Y |
| 2007 | TEST(Kr) | 4 | 4 | 4 | Y | Y | 0.25 | Y |
| 2007 | TEST(Um) | 2 | 2 | 2 | Y | Y | 0.5 | Y |

- **set == survivors in 19/19 deposits** (tracking of the survivor set is exact).
- **posterior uniform over survivors in 17/19**.

**Two negative observations are recorded — two distinct phenomena that must not be merged:**

**(a) Logical duplication in hypothesis enumeration** — different names collapse to the *same* truth table,
so the equivalence class takes two shares of the probability mass:

- `2005` / TEST(Bf): (NOT p1 XOR p2) ≡ (p1 XOR NOT p2) — 6 names for 5 distinct hypotheses (weight on the duplicated class ≈ 0.3333 instead of 0.2).

**A canonicalization defect on the part of the agent**: the survivor set is correct, but the posterior is
incorrectly weighted across a logical equivalence class.

**(b) Non-uniform weighting with no evidentiary support** — there is no duplication here; the names are distinct and all are survivors,
i.e., equally consistent with the evidence, and yet the mass was distributed unequally:

- `2006` / TEST(Jm): 4 distinct hypotheses, all consistent with the evidence, and the mass on the true law is 0.2 instead of 0.25 — a deviation from the reference posterior.

Under deterministic elimination and a uniform prior, the correct reference is the uniform distribution over survivors; any additional
weighting is unsupported by the evidence. This does not violate the contract (the probabilities sum to 1.0), but it is an **unjustified default preferential tendency**
that warrants tracking in Pilot-B, where calibration becomes a core metric.

Both are explicitly recorded and not swallowed: the batch is not defect-free, even though neither changed
the final outcome (all episodes ended SOLVED with full Blind-ID).

## 4. Oracle diagnostics — the first empirical test of the A-004 formulation (unsealed)

D_floor = instance-optimal under epistemic admissibility (a diagnostic-only lower envelope).
Justification for the computation: on a deterministic instance, any admissible policy collapses to a fixed sequence of actions,
and the ordering of the tests does not change the survivor set ⇒ min over policies = min over test sets.

**A branch point discovered in the definition** (absent from the initial formulation): the stopping point has two readings —
`weak` = majority vote of survivors achieves BlindScore ≥ tau on the realized truth (the criterion is met,
even if the survivors remain split); `strict` = the survivors agree on every Blind-ID case (the evidence has *determined*
the answers). Always weak ≤ strict. **The audit threshold must be weak** because it is the validity bound:
any N below it is impossible for any admissible policy ⇒ bug/leak; using strict produces false alarms.

| episode | D_floor(weak) | D_floor(strict) | D_robust | D_inst | N_realized | region | audit (old rule) |
|---|---|---|---|---|---|---|---|
| 2000#r1 | 4 | 4 | 5 | 5 | 4 | FAVORABLE_TRAJECTORY | YES |
| 2000#r2 | 4 | 4 | 5 | 5 | 5 | NORMAL/ABOVE_ROBUST_COST | - |
| 2001 | 4 | 4 | 5 | 5 | 5 | NORMAL/ABOVE_ROBUST_COST | - |
| 2002 | 3 | 4 | 4 | 4 | 5 | NORMAL/ABOVE_ROBUST_COST | - |
| 2003 | 4 | 4 | 6 | 6 | 6 | NORMAL/ABOVE_ROBUST_COST | - |
| 2004 | 4 | 4 | 6 | 6 | 6 | NORMAL/ABOVE_ROBUST_COST | - |
| 2005 | 3 | 4 | 5 | 6 | 5 | NORMAL/ABOVE_ROBUST_COST | - |
| 2006 | 4 | 4 | 5 | 5 | 5 | NORMAL/ABOVE_ROBUST_COST | - |
| 2007 | 4 | 4 | 5 | 5 | 5 | NORMAL/ABOVE_ROBUST_COST | - |

- region distribution: {"FAVORABLE_TRAJECTORY": 1, "NORMAL/ABOVE_ROBUST_COST": 8}
- TRUE_AUDIT (N < D_floor_weak) = leakage/accounting/oracle bug: **0** out of 9.
- weak ≠ strict in this batch: yes — the branch point is real in practice, not merely theoretical.
- D_robust ≠ D_inst in: 2005 — where they diverge, task-aligned stopping is actually cheaper than full identification of the law, which is direct evidence that amendment A-001 (the task-aligned ruler, not full identification) is doing real work, not merely a renaming.

## 5. Measurement Instrument Corrections During Pilot-A

One correction occurred during Pilot-A, **in the analysis tool, not in the experiment**. It is recorded in full because
the integrity of the analysis is part of the provenance:

| Item | Detail |
|---|---|
| **Problem** | The diagnostic normalizer recognized `NOT` and `¬` but not `~` (nor `!`). The COMMIT_SCHEMA does not mandate a notation for names — it only requires that the probabilities sum to 1.0 — so writing `(~p0 AND p2)` is a valid deposit and conforms to the contract. |
| **Initial erroneous impact** | seed 2003 appeared as though the model was declaring hypotheses outside the hypothesis space, that its mass on the true law = 0.0, and that the true law was not declared at all (3 of 4 names "unmatched"). The conclusion available at the time was: *the model drops the true law*. |
| **How it was verified** | The raw deposit was inspected from the sealed chain before drawing any conclusion: `{"(p1 XOR p2)":0.25, "(~p0 AND p2)":0.25, "(~p0 AND ~p1)":0.25, "(~p1 AND p2)":0.25}` and SUFFICIENCY = `(~p0 AND p2)`, while the true law is `(NOT p0 AND p2)` — that is, **the exact same thing** in equivalent notation. The error was in the ruler, not in the measured subject. |
| **Location of the fix** | `pilot_a_gate_report._norm` only (an analysis tool outside the pipeline): accept `~`, `!`, and `¬` as negation. world/channel/session/agents/llm_agent were not touched, nor was the protocol, the schema, or any sealed data. |
| **Result of the re-analysis** | 19/19 deposits: the declared hypothesis set = the actual survivor set, exactly; the true law is within the declared set in 19/19. |
| **Original records** | Unchanged: the tool does not open any file for writing, and the hash chains above (Section 2) were re-verified after the fix and remained VALID — which is technical, not merely procedural, evidence. |

The recorded lesson: the separation between the **formal contract** (which constrains what is counted) and **downstream analysis tools** (which read but do not bind) is what made this error discoverable and fixable without contaminating the experiment. The measurement instrument is audited before judging the measured subject — the same rule as OracleViolation, applied to the analyzer.

## Gate verdict

The gate question: **Did the contract remain intact when facing a real LLM across multiple worlds/runs?**
(Blind-ID is not the sole passing criterion — the judgment concerns the integrity of the contract and the record.)

The committed formulation of what the third layer established, without inflation:

> **Exact survivor-set tracking in Pilot-A, with two documented posterior-weighting defects**

That is: the survivor set is exact in **19/19** deposits — this is the strong claim. The weights, however, are uniform in only **17/19**, and the difference is not noise but two distinct, documented defects noted above: (a) logical duplication distorting the weight of an equivalence class, (b) non-uniform weighting with no evidentiary support. The sealed outcome predictions matched the proportion of survivors voting for 1 with a discrepancy ≤ 3×10⁻⁴. This is **not** a general claim of "epistemic Bayesian competence": the depth-2 scope is small, the declaration is complete, and the hypothesis space is only 30 and can be enumerated by hand — and deterministic elimination under a uniform prior makes the correct posterior a direct exercise.

Definitively outside the scope of Pilot-A's judgment: **Blind-X, Frame Expansion, latent probes** — these are counted here neither as success nor as failure; their presence in the code is recorded only as plumbing ready for the next stage (Blind-X is structurally empty in this world, and the declaration is complete, so there is no opportunity for Frame Expansion in the first place).

The two steps conditioned on passing, before Pilot-B and in this order:
1. Review of the A-004 candidate against this frozen data, and a decision to seal or reject it.
2. Sealing the Pilot-B specification: probe separation, t_inadequacy, Frame Expansion, and the Blind-X triad.

The confirmation seeds are not opened.
