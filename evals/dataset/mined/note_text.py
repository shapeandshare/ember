"""The shared state shaping for mined notes."""

from __future__ import annotations

from .candidate_note import CandidateNote


def note_text(note: CandidateNote) -> str:
    """Return the note's title and body, frontmatter stripped.

    A body whose heading repeats the title drops it, so the title appears once.
    """
    body = note.body.strip()
    heading = f"# {note.title}"
    if body.startswith(heading):
        body = body[len(heading) :].lstrip("\n")
    return f"{note.title}\n\n{body}"
