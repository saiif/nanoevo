"""check_raw_proposal.py — تحقّق قرار 3: المستوى الخام محفوظ قبل التصديق، والالتزام المُصدَّق وحده يحرّك.

يثبت أن DuplicationRate صار قابلًا للقياس: المفتاح المكرّر يُبتلَع في dep المُفكَّك (json.loads يبقي
الأخير) لكنه محفوظ في RAW_PROPOSAL — فلا يمكن قياسه إلا من الخام.
"""

import json
import os
import tempfile

from world_b1 import generate_accepted_world_b1
from session_b1 import SessionB1
from llm_agent_b1 import JSON_RE

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def duplicate_key_count(raw):
    """عدد المفاتيح المكرّرة في أي كائن JSON داخل الخام (json.loads وحده يخفيها).

    يمسح كائنات JSON ضمن النص (النص قد يبدأ بتفكير حر)، ثم يفكّ كلًّا مع object_pairs_hook.
    """
    dups = [0]

    def hook(pairs):
        keys = [k for k, _ in pairs]
        dups[0] += len(keys) - len(set(keys))
        return dict(pairs)
    for m in JSON_RE.finditer(raw):
        try:
            json.loads(m.group(0), object_pairs_hook=hook)
        except json.JSONDecodeError:
            continue
    return dups[0]


class FakeAgent:
    def __init__(self, raw):
        self.last_raw = raw
        self._dep = json.loads(raw[raw.index("{"):])      # كما يفعل _extract (json.loads يطوي التكرار)

    def deposit(self):
        return self._dep, "reasoning..."

    def notify(self, msg):
        pass


def session_for(raw):
    tmp = tempfile.mkdtemp()
    s = SessionB1(generate_accepted_world_b1(3000), FakeAgent(raw),
                  os.path.join(tmp, "raw.jsonl"), os.path.join(tmp, "raw.side"))
    return s, os.path.join(tmp, "raw.jsonl")


def raws_in(log):
    return [json.loads(l)["payload"] for l in open(log, encoding="utf-8")
            if json.loads(l)["payload"]["kind"] == "RAW_PROPOSAL"]


def main():
    # --- مشهد أ: إيداع صالح — الخام يُختم، والمُصدَّق يُحرّك الجلسة ---
    valid = ('reasoning A\n{"type":"COMMITMENT","hypotheses":{"H00":0.5,"H01":0.5},'
             '"action":"EXPERIMENT(Qz)","predictions":{"outcome=1":0.5},"update_kind":"INITIAL"}')
    s, log = session_for(valid)
    dep = s._deposit()
    ra = raws_in(log)
    check("A: RAW_PROPOSAL sealed before validation", len(ra) == 1)
    check("A: raw stored verbatim (byte-for-byte)", ra and ra[0]["raw"] == valid)
    check("A: validated commitment returned and drives the session",
          dep is not None and dep["type"] == "COMMITMENT" and dep["hypotheses"] == {"H00": 0.5, "H01": 0.5})

    # --- مشهد ب: مفتاح مكرّر — الخام يُختم قبل الرفض؛ التكرار قابل للقياس من الخام وحده ---
    dup = ('reasoning B\n{"type":"COMMITMENT","hypotheses":{"H07":0.5,"H07":0.5},'
           '"action":"EXPERIMENT(Qz)","predictions":{"outcome=1":0.5},"update_kind":"INITIAL"}')
    s2, log2 = session_for(dup)
    dep2 = s2._deposit()                       # ينهار إلى {"H07":0.5} مجموعه 0.5 ⇒ يُرفض بعد retry
    rb = raws_in(log2)
    check("B: raw preserved even for a REJECTED proposal (sealed each attempt)", len(rb) == 2)
    check("B: rejected proposal did NOT drive the session (dep is None)", dep2 is None)
    dup_in_raw = duplicate_key_count(rb[0]["raw"]) if rb else 0
    keys_after_parse = len(FakeAgent(dup)._dep["hypotheses"])
    check("B: duplication recoverable from RAW; json.loads hides it in the parsed dep",
          dup_in_raw >= 1 and keys_after_parse == 1,
          f"dup keys in raw={dup_in_raw}, keys after parse={keys_after_parse}")

    print(f"\nRAW-PROPOSAL VALIDATION: {sum(CHECKS)}/{len(CHECKS)} checks passed")
    return all(CHECKS)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
