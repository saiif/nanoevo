"""run_pilot_b1_replication.py — دفعة تكرار R-001 على البذور 4010-4019.

لا يعدّل المسار المجمّد إطلاقًا: يعيد ضبط B1_SEED_BASE والـ RUN_DIR فقط ثم يستدعي
run_pilot_b1.main حرفيًا — نفس SessionB1 ونفس LLMAgentB1 ونفس الـ prompt والـ adapter
semantics. مجلد منفصل (pilot_b1_replication) حتى لا يُمسّ provenance 4000-4009.

التعريفات المثبَّتة على commit 2441332 هي المرجع للتحليل بعد التشغيل — لا إعادة تعريف.
"""

import os
import sys

import run_pilot_b1

run_pilot_b1.B1_SEED_BASE = 4010
run_pilot_b1.RUN_DIR = os.path.join(
    os.path.dirname(os.path.abspath(run_pilot_b1.__file__)),
    "provenance", "pilot_b1_replication")

if __name__ == "__main__":
    run_pilot_b1.main(
        int(sys.argv[1]) if len(sys.argv) > 1 else 10,
        sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-5",
        sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8787/v1")
