#!/bin/bash
# tailscale-join.sh — join the tailnet and set up the HTTPS reverse proxy.
#
# Runs as ember-tailscale.service (oneshot, Before=ember-converge.service).
# Reads the Tailscale join key from SSM, joins the tailnet, deletes the key,
# then starts the HTTPS reverse proxy on port 443.
#
# If tailscale serve fails (HTTPS Certificates not enabled), writes a message
# to the journal and exits non-zero. ember.service still starts on loopback
# because it depends only on ember-converge.service, not this unit.
#
# Do NOT enable xtrace (set -x): it would echo the join key to the journal.
# Do NOT echo the join key or any secret.

set -euo pipefail

DEPLOYMENT_NAME="{{DEPLOYMENT_NAME}}"
REGION="{{REGION}}"
TAILSCALE_TAG="{{TAILSCALE_TAG}}"
JOIN_KEY_PARAM="{{JOIN_KEY_PARAM}}"

# ---------------------------------------------------------------------------
# Step 1: Join the tailnet (skip if already logged in)
# ---------------------------------------------------------------------------

if tailscale status --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('BackendState') == 'Running' else 1)" 2>/dev/null; then
    echo "tailscale: already logged in, skipping join"
else
    echo "tailscale: fetching join key from SSM"
    AUTH_KEY="$(aws ssm get-parameter \
        --region "${REGION}" \
        --name "${JOIN_KEY_PARAM}" \
        --with-decryption \
        --query 'Parameter.Value' \
        --output text)"

    echo "tailscale: joining tailnet as ember-${DEPLOYMENT_NAME}"
    tailscale up \
        --auth-key="${AUTH_KEY}" \
        --hostname "ember-${DEPLOYMENT_NAME}" \
        --advertise-tags "${TAILSCALE_TAG}" \
        --ssh

    # Delete the join key immediately after use (single-use, expires in 1 h anyway)
    echo "tailscale: deleting join key from SSM"
    aws ssm delete-parameter \
        --region "${REGION}" \
        --name "${JOIN_KEY_PARAM}"

    unset AUTH_KEY
fi

# ---------------------------------------------------------------------------
# Step 2: Start the HTTPS reverse proxy (requires HTTPS Certificates enabled)
# ---------------------------------------------------------------------------

echo "tailscale: starting HTTPS reverse proxy on port 443"
if ! tailscale serve --bg --https=443 http://127.0.0.1:8765; then
    MSG="ember: tailscale serve failed — enable HTTPS Certificates in the Tailscale admin console (DNS page)"
    echo "${MSG}" | systemd-cat -t ember-tailscale -p err
    echo "${MSG}" >&2
    exit 1
fi

echo "tailscale: HTTPS proxy started"
