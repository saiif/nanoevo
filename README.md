# Mechanical Validation — التشغيل الأول (الملحق ب)

تنفيذ حرفي لنطاق التشغيل الأول من وثيقة "منهج معرفي قابل للنقل" v1.2
(`منهج_معرفي_قابل_للنقل.md` — مختومة، لا تُعدَّل؛ كل تعديل يمر عبر الـ ledger):
depth-2 grammar، ذراعان، Verifier/Archivist حتميان، بلا LLM وبلا ادعاءات إحصائية.

## البنية
انظر `STRUCTURE.md`. باختصار: الكود + الـ ledger + الـ provenance تحت `epistemic/`،
ووثيقة التسجيل المسبق في الجذر.

- `epistemic/world.py` — grammar depth-2 (صيغ منطقية على خصائص) + oracle + D_min (minimax) + D_inst + D_pred
- `epistemic/channel.py` — Schema validator (COMMIT_SCHEMA + BLIND_SCHEMA) + Archivist append-only بسلسلة hash
- `epistemic/session.py` — بوابة الـ Experimenter، جدول الانتهاكات أ.3 + A-003، الاختبار الأعمى، E/Success/OracleViolation
- `epistemic/agents.py` — Learner (اختيار فاصل) / Control (عشوائي) + bots اختبار الانتهاكات والتسريب
- `epistemic/llm_agent.py` — Pilot-A adapter
- `epistemic/run_mechanical.py` — الأسئلة الميكانيكية السبعة + أ.3 + A-003 + عرض توضيحي
- `epistemic/run_pilot_a.py` — Pilot-A (يحتاج اعتماد Anthropic)
- `epistemic/ledger.py` — `verify` / `append` / `show` للـ amendments ledger
- `epistemic/amendments.jsonl` — الـ ledger المختوم (رأس السلسلة الحالي: `32dd35b1f14ab8a7`)

## التشغيل
    cd epistemic
    python run_mechanical.py        # النتيجة: 22/22 checks passed  → provenance/mech_run/
    python ledger.py verify         # VALID  entries=7  head=32dd35b1f14ab8a7

الإصدارات المجمدة الحالية (تُختم في GENESIS كل جلسة):
`schema_hash=0043f752a119c0c8` (لم يتغير منذ التشغيل الأول) · `blind_schema_hash=dd7a56a0e3e93e1c` ·
`protocol 1.0-mech-A003 / protocol_hash=710f896b96544e0b` · `grammar_hash=02445a0a5566be2d` ·
`adapter_hash=bd2a2c04778cfe57`.

## قرارات نطاق موثقة (mechanical فقط)
1. جدول الخصائص ظاهر والقانون مخفي — الخصائص الكامنة القابلة للـ probe تدخل في الـ pilot
   (الوثيقة: الهدف الأول اختبار الماسورة لا richness العالم).
2. الإعلان كامل (declaration_complete) — الإعلان المنقوص لقياس Frame Expansion يدخل في الـ pilot.
3. نافذة D_min للـ mechanical: [2,6] بدل [4,15] — العالم أصغر عمدًا.
   ملاحظة بنيوية مقيسة (60 بذرة): كل عالم مقبول له D_min=6 بالضبط (30 فرضية، 6 اختبارات ثنائية)،
   وD_pred ∈ {4,5,6}؛ ~87% من العوالم الخام تُرفض لعدم القابلية للتمييز. النافذة عمليًا = بوابة identifiability.

## اكتشاف التحقق الميكانيكي (سُجّل عبر OracleViolation audit)
النسخة الأولى قاست E على D_min الـ worst-case، فقدح الـ audit على كل جلسة —
لأن D_min minimax ليس lower bound على الجلسة الواحدة (العالم الفعلي قد ينحسم أسرع)،
ولأن الاستطلاعات الحرة تحمل معلومات دون أن تُحتسب. التصحيح المطبق:
- N_total = التدخلات + الاستطلاعات الحرة (كلاهما يستهلك الميزانية).
- المسطرة: D_inst = تكلفة السياسة المثلى على القانون الحقيقي بالذات.
- D_min يبقى بوابة صعوبة التوليد فقط.
هذا التعديل يمس تعريف E في الوثيقة → يتطلب amendment مختومًا قبل فتح البذور
التأكيدية (وفق قاعدة الزمن في أ.1). آلية الـ audit عملت بالضبط كما صُممت.

## Amendment A-001 (مختوم في amendments.jsonl)
- المسطرة الرسمية لـ E: D_pred-inst الـ task-aligned — oracle يعرف hypothesis class فقط،
  تحت نفس I0، وهدفه BlindScore >= tau لا identification كامل. C(pi*, W_i | I0).
- N_total = N_free + N_formal (نفس observation protocol للوكيل والـ oracle).
- D_min: بوابة توليد فقط، خارج الـ Primary Endpoint. D_inst: تقرير.
- protocol_hash تغيّر تلقائيًا مع الـ amendment (التجميد الثلاثي يعمل).

## اكتشاف ميكانيكي #2 (أثناء تنفيذ A-001)
فرضيات متطابقة على مدى التدريب (6 vectors) ومختلفة على العمياء (8) تجعل
"الضمان للجميع" غير قابل للبلوغ في بعض الفروع، فتنكسر سياسة minimax الصرفة.
الحل الموثق: fallback جشع بأقصى تقسيم؛ D_pred عندها مرجع لا ضمان.

## Amendment A-002 (مختوم) — Identifiability / Extrapolation Separation
- فئات التكافؤ الرصدية: H_a ~ H_b ⇔ متطابقتان على كل ما تسمح التدخلات به.
- Blind-ID (هدف ثابت داخل كل فئة) يقرر Success وE؛ Blind-X ثانوي:
  extrapolation + Extrapolation Calibration (هل تهبط الثقة حيث لا تميّز الأدلة؟).
- D_pred-inst = UNREACHABLE عند اللا-قابلية؛ الجشع يُسجَّل كـ D_greedy_ref منفصلًا.
- قرار مصمم مختوم: مدى العمياء لا يُقيَّد بمدى التدريب — الفارق يُحفظ عمدًا بوظيفة مفصولة.
- ملحق: العوالم UNREACHABLE غير مؤهلة لـ E (لا 0 ولا null) وتُرفض في التوليد؛ العتبة تُسمّى tau_ID.

## اكتشاف ميكانيكي #3 (أثناء تنفيذ A-002)
شرط الإنهاء كان يقيس الاتفاق مع القانون الحقيقي الثابت، بينما في فروع minimax
المضادة للواقع "الحقيقة" هي فرضية الفرع — فحالة {فرضية خاطئة وحيدة} كانت طريقًا
مسدودًا أبديًا يسمّم الشجرة بـ inf. التصحيح: الضمان = قاعدة الأغلبية داخل الحالة
تحقق العتبة ضد أي عضو لو كان هو الصحيح (اتفاق متبادل، counterfactual-correct).

## سلوك A-002 موثق بالتجربة
عوالم بمدى تدريب ضيق (4 vectors — محاكاة pilot، `provenance/mech_run_archive_1787333903/x*`):
nID=4/nX=4، الوكيل يستنفد الأدلة، يعلن الاكتفاء بثقة صادقة، وينجح على ID بثقة 1.0 بينما
تهبط ثقته على X إلى 0.67-0.75 تلقائيًا — Extrapolation Calibration يعمل.
في عالم mechanical الكامل (6 vectors تدريب) كل الفئات مفردة فـ Blind-X فارغة بنيويًا؛ تتفعل في الـ pilot.

## اكتشاف ما قبل الـ pilot #4 → Amendment A-003 (مختوم) — Pilot-A hardening
تحليل الكود قبل تشغيل أي LLM (2026-08-21) وجد مسارات كان وكيل لغوي سيكسرها — وكل واحد منها
كان سيُصنَّف خطأً تحت taxonomy P-001 (مثلًا crash في الماسورة بدل عدم امتثال). ما صُلّح وخُتم:
- **فعل مشوه** (`TEST(Qz, Vx)`، `test qz`…) يمر الـ schema ثم يُرفض في الـ Verifier كفعل ممنوع
  (attempt consumed) في المرحلتين — بدل crash غير ملتقط. `FREE_OBS_REFUSED` / `REFUSED_ACTION`.
- **نوع خارج مرحلته** (FREE_OBS رابع بعد الاستطلاع): إعادة محايدة واحدة (`PHASE_REJECT`) ثم failure —
  بدل failure فوري مخالف لجدول أ.3.
- **INADEQUACY تستهلك attempt**: الحلقة محدودة بالبناء (كانت بلا ثمن → حلقة لانهائية ممكنة).
- **الرد الأعمى يمر عبر validator** (`BLIND_SCHEMA`: كل الرموز، pred عدد صحيح 0/1، conf ∈ [0,1]، بلا coercion):
  إعادة واحدة (`BLIND_REJECT`) ثم `AGENT_PROTOCOL_FAILURE(stage=blind)` دون كشف الحقيقة.
  (كان الرد المشوه يتحول صامتًا إلى pred=0/conf=0.5 لكل الحالات ويلوّث الـ calibration.)
- **ادعاء الاكتفاء-بالنقص يُتحقق منه**: صحيح ⇔ المجموعة المتبقية داخل فئة تكافؤ رصدية واحدة تحوي القانون →
  اختبار أعمى (المادة 41: نجاح معرفي)؛ خاطئ → `INCORRECT_INCOMPLETENESS_CLAIMED`، E=0.
  (كانت التسمية `CORRECT_…` تُمنح بلا تحقق.)
- **هوية التنفيذ تُختم مرتين**: `EXEC_IDENTITY` بداية و`EXEC_IDENTITY_END` نهاية (request_ids، stop_reasons،
  عدد القطع بـ max_tokens) — كانت request_ids تُختم دائمًا فارغة. الانهيارات تُختم `SESSION_ABORTED`.
- `run_pilot_a.py`: إصلاح crash في التقرير، taxonomy بأنواع استثناءات الـ SDK (BadRequest → adapter،
  باقي APIError → provider، غير ذلك → world/session bug)، الاعتماد يُحل من البيئة أو profile.
- ترميز UTF-8 صريح للقناة الجانبية والسجلات والـ console (كان التشغيل ينهار على Windows cp1252).
- **لم يتغير**: E، tau_ID، D_pred، تعريف N_total، COMMIT_SCHEMA (`schema_hash` ثابت)، الـ grammar.
- 8 فحوص انحدار جديدة في `run_mechanical.py` → 22/22. السجلات السابقة كلها محفوظة تحت `provenance/`.

حدود معروفة مسجلة في A-003: tau_blind=0.90 مع 8 حالات Blind-ID تعني 8/8؛ سلسلة الـ hash
تكشف التلاعب الساذج فقط — رأس السلسلة يُثبَّت خارجيًا (git + هذا الملف).

## Pilot-A (جاهز للتشغيل)
- `llm_agent.py`: الـ adapter — الموديل يكتب تفكيرًا حرًا ثم JSON واحدًا؛ آخر كتلة
  JSON = الإيداع (تمر عبر الـ validator كأي وكيل)، والباقي قناة جانبية. الإيداع
  المشوه لا يُصلح في الـ adapter — العقد نفسه يتصرف (إعادة واحدة ثم failure).
- `run_pilot_a.py [n]`: S_pilot = seeds 2000+؛ مقياس النجاح = تقرير الامتثال البروتوكولي (العائلات الخمس)، لا E.
  smoke test عبر عميل وهمي مكتوب (3 استطلاعات، FREE_OBS رابع، رد أعمى مشوه مرة، نص عربي في القناة
  الجانبية، ومسار crash) عدّى: PHASE_REJECT وBLIND_REJECT مختومان، request_ids=7 مختومة في النهاية،
  SESSION_ABORTED مع taxonomy صحيح، التقرير يُطبع كاملًا.
- خطة P-001 مختومة في الـ ledger: مراحل A/B، القضايا الثلاث (فصل N_probe/N_experiment،
  t_inadequacy الزمني للـ DetectionLatency، ثلاثية Blind-X)، وقواعد التوقيت الملزمة:
  كل تعديل ناتج عن Pilot-A يُختم قبل Pilot-B؛ البذور التأكيدية لا تُفتح.

## Pilot-A — أول تشغيل فعلي على LLM حقيقي (2026-08-21)
شُغِّل على خادم debian عبر نقطة OpenAI-compatible (`claude-openai-shim`) تنفّذ عبر
اشتراك `claude -p` للمشغّل. النموذج: **claude-sonnet-5**. النقل عبر `shim_client.py`
(urllib، بلا اعتمادية) و`run_pilot_shim.py` — الـ adapter المجمّد `llm_agent.py` غير مُمَسّ
(adapter_hash ثابت bd2a2c04778cfe57). السجلات: `provenance/pilot_a_shim_run/` +
أدوات التحليل `analyze_pilot.py` / `check_r1.py` (قراءة فقط).

النتيجة (seeds 2000-2002، + تشغيل مفرد سابق لـ2000):

| episode | complete | rejects | invalid | Nfree | Nform | Ntot | Blind-ID | Dinst | Dpred | audit |
|---|---|---|---|---|---|---|---|---|---|---|
| 2000#r1 | ✓ | 0 | 0 | 3 | 1 | 4 | 8/8 | 5 | 5 | ORACLE_VIOLATION |
| 2000#r2 | ✓ | 0 | 0 | 3 | 2 | 5 | 8/8 | 5 | 5 | – |
| 2001 | ✓ | 0 | 0 | 3 | 2 | 5 | 8/8 | 5 | 5 | – |
| 2002 | ✓ | 0 | 0 | 3 | 2 | 5 | 8/8 | 4 | 4 | – |

**contract compliance: 4/4** — لا schema rejects، لا retries، لا أفعال غير مسموحة،
Blind-ID = 8/8 في كل episode، provenance كامل 4/4. الـ parser والـ Archivist والـ audit
صمدوا أمام output حقيقي غير نظيف (decorative ```json``` fences) دون semantic repair —
قاعدة "إيداع دلالي واحد بالضبط" هي الحد الصحيح.

**الـ audit اشتعل في 1/4** (2000#r1، N_total=4 < D_pred=5). التحليل (read-only، `check_r1.py`):
الوكيل حدّد القانون بالكامل (|H|: 30→15→7→4→1) في 4 تدخلات، فتجاوز D_pred **وD_inst=5** معًا —
لكن دون كسر أي حد نظري: D_min/D_inst/D_pred كلها تكاليف minimax/أسوأ-حالة (قسط تأمين للمتانة
عبر كل القوانين الممكنة)، بينما مسار الوكيل المُحقَّق على قانون مُواتٍ قد يقصر عنها. التباين
realized-path لا عيب في المسطرة: نفس العالم 2000 اشتعل في r1 (4) ولم يشتعل في r2 (5).

**مرشّح A-004 (لم يُختم — يُجمَّد رسميًا عند بوابة Pilot-A → Pilot-B وفق P-001):**
التشخيص: ما يسمى OracleViolation حاليًا ليس انتهاكًا رياضيًا بل mismatch بين
realized trajectory ومرجع robust. الصياغة المرشحة تفصل **ثلاث مساطر** بدل رقم واحد:

- **D_floor(W)** — instance-optimal cost تحت **epistemic admissibility**: السياسة
  π_t: h_t → a_t لا ترى W إلا عبر ما كشفه التاريخ؛ ثم يؤخذ min بعد تثبيت W.
  تحذير مسجَّل: بدون شرط الـ admissibility يدخل clairvoyance من الباب الخلفي؛ وحتى معه،
  الـ min هو **lower envelope تشخيصي** لا سياسة يمكن للـ oracle اختيارها rationally قبل
  معرفة العالم. (في instance حتمي مثبَّت، يكافئ min على مجموعات الاختبارات — قابل للحساب الدقيق.)
- **D_robust** — تكلفة السياسة المثلى وفق criterion مجمَّد مسبقًا (حاليًا minimax) — هذا هو D_pred تقريبًا.
- **N_realized** — المسار المحقق فعليًا.

المناطق: `N < D_floor` → **true audit** (leakage/accounting/oracle bug)؛
`D_floor ≤ N < D_robust` → **طبيعي تمامًا** (favorable realized trajectory)؛
`N ≥ D_robust` → لا violation، فقط كفاءة أقل من المرجع في هذه الحلقة.
denominator الـ E **لا** يتغير تلقائيًا إلى D_floor (baseline غريب — envelope محسوب بعد معرفة
العالم): E_robust = D_robust/N يبقى وصفيًا ويُسمح طبيعيًا بـ E_robust > 1 دون تسمية 1 حدًا أقصى.
الجذر: metric واحد كان يؤدي وظيفتين — Performance benchmark (D_robust) وValidity bound (D_floor) — والفصل واجب.

تحقق عددي read-only على هذه الدفعة (min على مجموعات الاختبارات، دون أي تعديل في الماسورة):
seeds 2000/2001/2002 → D_floor=4/4/4 مقابل D_robust=5/5/4 وD_min=6. التصنيف:
2000#r1: N=4 **= D_floor بالضبط** < D_robust → favorable trajectory لا true audit؛
البقية N ≥ D_robust. لا episode تحت D_floor → الحسابات والماسورة سليمة.
خلاصة Pilot-A الأدق: **Real LLM contract compatibility demonstrated in this pilot batch** —
لا ادعاء قدرة معرفية عامة؛ و2000#r1 = ملاحظة عن بنية العالم والـ oracle (سياسة غير minimax
سلكت فرعًا مواتيًا إلى singleton في 4)، لا تفوقًا على optimum. **لم يُعدَّل شيء في الماسورة.**
