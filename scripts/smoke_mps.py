"""MPS smoke test using the patched runtime (CPU load -> MPS move).

Usage:
    .venv/bin/python -u scripts/smoke_mps.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import torch  # noqa: E402
from clef_local.runtime import DEFAULT_MODEL_DIR, load_clef  # noqa: E402


def main() -> int:
    print(f"torch {torch.__version__} | mps={torch.backends.mps.is_available()}")
    if not DEFAULT_MODEL_DIR.is_dir():
        print(f"model dir missing: {DEFAULT_MODEL_DIR}")
        return 1

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    dtype = torch.float16 if device == "mps" else torch.float32
    print(f"loading (device={device}, dtype={dtype}) ...")
    t0 = time.time()
    model, processor = load_clef(DEFAULT_MODEL_DIR, device=device, dtype=dtype)
    print(f"loaded in {time.time() - t0:.1f}s")

    from joint_schema_model import systemone  # type: ignore

    request = {
        "model": "clef-flash",
        "state": (
            "The checkout endpoint started returning HTTP 500 errors for every "
            "customer about an hour ago. Orders are fully blocked."
        ),
        "questions": {
            "urgent": {"type": "noul", "instructions": "Is this support request urgent?"},
            "team": {
                "type": "choice",
                "instructions": "Which team should handle this request?",
                "criteria": {
                    "billing": "Payments, invoices, and refunds",
                    "technical": "Outages, errors, and configuration",
                    "sales": "Plans and upgrades",
                },
            },
            "severity": {
                "type": "score",
                "instructions": "How severe is the customer impact?",
                "criteria": ["No impact", "Minor", "Major", "Critical"],
            },
        },
    }

    print("running inference ...")
    t1 = time.time()
    response = systemone(model, processor, request)
    print(f"inference {time.time() - t1:.2f}s | input_tokens={response['usage']['input_tokens']}")
    print(json.dumps(response["answers"], indent=2))

    ok = True
    for qid, ans in response["answers"].items():
        if "probabilities" in ans:
            total = sum(ans["probabilities"].values())
            print(f"  {qid}: prob sum = {total:.4f}")
            ok = ok and abs(total - 1.0) < 0.05
    print("SMOKE TEST OK" if ok else "SMOKE TEST SUSPECT (prob sums off)")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
