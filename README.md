# Mechanical Validation — First Run (Addendum B)

A literal implementation of the first-run scope from the document "A Transferable Epistemic Method" v1.2
(`preregistration.md` — sealed, not to be edited; every amendment goes through the ledger):
depth-2 grammar, two arms, deterministic Verifier/Archivist, no LLM and no statistical claims.

## Structure
See `STRUCTURE.md`. In brief: the code + the ledger + the provenance live under `epistemic/`,
and the pre-registration document is at the root.

- `epistemic/world.py` — depth-2 grammar (logical formulas over properties) + oracle + D_min (minimax) + D_inst + D_pred
- `epistemic/channel.py` — Schema validator (COMMIT_SCHEMA + BLIND_SCHEMA) + append-only Archivist with a hash chain
- `epistemic/session.py` — the Experimenter gate, the violations table A.3 + A-003, the blind test, E/Success/TRUE_AUDIT
- `epistemic/agents.py` — Learner (interval selection) / Control (random) + bots for testing violations and leakage
- `epistemic/llm_agent.py` — the Pilot-A adapter
- `epistemic/run_mechanical.py` — the seven mechanical questions + A.3 + A-003 + a demonstration
- `epistemic/run_pilot_a.py` — Pilot-A (requires Anthropic credentials)
- `epistemic/ledger.py` — `verify` / `append` / `show` for the amendments ledger
- `epistemic/amendments.jsonl` — the sealed ledger (current chain head: `db80fade46477b04`)

## Running
    cd epistemic
    python run_mechanical.py        # Result: 44/44 checks passed  → provenance/mech_run/
    python ledger.py verify         # VALID  entries=19  head=568a26295773f512

The current frozen versions (sealed in GENESIS each session):
`schema_hash=aed0071834b61fac` (bumped to 1.1 by A-009, because tightening the validator changed what the schema means) · `blind_schema_hash=7a59d7735584a84e` ·
`protocol 1.0-mech-A004 / protocol_hash=8363d012d772055b` · `grammar_hash=02445a0a5566be2d` ·
`adapter_hash=bda5027979184d30` (the current file bytes; the Pilot-A episodes were sealed under `bd2a2c04778cfe57`, the A-003 adapter — the adapter file has since been edited, so the two differ by construction, and the episode records remain the authority for what ran).

## Documented scope decisions (mechanical only)
1. The property table is visible and the law is hidden — latent, probe-able properties enter in the pilot
   (per the document: the first goal is testing the pipeline, not the richness of the world).
2. The declaration is complete (declaration_complete) — an incomplete declaration for measuring Frame Expansion enters in the pilot.
3. The D_min window for the mechanical run: [2,6] instead of [4,15] — the world is deliberately smaller.
   A measured structural observation (60 seeds): every accepted world has D_min=6 exactly (30 hypotheses, 6 binary tests),
   and D_pred ∈ {4,5,6}; ~87% of raw worlds are rejected for non-distinguishability. The window is, in practice, an identifiability gate.

## Mechanical validation finding (logged via OracleViolation audit)
The first version measured E against worst-case D_min, so the audit fired on every session —
because minimax D_min is not a lower bound on any single session (the actual world may resolve faster),
and because free observations carry information without being counted. The correction applied:
- N_total = interventions + free observations (both consume the budget).
- The ruler: D_inst = the cost of the optimal policy on the true law itself.
- D_min remains only a generation-difficulty gate.
This change touches the definition of E in the document → it requires a sealed amendment before opening the
confirmatory seeds (per the timing rule in A.1). The audit mechanism worked exactly as designed.

## Amendment A-001 (sealed in amendments.jsonl)
- The official ruler for E: the task-aligned D_pred-inst — the oracle knows only the hypothesis class,
  under the same I0, and its goal is BlindScore >= tau, not full identification. C(pi*, W_i | I0).
- N_total = N_free + N_formal (the same observation protocol for the agent and the oracle).
- D_min: a generation gate only, outside the Primary Endpoint. D_inst: reported.
- protocol_hash changes automatically with the amendment (the triple freeze works).

## Mechanical finding #2 (during the implementation of A-001)
Hypotheses that are identical over the training range (6 vectors) and different on the blind range (8) make
"guarantee for all" unreachable on some branches, breaking the pure minimax policy.
The documented fix: a greedy fallback with maximum split; D_pred there is a reference, not a guarantee.

## Amendment A-002 (sealed) — Identifiability / Extrapolation Separation
- Observational equivalence classes: H_a ~ H_b ⇔ identical on everything the interventions allow.
- Blind-ID (a fixed target within each class) decides Success and E; Blind-X is secondary:
  extrapolation + Extrapolation Calibration (does confidence drop where the evidence doesn't discriminate?).
- D_pred-inst = UNREACHABLE under non-identifiability; the greedy value is logged separately as D_greedy_ref.
- A deliberate, sealed design decision: the blind range is not constrained by the training range — the gap is deliberately preserved by a separate function.
- Addendum: UNREACHABLE worlds are not eligible for E (neither 0 nor null) and are rejected at generation; the threshold is called tau_ID.

## Mechanical finding #3 (during the implementation of A-002)
The stopping condition was measuring agreement with the fixed true law, whereas in minimax's
counterfactual branches "the truth" is the branch's hypothesis — so the state {a single false hypothesis} was a
permanent dead end that poisoned the tree with inf. The fix: the guarantee = a majority rule within the state,
checking the threshold against any member as if it were the correct one (mutual agreement, counterfactual-correct).

## A-002 behavior documented experimentally
Worlds with a narrow training range (4 vectors — a pilot simulation, `provenance/mech_run_archive_1787333903/x*`):
nID=4/nX=4, the agent exhausts the evidence, declares sufficiency with honest confidence, and succeeds on ID with confidence 1.0 while
its confidence on X automatically drops to 0.67-0.75 — Extrapolation Calibration works.
In the full mechanical world (6 training vectors) every class is a singleton, so Blind-X is structurally empty; it activates in the pilot.

## Pre-pilot finding #4 → Amendment A-003 (sealed) — Pilot-A hardening
Code analysis before running any LLM (2026-08-21) found paths that a language agent would have broken — and each one
would have been misclassified under the P-001 taxonomy (e.g., a pipeline crash instead of non-compliance). What was fixed and sealed:
- **A malformed action** (`TEST(Qz, Vx)`, `test qz`…) passes the schema then is rejected by the Verifier as a forbidden action
  (attempt consumed) in both stages — instead of an uncaught crash. `FREE_OBS_REFUSED` / `REFUSED_ACTION`.
- **A type out of its phase** (a fourth FREE_OBS after the observation phase): one neutral retry (`PHASE_REJECT`) then failure —
  instead of an immediate failure that violated Table A.3.
- **INADEQUACY consumes an attempt**: the loop is now bounded by construction (it used to be free → an infinite loop was possible).
- **The blind reply passes through a validator** (`BLIND_SCHEMA`: all symbols, pred an integer 0/1, conf ∈ [0,1], no coercion):
  one retry (`BLIND_REJECT`) then `AGENT_PROTOCOL_FAILURE(stage=blind)` without revealing the truth.
  (A malformed reply used to silently turn into pred=0/conf=0.5 in every case and contaminate the calibration.)
- **The sufficiency-despite-incompleteness claim is verified**: correct ⇔ the remaining set lies inside a single observational equivalence class containing the law →
  a blind test (Article 41: epistemic success); incorrect → `INCORRECT_INCOMPLETENESS_CLAIMED`, E=0.
  (The `CORRECT_…` label used to be granted without verification.)
- **Execution identity is sealed twice**: `EXEC_IDENTITY` at the start and `EXEC_IDENTITY_END` at the end (request_ids, stop_reasons,
  the count of chunks truncated by max_tokens) — request_ids used to always be sealed empty. Crashes are sealed as `SESSION_ABORTED`.
- `run_pilot_a.py`: fixed a crash in the report, a taxonomy by SDK exception types (BadRequest → adapter,
  the rest of APIError → provider, otherwise → world/session bug), credentials resolved from the environment or a profile.
- Explicit UTF-8 encoding for the side channel, the logs, and the console (the run used to crash on Windows cp1252).
- **Unchanged**: E, tau_ID, D_pred, the definition of N_total, COMMIT_SCHEMA (`schema_hash` fixed), the grammar.
- 8 new regression checks in `run_mechanical.py` → 22/22. All prior records remain preserved under `provenance/`.

Known limits recorded in A-003: tau_blind=0.90 with 8 Blind-ID cases means 8/8; the hash chain
detects only naive tampering — the chain head is anchored externally (git + this file).

## Pilot-A (ready to run)
- `llm_agent.py`: the adapter — the model writes free-form reasoning then a single JSON block; the last
  JSON block = the deposit (it passes through the validator like any agent), and the rest is the side channel. A malformed
  deposit is not repaired in the adapter — the contract itself handles it (one retry then failure).
- `run_pilot_a.py [n]`: S_pilot = seeds 2000+; the success metric = the protocol-compliance report (the five families), not E.
  A smoke test via a hand-written fake client (3 observations, a fourth FREE_OBS, one malformed blind reply, Arabic text in the
  side channel, and a crash path) passed: PHASE_REJECT and BLIND_REJECT are sealed, request_ids=7 sealed at the end,
  SESSION_ABORTED with correct taxonomy, the report prints in full.
- Plan P-001 sealed in the ledger: stages A/B, the three issues (separating N_probe/N_experiment,
  the temporal t_inadequacy for DetectionLatency, the Blind-X triad), and the binding timing rules:
  every amendment resulting from Pilot-A is sealed before Pilot-B; the confirmatory seeds are not opened.

## Pilot-A — first actual run on a real LLM (2026-08-21)
Run on a debian server via an OpenAI-compatible endpoint (`claude-openai-shim`) executing through
the operator's `claude -p` subscription. Model: **claude-sonnet-5**. Transport via `shim_client.py`
(urllib, no dependency) and `run_pilot_shim.py` — the frozen adapter `llm_agent.py` is untouched
(adapter_hash fixed at bd2a2c04778cfe57). Records: `provenance/pilot_a_shim_run/` +
analysis tools `analyze_pilot.py` / `check_r1.py` (read-only).

Result (seeds 2000-2002, plus an earlier single run of 2000):

| episode | complete | rejects | invalid | Nfree | Nform | Ntot | Blind-ID | Dinst | Dpred | audit |
|---|---|---|---|---|---|---|---|---|---|---|
| 2000#r1 | ✓ | 0 | 0 | 3 | 1 | 4 | 8/8 | 5 | 5 | ORACLE_VIOLATION |
| 2000#r2 | ✓ | 0 | 0 | 3 | 2 | 5 | 8/8 | 5 | 5 | – |
| 2001 | ✓ | 0 | 0 | 3 | 2 | 5 | 8/8 | 5 | 5 | – |
| 2002 | ✓ | 0 | 0 | 3 | 2 | 5 | 8/8 | 4 | 4 | – |

**contract compliance: 4/4** — no schema rejects, no retries, no disallowed actions,
Blind-ID = 8/8 in every episode, full provenance 4/4. The parser, the Archivist, and the audit
held up against real, unclean output (decorative ```json``` fences) without semantic repair —
the rule "exactly one semantic deposit" is the correct boundary.

**The audit fired in 1/4** (2000#r1, N_total=4 < D_pred=5). The analysis (read-only, `check_r1.py`):
the agent fully identified the law (|H|: 30→15→7→4→1) in 4 interventions, so it beat both D_pred **and D_inst=5** together —
but without breaking any theoretical bound: D_min/D_inst/D_pred are all minimax/worst-case costs (an insurance premium for robustness
across every possible law), while the agent's realized path, on a favorable law, may fall short of them. The
realized-path variance is not a flaw in the ruler: the same world 2000 fired in r1 (4) and did not fire in r2 (5).

## Pilot-A gate: **PASSED** — and Amendment A-004 (sealed)
The gate question was pre-specified: *can a real LLM operate within the frozen contract without semantic
repair and without bypass?* The answer from 9 episodes over 8 worlds: **9/9 completion, 9/9 Blind-ID=8/8,
zero schema/phase/blind rejects, zero refusals, zero gate bypass, 9/9 provenance**.
Full report: `PILOT_A_GATE_REPORT.md`. The committed claim:

> **Exact survivor-set tracking in Pilot-A (19/19), with two documented flaws in posterior weighting (17/19).**

It was not elevated to "calibrated Bayesian behavior" because 17/19 ≠ 19/19. Both flaws remained visible and were not
cleaned up after the fact: (a) `2005` a logical duplicate — two names for the same truth table, so the equivalence class took two shares
(0.333 instead of 0.2); (b) `2006` a weighting of 0.4/0.2/0.2/0.2 over four hypotheses equally consistent with
the evidence, with the lowest weight on the true law. The first is a representation flaw, the second a belief flaw — they are not to be merged.

**A-004 (sealed, `1.0-mech-A003` → `1.0-mech-A004`)** — four named rulers instead of an ambiguous D_floor:

| Ruler | Definition | Role |
|---|---|---|
| `D_floor^task(W)` | the cheapest admissible path that satisfies the **task criterion** (a majority of survivors achieve BlindScore ≥ τ_ID) | **the audit's guard** |
| `D_floor^strict(W)` | the same for a stronger criterion: consensus among survivors and their correctness on every case | diagnostic |
| `D_robust^task` | the cost of the optimal policy that does not know W in advance and guarantees the task criterion (formerly D_pred) | **the denominator of E** |
| `N_realized` | what the agent actually consumed | — |

- **`TRUE_AUDIT ⇔ N_realized < D_floor^task(W)`** — the ruler is tied to the measured task, not to knowing
  the law completely; using the strict version would have produced false alarms (weak=3 versus strict=4 in 2002 and 2005).
- The zones: `N < floor^task` → TRUE_AUDIT; `floor^task ≤ N < D_robust` → **FAVORABLE_TRAJECTORY**
  (entirely normal); `N ≥ D_robust` → AT_OR_ABOVE_ROBUST.
- **The denominator of E has not changed** (it remains D_robust^task — the floor is a validity bound, not a behavioral baseline), but
  **the ceiling has been removed**: `E_robust = D_robust^task / N_realized` is uncapped, and E>1 simply means
  a path shorter than the guarantee. The root cause: a single metric was serving two functions — performance and validity — so they were separated.
- **No retroactive effect**: the Pilot-A records and the A-003 protocol remain as they are.
- **28/28** mechanical checks (22 + 6 for A-004), among them `EarlyStopAgent` showing E=1.250 = 5/4
  in FAVORABLE_TRAJECTORY with no audit — the same shape as `2000#r1` but by rule, not by exception.
- **Supporting evidence for A-001:** in `2005`, D_robust=5 separated from D_inst=6 for the first time — an operational proof that
  *Prediction sufficiency ≠ Full identification*, i.e., that **epistemic sufficiency is task-relative**.

<details><summary>The candidate formulation before sealing (preserved for the record)</summary>

**Candidate A-004 (was unsealed — sealed later as above):**
Diagnosis: what is currently called OracleViolation is not a mathematical violation but a mismatch between
the realized trajectory and the robust reference. The candidate formulation separates **three rulers** instead of one number:

- **D_floor(W)** — instance-optimal cost under **epistemic admissibility**: the policy
  π_t: h_t → a_t sees W only through what the history has revealed; the min is then taken after W is fixed.
  A recorded warning: without the admissibility condition, clairvoyance enters through the back door; and even with it,
  the min is a **diagnostic lower envelope**, not a policy the oracle could rationally choose before
  knowing the world. (For a fixed deterministic instance, it is equivalent to a min over test sets — exactly computable.)
- **D_robust** — the cost of the optimal policy under a criterion frozen in advance (currently minimax) — this is approximately D_pred.
- **N_realized** — the path actually realized.

The zones: `N < D_floor` → **true audit** (leakage/accounting/oracle bug);
`D_floor ≤ N < D_robust` → **entirely normal** (favorable realized trajectory);
`N ≥ D_robust` → no violation, just lower efficiency than the reference in this episode.
The denominator of E does **not** automatically change to D_floor (an odd baseline — an envelope computed after knowing
the world): E_robust = D_robust/N remains descriptive and E_robust > 1 is naturally allowed, without labeling 1 as a ceiling.
The root cause: a single metric was serving two functions — a performance benchmark (D_robust) and a validity bound (D_floor) — and separating them is required.

A read-only numerical check on this batch (min over test sets, with no change to the pipeline):
seeds 2000/2001/2002 → D_floor=4/4/4 versus D_robust=5/5/4 and D_min=6. The classification:
2000#r1: N=4 **= D_floor exactly** < D_robust → a favorable trajectory, not a true audit;
the rest have N ≥ D_robust. No episode falls below D_floor → the computations and the pipeline are sound.

</details>
The more precise summary of Pilot-A: **Real LLM contract compatibility demonstrated in this pilot batch** —
no claim of general epistemic capability; and 2000#r1 = an observation about the structure of the world and the oracle (a non-minimax policy
took a favorable branch to a singleton in 4), not superiority over the optimum. **Nothing in the pipeline was modified.**
