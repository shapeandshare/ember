# Third-Party Notices

`ember` itself is original work, released under the MIT License (see [`LICENSE`](LICENSE)).
This file lists the third-party **code** the project installs and runs, for license
compliance and audit. For data (model weights, brand assets, prompts), see
[`PROVENANCE.md`](PROVENANCE.md) instead.

The machine-readable inventory is [`provenance.json`](provenance.json). Its
`dependencies.inventory` records every locked package in `uv.lock`, with its version,
registry source, artifact URLs and hashes, and the license metadata installed on this
machine. Check it offline with:

```bash
python3 scripts/check_provenance.py
```

> **Note:** The licenses below are read from installed distribution metadata and are
> **evidence only**, not an SPDX-certified or complete legal audit. `provenance.json`
> records missing metadata explicitly. Confirm a license at its source before relying on
> it.

## Runtime dependencies

These ship as dependencies of the `ember-advise` distribution and run when ember serves advice.

| Package | Version (as installed) | License (as installed) | Role |
| --- | --- | --- | --- |
| [torch](https://pytorch.org) | 2.14.1 | Apache-2.0 with LLVM exception, BSD-2-Clause, BSD-3-Clause, BSL-1.0, MIT | Tensor runtime and the MPS backend |
| [torchvision](https://github.com/pytorch/vision) | 0.29.1 | BSD | Image transforms required by `transformers` |
| [transformers](https://github.com/huggingface/transformers) | 5.18.0 | Apache-2.0 | Model loading and the Clef processor |
| [safetensors](https://github.com/huggingface/safetensors) | 0.8.0 | Apache-2.0 (classifier) | Weight file format |
| [huggingface-hub](https://github.com/huggingface/huggingface_hub) | 1.33.0 | Apache-2.0 | Weight download and cache |
| [accelerate](https://github.com/huggingface/accelerate) | 1.15.0 | Apache-2.0 | Device placement helpers |
| [pillow](https://python-pillow.github.io) | 12.3.0 | MIT-CMU | Image decoding for vision inputs |
| [fastapi](https://fastapi.tiangolo.com) | 0.142.2 | MIT | The model server HTTP API |
| [uvicorn](https://www.uvicorn.org) | 0.54.0 | BSD-3-Clause | ASGI server |
| [pydantic](https://docs.pydantic.dev) | 2.13.5 | MIT | Request and response schemas |
| [mcp](https://modelcontextprotocol.io) | 2.3.0 | MIT | The MCP stdio server |
| [httpx](https://www.python-httpx.org) | 0.28.1 | BSD-3-Clause | MCP to server HTTP calls |
| [prometheus-client](https://github.com/prometheus/client_python) | 0.26.0 | Apache-2.0, BSD-2-Clause | `/metrics` endpoint |

> **Note:** `torch` bundles many vendored components under their own licenses (for
> example CUDA, oneDNN, and protobuf). Its wheels carry those notices under
> `torch-*-dist-info/licenses/`, and `provenance.json` hashes each file. Review them for a
> distribution audit. The same applies to `torchvision`.

## Development dependencies

Installed for contributors and CI. They are not part of the runtime distribution.

| Package | Version (as installed) | License | Role |
| --- | --- | --- | --- |
| [ruff](https://docs.astral.sh/ruff) | 0.16.10 | MIT | Formatter and linter |
| [mypy](https://mypy-lang.org) | 2.4.0 | MIT | Static type checker |
| [bandit](https://bandit.readthedocs.io) | 1.9.4 | Apache-2.0 | Security scanner |
| [pytest](https://pytest.org) | 9.1.1 | MIT | Test runner |
| [pytest-cov](https://pytest-cov.readthedocs.io) | 7.1.0 | MIT | Coverage plugin |
| [pyyaml](https://pyyaml.org) | 6.0.3 | MIT | YAML parsing in tests and scripts |
| [commitizen](https://commitizen-tools.github.io/commitizen) | 4.19.0 | MIT | Conventional commits and version bumps |

## Model artifacts

The Clef model weights and `joint_schema_model.py` are upstream Cloudflare work, licensed
**Apache-2.0**. They are downloaded at runtime from Hugging Face and are **not**
redistributed in this repository or the `ember-advise` distribution. `provenance.json` records each
model's repository, pinned revision, license, and distribution status.

See also: [`PROVENANCE.md`](PROVENANCE.md) for material origins, and
[`COMPATIBILITY.md`](COMPATIBILITY.md) for tested versions.

## Evaluation data

The long-context probe (`evals/context/`) pads benchmark states with text from one
public-domain book, vendored at `evals/context/filler.txt`. It lives only in a checkout and
is not part of the `ember-advise` distribution.

| Work | Author | Source | Status | Changes | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| *Moby-Dick; or, The Whale* (eBook #2701) | Herman Melville | [gutenberg.org/ebooks/2701.txt.utf-8](https://www.gutenberg.org/ebooks/2701.txt.utf-8) | Public domain | Kept only the text between the `*** START` and `*** END` markers, removed the transcriber's note, and normalized line endings to LF, so no Project Gutenberg header, licence, or other reference remains | `f4b274b0250e9c6239797efa7a30a05c78d9fca9a5bd0e2de2ed613e715c57d5` |
