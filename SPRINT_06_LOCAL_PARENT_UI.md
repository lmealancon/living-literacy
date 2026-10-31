# Sprint 06 — Local synthetic parent-facing UI

Implemented: local-only HTTP demonstration, black/gold responsive accessible labels, six-stage progress, session actions, practice recording, restart-isolated temporary SQLite data.

Run from project root: `python -m prototype.local_web`; visit `http://127.0.0.1:8765`. Python standard library only.

Security boundary: binds 127.0.0.1, creates fictional identity in temporary database, no real login, no CSRF-grade security, no guardian consent, no production deployment, no real child data, no diagnostic claims. UI is not a validated educational lesson.

Next: proper web stack, authentication, consent/guardian authorization, per-user sessions, CSRF protections, rate limiting, and independent security review before any public deployment.
