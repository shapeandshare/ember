"""GitHub-flavoured Markdown writer for the benchmark report.

``render`` returns the Markdown and the figures it references, as
``{file name: svg}``; the exporter writes them to ``figures/``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

from . import blocks as b
from . import brand, document
from .markup import Citations, md_code, md_fence, md_literal, to_markdown

TONE_LABEL = {"good": "Holds", "warn": "Watch", "info": "Note"}


class _Writer:
    def __init__(self, report: Mapping[str, Any]) -> None:
        self.cites = Citations(report["text"]["references"])
        self.figures: dict[str, str] = {}
        self.count = 0

    def markup(self, value: str) -> str:
        return to_markdown(value, self.cites)

    def cell(self, cell: b.Cell) -> str:
        if cell.kind == "code":
            return md_code(cell.value) if cell.value else ""
        if cell.kind == "good":
            return f"✅ {md_literal(cell.value)}"
        if cell.kind == "bad":
            return f"❌ {md_literal(cell.value)}"
        return md_literal(cell.value)

    def table(self, block: b.Table) -> list[str]:
        def align(index: int) -> str:
            kinds = {row[index].kind for row in block.rows}
            if kinds <= {"num"}:
                return "---:"
            if kinds <= {"good", "bad"}:
                return ":---:"
            return "---"

        lines = [
            "| " + " | ".join(md_literal(h) for h in block.headers) + " |",
            "| " + " | ".join(align(i) for i in range(len(block.headers))) + " |",
        ]
        lines += [
            "| " + " | ".join(self.cell(c) for c in row) + " |" for row in block.rows
        ]
        if block.caption:
            lines += ["", f"*{self.markup(block.caption)}*"]
        if block.collapse:
            lines = [
                f"<details><summary>{escape(block.collapse)}</summary>",
                "",
                *lines,
                "",
                "</details>",
            ]
        return lines

    def figure(self, block: b.Figure) -> list[str]:
        name = f"{block.name}.svg"
        self.figures[name] = block.draw(True)
        width = 760 if block.numbered else 560
        image = f'<img src="figures/{name}" alt="{escape(block.alt)}" width="{width}">'
        if not block.numbered:
            return [image]
        self.count += 1
        lines = [image, "", f"*Figure {self.count}. {self.markup(block.caption)}*"]
        if block.text:
            fence = md_fence(block.text)
            lines += ["", f"{fence}text", block.text, fence]
        return lines

    def card(self, block: b.Card) -> list[str]:
        lines = [
            f"#### {md_literal(block.title)}",
            "",
            f"*{md_literal(block.tag)}*",
            "",
            "| Field | Value |",
            "| --- | --- |",
        ]
        lines += [f"| {md_literal(k)} | {self.cell(v)} |" for k, v in block.facts]
        for inner in block.body:
            lines += ["", *self.block(inner)]
        return lines

    def block(self, block: b.Block) -> list[str]:
        if isinstance(block, b.Para):
            return [
                md_literal(block.text) if block.literal else self.markup(block.text)
            ]
        if isinstance(block, b.Bullets):
            return [f"- {self.markup(item)}" for item in block.items]
        if isinstance(block, b.Heading):
            return [f'<a id="{block.anchor}"></a>', "", f"### {block.text}"]
        if isinstance(block, b.Code):
            fence = md_fence(block.text)
            return [f"{fence}{block.lang}", block.text, fence]
        if isinstance(block, b.Callout):
            label = TONE_LABEL.get(block.tone, "Note")
            return [
                f"> **{label}: {md_literal(block.title)}.** {self.markup(block.text)}"
            ]
        if isinstance(block, b.Kpis):
            rows = [
                f"| {md_literal(k.label)} | **{md_literal(k.value)}** | "
                f"{md_literal(k.note)} |"
                for k in block.items
            ]
            return ["| Measure | Value | Detail |", "| --- | ---: | --- |", *rows]
        if isinstance(block, b.Formula):
            return ["$$", block.tex, "$$"]
        if isinstance(block, b.Definitions):
            rows = [
                f"| {md_literal(term)} | {self.markup(meaning)} |"
                for term, meaning in block.items
            ]
            return ["| Term | Meaning |", "| --- | --- |", *rows]
        if isinstance(block, b.Figure):
            return self.figure(block)
        if isinstance(block, b.Gallery):
            return self.join([self.figure(f) for f in block.items])
        if isinstance(block, b.Table):
            return self.table(block)
        if isinstance(block, b.Card):
            return self.card(block)
        if isinstance(block, b.Cards):
            return self.join([self.card(c) for c in block.items])
        if isinstance(block, b.References):
            return [
                f'{n}. <a id="ref-{key}"></a>{md_literal(text)} <{url}>'
                for n, (key, text, url) in enumerate(block.items, 1)
            ]
        raise TypeError(f"unknown block {block!r}")

    @staticmethod
    def join(parts: Sequence[list[str]]) -> list[str]:
        lines: list[str] = []
        for part in parts:
            lines += [*part, ""]
        return lines[:-1]


def render(report: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    """Return the Markdown report and its figures."""
    writer = _Writer(report)
    meta, text = report["meta"], report["text"]
    spec = meta["model_spec"]
    sections = document.build(report)
    writer.figures["ember-light.svg"] = brand.mascot("light")
    writer.figures["ember-dark.svg"] = brand.mascot("dark")
    model = f"{spec.get('repo', meta['model'])} @ {spec.get('revision', '?')[:7]}"
    lines = [
        '<p align="center"><picture><source media="(prefers-color-scheme: dark)" '
        'srcset="figures/ember-dark.svg"><img src="figures/ember-light.svg" '
        'alt="Ember, the ember mascot" width="120"></picture></p>',
        "",
        f"# {text['title']}",
        "",
        text["subtitle"] + ".",
        "",
        f"**Run** {md_code(meta['run_id'])} · **Model** {md_code(model)} · "
        f"**Dataset** {md_code(meta['dataset']['name'])} "
        f"({md_code(meta['dataset']['sha256'][:12])}) · **Commit** "
        f"{md_code(meta['git_hash'])} · **Run at** {meta['run_at']}",
        "",
        "## Contents",
        "",
        *(f"{s.number}. [{s.title}](#{s.anchor})" for s in sections),
    ]
    for section in sections:
        lines += [
            "",
            f'<a id="{section.anchor}"></a>',
            "",
            f"## {section.number}. {section.title}",
            "",
        ]
        lines += writer.join([writer.block(block) for block in section.blocks])
    lines += [
        "",
        "---",
        "",
        f"*Generated by `ember eval export` on {meta['generated_at']} from "
        f"{md_code(meta['results_file'])}. ember advises; the agent decides.*",
        "",
    ]
    return "\n".join(lines), writer.figures
