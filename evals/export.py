"""Write the reviewer bundle for one run: Markdown, HTML, figures, raw data.

Layout under ``out_dir`` (default ``results/<run_id>_report/``)::

    report.html        single self-contained file
    report.md          GitHub-flavoured Markdown; figures in figures/
    figures/*.svg
    data/results.json  the run's results, trace, and the dataset it scored
    data/trace.jsonl
    data/dataset.jsonl
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import analysis, render_html, render_markdown
from .agent import report as agent_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, target)


def export(
    results_path: Path, out_dir: Path | None = None, agent_path: Path | None = None
) -> Path:
    """Write the report bundle for ``results_path`` and return its directory.

    ``agent_path`` attaches an ``agent_*_results.json`` run as the
    agent-in-the-loop section.
    """
    report = analysis.build(results_path)
    if agent_path is not None:
        report["agent"] = agent_report.build(agent_path)
    meta = report["meta"]
    out = out_dir or results_path.with_name(f"{meta['run_id']}_report")
    markdown, figures = render_markdown.render(report)
    shutil.rmtree(out / "figures", ignore_errors=True)
    shutil.rmtree(out / "data", ignore_errors=True)
    for name, svg in figures.items():
        _write(out / "figures" / name, svg)
    _write(out / "report.md", markdown)
    _write(out / "report.html", render_html.render(report))
    _copy(results_path, out / "data" / "results.json")
    _copy(results_path.with_name(meta["trace_file"]), out / "data" / "trace.jsonl")
    dataset = analysis.dataset_for(results_path, meta["dataset"])
    if dataset.exists():
        _copy(dataset, out / "data" / "dataset.jsonl")
    if agent_path is not None:
        _copy(agent_path, out / "data" / "agent_results.json")
        trace = agent_path.with_name(report["agent"]["config"]["trace"])
        _copy(trace, out / "data" / "agent_trace.jsonl")
    return out
