# Project Structure — Transportable Epistemic Method

## Root
- `preregistration.md` — Sealed Pre-registration v1.2 (the hypothesis, the grammar, the four arms,
  the session protocol, the metrics, Researcher-Side Commitments). Not to be modified — amendments go in the ledger.
- `README.md` — implementation notes: mechanical validation, findings, amendments A-001..A-003, Pilot-A.
- `STRUCTURE.md` — this file.
- `.gitignore` — `__pycache__` only; provenance is deliberately tracked (failure is not erased).
- `.gitattributes` — `eol=lf` for all files: the sealed hashes (adapter_hash, ledger chains) are computed over the raw bytes,
  so Git is not permitted to convert line endings to CRLF on checkout.

## Code (epistemic/)
- `world.py` — grammar depth-2, oracle, D_min/D_inst/D_pred, equivalence classes, Blind-ID/X split
- `channel.py` — Schema Validator (COMMIT_SCHEMA + BLIND_SCHEMA) + Archivist (append-only, hash chain)
- `session.py` — the Experimenter gate, the isolated Verifier, the violations table (A.3 + A-003), the blind test, E
- `agents.py` — the mechanical agents (Learner/Control + violation bots A.3 and A-003)
- `llm_agent.py` — Pilot-A adapter (the frozen single-deposit rule + execution identity sealed at start and end)
- `run_mechanical.py` — the seven mechanical questions + A.3 + A-003 (22/22) → `provenance/mech_run/`
- `run_pilot_a.py` — Pilot-A: the five families + failure taxonomy → `provenance/pilot_a_run/`
- `ledger.py` — ledger tools: `verify` / `append <entry.json>` / `show`
- `amendments.jsonl` — the sealed ledger: GENESIS, A-001, A-002 (+addendum), P-001, ADAPTER_FREEZE, A-003, A-004

## Records (epistemic/provenance/)
- `mech_run/` — the latest mechanical run (protocol `1.0-mech-A004`)
- `mech_run_archive_<ts>/` — all previous runs, including those predating the corrections (failure is not erased)
- `mech_run_archive_1787334521_A002_final/` — the last run before A-003 (protocol `1.0-mech-A001`)
- `pilot_a_run/` — created when Pilot-A is run

## Running
    cd epistemic
    python run_mechanical.py          # 44/44 — automatically archives the previous run
    python ledger.py verify           # verifies the amendments chain and prints its head
    python run_pilot_a.py 3           # requires Anthropic credentials (ANTHROPIC_API_KEY or ant auth login)
