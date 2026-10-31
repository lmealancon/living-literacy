# Next bounded task: Guardian authorization foundation

Implement synthetic-only authorization model with explicit guardian-to-student relationship and workspace scope; no real child data. Avoid trusting client-submitted workspace IDs. Include negative tests for cross-family access, revoked grants, expired/withdrawn consent, token rotation and session invalidation. Do not treat a synthetic token as production login. Require independent security/privacy review and real identity provider before any live child onboarding. Preserve existing content withdrawal checks.
