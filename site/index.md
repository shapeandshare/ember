---
layout: home
title: ember
description: ember helps AI coding assistants like Claude Code and Codex know when to go ahead and when to stop and check with you. Free and open source. Run it on your Mac, on your own server, or use one your team runs.
---
{%- assign bench_url = '/results/' | relative_url %}
{%- assign h = site.data.benchmark.headline %}
<section class="splash-hero">
  <h1>Give your agent a <span class="glow-text">gut feeling.</span></h1>
  <p class="lede">ember helps AI coding assistants like Claude Code, Codex, and opencode know when to go ahead and when to stop and check with you.</p>
  <div class="hero-actions">
    <a class="button button-primary" href="{{ '/docs/overview/' | relative_url }}">Read the docs</a>
    <a class="button button-secondary" href="{{ bench_url }}">Benchmark</a>
    <a class="hero-link" href="{{ site.github }}">Source on GitHub</a>
  </div>
  <p class="hero-note">Run it on your Mac, on a server you host, or point it at one your team already runs.</p>
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
  {%- assign hero = site.data.benchmark.hero %}
  {%- if hero and hero.size >= 5 %}
  <ul class="hero-facts" data-swap aria-label="Questions your assistant asks ember, with ember's answers">
    {%- for q in hero limit: 5 %}
    <li tabindex="0">
      <span class="ask">{{ q.ask }}</span>
      <span class="thinking" aria-hidden="true"><i></i><i></i><i></i></span>
      <span class="reply"><b>{{ q.verdict }}</b> <span>{{ q.detail }}</span></span>
    </li>
    {%- endfor %}
  </ul>
  <button type="button" class="hero-pause" hidden aria-pressed="false">Pause motion</button>
  <script type="application/json" id="hero-pool">{{ hero | jsonify }}</script>
  {%- endif %}
</section>

<section class="splash-section" id="problem">
  <div class="splash-head reveal">
    <p class="eyebrow">The problem</p>
    <h2>Your assistant is great at writing code, and bad at knowing when to check in</h2>
    <p class="splash-intro">Today an assistant guesses at these moments, or follows a fixed rule. Too cautious, and it interrupts you about everything. Too bold, and it charges ahead on a vague request or pushes a risky change without a word. These are the three moments that matter most:</p>
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
    <h2>A quick second opinion, as a number</h2>
    <p class="splash-intro">At one of those moments, your assistant tells ember what's going on and asks a short question. ember replies with how likely each answer is, like “93% likely this needs review”. Your assistant uses that number to decide what to do next. You don't call ember yourself; your assistant does it for you.</p>
  </div>
  <div class="flow reveal">
    <svg class="flow-wide" viewBox="0 0 960 220" role="img" aria-labelledby="flow-wide-title">
      <title id="flow-wide-title">How a call flows: the coding agent sends state and typed questions to ember on your Mac, which returns how likely each answer is, and the agent decides.</title>
      <defs>
        <marker id="flow-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="flow-arrowhead" d="M0 0L10 5L0 10z"/></marker>
        <filter id="flow-soft" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="20"/></filter>
      </defs>
      <rect class="flow-node" x="10" y="60" width="190" height="100" rx="22"/>
      <text class="flow-text" x="105" y="116">Coding agent</text>
      <text class="flow-label" x="292" y="90">what's happening + a question</text>
      <line class="flow-wire" x1="210" y1="110" x2="372" y2="110" marker-end="url(#flow-arrow)"/>
      <ellipse class="flow-glow" cx="480" cy="110" rx="125" ry="72" filter="url(#flow-soft)"/>
      <rect class="flow-ember" x="385" y="55" width="190" height="110" rx="26"/>
      <text class="flow-name" x="480" y="110">ember</text>
      <text class="flow-note" x="480" y="134">on your Mac</text>
      <text class="flow-label" x="668" y="90">how likely each answer is</text>
      <line class="flow-wire" x1="586" y1="110" x2="748" y2="110" marker-end="url(#flow-arrow)"/>
      <rect class="flow-node" x="760" y="60" width="190" height="100" rx="22"/>
      <text class="flow-text" x="855" y="116">The agent decides</text>
    </svg>
    <svg class="flow-tall" viewBox="0 0 320 540" role="img" aria-labelledby="flow-tall-title">
      <title id="flow-tall-title">How a call flows: the coding agent sends state and typed questions to ember on your Mac, which returns how likely each answer is, and the agent decides.</title>
      <defs>
        <marker id="flow-arrow-tall" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="flow-arrowhead" d="M0 0L10 5L0 10z"/></marker>
        <filter id="flow-soft-tall" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="20"/></filter>
      </defs>
      <rect class="flow-node" x="40" y="12" width="240" height="84" rx="20"/>
      <text class="flow-text" x="160" y="60">Coding agent</text>
      <line class="flow-wire" x1="160" y1="106" x2="160" y2="194" marker-end="url(#flow-arrow-tall)"/>
      <text class="flow-label flow-label-side" x="174" y="144">what's happening</text>
      <text class="flow-label flow-label-side" x="174" y="162">+ a question</text>
      <ellipse class="flow-glow" cx="160" cy="270" rx="135" ry="82" filter="url(#flow-soft-tall)"/>
      <rect class="flow-ember" x="40" y="208" width="240" height="124" rx="26"/>
      <text class="flow-name" x="160" y="266">ember</text>
      <text class="flow-note" x="160" y="292">on your Mac</text>
      <line class="flow-wire" x1="160" y1="342" x2="160" y2="430" marker-end="url(#flow-arrow-tall)"/>
      <text class="flow-label flow-label-side" x="174" y="380">how likely each</text>
      <text class="flow-label flow-label-side" x="174" y="398">answer is</text>
      <rect class="flow-node" x="40" y="444" width="240" height="84" rx="20"/>
      <text class="flow-text" x="160" y="492">The agent decides</text>
    </svg>
  </div>
  <div class="cards">
    <article class="card reveal" style="--i: 0">
      <p class="card-kicker">Ask</p>
      <h3>Yes or no</h3>
      <p>“Does this change need review?”</p>
    </article>
    <article class="card reveal" style="--i: 1">
      <p class="card-kicker">Ask</p>
      <h3>Which one?</h3>
      <p>“Why did this test fail?”</p>
    </article>
    <article class="card reveal" style="--i: 2">
      <p class="card-kicker">Ask</p>
      <h3>How much?</h3>
      <p>“How risky is this change, from 0 to 3?”</p>
    </article>
  </div>
</section>

<section class="splash-section" id="where">
  <div class="splash-head reveal">
    <p class="eyebrow">Where it helps</p>
    <h2>Three real examples</h2>
    <p class="splash-intro">Each card shows what the assistant was facing, what ember said (0.96 means 96% likely), and what the assistant did as a result. These are real answers from ember.</p>
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
  <p class="splash-note reveal">ember also helps with routing (“which team owns this?”) and effort (“quick fix or proper redesign?”), and you can teach your assistant your own rules, like “check risk before every push”.</p>
</section>
{% if h %}
<section class="splash-section splash-tint" id="measured">
  <div class="splash-head reveal">
    <p class="eyebrow">Measured, not promised</p>
    <h2>When ember is sure, it's almost always right</h2>
    <p class="splash-intro">We tested ember on {{ h.items }} realistic coding situations with known right answers, written down before the test so the results couldn't be nudged.{% if h.capability %} Reading screenshots and clips is scored separately as a capability: {{ h.capability.accuracy_pct }}% on {{ h.capability.questions }} vision questions, on the <a href="{{ bench_url }}">benchmark page</a>.{% endif %}</p>
  </div>
  <div class="stats">
    <div class="stat reveal" style="--i: 0">
      <p class="stat-figure">{{ h.confident.correct }} <small>of</small> {{ h.confident.answered }}</p>
      <p class="stat-text">times ember was sure, it was right. It was sure enough to act on {{ h.confident.share_pct }}% of the yes-or-no and pick-one questions.</p>
    </div>
    <div class="stat reveal" style="--i: 1">
      <p class="stat-figure">{{ h.accuracy_pct }}%</p>
      <p class="stat-text">of all {{ h.questions }} questions answered correctly.</p>
    </div>
    <div class="stat reveal" style="--i: 2">
      <p class="stat-figure">{{ h.latency.p50_s }} <small>s</small></p>
      <p class="stat-text">typical time per answer, measured on an {{ h.host }}.</p>
    </div>
  </div>
  <figure class="calibration reveal">
    <figcaption>
      <strong>It doesn't overstate how sure it is.</strong>
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
  <p class="splash-note reveal">The full report shows every result, including where it gets things wrong. <a href="{{ bench_url }}">Read the benchmark report</a></p>
</section>
{% endif %}
<section class="splash-section" id="run">
  <div class="splash-head reveal">
    <p class="eyebrow">Run it your way</p>
    <h2>On your Mac, or on a server</h2>
    <p class="splash-intro">ember works the same wherever the model runs. You choose when you set it up, and it never sends anything anywhere you didn't pick.</p>
  </div>
  <div class="cards">
    <article class="card reveal" style="--i: 0">
      <h3>On your Mac</h3>
      <p>The model runs on your own Apple Silicon Mac, so your code stays on it. Needs 32 GB of memory and a one-time 18 GB download.</p>
    </article>
    <article class="card reveal" style="--i: 1">
      <h3>On a server you host</h3>
      <p>Run one copy on a spare Mac or a GPU machine and share it with your whole team, protected by a token.</p>
    </article>
    <article class="card reveal" style="--i: 2">
      <h3>On a server someone else runs</h3>
      <p>Point ember at its address and you're done. Nothing to download, and your machine doesn't need to hold the model.</p>
    </article>
  </div>
  <div class="cards">
    <article class="card reveal" style="--i: 0">
      <h3>Fast</h3>
      <p>Answers come back in about {{ h.latency.p50_s }} seconds once ember is running, and asking several questions at once costs the same as one.</p>
    </article>
    <article class="card reveal" style="--i: 1">
      <h3>Deterministic</h3>
      <p>The same request always gets the same answer, so a decision can be replayed.</p>
    </article>
    <article class="card reveal" style="--i: 2">
      <h3>Open</h3>
      <p>MIT-licensed code, no account, no per-call bill. Cloudflare's Clef weights are Apache-2.0, from their public Hugging Face repo.</p>
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
  <p class="splash-note reveal">One command connects ember to your assistant. ember also teaches your assistant when to ask it and how to read the answer, so there's nothing to configure by hand.</p>
</section>

<div class="get-started" id="get-started" markdown="1">

<p class="eyebrow">Get started</p>

## Up and running in five steps

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). To run the model
yourself, you also need an Apple Silicon Mac with 32 GB of memory or more and about 18 GiB of
free disk; to use a server, you only need its address.

1. **Install ember.**

   ```bash
   uv tool install --python 3.12 ember-advise
   ```

   To pin a specific release tag from GitHub instead:

   ```bash
   uv tool install --python 3.12 "ember-advise @ git+https://github.com/shapeandshare/ember@v0.16.0"
   ```

2. **Choose where it runs.** To run it on your Mac, download the model. It's about 18 GB,
   and an interrupted download resumes.

   ```bash
   ember model pull
   ```

   To use a server instead, skip the download: step 3 asks for its address, or you can pass
   it with `--server-url`. If the server needs a token, export `EMBER_AUTH_TOKEN` in the
   shell that starts your agent.

3. **Connect your agent.** Run the line for the agent you use, then restart it. `ember init`
   asks whether to run locally or use a server.

   ```bash
   ember init --opencode --global                    # opencode, every project
   claude mcp add --scope user ember -- ember-mcp    # Claude Code, every project
   ember init --codex                                # Codex CLI, this project
   ember init --kilocode                             # Kilo Code, this project
   ```

   Claude Code doesn't use `ember init`. To point it at a server, pass the address:

   ```bash
   claude mcp add --scope user ember -e EMBER_SERVER_URL=https://ember.example.com -e EMBER_AUTOSTART=0 -- ember-mcp
   ```

4. **Check the setup.** `ember doctor` reports the platform, the model, the server, and
   where ember is registered for each agent.

   ```bash
   ember doctor
   ```

5. **Ask a judgment question.** Try "Is this bug report urgent, and which team should own
   it?" The agent calls ember's `advise` tool. When ember runs on your Mac, the model
   starts on that first call.

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
    <p class="splash-intro">Setup takes a few commands, on your Mac or against a server.</p>
  </div>
  <div class="hero-actions reveal">
    <a class="button button-primary" href="{{ '/docs/overview/' | relative_url }}">Read the docs</a>
    <a class="button button-secondary" href="{{ bench_url }}">Benchmark</a>
  </div>
</section>
