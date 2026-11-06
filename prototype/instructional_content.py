"""Prototype-only instructional display content. Never use as validated instruction."""
import json
from pathlib import Path
from prototype.lesson_engine import STAGES, PolicyError

CONTENT_PATH = Path(__file__).resolve().parent.parent / 'content' / 'SYNTHETIC_WORD_STUDY.demo-1.json'

def load_demo_lesson(path=CONTENT_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return validate_demo_lesson(data)

def validate_demo_lesson(data):
    """Validate an already decoded synthetic lesson using the existing rules."""
    if not isinstance(data, dict):
        raise PolicyError('INVALID_STAGE_CONTENT')
    if data.get('publication_status') != 'prototype_only':
        raise PolicyError('DEMO_CONTENT_STATUS_REQUIRED')
    stages = data.get('stages', [])
    if not isinstance(stages, list) or any(not isinstance(stage, dict) for stage in stages):
        raise PolicyError('INVALID_LESSON_STAGES')
    if [stage.get('id') for stage in stages] != list(STAGES):
        raise PolicyError('INVALID_LESSON_STAGES')
    if data.get('skill_ids') != []:
        raise PolicyError('UNVALIDATED_SKILL_LINK')
    required = ('title', 'instruction', 'display_text', 'coach_note', 'response_prompt', 'independent_task')
    for index, stage in enumerate(stages):
        if any(not isinstance(stage.get(k), str) or not stage[k].strip() for k in required[:-1]):
            raise PolicyError('INVALID_STAGE_CONTENT')
        if type(stage.get('independent_task')) is not bool or stage['independent_task'] != (index == 4):
            raise PolicyError('INVALID_INDEPENDENCE_TAG')
    return data

def stage_content(lesson, index):
    if index < 0 or index >= len(STAGES):
        raise PolicyError('INVALID_STAGE_INDEX')
    return lesson['stages'][index]
