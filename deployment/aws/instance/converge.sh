#!/bin/bash
# converge.sh — read config from SSM and converge the instance to the desired state.
#
# Runs as ember-converge.service (oneshot, every boot, After=ember-tailscale.service).
# Reads /ember/<name>/config and the server token from SSM. If the generation
# changed, installs ember-advise==<version>, syncs the model from S3 (verifying
# every file's SHA-256 against manifest.json), and writes /etc/ember/env (0600).
#
# Do NOT enable xtrace (set -x): it would echo secrets to the journal.
# Do NOT echo EMBER_SERVER_AUTH_TOKEN.

set -euo pipefail

DEPLOYMENT_NAME="{{DEPLOYMENT_NAME}}"
REGION="{{REGION}}"
CONFIG_PARAM="{{CONFIG_PARAM}}"
TOKEN_PARAM="{{TOKEN_PARAM}}"

GENERATION_FILE="/var/lib/ember/generation"
MODEL_URI_FILE="/var/lib/ember/model_uri"
ENV_FILE="/etc/ember/env"

# ---------------------------------------------------------------------------
# Step 1: Read config from SSM
# ---------------------------------------------------------------------------

echo "converge: reading config from SSM (${CONFIG_PARAM})"
CONFIG_JSON="$(aws ssm get-parameter \
    --region "${REGION}" \
    --name "${CONFIG_PARAM}" \
    --query 'Parameter.Value' \
    --output text)"

EMBER_VERSION="$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['ember_version'])")"
MODEL_S3_URI="$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['model_s3_uri'])")"
MAX_REQUEST_LENGTH="$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['max_request_length'])")"
IDLE_MINUTES="$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['idle_minutes'])")"
GENERATION="$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['generation'])")"

# ---------------------------------------------------------------------------
# Step 2: Read the server auth token from SSM (SecureString)
# ---------------------------------------------------------------------------

echo "converge: reading server token from SSM (${TOKEN_PARAM})"
EMBER_SERVER_AUTH_TOKEN="$(aws ssm get-parameter \
    --region "${REGION}" \
    --name "${TOKEN_PARAM}" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text)"

# ---------------------------------------------------------------------------
# Step 3: Check generation — skip install/sync if unchanged
# ---------------------------------------------------------------------------

mkdir -p /var/lib/ember
LAST_GENERATION=""
if [[ -f "${GENERATION_FILE}" ]]; then
    LAST_GENERATION="$(cat "${GENERATION_FILE}")"
fi

if [[ "${GENERATION}" == "${LAST_GENERATION}" ]]; then
    echo "converge: generation ${GENERATION} unchanged — skipping install and sync"
else
    echo "converge: generation changed (${LAST_GENERATION} -> ${GENERATION}), converging"

    # -----------------------------------------------------------------------
    # Step 3a: Install ember-advise pinned to the exact version
    # -----------------------------------------------------------------------

    echo "converge: installing ember-advise==${EMBER_VERSION}"
    runuser -u ember -- env HOME=/home/ember XDG_CACHE_HOME=/home/ember/.cache \
        uv tool install --python 3.12 "ember-advise==${EMBER_VERSION}"

    # -----------------------------------------------------------------------
    # Step 3b: Determine the local model cache directory
    # (mirrors ember.cfg.paths.hosted_model_cache logic)
    # -----------------------------------------------------------------------

    URI_HASH="$(echo -n "${MODEL_S3_URI}" | python3 -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:16])")"
    MODEL_CACHE_DIR="/home/ember/.cache/ember/hosted-models/${URI_HASH}"
    mkdir -p "${MODEL_CACHE_DIR}"

    # -----------------------------------------------------------------------
    # Step 3c: Parse the S3 URI into bucket and prefix
    # -----------------------------------------------------------------------

    S3_BUCKET="$(echo "${MODEL_S3_URI}" | python3 -c "import sys; u=sys.stdin.read().strip(); print(u.split('/')[2])")"
    S3_PREFIX="$(echo "${MODEL_S3_URI}" | python3 -c "import sys; u=sys.stdin.read().strip(); print('/'.join(u.split('/')[3:]) + '/')")"

    # -----------------------------------------------------------------------
    # Step 3d: Download manifest.json and verify/sync model files
    # -----------------------------------------------------------------------

    echo "converge: downloading manifest.json from s3://${S3_BUCKET}/${S3_PREFIX}manifest.json"
    aws s3 cp \
        --region "${REGION}" \
        "s3://${S3_BUCKET}/${S3_PREFIX}manifest.json" \
        "${MODEL_CACHE_DIR}/manifest.json"

    export _EMBER_CACHE_DIR="${MODEL_CACHE_DIR}"
    export _EMBER_S3_BUCKET="${S3_BUCKET}"
    export _EMBER_S3_PREFIX="${S3_PREFIX}"
    export _EMBER_REGION="${REGION}"

    echo "converge: verifying and syncing model files against manifest.json"
    python3 - <<'PYEOF'
import json
import hashlib
import subprocess
import sys
import os

cache_dir = os.environ["_EMBER_CACHE_DIR"]
s3_bucket = os.environ["_EMBER_S3_BUCKET"]
s3_prefix = os.environ["_EMBER_S3_PREFIX"]
region = os.environ["_EMBER_REGION"]

manifest_path = os.path.join(cache_dir, "manifest.json")
with open(manifest_path) as f:
    manifest = json.load(f)

for entry in manifest["files"]:
    rel_path = entry["path"]
    expected_sha256 = entry["sha256"]
    local_path = os.path.join(cache_dir, rel_path)

    needs_download = True
    if os.path.exists(local_path):
        h = hashlib.sha256()
        with open(local_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        if h.hexdigest() == expected_sha256:
            needs_download = False
        else:
            print(f"converge: SHA-256 mismatch for {rel_path}, re-downloading", flush=True)
            os.remove(local_path)

    if needs_download:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        s3_key = s3_prefix + rel_path
        print(f"converge: downloading {rel_path}", flush=True)
        subprocess.run(
            ["aws", "s3", "cp", "--region", region,
             f"s3://{s3_bucket}/{s3_key}", local_path],
            check=True,
        )
        h = hashlib.sha256()
        with open(local_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        if h.hexdigest() != expected_sha256:
            print(f"converge: ERROR: SHA-256 still mismatches for {rel_path} after download", flush=True)
            sys.exit(1)

marker = os.path.join(cache_dir, "_download_complete")
tmp_marker = marker + ".tmp"
with open(tmp_marker, "w") as f:
    f.write("ok")
os.replace(tmp_marker, marker)
print("converge: all model files verified", flush=True)
PYEOF

    # -----------------------------------------------------------------------
    # Step 3e: chown the model cache directory to the ember user
    # -----------------------------------------------------------------------

    echo "converge: chown -R ember:ember ${MODEL_CACHE_DIR}"
    chown -R ember:ember "${MODEL_CACHE_DIR}"

    # -----------------------------------------------------------------------
    # Step 3f: Record the applied generation
    # -----------------------------------------------------------------------

    echo "${GENERATION}" > "${GENERATION_FILE}"
    echo "converge: generation ${GENERATION} applied"
fi

# ---------------------------------------------------------------------------
# Step 4: Write /etc/ember/env (0600, root-owned)
# ---------------------------------------------------------------------------

echo "converge: writing ${ENV_FILE}"
mkdir -p /etc/ember

# Determine model cache dir (needed even when generation unchanged)
URI_HASH="$(echo -n "${MODEL_S3_URI}" | python3 -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:16])")"
MODEL_CACHE_DIR="/home/ember/.cache/ember/hosted-models/${URI_HASH}"

umask 077
cat > "${ENV_FILE}" <<EOF
EMBER_HOST=127.0.0.1
EMBER_DEVICE=cuda
EMBER_AUTOSTART=0
EMBER_MODEL_S3_URI=${MODEL_S3_URI}
EMBER_MAX_REQUEST_LENGTH=${MAX_REQUEST_LENGTH}
EMBER_SERVER_AUTH_TOKEN=${EMBER_SERVER_AUTH_TOKEN}
EOF
chmod 600 "${ENV_FILE}"

# Clear the token from the environment
unset EMBER_SERVER_AUTH_TOKEN

# ---------------------------------------------------------------------------
# Step 5: Enable or disable ember-idle.timer based on idle_minutes
# ---------------------------------------------------------------------------

if [[ "${IDLE_MINUTES}" -gt 0 ]]; then
    echo "converge: enabling ember-idle.timer (idle_minutes=${IDLE_MINUTES})"
    systemctl enable --now ember-idle.timer 2>/dev/null || true
else
    echo "converge: disabling ember-idle.timer (idle_minutes=0)"
    systemctl disable --now ember-idle.timer 2>/dev/null || true
fi

echo "converge: done"
