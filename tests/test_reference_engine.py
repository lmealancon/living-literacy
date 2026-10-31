import unittest
from prototype.lesson_engine import LessonEngine, Actor, ApprovedLesson, PolicyError, ConflictError, STAGES

class ReferenceEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine=LessonEngine()
        self.actor=Actor("adult-1","family-1",frozenset({"synthetic-child-1"}))
        self.lesson=ApprovedLesson("LL-LSN-0001","1.0.0","approved_for_prototype")
        self.s=self.engine.start(self.actor,"synthetic-child-1",self.lesson,"start-1")
    def test_start_is_idempotent(self):
        self.assertIs(self.s,self.engine.start(self.actor,"synthetic-child-1",self.lesson,"start-1"))
    def test_key_reuse_with_changed_lesson_is_rejected(self):
        with self.assertRaises(ConflictError):
            self.engine.start(self.actor,"synthetic-child-1",ApprovedLesson("LL-LSN-0002","1.0.0","approved_for_prototype"),"start-1")
    def test_unapproved_lesson_is_rejected(self):
        with self.assertRaises(PolicyError):
            self.engine.start(self.actor,"synthetic-child-1",ApprovedLesson("LL-LSN-0002","1.0.0","draft"),"start-2")
    def test_cross_workspace_denied(self):
        other=Actor("adult-2","family-2",frozenset({"synthetic-child-1"}))
        with self.assertRaises(PolicyError):
            self.engine.transition(other,self.s.session_id,"active",0)
    def test_other_student_denied(self):
        other=Actor("adult-2","family-1",frozenset({"synthetic-child-2"}))
        with self.assertRaises(PolicyError):
            self.engine.transition(other,self.s.session_id,"active",0)
    def test_stale_revision_denied(self):
        self.engine.transition(self.actor,self.s.session_id,"active",0)
        with self.assertRaises(ConflictError):
            self.engine.advance_stage(self.actor,self.s.session_id,0)
    def test_invalid_transition_denied(self):
        with self.assertRaises(PolicyError):
            self.engine.transition(self.actor,self.s.session_id,"completed",0)
    def test_cannot_complete_early(self):
        self.engine.transition(self.actor,self.s.session_id,"active",0)
        with self.assertRaises(PolicyError):
            self.engine.transition(self.actor,self.s.session_id,"completed",1)
    def test_independent_evidence_excludes_audio(self):
        self.engine.transition(self.actor,self.s.session_id,"active",0)
        for _ in range(4): self.engine.advance_stage(self.actor,self.s.session_id,self.s.revision)
        r=self.engine.record_response(self.actor,self.s.session_id,self.s.revision,"synthetic response",{"audio_or_modeling":True},True)
        self.assertFalse(r["independent_evidence_eligible"])
        r=self.engine.record_response(self.actor,self.s.session_id,self.s.revision,"synthetic response",{"audio_or_modeling":False},True)
        self.assertTrue(r["independent_evidence_eligible"])
    def test_missing_assistance_rejected(self):
        self.engine.transition(self.actor,self.s.session_id,"active",0)
        with self.assertRaises(PolicyError):
            self.engine.record_response(self.actor,self.s.session_id,self.s.revision,"test",{},True)
    def test_completion_never_declares_mastery(self):
        self.engine.transition(self.actor,self.s.session_id,"active",0)
        for _ in range(5): self.engine.advance_stage(self.actor,self.s.session_id,self.s.revision)
        self.engine.transition(self.actor,self.s.session_id,"completed",self.s.revision)
        self.assertEqual(self.s.mastery_status,"not_assessed")
    def test_real_data_rejected(self):
        with self.assertRaises(PolicyError):
            self.engine.start(self.actor,"synthetic-child-1",self.lesson,"start-3",environment="production")
    def test_stage_order_is_canonical(self):
        self.assertEqual(STAGES,("activate","model","guide","practice","apply_independently","review"))
if __name__=="__main__": unittest.main()
