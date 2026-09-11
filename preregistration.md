# Transferable Epistemic Method
## Design Document and Pre-registration for an Experiment on Transferring the Epistemic Method Across Verifiable Worlds

**Version:** 1.2 — Sealed Version (corrected Primary Endpoint + OracleViolation + Triple Freeze of Versions)
**Status:** Final Pre-registration — ready for first mechanical validation
**Date:** August 2026

---

# Part One: Hypothesis and Framework

## 1. Research Question

Can an AI agent be trained or shaped inside a verifiable world such that it does not merely learn the content of that world, but acquires an **epistemic method** that transfers to a new world it has never seen before?

By epistemic method we do not mean knowledge of the C language or of any particular set of programming rules, but a set of general capacities:

- Knowing the limits of one's certainty (Calibration).
- Formulating testable hypotheses.
- Choosing experiments that discriminate between competing hypotheses (Experimental Design).
- Revising belief after new evidence appears (Belief Revision).
- Discovering that the hypothesis space itself is incomplete (Frame Expansion).
- Building abstractions that compress multiple experiments (Abstraction).
- Knowing when the evidence has become sufficient to stop (Epistemic Sufficiency).

## 2. The Central Hypothesis

> **Competent epistemic behavior acquired in a verifiable world produces faster and more disciplined adaptation in a structurally new world, even when the object-level knowledge itself does not transfer.**

Put more plainly: what the agent learned about C may not transfer, but the way it discovers what it does not know, the way it tests its hypotheses, and the way it updates its knowledge may transfer.

## 3. Falsification Criterion

The hypothesis is not considered supported merely because the trained agent succeeds. It must outperform in a new world **that is absent from both the training data and the pretraining data**, and under the same resource budget.

If `Transfer(trained) ≈ Transfer(control)` on the pre-registered primary metric, then the method-transfer hypothesis receives no support. **A negative result is fully acceptable — the project is designed so that it can kill its own original hypothesis.**

## 4. Operational Definition of Intelligence

> **Intelligence = the capacity to build internal models, to attack them oneself, and to revise them through interaction with an independent reality that resists them.**

An intelligent system: (1) builds an interpretation, (2) commits to predictions arising from it, (3) intervenes in the world, (4) allows reality to resist its interpretation, (5) revises its knowledge upon failure. This is an extension of critical rationalism (Hypothesis → Test → Falsification → Revision), where the external world is not a teacher handing out the solution but a **resisting reality**. The basic loop at the level of belief:

`Belief(t) → Action → Reality → Error → Belief(t+1)`

Knowledge arises from the collision between what the system believes and what the world permits.

---

# Part Two: The First Training World (C)

## 5. Why C

The C language offers a highly verifiable environment: a compiler, a runtime, sanitizers (ASan/UBSan), declared and hidden tests, counterexamples, memory errors, and deterministic execution in most cases. The compiler is not an evaluation tool — it is **part of the laws of the world**. If the agent believes its program is valid and the compiler rejects it, or ASan reveals a defect, then `Belief ≠ Reality`, and learning occurs from the difference.

Mandatory technical note: undefined behavior makes the reward non-deterministic if one relies on ordinary execution alone; therefore ASan and UBSan are mandatory in every evaluation build — they convert "may fail later" into "fails now with a clear message."

## 6. Principle: Reward Guides, Evidence Teaches

A scalar reward such as `R = -1` tells the agent that something bad happened but does not build causal understanding. Hence a separation between **Reward** (which determines the direction of selection) and **Evidence** (which contains the causal structure: sanitizer traces, hidden test failures, counterexamples, runtime behavior, performance, memory).

> **Reward guides, Evidence teaches.**

## 7. Constraints Before Weights (Gates Instead of Weighted Sum)

A formula such as `R = 0.4·Compile + 0.4·Tests + 0.2·Safety` is not permitted, because it is a market in which the agent can buy a memory leak with test points. The alternative is a strict gated ordering:

`Compile → Safety → Correctness → Efficiency → Elegance`

```
Eligible = CompileGate ∧ UBGate ∧ MemoryGate
R        = PassedHiddenTests / TotalHiddenTests   (only if Eligible = 1)
```

Efficiency and elegance come **after** correctness, not in place of it. Any reward on an intermediate step (such as mere compilation) has only temporary validity and withers as capability advances.

## 8. Protection Against Cheating on Tests

- Test files and the Makefile are structurally outside the agent's write permissions.
- Part of the tests is **hidden** and unseen by the agent during work; the final verdict rests on it.
- Tests use multiple, varying inputs to prevent memorizing outputs.
- The final verdict is issued by an independent verifier that reruns the program itself, not by the agent's claims.

---

# Part Three: Learning Architecture

## 9. Two Timescales of Learning: Fast and Slow

**Fast Learning (during the agent's lifetime):** `Experience → Episodic Memory`. The task, hypotheses, attempts, evidence, diagnoses, errors, corrections, and the final outcome are all stored — without changing the weights. Learning at the level of the system.

**Slow Learning (Consolidation):** `Episodes → Filtering → Training → θ(t) → θ(t+1)`. Recurring knowledge turns into a change within the weights. The functional architecture parallels Complementary Learning Systems: a fast episodic store plus slow consolidation ("sleep"). What the system needed to explicitly recall yesterday becomes part of its intuition tomorrow.

## 10. Context Distillation

If the agent solves a problem using retrieved memory, the trajectory is conditioned on it. Training on `Task + Memory → Solution` teaches permanent dependence on memory. The alternative: training on `Task → Solution`, where the target is extracted from a teacher who had access to the memory — pushing knowledge from the context into the weights.

A fundamental warning: **Distillation ≠ Proof of Abstraction.** Distillation is the transfer mechanism; the actual proof comes exclusively from far transfer across domains (a concept learned in linked lists being tested in a parser or an entirely different structure).

## 11. Abstraction: Understanding as Predictive Compression

Declarative knowledge does not count — the agent may eloquently articulate the Ownership principle and then write a use-after-free. The criterion for abstraction is **behavioral**, and follows Minimum Description Length logic:

```
Before: L(E₁) + L(E₂) + … + L(Eₙ)
After:  L(Concept) + Σ L(εᵢ)   where εᵢ are small exceptions
```

If description length decreases while predictive power on unseen cases is preserved, genuine epistemic compression has occurred:

> **Understanding ≈ Predictively useful compression.**

The condition is dual: Compression + Prediction — compression alone may produce a beautiful but false story.

## 12. The Risk of Self-Collapse (Model Collapse)

In the chain `θ₀ → θ₁ → θ₂ …`, each generation trains on the output of its predecessors, so the distribution narrows: loss of diversity, forgetting of skills, inflation of a single style, accumulation of invisible errors. Every consolidation cycle must include: diverse original data, experiments from outside the system, held-out evaluation, KL coupling to the previous version, regression testing against old checkpoints, and independent external sources.

> The system feeds on its own experiences, but it does not live on them alone.

## 13. Identity: The Institution, Not θ

The true entity is not θ but the complete institution:

`Organism(t) = (θₜ, Memoryₜ, Curriculumₜ, Goalsₜ, Archiveₜ, EvaluationHistoryₜ)`

The weights are tissue that renews itself; identity is the continuity of memory, learning, purpose, and history. Ancestors (checkpoints) are retained, and every generation is tested against them — a generation that loses important prior capabilities represents a discontinuity that must be measured, not hidden.

---

# Part Four: The Epistemic Constitution

## 14. Separation of Powers

The Reward is not the whole constitution; the true constitution is the separation of powers within the system. The six institutions:

| Institution | Function |
|---|---|
| **Learner** | Proposes hypotheses and solves problems |
| **Experimenter** | Executes interventions strictly according to protocol |
| **Verifier** | Decides what actually happened, not what the Learner claims happened |
| **Adversary** | Searches for tasks that break current capabilities |
| **Skeptic** | Tries to refute the claim that a given capability has been learned or abstracted |
| **Archivist** | Preserves history as it was before the outcome appeared, and prevents its rewriting |

The Learner has no authority to modify any other institution. The governing principle:

> **No component judges itself.**

## 15. The Skeptic: Refuting Knowledge, Not the Solution

The Adversary asks "which task defeats you?", whereas the Skeptic asks: **"what do you claim to have learned, and how do I break that claim?"** Its tools: symbol substitution, surface change, inverting correlations present in training, transferring the concept to a new context, introducing distractors, and edge cases. If performance collapses: `Apparent abstraction ≠ Real abstraction`. Critical rationalism here is architecture, not a philosophical citation, and it operates on two levels: within the Episode (refuting the hypothesis) and across generations (refuting the claimed capability).

## 16. The Risk of the Closed Epistemic Loop (Epistemic Bubble)

More dangerous than collapse:

`Beliefs → Experiments → Data → Training → Stronger Same Beliefs`

A system that chooses its own questions, its own data, and its own evaluation may build a world that confirms its beliefs even if all the data is technically correct. Structural prevention: human-sourced tasks, independently generated worlds, external benchmarks, adversarial tasks, hidden evaluation, separate generators, and verifiers frozen outside the learner's control. The rule applies recursively to every layer (even the Adversary needs an independent reality above it):

> The system cannot be the scientist, the world, and the judge all at once.

---

# Part Five: The Second, Invented World

## 17. Why an Invented World

Python or Rust are not suitable for measuring transfer: the model has seen enormous amounts of both in pretraining, so one cannot distinguish "method transfer" from "content retrieval." The second world must be **entirely invented**: no prior knowledge, no meaningful names, no published laws. Any superiority shown in it has no explanation other than the method.

## 18. A Family of Worlds Generated by a Grammar, Not a Single World

A single fixed world reinstates the overfitting trap (and designers might leak their own intuitions into it). Hence:

`W ~ Grammar(seed)`

The grammar generates a complete family of worlds. Evaluation occurs on **held-out** worlds (held-out seeds) unseen by the learner, the curriculum generator, or the designer during training. Surface symbols are meaningless (⊗, ◊, ℓ₄ — neither "fire" nor "water," to prevent importing linguistic semantics), and the true laws operate on **hidden properties**, not on the symbols — so a rule discovered on one symbol generalizes to everything that shares that property.

## 19. The Five Required Properties of Every World

1. **Fixed, verifiable laws** — no randomness except when declared and intentional.
2. **A plurality of plausible hypotheses** — the solution is not brute force.
3. **Experimentability** — the agent chooses interventions that reveal new information.
4. **Latent structure** — general, discoverable rules, not a random mapping table.
5. **Internal transferability** — a rule discovered in one region is tested in a new region with a different surface.

## 20. Primitives

- **Property check:** `hasProp(x, pᵢ)` — the only permitted read on the hidden world.
- **Relation:** `sharesProp(x, y, pᵢ)` or an ordering over a hidden numeric value.
- **Transformation:** `flip(pᵢ)`, `set(pᵢ, v)`, `swap(pᵢ, pⱼ)` — actions on properties, not on symbols.
- **Primitive temporal memory:** `count(action, k)` — the only primitive that introduces time.

## 21. Operators

- **Logical:** ∧, ∨, ⊕, ¬ on conditions.
- **Causal sequencing:** the output of one law becomes a condition for another.
- **Temporal guard:** the condition is evaluated on the previous state, not the current one.
- **Regime switch:** a latent variable switches the set of active laws.

## 22. The Complexity Ladder and Its Computational Classes

| Depth | Structure | Theoretical Class |
|---|---|---|
| 1–2 | a rule from one property or a conjunction of two conditions | Propositional logic |
| 3 | a law depending on the outcome of a prior law | Causal DAG compositions |
| 4 | dependence on history/context | Finite-state behavior |
| 5 | a latent variable or switching regime | HMM / POMDP-like |

The benefit: each theoretical class has identifiability that is solved or nearly solved — conditions are proven, not merely hoped for.

## 23. Forbidden Rules

Not permitted: laws on symbol names, individual exceptions without structure ("⊗ specifically behaves differently"), undeclared randomness, rules that are not experimentally distinguishable, unverifiable cases, or surface shortcuts tied to naming. Every law is part of the declared or hidden support of the grammar, not a whimsical exception.

## 24. The Identifiability Condition

> **Ambiguity initially, Identifiability eventually.**

At the outset, multiple hypotheses are consistent with the evidence; after sufficient interventions, distinguishing between them must become possible. If two hypotheses remain indistinguishable under every possible intervention, the flaw lies in the world's design, not in the agent.

## 25. D_min and Built-In Difficulty Calibration

For every world, the oracle computes or estimates the minimum number of interventions theoretically required to distinguish the correct law: `D_min`. The generator **rejects** any world outside the window (initial proposed value: `4 ≤ D_min ≤ 15`; the numbers are calibratable, the idea is not). D_min is also a quantitative definition of difficulty, truer than a layer counter.

**Strict constraint:** D_min is an oracle-side concept exclusively. The agent never sees it, and it is never used as feedback during the session — otherwise the agent would learn "how much I am supposed to need" instead of judging for itself. It is a post-hoc metric only.

## 26. Resistance to Shortcuts and Statistical Contamination

Counterintuitive laws are necessary (to prevent rewarding retrieval from human priors) but are not sufficient on their own: a world that is consistently "anti-human" teaches the meta-rule "invert your intuition." The solution is a balanced mixture: intuitive + counterintuitive + neutral + hybrid, with continuous full permutation of symbols.

Deeper still: any **statistic that is fixed across worlds** is exploitable (if 70% of worlds are sequential, the agent learns a prior on the benchmark itself). The solution: hierarchical randomization — drawing random mixture weights for each batch, then drawing worlds from them. The dividing line:

> **Learning the support of the distribution is legitimate (it is the meta-learning being sought); exploiting fixed frequencies is contamination.**

## 27. Deliberately Incomplete Disclosure (Measuring Frame Expansion)

To measure the discovery of a frame's incompleteness, the agent is not given the full grammar — it is disclosed only a **subset** (for instance: "the laws are logical over properties") while the world uses an undisclosed primitive (a temporal guard, for example). A mature agent, after all its disclosed hypotheses fail to explain the evidence, arrives at: "the disclosed hypothesis space is incomplete." What is disclosed and what is hidden are sealed by the Archivist before the session — **calibrated deception of the agent is a legitimate, documented measurement tool.**

## 28. Unknown Unknowns: The Operational Signal

It is not enough to distribute probabilities within a set of hypotheses; one must detect that the set itself is incomplete. The quantitative trigger: if `P(Evidence | Hᵢ)` is low for all current hypotheses for a sufficient period, the probability that the space is incomplete rises. This signal triggers the expansion process, and **its accuracy is then held to account afterward** — it does not enter the reward directly.

---

# Part Six: Experimental Design

## 29. The Four Arms

| Arm | Description | What It Isolates |
|---|---|---|
| **1. Trained** | full epistemic upbringing; chooses its own experiments | the central claim |
| **2. Control** | same base model and resources, without upbringing; chooses its own experiments | baseline |
| **3. Yoked** | does not choose; receives the same sequence of observations produced by Trained | interpretation of evidence isolated from choice of experiments |
| **4. Random** | random interventions under the same budget | the value of experimental design itself |

## 30. Decomposing the Differences

The expected ordering if the hypothesis holds: `Random < Yoked < Control < Trained`. The differences themselves are the information:

- **Random → Yoked:** the value of a directed versus a random information sequence.
- **Yoked → Trained:** the quality of exploiting the same evidence (interpretation and abstraction).
- **Control → Trained:** the central claim — the effect of epistemic upbringing.

If Yoked catches up to Trained, then the entire method lies in interpretation, not in experiment design. Any reversal in any link is precise falsifying information about the failing component. The analysis is built on what the arms actually establish, not on their labels.

## 31. Resource Control (Condition for the Validity of Causal Inference)

Held fixed across all arms: the number of model calls, context length, the number of interventions, the number of free observations, token budget, tools, available memory, and wall-clock time where applicable. Any difference in resources invalidates the inference.

## 32. Calibrating the Difficulty of the Experiment Itself

Before the main experiment, Control alone is trialed on a sample of worlds: a success rate of ~95% means a ceiling that hides differences, and a success rate of ~2% means a floor that hides them. A difficulty window is chosen so that the experiment falls within its own "zone of proximal growth" — the same principle as the capability edge, applied to the experiment rather than to the learner.

---

# Part Seven: Session Protocol

## 33. The Governing Principle: The Session Is a Contract, Not a Conversation

Every formal epistemic act (hypothesis, prediction, experiment, declaration of inadequacy, declaration of sufficiency) passes exclusively through a sealed form deposited with the Archivist, and has no meaning outside it. Free speech is permitted but carries no formal weight. The reason: the most dangerous skill of a language model is implicitly renegotiating the rules through talk; a loose protocol erodes sentence by sentence.

## 34. Phase Zero: Delivery

**The agent receives only:** (1) the symbols visible in its initial region, (2) the available actions, (3) the **disclosed** portion of the primitives, (4) the budget (number of interventions and mandatory predictions).

**It never sees:** D_min, the hidden primitives, the depth, the seed, the logic of the hidden tests, the true law. Everything disclosed and everything hidden is sealed before the session begins.

## 35. Free Exploration

A small number of free observations before the first commitment (3–4), because forcing hypotheses before any evidence produces a theatrical certainty that contaminates the calibration data. Binding conditions: the same number and type **for all arms**, deducted from the budget, logged with the Archivist, treated as a separate phase, and excluded from the primary Brier scoring.

## 36. Precommitment — the Heart of the Protocol

Before **every** formal intervention, the agent deposits with the Archivist:

1. The current set of hypotheses `H(t)` with their weights `P(Hᵢ)` — including a `P(None of current hypotheses)` term where applicable.
2. The chosen experiment and why.
3. The expected outcome **under each hypothesis**, with its probabilities.

The Experimenter executes nothing before the deposit is complete — this is the sole barrier against epistemic retrofitting ("I knew it all along"). Calibration curves are built from these deposits exclusively, not from the agent's own account of itself.

## 37. The Basic Cycle

`Belief(t) → Experiment(t) → Prediction(t) → Commit → Observation(t) → Revision → ↺`

## 38. Types of Knowledge Update (Mandatorily Classified)

After every observation, the update is classified as:

- **Reweight:** same hypotheses, new weights.
- **Revise:** modification of an existing hypothesis.
- **Expand:** acknowledging the space's incompleteness and adding a new family.

This turns Frame Expansion into a sealed, measurable event, not a post-hoc analysis.

## 39. Declaration of Inadequacy (Model Inadequacy Declaration)

A formal act: "my current hypotheses, taken together, give a likelihood below threshold for the evidence; I request expansion of the space toward such-and-such family." Measured from it: detection time, latency since the first anomalous evidence, false alarm rate, diagnostic accuracy, and the success of the expansion in improving prediction. **Mandatory separation between two levels:**

- **Detection:** did it know the frame was incomplete?
- **Diagnosis:** did it know how it was incomplete?

An excellent agent may discover the inadequacy before it has the vocabulary to name it — conflating the two levels does it an injustice (in the history of science itself, the gap between "something is wrong with the frame" and "here is the alternative" has sometimes taken a generation).

## 40. Free Reasoning

It is recorded and is suitable for later qualitative study, but it **does not count as a commitment and does not change any score.** Measurement rests exclusively on what is sealed before the results appear:

> **Free reasoning is not epistemic commitment.**

## 41. Session Endings

- **Solved:** a final declared model + passing the challenge cases.
- **Budget Exhausted:** interventions ran out.
- **False Certainty:** a declared high confidence was immediately broken by the hidden cases.
- **Correct Incompleteness:** it declared that the evidence was insufficient to discriminate, **and was correct** — this counts as an epistemic success, not a failure.

## 42. Declaration of Sufficiency and the Blind Test

The natural ending: an **Epistemic Sufficiency Declaration** — "the evidence is sufficient, and here are my predictions with such-and-such confidence." After this, it is not asked about the law verbally; it is given a **Blind Prediction Test**: new cases, permuted symbols, unvisited regions, boundary cases, cases that specifically discriminate between the competing hypotheses, and transfer within the world (and sometimes to another world from the same grammar). The predictive outcome matters more than the phrasing — we measure behavior, not rhetoric, and an agent that states the law incorrectly yet predicts correctly is better than the reverse, and both cases are informative.

---

# Part Eight: Metrics

## 43. The Six Metrics

| # | Metric | Question | Measurement |
|---|---|---|---|
| 1 | **Calibration** | Does declared confidence match actual accuracy? | Brier score / calibration curves on the sealed deposits |
| 2 | **Falsification Quality** | Did it design an experiment that could have proven it wrong? | discriminative power of the chosen experiments between its deposited hypotheses |
| 3 | **Experiment Efficiency** | How much useful information per unit cost of interventions? | comparison against D_min / oracle policy |
| 4 | **Abstraction Transfer** | Does the concept transfer to a new surface/domain? | predictive performance on permuted surfaces — behavioral, not verbal |
| 5 | **Model Inadequacy Detection** | Does it detect that its hypothesis space is incomplete? | latency, false positives, success of expansion; Detection ≠ Diagnosis |
| 6 | **Epistemic Sufficiency** | Does it know when the evidence is enough? | distance of its declaration point from the optimal stopping boundary |

## 44. D_min Versus Optimal Stopping

Two separate concepts: D_min measures the minimum under an **optimal experimental design**; optimal stopping measures, given the evidence actually collected, **when it was best to stop**. SPRT is used as a normative reference where its conditions apply, with the acknowledgment that it is not a general solution (multiple hypotheses, adaptive interventions, expansion, POMDP-like worlds) — in those cases, generalized sequential decision rules apply. All bounds are oracle-side; the agent never sees them.

## 45. Epistemic Regret

`Regret = Cost(agent policy) − Cost(oracle policy)`

Computed over: the number of interventions, information gain, stopping, total resources — how much was lost to weak epistemic decisions.

## 46. Information Gain: Selection, Not Reward

Information gain is not placed in the reward (the agent would game the priors: declaring artificial uncertainty and then "resolving" it). The alternative: the prior is sealed before the experiment, compared against the true outcome, calibration monitors its honesty, and the more efficient trajectories are **selected afterward** for training. Whoever cheats on the first metric is exposed by the second:

> **The metrics guard one another. No metric judges itself.**

## 47. The Archivist: Protecting the Direction of Epistemic Time

It prevents epistemic retrofitting. It stores, before any outcome appears: beliefs and their probabilities, predictions, the chosen experiment, the disclosed family, the state of free exploration, declarations of inadequacy, the declaration of sufficiency, and what was disclosed/hidden from the grammar. After the evidence appears: modifying history is forbidden. `Belief(before) ≠ Belief(after)`, and the difference between them is the material being measured.

## 48. The Permanent Separation: Evidence ≠ Interpretation

The evidence may be correct while the diagnosis is wrong — and this case itself is valuable for learning. The two are always stored separately.

## 49. The Episode: The Original Record

The Episode is not a training sample; it is the complete record:

`Task | Prior Context | Beliefs | Actions | Predictions | Evidence | Interpretations | Updates | Outcome`

From it are later derived: SFT samples, preference pairs, RL trajectories, memory lessons, failure examples, evaluation cases. No single training format is stored as the original ground truth.

## 50. Memory Dependency

`MemoryDependency = P(success | Task+Memory) − P(success | Task)`

If this decreases after consolidation while performance is maintained, then part of the knowledge has migrated into the weights — a direct measure of the success of "sleep."

---

# Part Nine: Training, Selection, and Ablation

## 51. The Training Pipeline

`Raw Episodes → Verification → Deduplication → Novelty → Difficulty → Failure Taxonomy → Trajectory Selection`

Then, depending on the stage: `SFT → Preference Training → RLVR`. The model is not trained on everything it produces; filtering is the most expensive part of the system — reliability before quantity.

## 52. Selection Instead of a Curiosity Reward

No "+0.3 because you ran a nice experiment" — any direct reward for experimentation is exploited through theatrics. Instead, among correct solutions: in SFT and preference data, the trajectory that methodically chose discriminating experiments is preferred over the one that arrived by chance or through random tweaks. **Selection pressure plants the method into the weights without defining an exploitable notion of "curiosity."**

And a deeper Goodhart warning: after several generations, the model may learn to produce the selected **behavioral shape** (hypothesis → experiment → fix) without its epistemic function. Hence the quality criterion is neither the shape of the trajectory nor its length, but: `Useful information acquired / Cost of experimentation` — did each experiment produce a measurable reduction in the space of possibilities?

## 53. Ablations (a Condition for Understanding Any Positive Result)

If transfer appears, its cause must be known. Two kinds:

**Structural:** without Skeptic / without Archivist / without Adversary / without calibration selection / without consolidation / without context distillation.

**Behavioral:** without mandatory prediction / without separating evidence from interpretation / selection by success alone rather than by search efficiency / without frame expansion / without memory retrieval.

The real question: does removing the part change **the method** or only its shape? An institution that can be removed without effect is not central — and with this, the Epistemic Architecture is converted from an elegant design into a theory that is experimentally decomposable.

## 54. Protecting the Transfer Test from Contamination

The second world is generated from held-out seeds unseen by the learner, the curriculum generator, or the designer during training. Preferred: held-out grammar combinations, held-out symbol mappings, independent task sources, and independent generator families in some tests — to prevent generator overlap from masquerading as generalization.

## 55. The Execution Ladder: The Minimal Experiment First

**The minimal stage (no GPUs, no weight updates):** a frozen model; upbringing occurs via scaffolding + memory + structured commitments + selection + institutions. This separates two questions:

- **Q1:** does epistemic scaffolding alone improve adaptation across worlds?
- **Q2:** can this behavior later be compressed into the weights?

Failure of Q1 removes the justification for moving to costly RL. Its success makes consolidation a second, independent question.

**The second stage (upon a positive signal):** thousands of documented trajectories → training → comparing θ₀ against θ₁ on worlds that did not appear during consolidation. Evidence of the transformation of experience into internal capability: fewer experiments, less retrieval, fewer corrections, less context — with equal or better performance.

## 56. The Strong Success Criterion

Success is not more answers, but the system entering a world it does not know and then: (1) acknowledging its ignorance with a calibrated degree, (2) building competing hypotheses, (3) choosing an experiment that discriminates between them, (4) recording its predictions before the outcome, (5) updating its beliefs according to the evidence, (6) discovering the frame's incompleteness when it occurs, (7) building transferable abstractions, (8) knowing when the evidence is sufficient, (9) predicting well what it has not seen.

What is expected to transfer is not malloc, nor pointer arithmetic, nor ownership as a subject matter, but:

> **Not knowledge, but a method for producing knowledge.**

---

# Appendix A — Researcher-Side Commitments
## Commitments on the Researcher's Side (sealed before the first official run)

The founding principle of this appendix: a system that binds its agent to commitment before knowledge equally binds its researchers. **The Archivist judges us too.**

## A.1 — Pre-registration

Sealed before the first measurement session, and not amended after seeing any result:

- **The single primary metric (Primary Endpoint):** experimentation efficiency **conditioned on success** in the second world, in the version 1.2 formulation:

  ```
  Success = 1[BlindScore ≥ τ_blind]                    (blind success criterion, frozen in advance)

  E = min(1, D_min / N_agent)    if Success = 1
  E = 0                          if Success = 0

  OracleViolation = 1[Success = 1 ∧ N_agent < D_min]
  ```

  where `0 ≤ E ≤ 1` and higher is better (E = 1 means oracle-level performance in the number of interventions). Justification: the unconditioned formula `N/D_min` equates an agent that solved it in 5 experiments with an agent that consumed 5 and failed the blind test — a direct contradiction of the document's own principle that knowledge is held accountable predictively, not by the shape of the investigation. This is a gate at the level of the metric, following the same logic as the gates of the C world: **efficiency does not buy a pass over knowledge.**

  **The OracleViolation rule:** the case `N_agent < D_min` with a blind success is theoretically possible (luck on the test, an insufficiently strong blind test, or an error in the computation of D_min itself). It is not hidden by the min, and it is not counted as superhuman performance: every OracleViolation **mandatorily opens an audit event** on the measurement apparatus. The principle: if the learner exceeds a bound we called a theoretical minimum, the first thing to be doubted is our own measuring instrument, not a declaration that the agent has defeated mathematics — falsification reaches the tools of measurement before it glorifies the one being measured.

  The definition of "passed" is frozen in advance (BlindScore ≥ τ_blind on hidden predictions — not merely `Solved` as declared by the agent), the threshold is calibrated from pilot data, and any modification to it is a sealed amendment lodged with the Archivist **before the confirmatory seeds are opened**, declared openly rather than silently. All other metrics are secondary or exploratory.
- **Sample size:** number of worlds, number of seeds, number of sessions per arm.
- **Exclusion conditions:** defined in advance (technical failure, protocol violation, a world outside the D_min window).
- **Statistical tests and significance threshold**, with correction for multiple comparisons on the secondary metrics.
- **The experiment's own stopping rule.**
- **Strictly forbidden:** redefining success after seeing the results, or promoting a secondary metric that "succeeded" to primary status.

## A.2 — Frozen Training Regimen

"Epistemic upbringing" is converted from a description into a protocol frozen before any transfer measurement:

- the number of C-world sessions, their difficulty distribution, and the curriculum ordering.
- when memory is used, and how lessons are selected and injected.
- the criteria for selecting trajectories.
- when training stops and what counts as the end of the upbringing.

**The hard rule:** it is forbidden to modify this regimen based on the first transfer results. Any subsequent modification = an independent **Experiment 2** with a new pre-registration, not a "minor improvement" within the same experiment — this is the barrier against "let's add a bit more upbringing until the difference shows up" (p-hacking dressed as methodology).

## A.3 — Institutional Independence Limits

- **Verifier and Archivist:** deterministic code built on the grammar/oracle, not an LLM. The grammar fully permits this.
- **Skeptic and Adversary:** if the same model family is used, it must be stated in writing that the independence is **functional, not fully epistemic** — a critic that shares the learner's blind spots is blind in the same places. The minimal version begins with the same model, on condition that this constraint is explicitly recorded; the later version uses a different family or a heterogeneous ensemble.
- Transparency about this constraint is part of the validity of any conclusion.

---

# Appendix B — Mechanical Validation Plan (First Run)

## B.1 — Objective

The first run is not an experiment to prove the hypothesis but **mechanical validation of the protocol itself**. Most failed experiments do not fail at the hypothesis — they fail at a leaky pipe no one noticed.

## B.2 — Specifications

- One world, depth 2 only, a simple grammar that is fully computable (propositional over hidden properties).
- Two arms only: Learner and Control.
- A frozen model, no weight updates, no statistical claims.
- Verifier and Archivist as deterministic code from day one.

## B.3 — Success Questions (all mechanical)

1. Is there any path by which the agent reaches information before it is sealed? (leakage)
2. Does the Experimenter actually reject every intervention lacking a complete deposit?
3. Is the blind prediction test truly blind?
4. Does the commitment format hold up in practice, or does it break on cases we did not anticipate?
5. Is the Episode stored in full, with strict separation between Evidence and Interpretation?
6. Are declarations of inadequacy and sufficiency issuable and sealable without ambiguity?
7. Is D_min computed correctly for the simplified grammar (manual verification possible at depth 2)?

## B.4 — The Escalation Ladder

`Mechanical Validation → small Pilot (measuring the metrics without claims) → sealing the Pre-registration → the Main Experiment (4 arms) → Ablations upon the appearance of transfer`

A failure of mechanical validation is an excellent result: we fix the mechanics before any science.

---

# Appendix C — Pre-Freeze Amendments (fixed in Version 1.1)

## C.1 — Independence of the Frame Expansion Metrics

The fifth metric remains entirely independent of D_min (which answers a different question: the theoretical minimum for discriminating between hypotheses). Its three metrics:

```
FPR_expand        = False Expansion Declarations / Opportunities for Expansion Decision
DetectionLatency  = the time from the first anomalous evidence to the declaration of inadequacy
DiagnosisAccuracy = is the proposed family actually the hidden one?
```

The goal is neither "Never expand" nor "Always expand" but: **Expand when the current model class actually becomes inadequate.** We neither punish caution nor reward pathological doubt, and the separation of Detection from Diagnosis remains as it is.

## C.2 — The Machine-Verifiable Commitment Channel

The scientific principle is not "JSON specifically" but the existence of a **machine-validatable commitment channel** (and in practice JSON is excellent). The frozen rule:

> Whatever is not accepted by the Schema Validator and sealed by the Archivist has no formal epistemic existence.

And stronger than "free reasoning does not count": **the Verifier structurally does not need the agent's reasoning at all** — it sees only the structured commitment + the intervention + the observed outcome. The system is blind to the chain-of-thought by construction, not by discipline.

## C.3 — The Statistical Unit

The basic unit of analysis: **World × Agent Assignment**. Measurements within a single world are repeated observations, not independent samples; repetitions on the same seed are treated as nested replicates, not as independent worlds. This prevents pseudo-replication.

## C.4 — Seed Partition

Before any run:

```
Seeds = S_mechanical ∪̇ S_pilot ∪̇ S_confirmatory   (a strictly disjoint partition)
```

No reverse movement: a seed that entered mechanical or pilot becomes **burned as confirmatory forever**. And confirmatory seeds are never opened before the pre-registration is sealed.

## C.5 — Protocol Violation Decision Table (frozen in advance)

| Case | Pre-committed Decision |
|---|---|
| invalid JSON/schema | a single retry only, without revealing any result |
| probabilities do not sum to 1 | schema failure → the same single retry |
| a disallowed intervention | rejected before execution and consumes an attempt per the frozen rule |
| rejection/failure after the retry | **Agent protocol failure** — counted against the agent, not a research exclusion |
| infrastructure crash outside the agent's control | **Technical exclusion**, recorded in advance |
| leakage of hidden information | the session/world is invalid + an incident is opened; it does not enter the confirmatory analysis |

The governing principle: `AgentFailure ≠ InfrastructureFailure` — excluding malformed outputs as "technical problems" artificially improves the agent's performance, and is a form of retrofitting at the level of the researcher.

## C.6 — The Triple Freeze of Versions (Frozen Schema + Protocol + Grammar)

Every Episode carries **three version identifiers**, not one:

```
schema_version   + schema_hash      (the structure of the deposits)
protocol_version + protocol_hash    (the semantics of the protocol: session rules, budget, violations)
grammar_version  + grammar_hash     (the method of generating the world: primitives, operators, the D_min window)
```

Justification: changing the protocol's semantics or the method of generating the world changes the experiment **even if the JSON remains literally identical** — the schema hash alone protects the form, not the meaning. Any change at any layer = a new sealed version, and the analysis never mixes versions across any of the three layers. An amendment made after hundreds of sessions without triple versioning mixes protocols within "one experiment" — the exact kind of silent leakage the whole system was built to prevent.

## C.7 — Scope of Mechanical Validation

Time-guarded dynamics (depth 4) exist in the design but **do not enter mechanical validation** — the first run is depth 2 exclusively, as specified. Temporal/state worlds enter at the pilot stage. The first goal is testing the pipe, not the richness of the world.

## C.8 — The Final Sign-Off Formula (Version 1.2)

The project is considered frozen and ready to run once the sealing of the ten elements is complete:

```
Hypothesis
+ Primary Endpoint (E)
+ Blind Success Criterion (τ_blind + the amendment rule)
+ Statistical Unit
+ Seed Partition
+ Protocol Violations Table
+ Frozen Training Regimen
+ Frozen Schema
+ Frozen Protocol
+ Frozen Grammar
```

Then the mandatory path:

```
Mechanical Validation → Pilot → Freeze → Confirmatory Experiment
```

The question of the first run is not "is the method-transfer hypothesis true?" but: **"does the machine we designed work as the paper says it does?"** — the correct separation between the validity of the measuring instrument and the scientific result it will measure. And with these specific elements, the phrase "version for freezing before the first official run" in the document's header becomes literally applicable, not merely a title.

---

# Conclusion: The Final Principle

The project does not require trust in the agent's speech, nor even in the researchers' enthusiasm. Everything reduces to:

`Precommitment → Intervention → Independent Evidence → Revision → Blind Prediction`

We do not ask: does it look like it is thinking scientifically? We ask:

- What did it believe before it knew?
- What did it test?
- What happened?
- Did its expectations change correctly?
- Was it later able to predict what it had not seen?

This is the proposed operational definition of the **Transferable Epistemic Method**.

**The final hypothesis:** shaping competent epistemic behavior inside a verifiable world can improve the speed and quality of adaptation in a structurally new world, even when the object-level knowledge does not transfer between the two worlds. And if this does not occur under a controlled, reproducible experiment, then the system is designed to tell us so clearly.

> **Building a system that does not merely learn answers, but learns how to make reality correct its ideas — and subjects its own builder to the same rule.**
