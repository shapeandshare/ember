---
layout: home
title: ember
description: A local gut feeling for coding agents. ember runs a decision model (currently Cloudflare's Clef) on your Apple Silicon Mac and answers typed judgment questions as calibrated probabilities.
---
{%- assign bench_home = site.data.benchmark.sections[0].anchor | default: "summary" %}
<picture class="hero-art">
  <source media="(prefers-color-scheme: dark)" srcset="{{ '/assets/brand/svg/ember-dark.svg' | relative_url }}">
  <img src="{{ '/assets/brand/svg/ember-light.svg' | relative_url }}" alt="ember — a curled plum mascot hugging a glowing tummy." width="200" height="200">
</picture>

# Give your agent a gut feeling.

<p class="lede">A local gut feeling for coding agents. ember runs a decision model (currently Cloudflare's Clef) on your Apple Silicon Mac and answers typed judgment questions as calibrated probabilities — privately, in about a second.</p>

<ul class="hero-links">
  <li>
    <a href="{{ '/docs/overview/' | relative_url }}">
      <strong>Install ember</strong>
      <span>uv tool install, then connect it to your coding agent</span>
    </a>
  </li>
  <li>
    <a href="{{ '/results/' | append: bench_home | append: '/' | relative_url }}">
      <strong>Benchmark</strong>
      <span>How ember scores against the agent kit's decision rules</span>
    </a>
  </li>
  <li>
    <a href="{{ site.github }}">
      <strong>Source on GitHub</strong>
      <span>Code, issues, and the MIT license</span>
    </a>
  </li>
</ul>

```bash
uv tool install --python 3.12 "gut @ git+https://github.com/shapeandshare/ember"

ember model pull          # ~18 GB, resumable
ember doctor              # platform, dependencies, model, server
ember init --opencode     # register the MCP server and skill
```

ember plugs into coding agents as an MCP tool, `advise`: describe a situation, ask typed
questions (`noul`, `choice`, `score`), and get back a calibrated probability for every option.
No prose. The model server stays warm on your machine; the agent decides what to do with the
answer.

Read the [Overview]({{ '/docs/overview/' | relative_url }}) to install and run it, or the
[Benchmark report]({{ '/results/' | append: bench_home | append: '/' | relative_url }}) to see
how it scores against the agent kit's decision rules.
