# Experimental offline extension packages

`prototype/extension_package.py` lets developers inspect a local JSON package that declares a curriculum, narration, or assessment extension. It is **synthetic-only**, experimental, offline and data-only. It is not an HTTP API, provider loader, publication pipeline or code sandbox. The running application does not import or serve these packages. This interface makes no request to a cloud service and has no billing dependency.

```sh
python3 -m prototype.extension_package examples/extensions/synthetic-curriculum.json
```

A successful run prints the manifest identity, each record's version and SHA-256 digest, and a package digest. These deterministic hashes help compare data; they are **not digital signatures, evidence of provenance, or approval**. Invalid input exits nonzero without importing or modifying anything. Do not include real student data.

The package is UTF-8 JSON with exactly three top-level keys:

- `format`: the literal `living-literacy.synthetic-extension-package.v0.1`.
- `manifest`: the existing strict manifest defined in [EXTENSION_CONTRACTS.md](EXTENSION_CONTRACTS.md), declaring `curriculum`, `narration`, or `assessment`, the corresponding allowed read capability, and `synthetic_only`.
- `records`: a nonempty array of up to 100 records. Each record has exactly `id`, `version`, `status`, `provenance`, `rights`, and `payload`. The ID starts with `synthetic-`; version is `major.minor.patch`; status can only be `draft` or `needs_expert_review`. Provenance and rights are nonempty strings **asserted by the package author**, not verified facts; payload is a JSON object of draft data. Duplicate ID/version pairs are rejected.

JSON files are limited to 1 MiB. Duplicate keys, nonfinite numbers, floating-point values, excessive nesting and node counts, unknown fields, unsupported capabilities, and non-synthetic scope fail closed. Identifiers and canonical JSON are summarized in output; record payloads and rights text are not printed. Package file paths are local input only and are not interpreted as commands, module names or URLs. No arbitrary extension code is loaded or executed. Treat all content as untrusted even if validation succeeds.

Record and package hashes use UTF-8 JSON with sorted keys, unescaped Unicode and compact separators. This experimental serialization is not presented as a standardized signature format; pin the full package and contract version and do not treat it as cryptographic identity. Future imports and provider calls need separately reviewed authorization, verified provenance and licensing, independently reviewed publication, integrity and withdrawal, and compatible secure storage before integration. The prototype remains unsuitable for real student data.
