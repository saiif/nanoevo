"""analyze_pilot.py — read-only analysis of the Pilot-A shim batch.
Does NOT import or modify any pipeline state beyond reading sealed logs and
recomputing oracle quantities. Nothing about D_pred is changed.
"""
import json
from world import generate_accepted_world, d_min_instance

SEEDS = (2000, 2001, 2002)
RUN = "provenance/pilot_a_shim_run"


def _segment(recs):
    """Split an append-only chain that may hold several sessions into per-session blocks.
    A session runs from EXEC_IDENTITY (or GENESIS) up to and including its SESSION_END."""
    sessions, cur = [], []
    for r in recs:
        k = r["payload"]["kind"]
        if k in ("EXEC_IDENTITY",) and cur and any(x["payload"]["kind"] == "SESSION_END" for x in cur):
            sessions.append(cur)
            cur = []
        cur.append(r)
    if cur:
        sessions.append(cur)
    return [s for s in sessions if any(x["payload"]["kind"] == "SESSION_END" for x in s)]


def parse_session(recs):
    K = [r["payload"]["kind"] for r in recs]
    end = next(r["payload"]["result"] for r in recs if r["payload"]["kind"] == "SESSION_END")
    packet = next(r["payload"]["packet"] for r in recs if r["payload"]["kind"] == "PHASE_ZERO")
    free = [r["payload"]["deposit"]["action"] for r in recs if r["payload"]["kind"] == "FREE_OBS_COMMIT"]
    freeobs = [r["payload"]["observation"] for r in recs if r["payload"]["kind"] == "FREE_OBS_RESULT"]
    formal = [r["payload"]["deposit"]["action"] for r in recs if r["payload"]["kind"] == "COMMITMENT"]
    formalobs = [r["payload"]["observation"] for r in recs if r["payload"]["kind"] == "OBSERVATION"]
    suff = next((r["payload"]["deposit"] for r in recs if r["payload"]["kind"] == "SUFFICIENCY"), None)
    rejects = sum(K.count(x) for x in ("SCHEMA_REJECT", "PHASE_REJECT", "BLIND_REJECT"))
    refus = sum(K.count(x) for x in ("REFUSED_ACTION", "FREE_OBS_REFUSED"))
    audit = "ORACLE_VIOLATION" if "ORACLE_VIOLATION_AUDIT" in K else "-"
    return dict(end=end, packet=packet, free=free, freeobs=freeobs, formal=formal,
                formalobs=formalobs, suff=suff, rejects=rejects, refus=refus, audit=audit)


def load(seed):
    recs = [json.loads(l) for l in open(f"{RUN}/s{seed}.jsonl", encoding="utf-8")]
    return [parse_session(s) for s in _segment(recs)]


def oracle_realized_path(hyps, vectors, true_id):
    """Mirror of d_min_instance's optimal loop, logging each step (read-only)."""
    memo = {}
    all_ids = frozenset(range(len(hyps)))

    def depth(state):
        if len(state) <= 1:
            return 0
        if state in memo:
            return memo[state]
        best = float("inf")
        for props in vectors:
            g = {}
            for h in state:
                g.setdefault(hyps[h].eval(props), set()).add(h)
            if len(g) < 2:
                continue
            best = min(best, 1 + max(depth(frozenset(x)) for x in g.values()))
        memo[state] = best
        return best

    state, steps = all_ids, []
    while len(state) > 1:
        best, bestd = None, float("inf")
        for props in vectors:
            g = {}
            for h in state:
                g.setdefault(hyps[h].eval(props), set()).add(h)
            if len(g) < 2:
                continue
            d = 1 + max(depth(frozenset(x)) for x in g.values())
            if d < bestd:
                bestd, best = d, props
        if best is None:
            break
        out = hyps[true_id].eval(best)
        state = frozenset(h for h in state if hyps[h].eval(best) == out)
        steps.append((list(best), out, len(state)))
    return steps


hdr = ["episode", "Cmplt", "Rej", "Retry", "InvAct", "Nfree", "Nform", "Ntot",
       "BlindID", "Dmin", "Dinst", "Dpred", "E", "Audit"]
print("EPISODE TABLE (model=claude-sonnet-5 via shim; sessions split from append-only chains)")
print("| " + " | ".join(hdr) + " |")
print("|" + "|".join(["---"] * len(hdr)) + "|")
episodes = []
for seed in SEEDS:
    w = generate_accepted_world(seed)
    dinst = d_min_instance(w.hypotheses, w.train_vectors, w.true_id)
    sessions = load(seed)
    for j, d in enumerate(sessions):
        tag = f"{seed}" + (f"#r{j+1}" if len(sessions) > 1 else "")
        e = d["end"]
        episodes.append((tag, w, d, dinst))
        comp = "Y" if e["outcome"] == "SOLVED" else e["outcome"]
        print("| " + " | ".join(map(str, [tag, comp, d["rejects"], d["rejects"], d["refus"],
              e["free_used"], e["N_interventions"], e["N_total"], e["blind_ID"],
              w.D_min, dinst, w.D_pred, e["E"], d["audit"]])) + " |")

print()
print("D_min = worst-case minimax gate | D_inst = REALIZED oracle path on the true law "
      "| D_pred = task-aligned GUARANTEE to tau (worst-case over counterfactual branches)")
print()
for tag, w, d, dinst in episodes:
    e = d["end"]
    print(f"--- episode {tag}: true law = {w.true_law_name()} ---")
    print("    AGENT free:   " + ", ".join(f"{a}={o}" for a, o in zip(d["free"], d["freeobs"])))
    fin = d["suff"]["final_hypothesis"] if d["suff"] else "?"
    conf = d["suff"]["confidence"] if d["suff"] else "-"
    print("    AGENT formal: " + (", ".join(f"{a}={o}" for a, o in zip(d["formal"], d["formalobs"])) or "(none)")
          + f"  -> declared {fin} conf={conf}")
    steps = oracle_realized_path(w.hypotheses, w.train_vectors, w.true_id)
    print(f"    ORACLE realized path (D_inst={dinst}): "
          + ", ".join(f"vec{v}={o}->|H|={n}" for v, o, n in steps))
    verdict = ("N_total < D_pred but == D_inst is NOT beaten either" if e["N_total"] < w.D_pred
               else "N_total >= D_pred (no audit)")
    print(f"    accounting: N_free={e['free_used']} + N_formal={e['N_interventions']} "
          f"= N_total={e['N_total']};  D_inst={dinst}  D_pred={w.D_pred}  audit={d['audit']}  [{verdict}]")
    print()
