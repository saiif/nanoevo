# بنية المشروع — منهج معرفي قابل للنقل

## الجذر
- `منهج_معرفي_قابل_للنقل.md` — Pre-registration v1.2 المختومة (الفرضية، الـ grammar، الأذرع الأربعة،
  بروتوكول الجلسة، المقاييس، Researcher-Side Commitments). لا تُعدَّل — التعديلات في الـ ledger.
- `README.md` — ملاحظات التنفيذ: التحقق الميكانيكي، الاكتشافات، التعديلات A-001..A-003، Pilot-A.
- `STRUCTURE.md` — هذا الملف.
- `.gitignore` — `__pycache__` فقط؛ الـ provenance تُتتبع عمدًا (لا يُمسح الفشل).
- `.gitattributes` — `eol=lf` لكل الملفات: الـ hashes المختومة (adapter_hash، سلاسل السجلات) تُحسب على البايتات الخام،
  فلا يُسمح لـ Git بتحويل نهايات الأسطر إلى CRLF عند الـ checkout.

## الكود (epistemic/)
- `world.py` — grammar depth-2، oracle، D_min/D_inst/D_pred، فئات التكافؤ، تقسيم Blind-ID/X
- `channel.py` — Schema Validator (COMMIT_SCHEMA + BLIND_SCHEMA) + Archivist (append-only، hash chain)
- `session.py` — بوابة Experimenter، Verifier المعزول، جدول الانتهاكات (أ.3 + A-003)، الاختبار الأعمى، E
- `agents.py` — وكلاء الـ mechanical (Learner/Control + bots الانتهاكات أ.3 وA-003)
- `llm_agent.py` — Pilot-A adapter (قاعدة الإيداع الواحد المجمدة + هوية التنفيذ تُختم بداية ونهاية)
- `run_mechanical.py` — الأسئلة الميكانيكية السبعة + أ.3 + A-003 (22/22) → `provenance/mech_run/`
- `run_pilot_a.py` — Pilot-A: العائلات الخمس + taxonomy الفشل → `provenance/pilot_a_run/`
- `ledger.py` — أدوات الـ ledger: `verify` / `append <entry.json>` / `show`
- `amendments.jsonl` — الـ ledger المختوم: GENESIS، A-001، A-002 (+ملحق)، P-001، ADAPTER_FREEZE، A-003، A-004

## السجلات (epistemic/provenance/)
- `mech_run/` — آخر تشغيل ميكانيكي (بروتوكول `1.0-mech-A004`)
- `mech_run_archive_<ts>/` — كل التشغيلات السابقة بما فيها ما قبل التصحيحات (لا يُمسح الفشل)
- `mech_run_archive_1787334521_A002_final/` — آخر تشغيل قبل A-003 (بروتوكول `1.0-mech-A001`)
- `pilot_a_run/` — يُنشأ عند تشغيل Pilot-A

## التشغيل
    cd epistemic
    python run_mechanical.py          # 28/28 — يؤرشف التشغيل السابق تلقائيًا
    python ledger.py verify           # يتحقق من سلسلة الـ amendments ويطبع رأسها
    python run_pilot_a.py 3           # يحتاج اعتماد Anthropic (ANTHROPIC_API_KEY أو ant auth login)
