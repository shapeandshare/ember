---
title: "hosted.py treated any non-empty directory as a complete download"
type: discovery
tags:
  - type/discovery
  - domain/server
  - domain/runtime
  - status/draft
created: "2026-10-11"
updated: "2026-10-11"
code-refs:
  - ember/serving/hosted.py
---

# hosted.py treated any non-empty directory as a complete download

Part of [[ember]]. The original `ember/serving/hosted.py` guard checked `any(model_dir.iterdir())` to decide whether a cached model directory was complete. Any non-empty directory, including one from a partially interrupted download, was silently accepted as complete.

## What was tested

The AWS GPU deployment spec (research R4) required that instances load weights only from the S3 model cache and never from Hugging Face. The converge script downloads the model on first boot and on explicit replace. If a download was interrupted mid-way (network drop, instance stop), the directory would be non-empty but incomplete. The old guard would accept it, and `ember serve` would fail at model-load time with a confusing error rather than re-downloading.

The code path was traced in `ember/serving/hosted.py`, function `resolve()`, which called `any(model_dir.iterdir())` as its completeness check.

## Finding

The old guard:

```python
if model_dir.is_dir() and any(model_dir.iterdir()):
    return HostedModelSource(uri=uri, model_dir=model_dir)
```

accepted any non-empty directory as complete. A partial download (interrupted after the first file was written but before all files arrived) would pass this check and cause a silent model-load failure downstream.

The fix introduces a `_download_complete` completion marker written atomically (via a sibling `.tmp` file and `os.replace()`) after every successful download. The new guard:

```python
def _is_complete(model_dir: Path) -> bool:
    return model_dir.is_dir() and (model_dir / COMPLETION_MARKER).exists()
```

A non-empty directory without the marker is treated as partial and re-downloaded in full. Existing caches that pre-date the marker are also treated as incomplete and re-downloaded — a redundant re-download is far less harmful than serving a corrupt model.

## Relevance

This fix is load-bearing for the AWS deployment: the converge script verifies the model against the S3 manifest before `ember.service` starts, and the completion marker is the first gate. Without it, a partially downloaded cache would pass the directory check, fail the manifest verification, and leave the instance in a broken state that requires manual intervention.

The fix also applies to the Outerbounds deployment path: any `EMBER_MODEL_S3_URI`-based download now uses the marker.

## References

- `ember/serving/hosted.py` — `_is_complete`, `_write_marker`, `resolve`
- `specs/005-aws-gpu-deployment/research.md` — R4 (weights on the instance)
- `vault/decisions/2026-10-11-aws-gpu-deployment-over-tailscale.md`
