"""Draft, vendor-neutral contracts for synthetic-only extension discovery.

These interfaces are not a plugin loader, execution sandbox, authorization check,
content approval, or permission to handle real student data. A host must validate
all provider outputs using its own trusted policies after authorization. In
particular, existing lesson withdrawal, narration and assessment gates apply.

Contract v0.1 is experimental while API schemas and migrations (D-015) remain
unresolved. Provider implementations and any network calls are deliberately not
loaded or executed here. Manifest declarations are untrusted metadata.
"""
from dataclasses import dataclass
import re
from typing import Mapping, Protocol


class ExtensionContractError(ValueError):
    """A manifest is malformed or requests an unsupported contract."""


@dataclass(frozen=True)
class VersionedReference:
    """An opaque, version-pinned reference; not a retrieval URL or an approval."""
    identifier: str
    version: str


@dataclass(frozen=True)
class ExtensionManifest:
    extension_id: str
    version: str
    contract_version: str
    kind: str
    capabilities: tuple[str, ...]
    data_scope: str


# Methods deliberately operate on references rather than child records. Return
# data is untrusted; the host must verify its shape, provenance, approval and
# authorization at point of use. Protocol conformance is not security review.
class CurriculumProvider(Protocol):
    def lesson(self, reference: VersionedReference) -> Mapping[str, object]:
        """Describe a versioned lesson candidate for host-side validation."""
        ...


class NarrationProvider(Protocol):
    def asset(self, reference: VersionedReference) -> Mapping[str, object]:
        """Describe a versioned asset candidate, not authorization to play it."""
        ...


class AssessmentInstrumentProvider(Protocol):
    def form(self, reference: VersionedReference) -> Mapping[str, object]:
        """Describe a versioned form candidate, not a validated assessment."""
        ...


_FIELDS = frozenset({'extension_id', 'version', 'contract_version', 'kind',
                     'capabilities', 'data_scope'})
_ALLOWED = {
    'curriculum': frozenset({'lesson.read'}),
    'narration': frozenset({'asset.describe'}),
    'assessment': frozenset({'form.read'}),
}
_ID = re.compile(r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$')
_VERSION = re.compile(r'^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$')


def parse_manifest(raw: object) -> ExtensionManifest:
    """Validate data-only metadata; never import or execute provider code.

    Strict fields and explicit capability names make unexpected permissions
    fail closed. All manifests remain synthetic-only in this prototype; this
    declaration alone does not enforce isolation or authorize data processing.
    """
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise ExtensionContractError('Invalid manifest fields')
    extension_id, version = raw['extension_id'], raw['version']
    kind, contract_version = raw['kind'], raw['contract_version']
    capabilities, data_scope = raw['capabilities'], raw['data_scope']
    if (not isinstance(extension_id, str) or len(extension_id) > 128
            or not _ID.fullmatch(extension_id)):
        raise ExtensionContractError('Invalid extension identifier')
    if not isinstance(version, str) or len(version) > 32 or not _VERSION.fullmatch(version):
        raise ExtensionContractError('Invalid extension version')
    if contract_version != '0.1':
        raise ExtensionContractError('Unsupported contract version')
    if not isinstance(kind, str) or kind not in _ALLOWED:
        raise ExtensionContractError('Unsupported extension kind')
    if (not isinstance(capabilities, list) or not capabilities
            or any(not isinstance(x, str) for x in capabilities)
            or len(capabilities) != len(set(capabilities))
            or not set(capabilities).issubset(_ALLOWED[kind])):
        raise ExtensionContractError('Unsupported capabilities')
    if data_scope != 'synthetic_only':
        raise ExtensionContractError('Only synthetic-only manifests are supported')
    return ExtensionManifest(extension_id, version, contract_version, kind,
                             tuple(capabilities), data_scope)
