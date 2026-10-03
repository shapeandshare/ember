"""Single-file HTML writer for the benchmark report.

The page inlines its stylesheet, every chart as SVG, the Ember mascot, and a
few lines of progressive-enhancement script (theme toggle, contents highlight,
item filters). It loads nothing from the network.
"""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import Any

from . import blocks as b
from . import brand, document, svg
from .markup import Citations, to_html

CSS = Path(__file__).with_name("report.css")
TONE_LABEL = {"good": "Holds", "warn": "Watch", "info": "Note", "bad": "Wrong action"}
ICONS = {
    "good": '<path d="M3.5 8.5l3 3 6-7"/>',
    "bad": '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
    "warn": '<path d="M8 2.5l6 11H2z"/><path d="M8 6.8v3M8 11.9v.1"/>',
    "info": '<circle cx="8" cy="8" r="6"/><path d="M8 7.4v4M8 4.9v.1"/>',
}
SCRIPT = """
(() => {
  const root = document.documentElement, button = document.getElementById("theme");
  const modes = ["auto", "light", "dark"];
  let mode = "auto";
  try { mode = localStorage.getItem("ember-report-theme") || "auto"; } catch (e) {}
  const apply = (next) => {
    mode = next;
    if (mode === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", mode);
    button.querySelector("span").textContent = mode;
    try { localStorage.setItem("ember-report-theme", mode); } catch (e) {}
  };
  button.hidden = false;
  button.addEventListener("click", () => apply(modes[(modes.indexOf(mode) + 1) % 3]));
  apply(mode);
  document.querySelectorAll("form[data-filter-table]").forEach((form) => {
    const table = document.getElementById(form.dataset.filterTable);
    const status = form.querySelector("[data-count]");
    const update = () => {
      const picks = [...form.querySelectorAll("select")].map((s) => [s.name, s.value]);
      let shown = 0;
      table.querySelectorAll("tbody tr").forEach((row) => {
        const keep = picks.every(([k, v]) => !v || row.dataset[k] === v);
        row.hidden = !keep;
        shown += keep ? 1 : 0;
      });
      status.textContent = shown + " of " + table.tBodies[0].rows.length + " items";
    };
    form.addEventListener("change", update);
    form.addEventListener("submit", (e) => e.preventDefault());
    form.hidden = false;
    update();
  });
  const links = new Map([...document.querySelectorAll(".toc a")]
    .map((a) => [a.getAttribute("href").slice(1), a]));
  const seen = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      links.forEach((a) => a.removeAttribute("aria-current"));
      const link = links.get(entry.target.id);
      if (link) link.setAttribute("aria-current", "true");
    });
  }, { rootMargin: "-15% 0px -75% 0px" });
  document.querySelectorAll("main > section[id]").forEach((s) => seen.observe(s));
})();
"""


def _icon(kind: str) -> str:
    return (
        f'<svg class="icon" viewBox="0 0 16 16" aria-hidden="true">'
        f"{ICONS.get(kind, ICONS['info'])}</svg>"
    )


def _lines(value: str) -> str:
    return escape(value).replace("\n", "<br>")


def _theme_css() -> str:
    light = ";".join(f"--c-{k}:{v}" for k, v in svg.LIGHT.items())
    dark = ";".join(f"--c-{k}:{v}" for k, v in svg.DARK.items())
    return (
        f":root{{{light}}}"
        "@media (prefers-color-scheme: dark)"
        f"{{:root:not([data-theme=light]){{{dark}}}}}"
        f":root[data-theme=dark]{{{dark}}}"
        "@media print{:root,:root:not([data-theme=light]),:root[data-theme=dark]"
        f"{{{light}}}}}" + svg.rules(lambda token: f"var(--c-{token})", scope=".chart")
    )


class _Writer:
    def __init__(self, report: Mapping[str, Any]) -> None:
        self.cites = Citations(report["text"]["references"])
        self.count = 0

    def markup(self, value: str) -> str:
        return to_html(value, self.cites)

    def cell(self, cell: b.Cell, tag: str = "td") -> str:
        if cell.kind == "code":
            inner = f"<code>{_lines(cell.value)}</code>" if cell.value else ""
        elif cell.kind in ("good", "bad"):
            inner = (
                f'<span class="pill {cell.kind}">{_icon(cell.kind)}'
                f"{escape(cell.value)}</span>"
            )
        else:
            inner = _lines(cell.value)
        cls = ' class="num"' if cell.kind == "num" else ""
        return f"<{tag}{cls}>{inner}</{tag}>"

    def table(self, block: b.Table) -> str:
        parts = []
        if block.filters:
            selects = "".join(
                f'<label>{escape(label)} <select name="{key}"><option value="">all'
                "</option>"
                + "".join(
                    f'<option value="{escape(o)}">{escape(o)}</option>' for o in options
                )
                + "</select></label>"
                for key, label, options in block.filters
            )
            parts.append(
                f'<form class="filters" data-filter-table="{block.anchor}" '
                f'hidden>{selects}<output data-count aria-live="polite">'
                "</output></form>"
            )
        ident = f' id="{block.anchor}"' if block.anchor else ""
        caption = (
            f"<caption>{self.markup(block.caption)}</caption>" if block.caption else ""
        )
        head = "".join(f'<th scope="col">{escape(h)}</th>' for h in block.headers)
        rows = []
        for index, row in enumerate(block.rows):
            data = block.row_data[index] if block.row_data else {}
            attrs = "".join(f' data-{k}="{escape(v)}"' for k, v in data.items())
            rows.append(f"<tr{attrs}>" + "".join(self.cell(c) for c in row) + "</tr>")
        parts.append(
            f'<div class="table-wrap"><table{ident}>{caption}<thead><tr>{head}'
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        )
        return "".join(parts)

    def figure(self, block: b.Figure) -> str:
        media = block.draw(False)
        if not block.numbered:
            return f'<div class="mini">{media}</div>'
        self.count += 1
        text = (
            '<details class="fig-text"><summary>Text version</summary>'
            f'<pre class="code"><code>{escape(block.text)}</code></pre></details>'
            if block.text
            else ""
        )
        return (
            f'<figure class="fig" id="fig-{block.name}"><div class="fig-media">'
            f'{media}</div><figcaption><span class="fig-label">Figure '
            f"{self.count}</span> {self.markup(block.caption)}</figcaption>"
            f"{text}</figure>"
        )

    def card(self, block: b.Card) -> str:
        facts = "".join(
            f"<div><dt>{escape(k)}</dt>{self.cell(v, 'dd')}</div>"
            for k, v in block.facts
        )
        body = "".join(self.block(inner) for inner in block.body)
        return (
            f'<article class="card {block.tone}"><header class="card-head">'
            f'<h4>{escape(block.title)}</h4><span class="tag">'
            f'{escape(block.tag)}</span></header><dl class="facts">{facts}</dl>'
            f"{body}</article>"
        )

    def block(self, block: b.Block) -> str:
        if isinstance(block, b.Para):
            inner = escape(block.text) if block.literal else self.markup(block.text)
            return f"<p>{inner}</p>"
        if isinstance(block, b.Bullets):
            items = "".join(f"<li>{self.markup(i)}</li>" for i in block.items)
            return f'<ul class="list">{items}</ul>'
        if isinstance(block, b.Heading):
            return f'<h3 id="{block.anchor}">{escape(block.text)}</h3>'
        if isinstance(block, b.Code):
            return (
                f'<pre class="code"><code data-lang="{escape(block.lang)}">'
                f"{escape(block.text)}</code></pre>"
            )
        if isinstance(block, b.Callout):
            return (
                f'<aside class="callout {block.tone}" role="note"><p class="callout-'
                f'title">{_icon(block.tone)}<span class="tone">'
                f"{TONE_LABEL.get(block.tone, 'Note')}</span><strong>"
                f"{escape(block.title)}</strong></p><p>{self.markup(block.text)}"
                "</p></aside>"
            )
        if isinstance(block, b.Kpis):
            cards = "".join(
                f'<div class="kpi {k.tone}"><p class="kpi-label">{escape(k.label)}</p>'
                f'<p class="kpi-value">{escape(k.value)}</p><p class="kpi-note">'
                f"{escape(k.note)}</p></div>"
                for k in block.items
            )
            return f'<div class="kpis">{cards}</div>'
        if isinstance(block, b.Formula):
            return (
                f'<div class="formula" role="math" aria-label="{escape(block.text)}">'
                f"<code>{escape(block.text)}</code></div>"
            )
        if isinstance(block, b.Definitions):
            items = "".join(
                f"<div><dt>{escape(t)}</dt><dd>{self.markup(d)}</dd></div>"
                for t, d in block.items
            )
            return f'<dl class="defs">{items}</dl>'
        if isinstance(block, b.Figure):
            return self.figure(block)
        if isinstance(block, b.Gallery):
            figures = "".join(self.figure(f) for f in block.items)
            return f'<div class="gallery">{figures}</div>'
        if isinstance(block, b.Table):
            return self.table(block)
        if isinstance(block, b.Card):
            return self.card(block)
        if isinstance(block, b.Cards):
            return (
                f'<div class="cards">{"".join(self.card(c) for c in block.items)}</div>'
            )
        if isinstance(block, b.References):
            items = "".join(
                f'<li id="ref-{key}">{escape(text)} <a href="{escape(url)}">'
                f"{escape(url)}</a></li>"
                for key, text, url in block.items
            )
            return f'<ol class="refs">{items}</ol>'
        raise TypeError(f"unknown block {block!r}")


def _hero(report: Mapping[str, Any]) -> str:
    meta, text = report["meta"], report["text"]
    spec, host = meta["model_spec"], meta["host"]
    chips = [
        ("Run", meta["run_id"]),
        (
            "Model",
            f"{spec.get('repo', meta['model'])} @ {spec.get('revision', '?')[:7]}",
        ),
        ("Dataset", f"{meta['dataset']['name']} · {meta['dataset']['sha256'][:12]}"),
        ("Commit", meta["git_hash"]),
        ("Host", host.get("cpu", "not recorded")),
    ]
    chip_html = "".join(
        f"<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>" for k, v in chips
    )
    return (
        '<header class="hero"><div class="hero-inner"><div class="mascot">'
        f'{brand.inline("light")}{brand.inline("dark")}</div><div class="hero-text">'
        f'<p class="eyebrow">Benchmark report · {escape(meta["run_at"])}</p>'
        f'<h1>{escape(text["title"])}</h1><p class="lede">{escape(text["subtitle"])}.'
        f'</p><dl class="chips">{chip_html}</dl></div></div>'
        '<button id="theme" class="theme" type="button" hidden aria-label="Switch '
        'colour theme">Theme: <span>auto</span></button></header>'
    )


def render(report: Mapping[str, Any]) -> str:
    """Return the report as one self-contained HTML document."""
    writer = _Writer(report)
    meta, text = report["meta"], report["text"]
    sections = document.build(report)
    toc = "".join(
        f'<li><a href="#{s.anchor}"><span>{s.number}</span>{escape(s.title)}</a></li>'
        for s in sections
    )
    body = "".join(
        f'<section id="{s.anchor}" aria-labelledby="{s.anchor}-title"><h2 id="'
        f'{s.anchor}-title"><span class="sec-num">{s.number}</span>{escape(s.title)}'
        f"</h2>{''.join(writer.block(block) for block in s.blocks)}</section>"
        for s in sections
    )
    title = f"{text['title']}: {meta['run_id']}"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="generator" content="ember eval export">'
        f"<title>{escape(title)}</title><style>{_theme_css()}"
        f"{CSS.read_text(encoding='utf-8')}</style></head><body>"
        '<a class="skip" href="#main">Skip to the report</a>'
        f"{_hero(report)}"
        '<div class="layout"><nav class="toc" aria-label="Contents">'
        f'<p class="toc-title">Contents</p><ol>{toc}</ol></nav>'
        f'<main id="main">{body}</main></div>'
        f'<footer class="footer"><p>Generated by <code>ember eval export</code> on '
        f"{escape(meta['generated_at'])} from <code>{escape(meta['results_file'])}"
        "</code>. ember advises; the agent decides.</p></footer>"
        f"<script>{SCRIPT}</script></body></html>"
    )
