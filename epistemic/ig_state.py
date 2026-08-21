"""ig_state.py — IG_Σ (state / assignment information gain) — تحليل فقط، خارج العقد المجمّد.

قرار ما بعد B1-small (لا يمسّ A-005 ولا world_b1 ولا oracle search):
information_gain() في world_b1 يعيد (IG_joint, IG_law) حيث IG_law ≡ IG_H = I(H;Y|E).
الكمية الناقصة هي IG_Σ = I(Σ;Y|E) — كم يثبّت الفعلُ **الإسنادَ** (أيّ رمز صاحب أيّ متجه).

الفصل الجديد (خرج من نقطة "EXPERIMENT قبل PROBE قد يكون عقلانيًا"):

    information about state (Σ)  ≠  information about law (H)

مع أن الفعل الواحد قد يحمل الاثنين: تجربة على رمز مجهول الحالة قد تقصي أزواج (h,σ)
فترفع IG_Σ وIG_H معًا. لذا الثلاثة تشخيصية غير جمعية: IG_H + IG_Σ ≠ IG_joint عمومًا.

**لماذا خارج world_b1 وليس على evidence.key():** Σ هو بالضبط ما يطويه تكافؤ تبديل الرموز
(المفتاح القانوني). لذا IG_Σ يُحسب على الأدلة **المُوسَّمة** (self.ev في الجلسة)، وتعدادُ
التقابلات (≤ n!) رخيص هنا لأن الاستدعاء ≤ مرة/التزام — لا داخل حلقة البحث الحارّة.
"""

import itertools
import math

from world_b1 import posterior, apply_action, action_outcomes, information_gain


def state_entropy(hyps, evidence, ctx, emask):
    """H(Σ | E) = إنتروبيا هامش الإسناد المُوسَّم، والمقام Z (يجب أن يطابق posterior).

    الهامش المشترك منتظم على أزواج (h, σ) المتسقة، فوزن التقابل σ هو c(σ) = عدد القوانين
    المتوافقة مع تجارب σ:

        P(σ) ∝ c(σ),   Z = Σ_σ c(σ) = Σ_h W(h)   (نفس Z في posterior)
        H(Σ) = -Σ_σ (c/Z) log2(c/Z) = log2 Z − (Σ_σ c·log2 c)/Z

    σ يمرّ على التقابلات المتوافقة مع أقنعة الـ probe فقط؛ قيد التجربة يدخل عبر c(σ).
    """
    declared = ctx.declared
    n_syms, n_vecs = ctx.n, len(declared)
    pmask = evidence.pmask
    constraints = [(x, e) for x, e in enumerate(evidence.exp) if e is not None]
    Z = 0
    clogc = 0.0
    for perm in itertools.permutations(range(n_vecs), n_syms):
        ok = True
        for x in range(n_syms):
            if not (pmask[x] >> perm[x]) & 1:      # هذا الإسناد يخالف probe الرمز x
                ok = False
                break
        if not ok:
            continue
        c = 0
        for k in range(len(hyps)):                 # عدّ القوانين المتوافقة مع تجارب هذا σ
            good = True
            for x, e in constraints:
                if not (emask[k][e] >> perm[x]) & 1:
                    good = False
                    break
            if good:
                c += 1
        if c:
            Z += c
            clogc += c * math.log2(c)
    if Z == 0:
        return 0.0, 0
    return math.log2(Z) - clogc / Z, Z


def information_gain_full(hyps, evidence, emask, ctx, action):
    """(IG_joint, IG_H, IG_Σ) لفعلٍ واحد. IG_joint/IG_H من world_b1 حرفيًا (توافق تام مع
    الصفوف السابقة)، وIG_Σ يُضاف هنا. p(out) = Z2/Z0 المشترك — نفس ترجيح world_b1.

    قد يكون IG_Σ = 0 مع IG_H > 0 (تجربة بعد تثبيت الإسناد)، أو IG_Σ > 0 (تجربة/probe تقصي
    أزواج إسناد). الحالة الابتدائية: H(Σ) = log2(n!)، وبعد تثبيت كل الرموز H(Σ) = 0.
    """
    # فعل زائد: تجربةٌ على رمزٍ نتيجته مسجَّلة سلفًا = إعادة رصد كمية محدَّدة ⇒ صفر معلومة.
    # (apply_action يكتب فوق exp[x]، فيولّد فرعًا مضادًّا-للواقع وهميًّا يكسر Σ p_out = 1؛
    #  world_b1.information_gain المجمّد يسيء تسعير هذه الحالة أيضًا — نصفّرها هنا بأمان.)
    kind, x, _ = action
    if kind == "EXPERIMENT" and evidence.exp[x] is not None:
        return 0.0, 0.0, 0.0
    ig_joint, ig_law = information_gain(hyps, evidence, emask, ctx, action)
    _, Z0, _, _ = posterior(hyps, evidence, emask, ctx)
    if Z0 == 0:
        return 0.0, 0.0, 0.0
    H0_state, _ = state_entropy(hyps, evidence, ctx, emask)
    exp_state = 0.0
    for out in action_outcomes(evidence, action):
        e2 = apply_action(evidence, action, out)
        _, Z2, _, _ = posterior(hyps, e2, emask, ctx)
        if Z2 == 0:
            continue
        Hs2, _ = state_entropy(hyps, e2, ctx, emask)
        exp_state += (Z2 / Z0) * Hs2
    return ig_joint, ig_law, H0_state - exp_state
