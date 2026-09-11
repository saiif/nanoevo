"""ledger.py — tools for the amendments ledger (amendments.jsonl): verify + append.

  python ledger.py verify                 # verifies the chain and prints its head (pinned externally in git/README)
  python ledger.py append entry.json      # appends a sealed amendment (a single JSON payload)
  python ledger.py show                   # prints a summary of the entries

Rule (A.1): every amendment is sealed before the confirmatory seeds are opened, declared not silent.
"""

import json
import os
import sys

from channel import Archivist

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "amendments.jsonl")


def verify(path=LEDGER):
    ok = Archivist.verify_file(path)
    arch = Archivist(path)
    print(f"{'VALID' if ok else 'BROKEN'}  entries={len(arch.records())}  head={arch.head()}")
    return ok


def append(payload_path, path=LEDGER):
    with open(payload_path, encoding="utf-8") as f:
        payload = json.load(f)
    kind = payload.pop("kind", "AMENDMENT")
    arch = Archivist(path)
    h = arch.seal(kind, payload)
    print(f"sealed {kind} {payload.get('amendment_id', '')} -> {h}")
    return h


def show(path=LEDGER):
    for r in Archivist(path).records():
        p = r["payload"]
        print(f"{r['index']:>2} {r['hash']}  {p['kind']:<22} {p.get('amendment_id', p.get('plan_id', ''))}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "verify":
        raise SystemExit(0 if verify() else 1)
    if cmd == "append":
        append(sys.argv[2])
    elif cmd == "show":
        show()
    else:
        print(__doc__)
