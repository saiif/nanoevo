"""Read-only: was 2000#r1's early sufficiency (N_total=4) epistemically justified?
Reconstruct the surviving hypothesis set after the agent's 4 observations and ask
whether those survivors AGREE on every Blind-ID case (i.e. evidence sufficed for the task)."""
from world import generate_accepted_world

w = generate_accepted_world(2000)
packet = w.phase_zero_packet()
sym2vec = {s: tuple(v) for s, v in packet["symbols"].items()}

# 2000#r1 agent observations (from the sealed chain):
obs = [("Kr", 1), ("Ea", 1), ("Ok", 0), ("Xp", 0)]
alive = [i for i in range(len(w.hypotheses))]
for k, (sym, out) in enumerate(obs, 1):
    v = sym2vec[sym]
    alive = [h for h in alive if w.hypotheses[h].eval(v) == out]
    print(f"after obs {k} ({sym}={out}): |H alive| = {len(alive)}  -> "
          + ", ".join(w.hypotheses[h].name() for h in alive[:8]))

print()
print(f"survivors after 4 obs: {len(alive)}  (full identification D_inst = "
      f"{__import__('world').d_min_instance(w.hypotheses, w.train_vectors, w.true_id)})")
print(f"true law: {w.true_law_name()}  (true_id in survivors: {w.true_id in alive})")

# Do the survivors agree on every Blind-ID case? If yes, evidence SUFFICED for the blind task.
blind_ID = w.blind_ID
all_agree = True
for s, v in blind_ID.items():
    preds = {w.hypotheses[h].eval(tuple(v)) for h in alive}
    truth = w.hypotheses[w.true_id].eval(tuple(v))
    tag = "AGREE" if len(preds) == 1 else "SPLIT"
    if len(preds) != 1:
        all_agree = False
    print(f"  blind_ID {s} {list(v)}: survivors predict {preds}  truth={truth}  [{tag}]")
print()
print(f"==> survivors ({len(alive)}) all agree on every Blind-ID case: {all_agree}")
print("==> interpretation:",
      "early sufficiency at N=4 was EPISTEMICALLY JUSTIFIED — the evidence collapsed H to a"
      " Blind-ID-equivalence class before full identification (which needs 5)."
      if all_agree and len(alive) >= 1 else "survivors still split on Blind-ID — would be luck.")
