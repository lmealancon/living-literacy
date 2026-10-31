# Experimental extension contracts

`prototype/extension_contracts.py` defines Python interfaces and strict data-only manifest parsing for three prospective provider boundaries: versioned curriculum lessons, narration assets and assessment forms. Contract version `0.1` is a draft, not a stable public API or HTTP API. The current application does not discover, load or call providers through these interfaces.

A manifest can declare only one type and that type's read/description capability. Version strings use three numeric components; unknown fields, capabilities, types, contract versions and scopes fail closed. The current scope is explicitly `synthetic_only`. For example:

```json
{
  "extension_id": "synthetic.example",
  "version": "1.0.0",
  "contract_version": "0.1",
  "kind": "curriculum",
  "capabilities": ["lesson.read"],
  "data_scope": "synthetic_only"
}
```

Narration uses kind `narration` and capability `asset.describe`; assessments use kind `assessment` and capability `form.read`. Declarations are untrusted data: they do not establish licensing, privacy, safety, content approval, authority, or permission to process data. A provider cannot be safely loaded solely because a manifest parses. There is no plugin installer, code execution, sandbox, external network call, provider registry, or automatic permission grant in this module.

Any future integration must enforce server-side identity, role, workspace, relationship, purpose and consent before calling a provider; minimize data sent; verify provider provenance, license, version, content integrity, review and withdrawal status; and recheck those controls on use. Read Exactly requires verbatim fidelity and Story Vibes requires a reviewed retelling; narration exposure must be recorded before approved playback. Assessment validity and scientific claims require separate review. External providers and real child data remain blocked pending the release and vendor gates in `specs/RELEASE_GATES.md` and `docs/DECISION_REGISTER.md`.
