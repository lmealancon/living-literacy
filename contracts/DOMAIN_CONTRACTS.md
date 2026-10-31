# Proposed domain contracts (non-executable draft)

Core entities: users, workspaces, workspace_memberships, student_profiles, student_relationships, consent_records, skill_versions, skill_dependencies, lesson_versions, lesson_sessions, session_stage_events, student_responses, assistance_events, evidence_records, validation_approvals, narration_scripts, audio_assets, billing_customers, subscriptions, entitlements, audit_events.

Lesson session states: created, active, paused, completed, abandoned, invalidated, closed. Completion != mastery.

API prefix /api/v1. Candidate routes: GET /me, /workspaces, /students, /skills, /lessons, /lessons/{id}, /lesson-sessions/{id}, /students/{id}/activity, /entitlements; POST /students, /lesson-sessions, /lesson-sessions/{id}/responses, /lesson-sessions/{id}/transitions, /narration/playback-requests, /privacy-requests.

Formal JSON Schema/OpenAPI, field-level data classification, FK constraints, authorization matrices, indexes and migration designs remain to be authored and reviewed. This document is not a runnable contract.
