"""Living Literacy reference lesson-session engine; in-memory, synthetic data ONLY.
Not a server, authorization system, or production-ready assessment service.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

STAGES = ("activate", "model", "guide", "practice", "apply_independently", "review")
TRANSITIONS = {
    "created": {"active", "abandoned", "invalidated"},
    "active": {"paused", "completed", "abandoned", "invalidated"},
    "paused": {"active", "abandoned", "invalidated"},
    "completed": {"closed", "invalidated"},
    "abandoned": {"closed"},
    "invalidated": {"closed"},
    "closed": set(),
}

class PolicyError(ValueError): pass
class ConflictError(ValueError): pass

@dataclass(frozen=True)
class ApprovedLesson:
    lesson_id: str
    version: str
    status: str
    stages: tuple = STAGES

@dataclass(frozen=True)
class Actor:
    actor_id: str
    workspace_id: str
    permitted_student_ids: frozenset

@dataclass
class Session:
    session_id: str
    workspace_id: str
    student_id: str
    lesson_id: str
    lesson_version: str
    status: str = "created"
    stage_index: int = 0
    revision: int = 0
    responses: List[dict] = field(default_factory=list)
    audit: List[dict] = field(default_factory=list)
    mastery_status: str = "not_assessed"
    # Any approved narration requested during this session is conservatively
    # treated as assistance for subsequent responses. Old records default empty.
    narration_exposures: List[dict] = field(default_factory=list)

class LessonEngine:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.idempotency: Dict[tuple, str] = {}

    @staticmethod
    def _authorize(actor, workspace_id, student_id):
        if actor.workspace_id != workspace_id or student_id not in actor.permitted_student_ids:
            raise PolicyError("ACTION_NOT_PERMITTED")

    @staticmethod
    def _event(session, actor, action):
        session.audit.append({"action": action, "actor_id": actor.actor_id,
                              "at": datetime.now(timezone.utc).isoformat(), "revision": session.revision})

    def start(self, actor, student_id, lesson, idempotency_key, environment="synthetic"):
        if environment != "synthetic":
            raise PolicyError("REAL_STUDENT_DATA_NOT_SUPPORTED")
        self._authorize(actor, actor.workspace_id, student_id)
        if lesson.status not in {"approved_for_prototype", "approved_for_limited_pilot", "approved_for_production"}:
            raise PolicyError("CONTENT_NOT_APPROVED")
        if tuple(lesson.stages) != STAGES:
            raise PolicyError("INVALID_LESSON_STAGES")
        if not idempotency_key:
            raise PolicyError("IDEMPOTENCY_KEY_REQUIRED")
        key = (actor.workspace_id, actor.actor_id, idempotency_key)
        if key in self.idempotency:
            session = self.sessions[self.idempotency[key]]
            if (session.student_id, session.lesson_id, session.lesson_version) != (student_id, lesson.lesson_id, lesson.version):
                raise ConflictError("IDEMPOTENCY_KEY_REUSED")
            return session
        session = Session(str(uuid4()), actor.workspace_id, student_id, lesson.lesson_id, lesson.version)
        self._event(session, actor, "created")
        self.sessions[session.session_id] = session
        self.idempotency[key] = session.session_id
        return session

    def _get(self, actor, session_id):
        session = self.sessions.get(session_id)
        if session is None:
            raise PolicyError("RESOURCE_NOT_FOUND")
        self._authorize(actor, session.workspace_id, session.student_id)
        return session

    def transition(self, actor, session_id, target, expected_revision):
        session = self._get(actor, session_id)
        if expected_revision != session.revision:
            raise ConflictError("REVISION_CONFLICT")
        if target not in TRANSITIONS[session.status]:
            raise PolicyError("INVALID_SESSION_STATE")
        if target == "completed" and session.stage_index != len(STAGES)-1:
            raise PolicyError("STAGES_NOT_FINISHED")
        session.status = target
        session.revision += 1
        self._event(session, actor, "transition:" + target)
        return session

    def advance_stage(self, actor, session_id, expected_revision):
        session = self._get(actor, session_id)
        if expected_revision != session.revision:
            raise ConflictError("REVISION_CONFLICT")
        if session.status != "active" or session.stage_index >= len(STAGES)-1:
            raise PolicyError("INVALID_STAGE_TRANSITION")
        session.stage_index += 1
        session.revision += 1
        self._event(session, actor, "stage:" + STAGES[session.stage_index])
        return session

    def record_response(self, actor, session_id, expected_revision, response_text,
                        assistance, independent_task=False):
        session = self._get(actor, session_id)
        if expected_revision != session.revision:
            raise ConflictError("REVISION_CONFLICT")
        if session.status != "active":
            raise PolicyError("INVALID_SESSION_STATE")
        if not isinstance(assistance, dict) or not isinstance(assistance.get("audio_or_modeling"), bool):
            raise PolicyError("ASSISTANCE_PROVENANCE_REQUIRED")
        if not isinstance(response_text, str) or not response_text.strip():
            raise PolicyError("INVALID_RESPONSE")
        assistance = dict(assistance)
        if session.narration_exposures:
            assistance["audio_or_modeling"] = True
            assistance["narration_exposure"] = True
        eligible = bool(independent_task and session.stage_index == 4 and not assistance["audio_or_modeling"])
        session.responses.append({"stage": STAGES[session.stage_index], "response": response_text,
                                  "assistance": dict(assistance), "independent_evidence_eligible": eligible,
                                  "at": datetime.now(timezone.utc).isoformat()})
        session.revision += 1
        self._event(session, actor, "response_recorded")
        return session.responses[-1]
