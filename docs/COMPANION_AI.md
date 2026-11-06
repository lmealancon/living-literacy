# Local AI companion experiment

The optional, disabled-by-default **adult synthetic experiment** includes a
fixed-prompt greeting and a freeform conversation adapter. It is not for children
or connected to lessons. On a localhost-only demo, the website can expose these
authenticated, CSRF-protected tools when the operator explicitly starts it with
`python3 -m prototype.app_server --synthetic-ai-model MODEL_NAME`. It remains
disabled by default and cannot be enabled through the staging or container CLI
modes. A local model service must already be running on port 11434. Trusted test
code may also explicitly construct
`LocalAICompanion(enabled=True, model='...', port=11434)` and request one of
`hello`, `encourage` or `break`. A separate Ollama-compatible server and model
must already be installed and running. No model is downloaded or bundled.

The fixed-prompt greeting only accepts approved action IDs and rejects outputs
other than its fixed phrases. The separate conversation experiment sends the
typed test message and up to three prior turns to the local model and displays
unreviewed generated text. Do not enter real names, student details, or other
personal information; the application cannot reliably detect them. The app
does not persist the conversation, but the model service can independently log
or forward it. No account ID, lesson or student record is added to the request.

The model adapter connects only to
`127.0.0.1` on an explicitly selected port, uses a fixed route, follows no
redirects, has a short timeout and limits response size. It never configures or
calls a hosted service itself. The operator must separately verify that the
local server and its chosen model do not forward traffic, log data or invoke
remote services; loopback alone does not establish that. The model and runtime
licenses, resource needs and behavior must also be reviewed.

The fixed greeting has a five-second caller deadline and a three-second socket
idle timeout. Conversation has a 45-second caller deadline and 30-second
socket idle timeout. Only one model request per application process can run at a time;
additional calls fail immediately. A timed-out worker retains that slot until
its socket operation ends, preventing a backlog but potentially leaving the
experiment unavailable until the worker or process is stopped.

The optional browser microphone and speech playback may use platform services
that transmit audio or spoken text. They require deliberate user actions and
have typed and silent alternatives. This is an unreviewed adult conversation
experiment, not a child-ready tutor or validated educational content. The adapter
itself has no child authorization, consent, moderation, youth safety,
audio-assistance tracking or clinical/educational validation. The demo HTTP
route uses synthetic account authentication and CSRF protection only. It must not be connected to real learners or
used with real student information. Follow the project's release gates before
any learner-facing AI or microphone functionality. If a model or service is
unavailable or returns unexpected output, the adapter reports a generic
`COMPANION_UNAVAILABLE` and does not return the generated text.
