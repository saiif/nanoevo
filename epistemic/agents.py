"""agents.py — وكلاء مبرمجون للتحقق الميكانيكي (بلا LLM — الماسورة أولًا).

Learner: يحدّث فضاء الفرضيات بالحذف، يختار الرمز الأكثر تمييزًا (worst-case split)،
        يعلن الاكتفاء عند بقاء فرضية واحدة، وIncomplete إذا نفدت الميزانية بغموض حقيقي.
Control: نفس التحديث، لكن اختيار الرموز عشوائي — يعزل جودة اختيار التجربة.
Violation bots: لاختبار جدول الانتهاكات والبوابة (أ.3 + A-003) — كل بوت ينتهك قاعدة واحدة.
"""

import random

from world import enumerate_hypotheses


class BaseAgent:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.hyps = enumerate_hypotheses()
        self.alive = set(range(len(self.hyps)))
        self.symbols = {}
        self.free_left = 3

    def receive_phase_zero(self, packet):
        self.symbols = {s: tuple(v) for s, v in packet["symbols"].items()}

    def observe(self, action, obs):
        sym = action[5:-1]
        props = self.symbols[sym]
        self.alive = {h for h in self.alive if self.hyps[h].eval(props) == obs}

    def interpret(self, obs):
        return ({"alive_count": len(self.alive),
                 "update_kind": "REWEIGHT"},
                f"free-thought: {len(self.alive)} hypotheses remain")

    def notify(self, msg):
        pass

    def _beliefs(self):
        w = 1.0 / len(self.alive)
        return {self.hyps[h].name(): round(w, 6) for h in sorted(self.alive)}

    def _fix_probs(self, probs):
        s = sum(probs.values())
        keys = list(probs)
        fixed = {k: probs[k] / s for k in keys[:-1]}
        fixed[keys[-1]] = 1.0 - sum(fixed.values())
        return fixed

    def _predictions_for(self, sym):
        props = self.symbols[sym]
        p1 = sum(1 for h in self.alive if self.hyps[h].eval(props) == 1) / len(self.alive)
        return {"outcome=1": round(p1, 6)}

    def blind_predict(self, blind_cases):
        """تنبؤ + ثقة = كتلة الفرضيات الباقية المتفقة على الجواب (A-002).
        وكيل صادق مع جهله: الثقة تهبط تلقائيًا حيث الفرضيات الباقية تختلف.
        يرجع (predictions, thoughts) — نفس عقد deposit (A-003)."""
        out = {}
        for s, v in blind_cases.items():
            if not self.alive:                       # لا نموذج: جهل صريح
                out[s] = {"pred": 0, "conf": 0.5}
                continue
            votes = [self.hyps[h].eval(tuple(v)) for h in self.alive]
            ones = sum(votes) / len(votes)
            pred = 1 if ones >= 0.5 else 0
            out[s] = {"pred": pred, "conf": round(max(ones, 1 - ones), 4)}
        return out, None

    def _sufficiency(self):
        return ({"type": "SUFFICIENCY",
                 "final_hypothesis": self.hyps[min(self.alive)].name(),
                 "confidence": 0.99}, "declaring sufficiency")

    def _incomplete(self):
        return ({"type": "INCOMPLETE",
                 "remaining_hypotheses": [self.hyps[h].name() for h in sorted(self.alive)],
                 "reason": "evidence insufficient to discriminate remaining hypotheses"}, None)

    def _inadequacy(self):
        # لا فرضية في العائلة المعلنة تفسر الأدلة — الإعلان الرسمي (المادة 39)
        return ({"type": "INADEQUACY",
                 "reason": "no hypothesis in declared family survives the evidence",
                 "requested_family": "unknown — detection without diagnosis"},
                "declaring model inadequacy")

    def _commitment(self, sym):
        return {"type": "COMMITMENT",
                "hypotheses": self._fix_probs(self._beliefs()),
                "action": f"TEST({sym})",
                "predictions": self._predictions_for(sym),
                "update_kind": "REWEIGHT"}

    def deposit(self):
        raise NotImplementedError


class LearnerAgent(BaseAgent):
    """التربية المعرفية (نسخة scripted): اختيار التجربة الفاصلة القصوى."""

    def _best_symbol(self):
        best, best_score = None, None
        for sym, props in self.symbols.items():
            split = {0: 0, 1: 0}
            for h in self.alive:
                split[self.hyps[h].eval(props)] += 1
            if 0 in (split[0], split[1]):
                continue  # غير فاصلة
            score = max(split.values())  # minimize worst case
            if best_score is None or score < best_score:
                best, best_score = sym, score
        return best

    def deposit(self):
        if not self.alive:
            return self._inadequacy()
        if len(self.alive) == 1:
            return self._sufficiency()
        sym = self._best_symbol()
        if sym is None:
            # A-002: استنفد الوكيل ما تسمح الأدلة بمعرفته (لا تجربة فاصلة متبقية).
            # الفئة الرصدية محددة → Blind-ID مضمونة الإجابة → يعلن الاكتفاء
            # بثقة صادقة = كتلة أكبر فرضية، ويترك الغموض يظهر في conf_X.
            return ({"type": "SUFFICIENCY",
                     "final_hypothesis": self.hyps[min(self.alive)].name(),
                     "confidence": round(1.0 / len(self.alive), 4)},
                    "evidence exhausted; observational class identified; "
                    "residual ambiguity carried honestly into blind confidence")
        if self.free_left > 0:
            self.free_left -= 1
            return ({"type": "FREE_OBS", "action": f"TEST({sym})"},
                    "free exploration on most-splitting symbol")
        return self._commitment(sym), f"choosing discriminative test {sym}"


class ControlAgent(BaseAgent):
    """بلا تربية: اختيار عشوائي — نفس الموارد، نفس التحديث."""

    def deposit(self):
        if not self.alive:
            return self._inadequacy()
        if len(self.alive) == 1:
            return self._sufficiency()
        sym = self.rng.choice(list(self.symbols))
        if self.free_left > 0:
            self.free_left -= 1
            return ({"type": "FREE_OBS", "action": f"TEST({sym})"}, None)
        return self._commitment(sym), None


# ----------------------------- violation bots (أ.3) -----------------------------

class MalformedOnceAgent(LearnerAgent):
    """أول إيداع باحتمالات تجمع إلى 1.2 → إعادة واحدة → صالح (أ.3 سطر 1-2).
    عند الإعادة يستدعي السيشن deposit من جديد والحالة لم تتغير → النسخة الصالحة."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self._poisoned = False

    def deposit(self):
        dep, th = super().deposit()
        if not self._poisoned and dep["type"] == "COMMITMENT":
            self._poisoned = True
            bad = dict(dep)
            bad["hypotheses"] = {k: v * 1.2 for k, v in dep["hypotheses"].items()}
            return bad, "malformed on purpose (probs sum to 1.2)"
        return dep, th


class MalformedTwiceAgent(LearnerAgent):
    """يفشل schema مرتين → AgentProtocolFailure بـ E=0 (أ.3 سطر 4)."""

    def deposit(self):
        return ({"type": "COMMITMENT", "hypotheses": {"h": 2.0},
                 "action": "TEST(??)", "predictions": {},
                 "update_kind": "REWEIGHT"}, "always malformed")


class LeakProbeAgent(LearnerAgent):
    """يحاول فعلًا ممنوعًا (رمز خارج منطقة التدريب) → رفض + attempt consumed."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self._probed = False
        self.free_left = 0

    def deposit(self):
        if not self._probed:
            self._probed = True
            dep = self._commitment(next(iter(self.symbols)))
            dep["action"] = "TEST(Zz)"          # رمز غير موجود في المنطقة المسموحة
            dep["predictions"] = {"outcome=1": 0.5}
            return dep, "probing outside allowed region"
        return super().deposit()


# ----------------------------- violation bots (A-003) -----------------------------

class BadActionAgent(LearnerAgent):
    """نص فعل مشوه (يمر schema، يُرفض في Verifier): مرة في الاستطلاع الحر ومرة في الالتزام.
    المتوقع: FREE_OBS_REFUSED + REFUSED_ACTION، الجلسة تستمر وتُحل، لا crash."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 1
        self._stage = 0

    def deposit(self):
        if self._stage == 0:
            self._stage = 1
            return ({"type": "FREE_OBS", "action": "TEST(Qz, Vx)"}, "malformed free action")
        if self._stage == 1:
            self._stage = 2
            dep = self._commitment(next(iter(self.symbols)))
            dep["action"] = "test qz"
            return dep, "malformed committed action"
        return super().deposit()


class ExtraFreeObsAgent(LearnerAgent):
    """يرسل FREE_OBS رابعًا بعد انتهاء مرحلة الاستطلاع → PHASE_REJECT + إعادة محايدة،
    ثم يلتزم. المتوقع: الجلسة تستمر (لا failure فوري)."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 4

    def notify(self, msg):
        if msg == "TYPE_NOT_ALLOWED_IN_PHASE":
            self.free_left = 0


class InadequacyLoopAgent(LearnerAgent):
    """يعلن القصور إلى الأبد → كل إعلان يستهلك attempt → BUDGET_EXHAUSTED لا حلقة لانهائية."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.free_left = 0

    def deposit(self):
        return self._inadequacy()


class BlindMalformedAgent(LearnerAgent):
    """رد أعمى مشوه n_bad مرة ثم صالح. n_bad=1 → BLIND_REJECT + إعادة + SOLVED؛
    n_bad=2 → AgentProtocolFailure في مرحلة blind دون كشف الحقيقة."""

    def __init__(self, seed=0, n_bad=1):
        super().__init__(seed)
        self.n_bad = n_bad

    def blind_predict(self, blind_cases):
        if self.n_bad > 0:
            self.n_bad -= 1
            return None, "garbled blind reply on purpose"
        return super().blind_predict(blind_cases)


class EarlyStopAgent(LearnerAgent):
    """يعلن الاكتفاء قبل التعريف الكامل (عند بقاء ≤ stop_at فرضية) ويتنبأ بالأغلبية.

    وجوده ضروري لاختبار A-004: الـ Learner المرجعي يسعى إلى identification كامل فلا يهبط
    أبدًا تحت D_robust، بينما الـ LLM فعلها (2000#r1). هذا البوت ينتج مسارًا أقصر من الضمان
    فيختبر: منطقة FAVORABLE_TRAJECTORY، وE_robust > 1 غير مسقوفة، وأن الـ audit لا يشتعل
    ما دام N ≥ D_floor^task. قد ينتهي أحيانًا FALSE_CERTAINTY — وهذا سلوك مشروع للتوقف المبكر.
    """

    def __init__(self, seed=0, stop_at=2):
        super().__init__(seed)
        self.stop_at = stop_at

    def deposit(self):
        if self.alive and len(self.alive) <= self.stop_at:
            return ({"type": "SUFFICIENCY",
                     "final_hypothesis": self.hyps[min(self.alive)].name(),
                     "confidence": round(1.0 / len(self.alive), 4)},
                    "early task-aligned stop (A-004 ruler test)")
        return super().deposit()


class IncompleteClaimAgent(LearnerAgent):
    """بعد الاستطلاع الحر يدّعي أن الأدلة لا تكفي بينما توجد تجربة فاصلة →
    INCOMPLETENESS_VERIFIED correct=False → INCORRECT_INCOMPLETENESS_CLAIMED، E=0."""

    def deposit(self):
        if self.free_left > 0 or len(self.alive) <= 1:
            return super().deposit()
        return self._incomplete()
