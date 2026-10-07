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

from . import analysis
from .agent import report as agent_report
from .render import render_html, render_markdown


def write_atomic(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a sibling ``.tmp`` and ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def copy_atomic(source: Path, target: Path) -> None:
    """Copy ``source`` to ``target`` via a sibling ``.tmp`` and ``os.replace``."""
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
        write_atomic(out / "figures" / name, svg)
    write_atomic(out / "report.md", markdown)
    write_atomic(out / "report.html", render_html.render(report))
    copy_atomic(results_path, out / "data" / "results.json")
    copy_atomic(
        results_path.with_name(meta["trace_file"]), out / "data" / "trace.jsonl"
    )
    dataset = analysis.dataset_for(results_path, meta["dataset"])
    if dataset.exists():
        copy_atomic(dataset, out / "data" / "dataset.jsonl")
    if agent_path is not None:
        copy_atomic(agent_path, out / "data" / "agent_results.json")
        trace = agent_path.with_name(report["agent"]["config"]["trace"])
        copy_atomic(trace, out / "data" / "agent_trace.jsonl")
    return out
