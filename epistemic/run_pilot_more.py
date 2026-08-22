"""run_pilot_more.py — يكمل Pilot-A على seeds جديدة دون لمس اي ملف من الماسورة.
python3 run_pilot_more.py <seed_base> <n> [model]"""
import sys
import run_pilot_a, run_pilot_shim
run_pilot_a.PILOT_SEED_BASE = int(sys.argv[1])
run_pilot_shim.main(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "claude-sonnet-5")
