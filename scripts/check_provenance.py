"""Check local provenance coverage and fingerprints without network access."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    record = json.loads((ROOT / "provenance.json").read_text())
    errors = []
    seen = set()
    for asset in record["assets"]:
        path = asset["path"]
        if path in seen:
            errors.append(f"Duplicate entry: {path}")
        seen.add(path)
        source = ROOT / path
        if not source.is_file():
            errors.append(f"Missing asset: {path}")
            continue
        if hashlib.sha256(source.read_bytes()).hexdigest() != asset["sha256"]:
            errors.append(f"Changed asset: {path}")
        for parent in asset["parents"]:
            if not (ROOT / parent).is_file():
                errors.append(f"Missing parent: {parent}")
        prompt = asset.get("prompt_path")
        if prompt and not (ROOT / prompt).is_file():
            errors.append(f"Missing prompt: {prompt}")
        if asset["kind"] == "byte_copy":
            if source.read_bytes() != (ROOT / asset["parents"][0]).read_bytes():
                errors.append(f"Copy differs from parent: {path}")
    actual = {
        str(p.relative_to(ROOT))
        for folder in ["assets/brand", "packages/opencode-plugin/assets"]
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and not p.name.startswith(".") and p.suffix != ".md"
    }
    for path in sorted(actual - seen):
        errors.append(f"Unrecorded asset: {path}")
    for path, expected in [
        ("uv.lock", record["dependencies"]["lockfile_sha256"]),
        ("LICENSE", record["project_license"]["sha256"]),
    ]:
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            errors.append(f"Refresh evidence for changed file: {path}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Verified {len(seen)} asset records, copies, paths, and fingerprints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
