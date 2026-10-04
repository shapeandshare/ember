"""Narrative text for the ember benchmark report.

Both renderers share these strings. They use a small inline markup: `code`,
**bold**, [text](https://url), and [@key] citations that resolve against
``REFERENCES``. Paragraphs with ``{name}`` fields are formatted with values
from the report model before rendering.
"""

from __future__ import annotations

TITLE = "ember benchmark report"
SUBTITLE = (
    "Calibrated advice for coding agents from Cloudflare's Clef-Flash, measured "
    "on the five decision recipes of ember's agent kit"
)

CONTEXT = [
    "ember runs Cloudflare's Clef-Flash decision model [@clef] locally on Apple "
    "Silicon and gives coding agents one [Model Context Protocol](https://"
    "modelcontextprotocol.io) tool, `advise` [@mcp]. An agent sends a `state` (the "
    "evidence) and a set of typed questions, and ember returns a probability for "
    "every option of every question. It generates no text: it advises, and the "
    "agent decides.",
    "Clef is a decision model, not a chat model. A Qwen3.5 backbone with a joint "
    "schema head scores the options of every question in one forward pass, so the "
    "questions in one call are weighed jointly. ember serves it in fp16 on the "
    "Apple GPU (MPS) behind a local HTTP server.",
    "Agents act on ember's answers through thresholds published in ember's agent "
    "kit: trust a `choice` at confidence 0.85 or above, read a `noul` as yes at "
    "P >= 0.80 and no at P <= 0.20, and read a `score` through its expected value. "
    "A threshold is only safe when confidence tracks accuracy, so this benchmark "
    "measures calibration and the outcomes of those decision rules, not only "
    "accuracy.",
]

QUESTION_TYPES = [
    {
        "type": "noul",
        "asks": "A yes/no proposition",
        "returns": "P(true)",
        "correct": "P >= 0.5 matches the gold label",
    },
    {
        "type": "choice",
        "asks": "Mutually exclusive, named options",
        "returns": "The top option, its confidence, and the full distribution",
        "correct": "The top option is the gold option",
    },
    {
        "type": "score",
        "asks": "Ordered levels",
        "returns": "A distribution over levels and its expected value",
        "correct": "The expected value rounds to the gold level",
    },
]

SYSTEM = [
    "Two runners exercise the same server. The benchmark runner posts every item to "
    "the model server's `POST /v1/systemone`, the endpoint the MCP tool forwards to, "
    "so it measures the model and server end to end. The agent eval runner drives a "
    "real coding agent through `opencode run --pure`, so it also measures whether "
    "the agent calls ember at the right moments, asks well, and acts on the answer.",
]

ARCHITECTURE = {
    "nodes": [
        {
            "id": "agent",
            "label": "Coding agent",
            "detail": "opencode, Claude Code, Codex",
        },
        {
            "id": "mcp",
            "label": "ember-mcp",
            "detail": "MCP stdio: advise tool, ember://guide",
        },
        {
            "id": "server",
            "label": "Model server",
            "detail": "FastAPI: POST /v1/systemone",
        },
        {
            "id": "engine",
            "label": "Clef-Flash",
            "detail": "Qwen3.5 + joint schema head, fp16 on MPS",
        },
        {
            "id": "agent_runner",
            "label": "Agent eval runner",
            "below": "agent",
            "detail": "evals/eval/run_agent_evals.py",
        },
        {
            "id": "runner",
            "label": "Benchmark runner",
            "below": "server",
            "detail": "evals/eval/run_evals.py",
        },
    ],
    "edges": [
        {"from": "agent", "to": "mcp", "label": "tools/call advise"},
        {"from": "mcp", "to": "server", "label": "HTTP"},
        {"from": "server", "to": "engine", "label": "Engine.advise"},
        {
            "from": "agent_runner",
            "to": "agent",
            "label": "opencode run --pure",
            "style": "dashed",
        },
        {
            "from": "runner",
            "to": "server",
            "label": "HTTP, every item",
            "style": "dashed",
        },
    ],
}

ARCHITECTURE_TEXT = """agent eval runner (evals/eval/run_agent_evals.py)
   │ opencode run --pure, one sandbox per session
   ▼
coding agent ──tools/call advise──► ember-mcp (stdio, ember/mcp/mcp_server.py)
                                       │ HTTP POST /v1/systemone
                                       ▼
model benchmark runner ──HTTP──► model server (ember/serving/server.py)
(evals/eval/run_evals.py)              │ Engine.advise
                                       ▼
                                Clef-Flash, fp16 on MPS"""

RECIPES = {
    "intent_readiness": {
        "title": "Intent and readiness",
        "when": "Before changing files in response to a conversational request.",
        "state": "The user's latest message, verbatim.",
        "decides": "What the user is asking for, and whether it is specific enough "
        "to act on without a clarifying question.",
    },
    "failure_triage": {
        "title": "Failure triage",
        "when": "Before retrying or fixing a failing test or command.",
        "state": "The test or command, and the relevant error lines.",
        "decides": "The most likely cause, and whether a plain re-run would pass.",
    },
    "change_risk": {
        "title": "Change risk",
        "when": "Before committing, pushing, or merging.",
        "state": "A diff summary, the files touched, and the lines changed.",
        "decides": "How risky the change is to ship unreviewed, and whether a "
        "person should review it.",
    },
    "routing": {
        "title": "Routing and ownership",
        "when": "When an error needs an owner.",
        "state": "The error message and the file or module it came from.",
        "decides": "Which part of the system should handle it. The option set is "
        "a template that projects replace with their own.",
    },
    "effort_approach": {
        "title": "Effort and approach",
        "when": "When planning a task.",
        "state": "The task and its constraints.",
        "decides": "How much work the task is, and which approach fits. The option "
        "sets are templates.",
    },
}

DATASET = [
    "The dataset has {items} items and {questions} scored questions: {choice} "
    "`choice`, {noul} `noul`, and {score} `score`. Each line is self-contained: the "
    "`state`, the recipe's fixed question set, a gold label for every question, its "
    "source, and a one-line rationale. Other implementations can score it without "
    "this harness.",
    "{skill_md} items reproduce the worked examples in the agent kit's playbook and "
    "sit in `dev`; the other {curated} were written for this benchmark. Items are "
    "split into `dev` ({dev} items, for tuning) and `test` ({test} items, for "
    "reporting), stratified so that every label of every question appears in both. "
    "The dataset card below answers the datasheet questions of [@gebru2021].",
]

PROTOCOL = [
    "Labels were judged from `state` and the option descriptions alone, and were "
    "fixed before any model run.",
    "`needs_review` is true exactly when `risk` is Medium or High, and `retry` is "
    "true only for `flaky` failures.",
    "Drafts whose evidence fit two options were rewritten or dropped while "
    "authoring, before any run.",
    "A label changes only when a reviewer finds it wrong on its merits, never "
    "because the model disagreed. Every change alters the dataset's SHA-256, which "
    "each run records, so runs on different label sets cannot be compared by "
    "accident.",
]

METRICS = [
    {
        "name": "Accuracy and 95% interval",
        "applies": "all",
        "tex": r"\mathrm{acc} = \frac{1}{N}\sum_{i=1}^{N} \mathbf{1}[\hat{y}_i = y_i]",
        "text": "acc = (1/N) * sum_i [prediction_i = gold_i]",
        "definition": "The share of scored questions answered correctly. The "
        "interval is a percentile bootstrap over questions: 1,000 resamples with "
        "replacement (seed 0), reporting the 2.5th and 97.5th percentiles "
        "[@efron1993].",
    },
    {
        "name": "Macro-F1",
        "applies": "choice",
        "tex": r"\mathrm{F1}_c = \frac{2\,TP_c}{2\,TP_c + FP_c + FN_c},\qquad "
        r"\text{Macro-F1} = \frac{1}{C}\sum_{c} \mathrm{F1}_c",
        "text": "F1_c = 2TP_c / (2TP_c + FP_c + FN_c); Macro-F1 = mean over classes",
        "definition": "The unweighted mean of per-class F1, so rare options count "
        "as much as common ones; computed as the arithmetic mean of per-class "
        "scores [@opitz2019].",
    },
    {
        "name": "Expected and maximum calibration error",
        "applies": "choice, noul",
        "tex": r"\mathrm{ECE} = \sum_{b=1}^{B} \frac{n_b}{N}\,\bigl|\mathrm{acc}(b) - "
        r"\mathrm{conf}(b)\bigr|,\qquad \mathrm{MCE} = \max_b \bigl|\mathrm{acc}(b) - "
        r"\mathrm{conf}(b)\bigr|",
        "text": "ECE = sum_b (n_b / N) * |acc(b) - conf(b)|; "
        "MCE = max_b |acc(b) - conf(b)|",
        "definition": "Answers are binned by top-label confidence into B = 10 "
        "equal-width bins; ECE is the count-weighted gap between each bin's "
        "accuracy and its mean confidence [@naeini2015] [@guo2017]. A `noul` "
        "answer's top-label confidence is max(P, 1 - P). With bins of a few items "
        "the estimate is noisy and depends on binning [@nixon2019], so read it "
        "with the reliability diagrams.",
    },
    {
        "name": "Brier score",
        "applies": "choice, noul",
        "tex": r"\mathrm{BS} = \frac{1}{N}\sum_{i=1}^{N}\sum_{k=1}^{K}"
        r"\left(p_{ik} - y_{ik}\right)^2",
        "text": "BS = (1/N) * sum_i sum_k (p_ik - y_ik)^2",
        "definition": "The squared error between the predicted distribution and "
        "the one-hot gold label, a proper scoring rule that rewards both "
        "calibration and sharpness [@brier1950]. 0 is perfect; the worst is 2 for "
        "`choice` and 1 for `noul` (where K = 2 is folded into P(true)).",
    },
    {
        "name": "Ranked probability score",
        "applies": "score",
        "tex": r"\mathrm{RPS} = \frac{1}{K-1}\sum_{k=1}^{K-1}"
        r"\Bigl(\sum_{j \le k} p_j - \sum_{j \le k} o_j\Bigr)^2",
        "text": "RPS = (1/(K-1)) * sum_k (cumulative p_k - cumulative o_k)^2",
        "definition": "The proper scoring rule for ordered levels: it compares "
        "cumulative distributions, so a near miss costs less than a far one "
        "[@epstein1969]. 0 is perfect and 1 the worst.",
    },
    {
        "name": "Mean absolute error",
        "applies": "score",
        "tex": r"\mathrm{MAE} = \frac{1}{N}\sum_{i=1}^{N} \bigl|E_i - g_i\bigr|",
        "text": "MAE = (1/N) * sum_i |expected_i - gold_i|, in levels",
        "definition": "How far the expected score lands from the gold level. "
        "Exact-level accuracy is strict for ordinal judgments, so read it with "
        "MAE, RPS, and the share within one level.",
    },
    {
        "name": "Coverage and accuracy at a threshold",
        "applies": "choice, noul",
        "tex": r"\mathrm{cov}(\tau) = \frac{\left|\{i : c_i \ge \tau\}\right|}{N},"
        r"\qquad \mathrm{acc}(\tau) = \mathrm{acc}\bigl(\{i : c_i \ge \tau\}\bigr)",
        "text": "coverage(t) = share of answers with confidence >= t; "
        "accuracy(t) = accuracy of those answers",
        "definition": "Selective prediction [@geifman2017]: how often an answer "
        "clears the threshold at which the kit tells an agent to act, and how "
        "accurate those answers are. The curve sweeps the threshold; the markers "
        "are the kit's published values.",
    },
]

POLICIES = [
    "The agent kit's AGENTS.md snippet ships a default project policy. The report "
    "replays it on every item and counts what an agent following it to the letter "
    "would have done: the right thing, a cautious extra step (an unnecessary "
    "question or review), or a wrong action (acting on a vague request, or "
    "shipping a risky change unreviewed).",
]

RELIABILITY = [
    "A reliability diagram plots each confidence bin's accuracy against its mean "
    "confidence; a perfectly calibrated advisor sits on the diagonal "
    "[@degroot1983]. Bars above the diagonal mean ember was more often right than "
    "its confidence claimed (under-confidence); bars below it mean "
    "over-confidence, the dangerous direction for threshold-driven agents.",
]

DATASHEET = [
    (
        "Why was it built?",
        "To measure whether ember's probabilities are accurate "
        "and calibrated enough for agents to act on the agent kit's thresholds, and to "
        "compare model revisions and setups.",
    ),
    (
        "What does it contain?",
        "{items} items across five recipes, {questions} "
        "scored questions, a gold label per question, a rationale per item.",
    ),
    (
        "How was it collected?",
        "{skill_md} items reproduce the agent kit's worked "
        "examples; {curated} were written by the ember authors. No user data.",
    ),
    (
        "How was it labelled?",
        "From `state` and the option descriptions alone, "
        "fixed before any run, under the rules in the labelling protocol.",
    ),
    (
        "What is it for?",
        "Tune on `dev`, report on `test`. It is not a measure of "
        "agent behaviour, and not a training set.",
    ),
    (
        "How is it maintained?",
        "Relabelling happens only on review, changes the "
        "dataset's SHA-256, and invalidates comparisons with earlier runs.",
    ),
]

LIMITATIONS = [
    "**Sample size.** {questions} questions give a 95% interval about "
    "{ci_width} points wide overall; per-question samples of 20 to 28 are wider "
    "still, and calibration bins hold a few items each.",
    "**One annotation team.** The labels come from the authors of the agent kit, "
    "with no inter-annotator agreement yet. Shared assumptions could make items "
    "easier or harder for ember than real traffic.",
    "**Curated, not sampled.** Items are short, English, and written for the "
    "benchmark rather than drawn from real agent sessions.",
    "**Ordinal judgments.** Risk and effort levels are judgments; neighbouring "
    "levels are often defensible, which is why MAE, RPS, and within-one are "
    "reported alongside exact accuracy.",
    "**One model, one machine.** One pinned model revision in fp16 on MPS; "
    "numerics on CPU or CUDA can differ slightly. Repeat runs on the same server "
    "are deterministic for identical requests.",
    "**Fixed question sets.** Questions are weighed jointly, so results hold for "
    "these question sets. The routing and effort option sets are templates; a "
    "project that replaces them should measure its own.",
    "**Model and server only.** The benchmark calls the HTTP endpoint directly. "
    "It does not measure an agent's decision to consult ember or the quality of "
    "the questions it writes.",
]

REPRODUCE = [
    "make bootstrap               # dependencies, pinned weights, readiness check",
    "ember start                  # warm model server on 127.0.0.1:8765",
    "ember eval run               # every item; or --split test, --category <recipe>",
    "ember eval export            # this report: Markdown, HTML, figures, raw data",
    "ember eval report --compare results/<a>_results.json results/<b>_results.json",
]

GLOSSARY = [
    ("state", "The evidence an agent passes to ember: a string or JSON object."),
    ("recipe", "A fixed question set for one kind of decision, from the agent kit."),
    ("noul", "A yes/no question; the answer is P(true)."),
    ("choice", "A question over named options; the answer is a distribution."),
    (
        "score",
        "A question over ordered levels; the answer is a distribution and "
        "its expected value.",
    ),
    (
        "top-label confidence",
        "The probability of the answer's chosen option, or max(P, 1 - P) for a noul.",
    ),
    ("coverage", "The share of answers that clear a decision threshold."),
    (
        "gate",
        "A decision rule from the agent kit, such as 'stop for review when "
        "needs_review >= 0.80 or risk >= 2.0'.",
    ),
]

REFERENCES = [
    {
        "key": "clef",
        "text": "Cloudflare. Clef-Flash. Model repository, Hugging Face Hub.",
        "url": "https://huggingface.co/Cloudflare/clef-flash",
    },
    {
        "key": "mcp",
        "text": "Model Context Protocol. Specification.",
        "url": "https://modelcontextprotocol.io/specification",
    },
    {
        "key": "naeini2015",
        "text": "Naeini, M. P., Cooper, G. F., and Hauskrecht, M. Obtaining well "
        "calibrated probabilities using Bayesian binning. AAAI, 2015.",
        "url": "https://ojs.aaai.org/index.php/AAAI/article/view/9602",
    },
    {
        "key": "guo2017",
        "text": "Guo, C., Pleiss, G., Sun, Y., and Weinberger, K. Q. On calibration "
        "of modern neural networks. ICML, 2017.",
        "url": "https://arxiv.org/abs/1706.04599",
    },
    {
        "key": "nixon2019",
        "text": "Nixon, J., Dusenberry, M., Zhang, L., Jerfel, G., and Tran, D. "
        "Measuring calibration in deep learning. CVPR Workshops, 2019.",
        "url": "https://arxiv.org/abs/1904.01685",
    },
    {
        "key": "brier1950",
        "text": "Brier, G. W. Verification of forecasts expressed in terms of "
        "probability. Monthly Weather Review 78(1), 1950.",
        "url": "https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2",
    },
    {
        "key": "epstein1969",
        "text": "Epstein, E. S. A scoring system for probability forecasts of ranked "
        "categories. Journal of Applied Meteorology 8(6), 1969.",
        "url": "https://doi.org/10.1175/1520-0450(1969)008%3C0985:ASSFPF%3E2.0.CO;2",
    },
    {
        "key": "opitz2019",
        "text": "Opitz, J., and Burst, S. Macro F1 and Macro F1. arXiv:1911.03347, "
        "2019.",
        "url": "https://arxiv.org/abs/1911.03347",
    },
    {
        "key": "efron1993",
        "text": "Efron, B., and Tibshirani, R. J. An Introduction to the Bootstrap. "
        "Chapman & Hall, 1993.",
        "url": "https://doi.org/10.1201/9780429246593",
    },
    {
        "key": "geifman2017",
        "text": "Geifman, Y., and El-Yaniv, R. Selective classification for deep "
        "neural networks. NeurIPS, 2017.",
        "url": "https://arxiv.org/abs/1705.08500",
    },
    {
        "key": "degroot1983",
        "text": "DeGroot, M. H., and Fienberg, S. E. The comparison and evaluation of "
        "forecasters. The Statistician 32(1-2), 1983.",
        "url": "https://doi.org/10.2307/2987588",
    },
    {
        "key": "gebru2021",
        "text": "Gebru, T., et al. Datasheets for datasets. Communications of the "
        "ACM 64(12), 2021.",
        "url": "https://arxiv.org/abs/1803.09010",
    },
]
