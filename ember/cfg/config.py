"""JSON config with env-var and CLI-flag precedence.

Precedence (highest first): CLI flag > EMBER_* env var > config file > default.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from . import paths

_log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    # MUST match ember.models.DEFAULT (ember/models.py). Not derived automatically:
    # ember/cfg/config.py MUST NOT import ember/models.py (Article XIII layering —
    # cfg is the shared/config layer models.py itself depends on). Update both
    # together when changing the default registry entry.
    "model": "flash",
    "host": "127.0.0.1",
    "port": 8765,
    "device": "auto",
    # 0 means "the model's own maximum" (ember.serving.limits.model_max_length).
    "max_length": 0,
    # Unset (None) means the loaded model's measured default, resolved in
    # ember/serving/limits.py; 0 disables the cap; a positive value caps the full
    # encoded request.
    "max_request_length": None,
    # Remote inference (see specs/001-remote-inference-servers/). `server_url` is where
    # the client sends advise requests; loopback by default (local-first). The auth_*
    # keys carry the client credential; `server_auth_token` is the optional token the
    # HTTP server itself requires. `request_timeout` bounds a remote request.
    "server_url": "http://127.0.0.1:8765",
    "auth_token": None,  # nosec B105 - None default: no client credential
    "auth_header": "Authorization",
    "allow_insecure_transport": False,
    "request_timeout": 300,
    "server_auth_token": None,  # nosec B105 - None default: server auth disabled
    # AWS S3 connection for EMBER_MODEL_S3_URI (see ember.serving.hosted): a
    # hosted deployment (e.g. Outerbounds) that supplies the model's S3
    # location directly at start time, independent of REGISTRY. These keys
    # are OPTIONAL: when unset (never baked in by default), the S3 client is
    # constructed with no explicit credentials at all and boto3's own default
    # credential chain applies — the expected case for a hosted deployment
    # with an IAM role attached to the compute (the usual Metaflow-managed S3
    # access pattern). Set them explicitly only when
    # running somewhere without an attached role (e.g. a local developer
    # machine).
    "s3_access_key_id": None,  # nosec B105 - None default: no credential
    "s3_secret_access_key": None,  # nosec B105 - None default: no credential
    "s3_region": None,
    # D-006: total S3 prefix size cap before downloading. 0 disables the check.
    # Default 100 GB is generous for any current model while catching
    # misconfigured prefixes pointing at an entire bucket's worth of data.
    "s3_max_bytes": 100 * 1024 * 1024 * 1024,
}

#: Integer keys whose default is unset, so the default alone can't type their env value.
_NULLABLE_INTS = frozenset({"max_request_length"})


def load() -> dict[str, Any]:
    """Load the config file, merged over the defaults.

    Returns
    -------
    dict[str, Any]
        ``DEFAULTS`` overridden by any keys present in the config file. A
        malformed config file is ignored and the defaults are returned as-is.
    """
    config = dict(DEFAULTS)
    path = paths.config_path()
    if path.exists():
        try:
            config.update(json.loads(path.read_text()))
        except json.JSONDecodeError:
            pass
    return config


def save(config: dict[str, Any]) -> Path:
    """Write a config dict to the config file as JSON.

    Parameters
    ----------
    config : dict[str, Any]
        The full config to persist.

    Returns
    -------
    Path
        The config file path written to.
    """
    path = paths.config_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def resolve(key: str, flag: Any = None, env: str | None = None) -> Any:
    """Resolve a setting with flag > env > config > default precedence."""
    if flag is not None:
        return flag
    env_name = env or f"EMBER_{key.upper()}"
    if os.environ.get(env_name) not in (None, ""):
        value: Any = os.environ[env_name]
        default = DEFAULTS.get(key)
        if isinstance(default, bool):
            return value.lower() in ("1", "true", "yes", "on")
        if isinstance(default, int) or key in _NULLABLE_INTS:
            try:
                return int(value)
            except ValueError:
                _log.warning(
                    "ignoring %s=%r: not an integer; using the default", env_name, value
                )
                return default
        return value
    return load().get(key, DEFAULTS.get(key))
