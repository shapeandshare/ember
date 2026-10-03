---
layout: home
title: ember
description: A local gut feeling for coding agents. ember runs Cloudflare's Clef model on your Apple Silicon Mac and answers typed judgment questions as calibrated probabilities.
---
<picture class="hero-art">
  <source media="(prefers-color-scheme: dark)" srcset="{{ '/assets/brand/svg/ember-dark.svg' | relative_url }}">
  <img src="{{ '/assets/brand/svg/ember-light.svg' | relative_url }}" alt="ember — a curled plum mascot hugging a glowing tummy." width="200" height="200">
</picture>

# Give your agent a gut feeling.

<p class="lede">A local gut feeling for coding agents. ember runs Cloudflare's Clef model on your Apple Silicon Mac and answers typed judgment questions as calibrated probabilities — privately, in about a second.</p>

<p class="hero-actions">
  <a class="button primary" href="{{ '/docs/overview/' | relative_url }}">Get started</a>
  <a class="button" href="{{ '/results/' | relative_url }}">Benchmark</a>
  <a class="button" href="{{ site.github }}">GitHub</a>
</p>

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
[Benchmark report]({{ '/results/' | relative_url }}) to see how it scores against the agent
kit's decision rules.
