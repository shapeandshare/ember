"""Run one model's probe cells in this process: memory first, then quality (R8)."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

import torch
from ember import models
from ember.serving import request_size, runtime
from ember.serving.limit_source import LimitSource
from ember.serving.limits import Limits, declared_max_length

from ..eval.provenance import REPO_ROOT
from .filler import filler_ids, load_filler, offset_for
from .memory_sampler import MemorySampler
from .padding import build_state
from .records.depth import Depth
from .records.probe_manifest import ProbeManifest
from .records.probe_row import ProbeRow
from .records.probe_summary import ProbeSummary
from .records.row_status import RowStatus
from .rows_file import append_row, pending, read_rows, repair
from .summarize import dataset_items, load_manifest, rows_name, summarize

#: The pilot compares these lengths at the middle depth (research R10).
PILOT_LENGTHS = (2048, 16384)
_log = logging.getLogger(__name__)


def check_pins(manifest: ProbeManifest, model: str) -> None:
    """Refuse weights other than the repo and revision the run pinned.

    Raises
    ------
    RuntimeError
        If the registry's entry for ``model`` no longer matches the manifest.
    """
    spec, pinned = models.get(model), manifest.models[model]
    if (spec.repo, spec.revision) != (pinned.repo, pinned.revision):
        raise RuntimeError(
            f"the registry's {model} is {spec.repo}@{spec.revision}, but this run "
            f"pinned {pinned.repo}@{pinned.revision}; start a new run, or check out "
            "the commit that pinned it"
        )


def pinned_filler(manifest: ProbeManifest) -> str:
    """Load the filler the manifest pinned, verifying its SHA-256."""
    path = Path(manifest.filler_path)
    return load_filler(
        path if path.is_absolute() else REPO_ROOT / path, manifest.filler_sha256
    )


class _Prober:
    """Holds the engine and inputs one worker needs to run probe cells."""

    def __init__(self, run_dir: Path, manifest: ProbeManifest, model: str) -> None:
        check_pins(manifest, model)
        model_dir = models.resolve_dir(model, override=False)
        if model_dir is None:
            raise RuntimeError(
                f"model {model} is not pulled; run: ember model pull {model}"
            )
        declared = declared_max_length(model_dir)
        if declared is None:
            raise RuntimeError(f"model {model} declares no maximum in its config.json")
        self.engine = runtime.Engine(
            model_dir,
            limits=Limits(
                max_length=declared,
                max_length_source=LimitSource.MODEL,
                max_request_length=0,
                max_request_length_source=LimitSource.OPERATOR,
            ),
        )
        self.js = runtime.joint_module(model_dir)
        self.filler = filler_ids(
            self.engine.processor.tokenizer, pinned_filler(manifest)
        )
        self.manifest = manifest
        self.model = model
        self.items = dataset_items(manifest, run_dir)
        self.path = run_dir / rows_name(model)
        self.approx_bytes = models.get(model).approx_bytes

    def _request(self, state: str, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.engine.model_name,
            "state": state,
            "questions": item["questions"],
        }

    def _infer(
        self, item: dict[str, Any], length: int, depth: Depth, exploratory: bool
    ) -> ProbeRow:
        def count(state: str) -> int:
            return request_size.measure(
                self.js, self.engine.processor, self._request(state, item)
            ).total

        state = build_state(
            self.js.render(item["state"]),
            self.filler,
            self.engine.processor.tokenizer,
            depth,
            length,
            count,
            offset=offset_for(item["id"], max(self.manifest.lengths), len(self.filler)),
            tolerance=self.manifest.length_tolerance_tokens,
        )
        size = request_size.measure(
            self.js, self.engine.processor, self._request(state, item)
        )
        status, answers, error = RowStatus.OK, {}, None
        started = time.monotonic()
        with MemorySampler() as sampler:
            try:
                answers = self.engine.advise(state, item["questions"])["answers"]
            except RuntimeError as exc:
                oom = "out of memory" in str(exc).lower()
                status, error = (RowStatus.OOM if oom else RowStatus.ERROR), str(exc)
            except Exception as exc:  # the row keeps any other failure's message
                status, error = RowStatus.ERROR, f"{type(exc).__name__}: {exc}"
        if status is RowStatus.OOM:
            torch.mps.empty_cache()
        if sampler.rss_start_bytes > self.approx_bytes // 4:
            _log.warning(
                "rss at start is %d bytes, over 25%% of the weights: the peak may "
                "double-count the CPU copy (research R11)",
                sampler.rss_start_bytes,
            )
        return ProbeRow(
            run_id=self.manifest.run_id,
            model=self.model,
            item_id=item["id"],
            split=item["split"],
            category=item["category"],
            length=length,
            depth=depth,
            total_tokens=size.total,
            state_tokens=size.state,
            media_tokens=size.media,
            fixed_tokens=size.fixed,
            answers=answers if status is RowStatus.OK else {},
            latency_ms=(time.monotonic() - started) * 1000,
            rss_start_bytes=sampler.rss_start_bytes,
            driver_peak_bytes=sampler.driver_peak_bytes,
            peak_bytes=sampler.peak_bytes,
            status=status,
            exploratory=exploratory,
            error=error,
        )

    def run(
        self, cells: list[tuple[str, Depth]], length: int, exploratory: bool
    ) -> list[ProbeRow]:
        """Run the cells not yet recorded; return every row for these cells."""
        planned = [(self.model, item_id, length, depth) for item_id, depth in cells]
        for _, item_id, _, depth in pending(planned, read_rows(self.path)):
            row = self._infer(self.items[item_id], length, depth, exploratory)
            append_row(self.path, row)
            print(
                f"{self.model} {length:>6} {depth:<6} {item_id:<22} {row.status} "
                f"{row.latency_ms:8.0f} ms  peak {row.peak_bytes / 2**30:6.2f} GiB",
                file=sys.stderr,
            )
        wanted = set(planned)
        return [row for row in read_rows(self.path) if row.key in wanted]


def first_failure_at(summary: ProbeSummary, model: str, upto: int) -> int | None:
    """Return the model's first failing length among those up to ``upto``.

    A resumed run may hold partial rows for longer lengths; only lengths whose
    full pool has run count.
    """
    failing = [
        verdict.length
        for verdict in summary.lengths
        if verdict.model == model and verdict.length <= upto and not verdict.passes
    ]
    return min(failing) if failing else None


def run_model(run_dir: Path, model: str, *, pilot: bool = False) -> int:
    """Run ``model``'s cells for the run in ``run_dir``; return an exit code.

    Each length starts with a memory check (the first item at every depth). A
    check over the budget, or out of memory, ends the model: longer lengths
    would fail too. Quality cells then run every item before the first failing
    length, and only the exploratory subset after it.
    """
    manifest = load_manifest(run_dir)
    try:
        prober = _Prober(run_dir, manifest, model)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    repair(prober.path)
    lengths = PILOT_LENGTHS if pilot else tuple(manifest.lengths)
    depths = (Depth.MIDDLE,) if pilot else tuple(manifest.depths)
    budget = manifest.models[model].memory_budget_bytes
    first_failure: int | None = None
    for length in lengths:
        exploratory = first_failure is not None and length > first_failure
        check = prober.run(
            [(manifest.item_ids[0], d) for d in depths], length, exploratory
        )
        if (
            any(r.status is RowStatus.OOM for r in check)
            or max(r.peak_bytes for r in check) > budget
        ):
            print(f"{model} {length}: memory check failed; stopping", file=sys.stderr)
            break
        pool = manifest.exploratory_item_ids if exploratory else manifest.item_ids
        prober.run(
            [(item_id, d) for item_id in pool for d in depths], length, exploratory
        )
        if not pilot and first_failure is None:
            first_failure = first_failure_at(summarize(run_dir), model, length)
    return 0
