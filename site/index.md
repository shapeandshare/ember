---
layout: home
title: ember
description: A local gut feeling for coding agents. ember runs a decision model (currently Cloudflare's Clef) on your Apple Silicon Mac and answers typed judgment questions as calibrated probabilities.
---
{%- assign bench_url = '/results/' | relative_url %}
{%- assign h = site.data.benchmark.headline %}
<section class="splash-hero">
  <div class="hero-stage">
    <div class="hero-glow" aria-hidden="true"></div>
    <div class="sparks" aria-hidden="true">
      <span class="spark" style="--x: 30%; --delay: 0s; --dur: 6.5s; --drift: -22px"></span>
      <span class="spark" style="--x: 44%; --delay: 1.1s; --dur: 7.5s; --drift: 10px; --size: 4px"></span>
      <span class="spark" style="--x: 58%; --delay: 2.3s; --dur: 6s; --drift: 24px; --tone: var(--ember-coral)"></span>
      <span class="spark" style="--x: 66%; --delay: 0.6s; --dur: 8s; --drift: 14px; --size: 5px"></span>
      <span class="spark" style="--x: 38%; --delay: 3.2s; --dur: 7s; --drift: -12px; --tone: var(--ember-coral); --size: 4px"></span>
      <span class="spark" style="--x: 52%; --delay: 4.1s; --dur: 6.8s; --drift: -4px; --size: 7px"></span>
      <span class="spark" style="--x: 72%; --delay: 2.8s; --dur: 7.8s; --drift: 30px; --size: 4px"></span>
      <span class="spark" style="--x: 26%; --delay: 5s; --dur: 8.4s; --drift: -30px; --tone: var(--ember-coral)"></span>
      <span class="spark" style="--x: 48%; --delay: 5.8s; --dur: 6.2s; --drift: 6px; --size: 5px"></span>
      <span class="spark" style="--x: 62%; --delay: 4.6s; --dur: 7.2s; --drift: -16px; --size: 3px"></span>
    </div>
    <picture class="hero-art">
      <source media="(prefers-color-scheme: dark)" srcset="{{ '/assets/brand/svg/ember-dark.svg' | relative_url }}">
      <img src="{{ '/assets/brand/svg/ember-light.svg' | relative_url }}" alt="ember, a curled plum mascot hugging a glowing tummy." width="260" height="260">
    </picture>
  </div>
  <p class="eyebrow">A local gut feeling for coding agents</p>
  <h1>Give your agent a <span class="glow-text">gut feeling.</span></h1>
  <p class="lede">Coding agents make judgment calls at every step: act or ask, retry or fix, ship or stop for review. ember answers each one with a calibrated probability, on your Mac, in about a second.</p>
  <div class="hero-actions">
    <a class="button button-primary" href="{{ '/docs/overview/' | relative_url }}">Read the docs</a>
    <a class="button button-secondary" href="{{ bench_url }}">Benchmark</a>
    <a class="hero-link" href="{{ site.github }}">Source on GitHub</a>
  </div>
</section>

<section class="splash-section" id="problem">
  <div class="splash-head reveal">
    <p class="eyebrow">The problem</p>
    <h2>Agents guess at the judgment calls</h2>
    <p class="splash-intro">An agent can write the fix. Knowing whether the request is clear, whether a failure is real, or whether a change needs a second pair of eyes is a different skill, and today it is a guess or a hard-coded rule. Lean one way and the agent stops to ask about everything; lean the other and the risky change ships.</p>
  </div>
  <div class="cards">
    <article class="card reveal" style="--i: 0">
      <svg class="card-icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M6 8.5A3.5 3.5 0 0 1 9.5 5h13A3.5 3.5 0 0 1 26 8.5v9a3.5 3.5 0 0 1-3.5 3.5H14l-6 5v-5.2A3.5 3.5 0 0 1 6 17.5z"/><path d="M13.6 10.4a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1.1 1-1.1 1.8"/><circle class="dot" cx="16" cy="17.6" r="1"/></svg>
      <h3>Act or ask?</h3>
      <p>Is “update the thing” enough to start on, or does it need one clarifying question?</p>
    </article>
    <article class="card reveal" style="--i: 1">
      <svg class="card-icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M25.5 16.5a9.5 9.5 0 1 1-2.8-6.7"/><path d="M23.5 4.5v5.8h-5.8"/></svg>
      <h3>Retry or fix?</h3>
      <p>A red test can be a flake, a missing service, or a real bug, and each needs a different next step.</p>
    </article>
    <article class="card reveal" style="--i: 2">
      <svg class="card-icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M16 4l10 4v7c0 6.2-4.2 11-10 13-5.8-2-10-6.8-10-13V8z"/><path d="M12 16l3 3 5.5-6"/></svg>
      <h3>Ship or stop?</h3>
      <p>A four-line rename and a change to auth deserve different amounts of caution.</p>
    </article>
  </div>
</section>

<section class="splash-section splash-tint" id="what">
  <div class="splash-head reveal">
    <p class="eyebrow">What ember does</p>
    <h2>Questions in, probabilities out</h2>
    <p class="splash-intro">The agent describes the situation and asks typed questions. ember scores every option in one pass and returns a probability for each. It writes no prose, so there is nothing to parse: the agent reads a number and decides.</p>
  </div>
  <div class="flow reveal">
    <svg class="flow-wide" viewBox="0 0 960 220" role="img" aria-labelledby="flow-wide-title">
      <title id="flow-wide-title">How a call flows: the coding agent sends state and typed questions to ember on your Mac, which returns a probability per option, and the agent decides.</title>
      <defs>
        <marker id="flow-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="flow-arrowhead" d="M0 0L10 5L0 10z"/></marker>
        <filter id="flow-soft" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="20"/></filter>
      </defs>
      <rect class="flow-node" x="10" y="60" width="190" height="100" rx="22"/>
      <text class="flow-text" x="105" y="116">Coding agent</text>
      <text class="flow-label" x="292" y="90">state + typed questions</text>
      <line class="flow-wire" x1="210" y1="110" x2="372" y2="110" marker-end="url(#flow-arrow)"/>
      <ellipse class="flow-glow" cx="480" cy="110" rx="125" ry="72" filter="url(#flow-soft)"/>
      <rect class="flow-ember" x="385" y="55" width="190" height="110" rx="26"/>
      <text class="flow-name" x="480" y="110">ember</text>
      <text class="flow-note" x="480" y="134">on your Mac</text>
      <text class="flow-label" x="668" y="90">a probability per option</text>
      <line class="flow-wire" x1="586" y1="110" x2="748" y2="110" marker-end="url(#flow-arrow)"/>
      <rect class="flow-node" x="760" y="60" width="190" height="100" rx="22"/>
      <text class="flow-text" x="855" y="116">The agent decides</text>
    </svg>
    <svg class="flow-tall" viewBox="0 0 320 540" role="img" aria-labelledby="flow-tall-title">
      <title id="flow-tall-title">How a call flows: the coding agent sends state and typed questions to ember on your Mac, which returns a probability per option, and the agent decides.</title>
      <defs>
        <marker id="flow-arrow-tall" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="flow-arrowhead" d="M0 0L10 5L0 10z"/></marker>
        <filter id="flow-soft-tall" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="20"/></filter>
      </defs>
      <rect class="flow-node" x="40" y="12" width="240" height="84" rx="20"/>
      <text class="flow-text" x="160" y="60">Coding agent</text>
      <line class="flow-wire" x1="160" y1="106" x2="160" y2="194" marker-end="url(#flow-arrow-tall)"/>
      <text class="flow-label flow-label-side" x="174" y="144">state + typed</text>
      <text class="flow-label flow-label-side" x="174" y="162">questions</text>
      <ellipse class="flow-glow" cx="160" cy="270" rx="135" ry="82" filter="url(#flow-soft-tall)"/>
      <rect class="flow-ember" x="40" y="208" width="240" height="124" rx="26"/>
      <text class="flow-name" x="160" y="266">ember</text>
      <text class="flow-note" x="160" y="292">on your Mac</text>
      <line class="flow-wire" x1="160" y1="342" x2="160" y2="430" marker-end="url(#flow-arrow-tall)"/>
      <text class="flow-label flow-label-side" x="174" y="380">a probability</text>
      <text class="flow-label flow-label-side" x="174" y="398">per option</text>
      <rect class="flow-node" x="40" y="444" width="240" height="84" rx="20"/>
      <text class="flow-text" x="160" y="492">The agent decides</text>
    </svg>
  </div>
  <div class="cards">
    <article class="card reveal" style="--i: 0">
      <p class="card-kicker"><code>noul</code></p>
      <h3>Yes or no</h3>
      <p>“Does this change need review?”</p>
    </article>
    <article class="card reveal" style="--i: 1">
      <p class="card-kicker"><code>choice</code></p>
      <h3>One of the options you name</h3>
      <p>“Why did this test fail?”</p>
    </article>
    <article class="card reveal" style="--i: 2">
      <p class="card-kicker"><code>score</code></p>
      <h3>A point on your scale</h3>
      <p>“How risky is this change, from 0 to 3?”</p>
    </article>
  </div>
</section>

<section class="splash-section" id="where">
  <div class="splash-head reveal">
    <p class="eyebrow">Where it helps</p>
    <h2>What it says at real decision points</h2>
    <p class="splash-intro">These are measured outputs from Cloudflare's Clef-Flash on an Apple M4 Max, taken from ember's agent kit. The kit turns each probability into an action.</p>
  </div>
  <div class="decisions">
    <figure class="decision reveal" style="--i: 0">
      <figcaption class="decision-label">Intent and readiness</figcaption>
      <blockquote class="decision-evidence">update the thing</blockquote>
      <ul class="decision-answers">
        <li style="--p: 0.96"><code>implement</code> <span class="bar" aria-hidden="true"></span> <span class="value"><b>0.96</b></span></li>
        <li style="--p: 0.09"><code>specific_enough</code> <span class="bar" aria-hidden="true"></span> <span class="value"><b>0.09</b></span></li>
      </ul>
      <p class="decision-action">Ask what to update</p>
    </figure>
    <figure class="decision reveal" style="--i: 1">
      <figcaption class="decision-label">Failure triage</figcaption>
      <blockquote class="decision-evidence">TimeoutError after 5.0s; passed on 3 of last 5 CI runs</blockquote>
      <ul class="decision-answers">
        <li style="--p: 0.89"><code>flaky</code> <span class="bar" aria-hidden="true"></span> <span class="value"><b>0.89</b></span></li>
        <li style="--p: 0.67"><code>retry</code> <span class="bar" aria-hidden="true"></span> <span class="value"><b>0.67</b></span></li>
      </ul>
      <p class="decision-action">Retry, then stabilize the test</p>
    </figure>
    <figure class="decision reveal" style="--i: 2">
      <figcaption class="decision-label">Change risk</figcaption>
      <blockquote class="decision-evidence">Skip auth token validation for localhost (180 lines)</blockquote>
      <ul class="decision-answers">
        <li style="--p: 0.81"><code>risk</code> <span class="bar" aria-hidden="true"></span> <span class="value"><b>2.43</b> of 3</span></li>
        <li style="--p: 0.93"><code>needs_review</code> <span class="bar" aria-hidden="true"></span> <span class="value"><b>0.93</b></span></li>
      </ul>
      <p class="decision-action">Stop and ask for review</p>
    </figure>
  </div>
  <p class="splash-note reveal">The kit has two more recipes, for routing and for effort, that you adapt to your own project.</p>
</section>
{% if h %}
<section class="splash-section splash-tint" id="measured">
  <div class="splash-head reveal">
    <p class="eyebrow">Measured, not promised</p>
    <h2>Confident answers held up</h2>
    <p class="splash-intro">ember ships with a {{ h.items }}-item benchmark, with gold labels fixed before the run, that scores the model the way the agent kit uses it.</p>
  </div>
  <div class="stats">
    <div class="stat reveal" style="--i: 0">
      <p class="stat-figure">{{ h.confident.correct }} <small>of</small> {{ h.confident.answered }}</p>
      <p class="stat-text">confident answers were right. At the agent kit's act-on-it thresholds, ember was confident on {{ h.confident.share_pct }}% of the yes-or-no and choice questions.</p>
    </div>
    <div class="stat reveal" style="--i: 1">
      <p class="stat-figure">{{ h.accuracy_pct }}%</p>
      <p class="stat-text">of all {{ h.questions }} questions answered correctly, with a 95% interval of {{ h.accuracy_ci_pct[0] }} to {{ h.accuracy_ci_pct[1] }}%.</p>
    </div>
    <div class="stat reveal" style="--i: 2">
      <p class="stat-figure">{{ h.latency.p50_s }} <small>s</small></p>
      <p class="stat-text">median time per call on an {{ h.host }}, and {{ h.latency.p95_s }} s at the 95th percentile.</p>
    </div>
  </div>
  <figure class="calibration reveal">
    <figcaption>
      <strong>Its confidence is conservative.</strong>
      {% if h.conservative %}Choice questions, grouped by how confident ember was. In every group it was right at least as often as it claimed.{% else %}Choice questions, grouped by how confident ember was, next to how often it was right.{% endif %}
    </figcaption>
    {%- capture bands_label %}{% for band in h.reliability %}claimed {{ band.claimed_pct }}%, right {{ band.actual_pct }}%{% unless forloop.last %}; {% endunless %}{% endfor %}{% endcapture %}
    <div class="calibration-bars" style="--bands: {{ h.reliability | size }}" role="img" aria-label="Claimed confidence against how often ember was right, by group: {{ bands_label }}.">
      {%- for band in h.reliability %}
      <div class="band" style="--claimed: {{ band.claimed_pct }}; --actual: {{ band.actual_pct }}; --i: {{ forloop.index0 }}">
        <span class="band-bar band-claimed"></span>
        <span class="band-bar band-actual"></span>
        <span class="band-label">{{ band.claimed_pct }}%</span>
      </div>
      {%- endfor %}
    </div>
    <p class="calibration-legend">
      <span><i class="band-claimed"></i>claimed</span>
      <span><i class="band-actual"></i>right</span>
    </p>
  </figure>
  <p class="splash-note reveal">One run of {{ h.items }} items across the five agent-kit recipes and four vision recipes. Ordered scores are harder: {{ h.score.exact_pct }}% exact, {{ h.score.within_one_pct }}% within one level. The full report shows where it misses. <a href="{{ bench_url }}">Read the benchmark report</a></p>
</section>
{% endif %}
<section class="splash-section" id="local">
  <div class="splash-head reveal">
    <p class="eyebrow">On your machine</p>
    <h2>Private by default, fast enough to ask often</h2>
    <p class="splash-intro">The model runs on your Mac's GPU, behind a server on your machine. Your agent's evidence stays there; the only network call is the one-time model download.</p>
  </div>
  <picture class="diagram reveal">
    <source media="(prefers-color-scheme: dark)" srcset="{{ '/assets/diagrams/call-path-dark.svg' | relative_url }}">
    <img src="{{ '/assets/diagrams/call-path-light.svg' | relative_url }}" width="760" alt="ember call path: a coding agent calls the advise tool over MCP into ember-mcp, which starts the ember model server on the first call; the server stays warm and runs Cloudflare's Clef-Flash on the Apple GPU.">
  </picture>
  <div class="cards cards-4">
    <article class="card reveal" style="--i: 0">
      <h3>Local by default</h3>
      <p>No account, no API key, no per-call bill. Point it at a server you run when one Mac serves another.</p>
    </article>
    <article class="card reveal" style="--i: 1">
      <h3>About a second</h3>
      <p>A warm call takes about a second, and two or three questions cost the same as one.</p>
    </article>
    <article class="card reveal" style="--i: 2">
      <h3>Deterministic</h3>
      <p>The same request always gets the same answer, so a decision can be replayed.</p>
    </article>
    <article class="card reveal" style="--i: 3">
      <h3>Open</h3>
      <p>MIT-licensed code. Cloudflare's Clef weights are Apache-2.0, downloaded from their public Hugging Face repo.</p>
    </article>
  </div>
</section>

<section class="splash-section splash-tint" id="works-with">
  <div class="splash-head reveal">
    <p class="eyebrow">Works with</p>
    <h2>Fits the agent you already use</h2>
  </div>
  <ul class="chips reveal">
    <li>opencode</li>
    <li>Claude Code</li>
    <li>Codex CLI</li>
    <li>Kilo Code</li>
  </ul>
  <p class="splash-note reveal">One command registers the server. The agent kit teaches the agent when to ask and how to read the answer, through MCP instructions, a skill, and an AGENTS.md policy.</p>
</section>

<div class="get-started" id="get-started" markdown="1">

<p class="eyebrow">Get started</p>

## Up and running in five steps

You need an Apple Silicon Mac with 32 GB of memory or more, about 18 GiB of free disk, and
[uv](https://docs.astral.sh/uv/getting-started/installation/).

1. **Install ember.**

   ```bash
   uv tool install --python 3.12 ember-advise
   ```

   To pin a specific release tag from GitHub instead:

   ```bash
   uv tool install --python 3.12 "ember-advise @ git+https://github.com/shapeandshare/ember@v0.10.3"
   ```

2. **Download the model.** It's about 18 GB, and an interrupted download resumes.

   ```bash
   ember model pull
   ```

3. **Connect your agent.** Run the line for the agent you use, then restart it.

   ```bash
   ember init --opencode --global                    # opencode, every project
   claude mcp add --scope user ember -- ember-mcp    # Claude Code, every project
   ember init --codex                                # Codex CLI, this project
   ember init --kilocode                             # Kilo Code, this project
   ```

4. **Check the setup.** `ember doctor` reports the platform, the model, the server, and
   where ember is registered for each agent.

   ```bash
   ember doctor
   ```

5. **Ask a judgment question.** Try "Is this bug report urgent, and which team should own
   it?" The agent calls ember's `advise` tool, and the model server starts on that first
   call.

To make ember part of a project's routine, add a policy your agents follow, such as "check
change risk before every push":

```bash
ember agents show snippet >> AGENTS.md    # Claude Code reads CLAUDE.md instead
ember agents install --agent claude       # the playbook skill, for Claude Code
```

If something looks wrong, run `ember doctor`, then `ember logs`. The
[Overview]({{ '/docs/overview/' | relative_url }}) covers every option, including remote
servers.

</div>

<section class="splash-section splash-closing" id="try">
  <div class="splash-head reveal">
    <h2>Try it on your next judgment call</h2>
    <p class="splash-intro">Installing takes four commands, and the model download is about 18 GB.</p>
  </div>
  <div class="hero-actions reveal">
    <a class="button button-primary" href="{{ '/docs/overview/' | relative_url }}">Read the docs</a>
    <a class="button button-secondary" href="{{ bench_url }}">Benchmark</a>
  </div>
</section>
