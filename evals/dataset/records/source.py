"""Source: where an item came from, with the references that regenerate it."""

from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, model_validator

from .source_kind import SourceKind

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")

REQUIRED: Mapping[SourceKind, frozenset[str]] = {
    SourceKind.authored: frozenset({"dataset_version"}),
    SourceKind.mined: frozenset({"artefact", "commit", "register_row"}),
    SourceKind.captured: frozenset({"session_id", "redaction_sha256"}),
    SourceKind.perturbed: frozenset({"parent_id", "perturbation"}),
    SourceKind.templated: frozenset({"family", "template_version"}),
    SourceKind.drafted: frozenset({"draft_id", "adjudicated"}),
    SourceKind.imported: frozenset({"register_row", "record_id"}),
}
OPTIONAL: Mapping[SourceKind, frozenset[str]] = {
    SourceKind.authored: frozenset({"note"}),
}
REFERENCE_FIELDS = frozenset().union(*REQUIRED.values(), *OPTIONAL.values())

SKILL_NOTE = "reproduces a worked example in ember/agent_kit/ember-advise/SKILL.md"
LEGACY_SOURCES: Mapping[str, str | None] = {"curated": None, "skill_md": SKILL_NOTE}

VARIANT_PERTURBATIONS = frozenset({"paraphrase", "format"})


class Source(BaseModel):
    """An item's provenance: its kind plus exactly that kind's references.

    Parameters
    ----------
    kind : SourceKind
        How the item was produced.
    dataset_version, note : str | None
        ``authored``: the content hash of the dataset version that introduced the
        item, and an optional note.
    artefact, commit, register_row : str | None
        ``mined``: the repository path, the 40-hex commit it was read at, and the
        register row that records the source's provenance.
    session_id, redaction_sha256 : str | None
        ``captured``: the session and the hash of its redaction record.
    parent_id, perturbation : str | None
        ``perturbed``: the original item and the perturbation applied
        (``paraphrase`` or ``format`` mark a variant).
    family, template_version : str | None
        ``templated``: the template family and its version.
    draft_id, adjudicated : str | bool | None
        ``drafted``: the model draft and the (required) human adjudication.
    register_row, record_id : str | None
        ``imported``: the data-source register row and the record within it.
    """

    model_config = ConfigDict(frozen=True)

    kind: SourceKind
    dataset_version: str | None = None
    note: str | None = None
    artefact: str | None = None
    commit: str | None = None
    session_id: str | None = None
    redaction_sha256: str | None = None
    parent_id: str | None = None
    perturbation: str | None = None
    family: str | None = None
    template_version: str | None = None
    draft_id: str | None = None
    adjudicated: bool | None = None
    register_row: str | None = None
    record_id: str | None = None

    @model_validator(mode="after")
    def _exactly_this_kinds_references(self) -> Source:
        allowed = REQUIRED[self.kind] | OPTIONAL.get(self.kind, frozenset())
        present = {f for f in REFERENCE_FIELDS if getattr(self, f) is not None}
        missing = REQUIRED[self.kind] - present
        foreign = present - allowed
        if missing:
            raise ValueError(f"{self.kind.value} source is missing {sorted(missing)}")
        if foreign:
            raise ValueError(
                f"{self.kind.value} source has foreign fields {sorted(foreign)}"
            )
        if self.dataset_version is not None and not _HEX64.match(self.dataset_version):
            raise ValueError("dataset_version must be a 64-hex SHA-256")
        if self.commit is not None and not _HEX40.match(self.commit):
            raise ValueError("commit must be a 40-hex git SHA")
        redaction = self.redaction_sha256
        if redaction is not None and not _HEX64.match(redaction):
            raise ValueError("redaction_sha256 must be a 64-hex SHA-256")
        if self.kind is SourceKind.drafted and self.adjudicated is not True:
            raise ValueError("a drafted item must be adjudicated by a person")
        return self

    @property
    def is_variant(self) -> bool:
        """Whether this is a paraphrase or format variant of its parent."""
        if self.kind is not SourceKind.perturbed:
            return False
        return self.perturbation in VARIANT_PERTURBATIONS


def from_legacy(value: str, dataset_version: str) -> Source:
    """Map a pre-Phase-0 string source (``curated``, ``skill_md``) to ``authored``.

    Parameters
    ----------
    value : str
        The legacy string.
    dataset_version : str
        The content hash recorded as the item's ``dataset_version``.

    Returns
    -------
    Source
        An ``authored`` source, with the SKILL.md note for ``skill_md``.

    Raises
    ------
    ValueError
        If ``value`` is not a known legacy source.
    """
    if value not in LEGACY_SOURCES:
        raise ValueError(f"unknown legacy source {value!r}")
    return Source(
        kind=SourceKind.authored,
        dataset_version=dataset_version,
        note=LEGACY_SOURCES[value],
    )
