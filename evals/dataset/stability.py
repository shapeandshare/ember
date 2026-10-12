"""The label-stability round tool: emit a blinded sheet, ingest it, publish agreement.

A round is a committed record (``evals/dataset/stability/<round-id>.json``), not a
per-item field: ``emit`` writes the blinded sheet (the gold level is withheld, only a
SHA-256 commitment travels so a gold change between emit and ingest is detected),
``ingest`` validates and writes the round, and ``compute`` turns rounds into the
per-recipe agreement the card publishes. Scope today: ``change_risk``/``risk`` and
``effort_approach``/``effort`` (Phase 1 decision R11).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ..atomic import write_atomic
from . import io
from .records.item import Item
from .records.stability_entry import StabilityEntry
from .records.stability_result import StabilityResult
from .records.stability_round import StabilityRound
from .scales import scale_for

STABILITY_DIR = Path(__file__).parent / "stability"
SCOPE: dict[str, str] = {"change_risk": "risk", "effort_approach": "effort"}
_COOLING_OFF = "7d"
_METHOD = "original labels withheld"
_ROUND_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

SINGLE_RATER = (
    "Single rater: stability is one person's blinded re-label after a cooling-off "
    "period, not inter-rater agreement; the model never labels."
)


class StabilityError(Exception):
    """Raised when a sheet or round violates the stability contract."""


def commit_label(value: int) -> str:
    """Return the blinding-safe SHA-256 commitment of a gold level.

    Parameters
    ----------
    value : int
        The gold level index.

    Returns
    -------
    str
        The 64-hex commitment stored on the sheet instead of the label.
    """
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def emit(
    items: list[Item],
    *,
    round_id: str,
    cooling_off: str = _COOLING_OFF,
    method: str = _METHOD,
) -> dict[str, Any]:
    """Build the blinded re-label sheet for the scoped items.

    Parameters
    ----------
    items : list[Item]
        The dataset items.
    round_id : str
        The round identifier.
    cooling_off : str, optional
        The declared cooling-off window.
    method : str, optional
        How blinding was ensured.

    Returns
    -------
    dict[str, Any]
        The sheet: per item, its rubric, state, and a commitment — never the label.
    """
    entries: list[dict[str, Any]] = []
    for item in items:
        question_id = SCOPE.get(item.category)
        if question_id is None or question_id not in item.questions:
            continue
        question = item.questions[question_id]
        criteria = list(question.get("criteria") or [])
        gold = item.gold_labels.get(question_id)
        if gold is None or not criteria:
            continue
        scale = scale_for(item.category, question_id)
        anchors = list(getattr(scale, "anchors", None) or []) if scale else []
        entries.append(
            {
                "id": item.id,
                "category": item.category,
                "question": question_id,
                "criteria": criteria,
                "anchors": anchors,
                "state": item.state,
                "original_sha256": commit_label(int(gold)),
                "relabel": None,
            }
        )
    return {
        "round_id": round_id,
        "cooling_off": cooling_off,
        "method": method,
        "items": entries,
    }


def ingest(
    sheet: dict[str, Any],
    items: list[Item],
    *,
    directory: Path = STABILITY_DIR,
    labelled_on: str | None = None,
) -> StabilityRound:
    """Validate a filled sheet and write its round record.

    Parameters
    ----------
    sheet : dict[str, Any]
        The filled sheet from :func:`emit`.
    items : list[Item]
        The current dataset items (the gold commitment is checked against them).
    directory : Path, optional
        Where the round record is written; defaults to ``STABILITY_DIR``.
    labelled_on : str | None, optional
        The re-label date; defaults to today.

    Returns
    -------
    StabilityRound
        The written round.

    Raises
    ------
    StabilityError
        If the sheet carries an unknown or duplicate item, an unfilled or
        out-of-range re-label, or a gold change since the sheet was emitted.
        Nothing is written on refusal.
    """
    round_id = str(sheet.get("round_id") or "")
    if not _ROUND_ID_RE.match(round_id):
        raise StabilityError(
            "the sheet must carry a round_id of letters, digits, '.', '-', or '_'"
        )
    raw = sheet.get("items")
    if not isinstance(raw, list) or not raw:
        raise StabilityError("the sheet contains no items")
    by_id = {item.id: item for item in items}
    seen: set[str] = set()
    today = labelled_on or date.today().isoformat()
    entries: list[StabilityEntry] = []
    for raw_entry in raw:
        item_id = str(raw_entry.get("id") or "")
        if item_id in seen:
            raise StabilityError(f"item {item_id!r} appears twice in the sheet")
        seen.add(item_id)
        item = by_id.get(item_id)
        if item is None:
            raise StabilityError(f"unknown item {item_id!r}: not in the dataset")
        question_id = str(raw_entry.get("question") or "")
        if raw_entry.get("category") != item.category or (
            question_id not in item.questions
        ):
            raise StabilityError(
                f"{item_id}: category/question do not match the dataset"
            )
        question = item.questions[question_id]
        levels = len(question.get("criteria") or [])
        relabel = raw_entry.get("relabel")
        if (
            levels <= 0
            or not isinstance(relabel, int)
            or isinstance(relabel, bool)
            or not 0 <= relabel < levels
        ):
            raise StabilityError(f"{item_id}: relabel is missing or out of range")
        gold = item.gold_labels.get(question_id)
        if gold is None or raw_entry.get("original_sha256") != commit_label(int(gold)):
            raise StabilityError(
                f"{item_id}: the gold level changed since the sheet was emitted"
            )
        entries.append(
            StabilityEntry(
                id=item_id,
                category=item.category,
                question=question_id,
                original=int(gold),
                relabel=relabel,
                agrees=relabel == int(gold),
                labelled_on=today,
            )
        )
    round_ = StabilityRound(
        round_id=round_id,
        cooling_off=str(sheet.get("cooling_off") or _COOLING_OFF),
        method=str(sheet.get("method") or _METHOD),
        labelled_on=today,
        entries=entries,
    )
    write_atomic(
        directory / f"{round_id}.json", round_.model_dump_json(indent=2) + "\n"
    )
    return round_


def load_rounds(directory: Path = STABILITY_DIR) -> list[StabilityRound]:
    """Return every committed round in ``directory``, oldest name first."""
    if not directory.is_dir():
        return []
    return [
        StabilityRound.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def compute(rounds: list[StabilityRound]) -> dict[str, StabilityResult]:
    """Compute per-recipe agreement from every committed round.

    Parameters
    ----------
    rounds : list[StabilityRound]
        The rounds to aggregate.

    Returns
    -------
    dict[str, StabilityResult]
        Agreement, per-label agreement, and the unstable ids, keyed by recipe.
    """
    per_recipe: dict[str, list[StabilityEntry]] = {}
    for round_ in rounds:
        for entry in round_.entries:
            per_recipe.setdefault(entry.category, []).append(entry)
    results: dict[str, StabilityResult] = {}
    for category, entries in sorted(per_recipe.items()):
        flags: dict[str, list[int]] = {}
        for entry in entries:
            flags.setdefault(str(entry.original), []).append(1 if entry.agrees else 0)
        results[category] = StabilityResult(
            agreement=sum(1 for e in entries if e.agrees) / len(entries),
            by_label={label: sum(v) / len(v) for label, v in sorted(flags.items())},
            unstable=[entry.id for entry in entries if not entry.agrees],
            rater_count=1,
        )
    return results


def render(results: dict[str, StabilityResult]) -> str:
    """Render the computed stability as the report's plain-text block."""
    lines: list[str] = []
    for category, result in sorted(results.items()):
        lines.append(
            f"{category}: agreement {result.agreement:.0%};"
            f" unstable {len(result.unstable)}"
        )
    lines.append(SINGLE_RATER)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``ember eval dataset stability --emit | --ingest | --report``."""
    parser = argparse.ArgumentParser(
        prog="ember eval dataset stability",
        description="emit a blinded re-label sheet, ingest it, or report agreement",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--emit", action="store_true", help="write the blinded sheet")
    action.add_argument("--ingest", metavar="SHEET", help="read a filled sheet")
    action.add_argument("--report", action="store_true", help="print agreement")
    parser.add_argument("--round", dest="round_id", default=None, help="round id")
    parser.add_argument("--dataset", default=str(io.DATASET_PATH))
    parser.add_argument("--out", default=None, help="sheet path (default: stdout)")
    parser.add_argument(
        "--rounds-dir", dest="rounds_dir", default=str(STABILITY_DIR)
    )
    args = parser.parse_args(argv)

    if args.emit:
        round_id = args.round_id or f"{date.today().isoformat()}-risk-effort"
        sheet = emit(io.read_items(Path(args.dataset)), round_id=round_id)
        text = json.dumps(sheet, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            write_atomic(Path(args.out), text)
            print(f"sheet: {args.out} ({len(sheet['items'])} items)")
        else:
            sys.stdout.write(text)
        return 0

    if args.ingest:
        try:
            sheet = json.loads(Path(args.ingest).read_text(encoding="utf-8"))
            round_ = ingest(
                sheet,
                io.read_items(Path(args.dataset)),
                directory=Path(args.rounds_dir),
            )
        except (StabilityError, json.JSONDecodeError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"round {round_.round_id}: {len(round_.entries)} entries written")
        return 0

    rounds = load_rounds(Path(args.rounds_dir))
    if not rounds:
        print("no stability rounds yet; --emit, fill the sheet, then --ingest")
        return 0
    print(render(compute(rounds)))
    return 0
