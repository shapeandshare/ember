"""RegisterRow: one external dataset in the data-source register."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .licence_class import LicenceClass
from .licence_reading import LicenceReading
from .mirror_ref import MirrorRef
from .snapshot_ref import SnapshotRef
from .url_reading import UrlReading
from .verdict import Verdict

EXCLUDING_CLASSES = frozenset(
    {LicenceClass.non_commercial, LicenceClass.research_only, LicenceClass.gated}
)


class RegisterRow(BaseModel):
    """Everything recorded about one external dataset.

    Parameters
    ----------
    id, name : str
        A slug and the dataset's name.
    urls : list[UrlReading]
        Where it lives, each with the date it was read.
    licence : LicenceReading
        The licence as read.
    verdict, reason : Verdict, str
        Whether it may be used, and why.
    permission : str | None
        The written permission a ``custom_permissive`` used row rests on.
    snapshot, mirror, transformation
        Required once the row is ``used``.
    feeds : list[str]
        The recipes it feeds.
    items_imported : int
        How many dataset items reference the row.
    attribution : str | None
        The notice its licence requires.
    upstream_available : bool
        Set by the audit; items and the mirror stay when it turns false.
    notes : str | None
        Anything else worth recording.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str = Field(min_length=1)
    urls: list[UrlReading] = Field(min_length=1)
    licence: LicenceReading
    verdict: Verdict
    reason: str = Field(min_length=1)
    permission: str | None = None
    snapshot: SnapshotRef | None = None
    mirror: MirrorRef | None = None
    transformation: str | None = None
    feeds: list[str] = Field(default_factory=list)
    items_imported: int = Field(default=0, ge=0)
    attribution: str | None = None
    upstream_available: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def _verdict_is_consistent(self) -> RegisterRow:
        if self.verdict is Verdict.used:
            if self.snapshot is None or self.mirror is None or not self.transformation:
                raise ValueError(
                    f"{self.id}: a used row needs snapshot, mirror, transformation"
                )
            if self.mirror.sha256 != self.snapshot.sha256:
                raise ValueError(f"{self.id}: mirror hash differs from snapshot hash")
            if self.licence.class_ is LicenceClass.share_alike and not self.attribution:
                raise ValueError(f"{self.id}: a share-alike source needs attribution")
            if (
                self.licence.class_ is LicenceClass.custom_permissive
                and not self.permission
            ):
                raise ValueError(
                    f"{self.id}: a custom-permissive used row needs the permission "
                    "it rests on"
                )
        elif self.items_imported:
            raise ValueError(f"{self.id}: only a used row may have imported items")
        excluded = self.verdict is Verdict.excluded
        if self.licence.class_ in EXCLUDING_CLASSES and not excluded:
            raise ValueError(
                f"{self.id}: {self.licence.class_.value} licence is excluded"
            )
        return self
