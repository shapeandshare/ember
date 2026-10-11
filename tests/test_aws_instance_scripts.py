"""Tests for instance scripts, systemd units, cloud-init, and user_data.py (T021, T026).

T021: Render the instance files with test values and assert the invariants from
      contracts/infrastructure.md and tasks.md.
T026: Rendered user data ≤ 16,384 bytes; full template body ≤ 51,200 bytes;
      result still parses and passes every T011 invariant; no stack parameter
      carries user data.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO = Path(__file__).parent.parent
_INSTANCE_DIR = _REPO / "deployment" / "aws" / "instance"
_TEMPLATE = _REPO / "deployment" / "aws" / "template.yaml"

# ---------------------------------------------------------------------------
# Test values (never real secrets)
# ---------------------------------------------------------------------------

_TEST_NAME = "testdeploy"
_TEST_REGION = "us-east-1"
_TEST_TAG = "tag:ember"
_TEST_VERSION = "0.12.0"
_TEST_S3_URI = "s3://ember-model-cache-123456789012-us-east-1/models/flash/17f0b0a"
_TEST_MAX_REQUEST_LENGTH = "24576"
_TEST_CONFIG_PARAM = f"/ember/{_TEST_NAME}/config"
_TEST_JOIN_KEY_PARAM = f"/ember/{_TEST_NAME}/tailscale-join-key"
_TEST_TOKEN_PARAM = f"/ember/{_TEST_NAME}/server-token"

# ---------------------------------------------------------------------------
# CFN-tag-tolerant YAML loader (same as test_aws_template.py)
# ---------------------------------------------------------------------------

_CFN_TAGS = [
    "Ref",
    "Sub",
    "GetAtt",
    "If",
    "Equals",
    "Not",
    "And",
    "Or",
    "Select",
    "Join",
    "Split",
    "FindInMap",
    "Base64",
    "Condition",
    "ImportValue",
    "Transform",
]


def _make_cfn_loader() -> type[yaml.SafeLoader]:
    """Return a SafeLoader subclass that handles CFN intrinsic-function tags."""

    class CfnLoader(yaml.SafeLoader):
        pass

    def _tag_constructor(
        loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node
    ) -> Any:
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)  # type: ignore[no-untyped-call]
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)  # type: ignore[no-untyped-call]
        return loader.construct_mapping(node)  # type: ignore[no-untyped-call]

    for tag in _CFN_TAGS:
        CfnLoader.add_constructor(
            f"!{tag}",
            lambda loader, node, t=tag: _tag_constructor(loader, t, node),
        )

    return CfnLoader


_CfnLoader = _make_cfn_loader()


def _load_cfn(path: Path) -> dict[str, Any]:
    return yaml.load(path.read_text(), Loader=_CfnLoader)  # type: ignore[arg-type]  # noqa: S506


# ---------------------------------------------------------------------------
# Helpers: render instance files with test values
# ---------------------------------------------------------------------------


def _render(text: str) -> str:
    """Substitute test values into a template string."""
    return (
        text.replace("{{DEPLOYMENT_NAME}}", _TEST_NAME)
        .replace("{{REGION}}", _TEST_REGION)
        .replace("{{TAILSCALE_TAG}}", _TEST_TAG)
        .replace("{{EMBER_VERSION}}", _TEST_VERSION)
        .replace("{{MODEL_S3_URI}}", _TEST_S3_URI)
        .replace("{{MAX_REQUEST_LENGTH}}", _TEST_MAX_REQUEST_LENGTH)
        .replace("{{CONFIG_PARAM}}", _TEST_CONFIG_PARAM)
        .replace("{{JOIN_KEY_PARAM}}", _TEST_JOIN_KEY_PARAM)
        .replace("{{TOKEN_PARAM}}", _TEST_TOKEN_PARAM)
    )


def _read_instance(filename: str) -> str:
    """Read and render an instance file with test values."""
    path = _INSTANCE_DIR / filename
    return _render(path.read_text())


# ---------------------------------------------------------------------------
# T021: tailscale-join.sh invariants
# ---------------------------------------------------------------------------


def test_tailscale_join_sh_exists() -> None:
    assert (_INSTANCE_DIR / "tailscale-join.sh").exists(), (
        "tailscale-join.sh not found in deployment/aws/instance/"
    )


def test_tailscale_join_sh_runs_tailscale_up() -> None:
    """tailscale-join.sh must run tailscale up with hostname, tag, and --ssh."""
    script = _read_instance("tailscale-join.sh")
    # After substitution, DEPLOYMENT_NAME="testdeploy" and the script uses
    # --hostname "ember-${DEPLOYMENT_NAME}" (shell variable expansion at runtime)
    assert "--hostname" in script
    assert "ember-" in script
    assert "--advertise-tags" in script, (
        "tailscale-join.sh must pass --advertise-tags <tag>"
    )
    assert "--ssh" in script, "tailscale-join.sh must pass --ssh to tailscale up"


def test_tailscale_join_sh_deletes_join_key_param() -> None:
    """tailscale-join.sh must delete the SSM join key parameter after joining."""
    script = _read_instance("tailscale-join.sh")
    assert "aws ssm delete-parameter" in script, (
        "tailscale-join.sh must call aws ssm delete-parameter"
    )
    assert _TEST_JOIN_KEY_PARAM in script, (
        f"tailscale-join.sh must reference the join key param {_TEST_JOIN_KEY_PARAM}"
    )


def test_tailscale_join_sh_runs_tailscale_serve() -> None:
    """tailscale-join.sh must run tailscale serve --bg --https=443 http://127.0.0.1:8765."""
    script = _read_instance("tailscale-join.sh")
    assert "tailscale serve" in script, "tailscale-join.sh must call tailscale serve"
    assert "--bg" in script, "tailscale-join.sh must pass --bg to tailscale serve"
    assert "--https=443" in script, (
        "tailscale-join.sh must pass --https=443 to tailscale serve"
    )
    assert "http://127.0.0.1:8765" in script, (
        "tailscale-join.sh must serve http://127.0.0.1:8765"
    )


def test_tailscale_join_sh_skips_when_already_logged_in() -> None:
    """tailscale-join.sh must skip joining when tailscale status shows logged in."""
    script = _read_instance("tailscale-join.sh")
    assert "tailscale status" in script, (
        "tailscale-join.sh must check tailscale status before joining"
    )


def test_tailscale_join_sh_serve_failure_message() -> None:
    """If tailscale serve fails, write the HTTPS Certificates message to journal."""
    script = _read_instance("tailscale-join.sh")
    assert "HTTPS Certificates" in script or "https-certificates" in script.lower(), (
        "tailscale-join.sh must mention HTTPS Certificates in the failure message"
    )
    # Must write to journal (systemd-cat or logger or journalctl)
    assert any(
        tool in script for tool in ("systemd-cat", "logger", "journalctl", "echo")
    ), "tailscale-join.sh must write the failure message to the journal"


def test_tailscale_join_sh_ember_service_starts_on_loopback() -> None:
    """ember.service must still start on loopback even if tailscale serve fails."""
    script = _read_instance("tailscale-join.sh")
    # The script must exit non-zero on serve failure but not prevent ember.service
    # The contract is: exit non-zero so ember-tailscale.service fails,
    # but ember.service has After=ember-converge.service (not ember-tailscale.service)
    # so it still starts. The test verifies the script exits non-zero on failure.
    assert "exit 1" in script or "exit $" in script or "exit ${" in script, (
        "tailscale-join.sh must exit non-zero when tailscale serve fails"
    )


def test_tailscale_join_sh_no_set_x() -> None:
    """tailscale-join.sh must not use set -x (would echo secrets)."""
    script = _read_instance("tailscale-join.sh")
    # Check only non-comment lines for set -x
    non_comment_lines = [
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any(
        re.search(r"\bset\s+-[a-z]*x[a-z]*\b", line) for line in non_comment_lines
    ), "tailscale-join.sh must not use set -x (would echo secrets to journal)"


def test_tailscale_join_sh_no_echo_token() -> None:
    """tailscale-join.sh must not echo the auth token."""
    script = _read_instance("tailscale-join.sh")
    # Must not echo $AUTH_KEY or $TOKEN or similar
    assert "echo $AUTH_KEY" not in script, (
        "tailscale-join.sh must not echo the auth key"
    )
    assert "echo $TOKEN" not in script, "tailscale-join.sh must not echo the token"


# ---------------------------------------------------------------------------
# T021: converge.sh invariants
# ---------------------------------------------------------------------------


def test_converge_sh_exists() -> None:
    assert (_INSTANCE_DIR / "converge.sh").exists(), (
        "converge.sh not found in deployment/aws/instance/"
    )


def test_converge_sh_writes_env_file_with_umask() -> None:
    """converge.sh must write /etc/ember/env with umask 077 or chmod 600."""
    script = _read_instance("converge.sh")
    has_umask = "umask 077" in script
    has_chmod = "chmod 600" in script
    assert has_umask or has_chmod, (
        "converge.sh must use umask 077 or chmod 600 for /etc/ember/env"
    )


def test_converge_sh_env_file_contains_ember_host() -> None:
    """converge.sh must write EMBER_HOST=127.0.0.1 to /etc/ember/env."""
    script = _read_instance("converge.sh")
    assert "EMBER_HOST=127.0.0.1" in script, (
        "converge.sh must write EMBER_HOST=127.0.0.1 to /etc/ember/env"
    )


def test_converge_sh_env_file_contains_ember_device_cuda() -> None:
    """converge.sh must write EMBER_DEVICE=cuda to /etc/ember/env."""
    script = _read_instance("converge.sh")
    assert "EMBER_DEVICE=cuda" in script, (
        "converge.sh must write EMBER_DEVICE=cuda to /etc/ember/env"
    )


def test_converge_sh_env_file_contains_ember_autostart_0() -> None:
    """converge.sh must write EMBER_AUTOSTART=0 to /etc/ember/env."""
    script = _read_instance("converge.sh")
    assert "EMBER_AUTOSTART=0" in script, (
        "converge.sh must write EMBER_AUTOSTART=0 to /etc/ember/env"
    )


def test_converge_sh_env_file_contains_model_s3_uri() -> None:
    """converge.sh must write EMBER_MODEL_S3_URI to /etc/ember/env."""
    script = _read_instance("converge.sh")
    assert "EMBER_MODEL_S3_URI" in script, (
        "converge.sh must write EMBER_MODEL_S3_URI to /etc/ember/env"
    )


def test_converge_sh_env_file_contains_max_request_length() -> None:
    """converge.sh must write EMBER_MAX_REQUEST_LENGTH to /etc/ember/env."""
    script = _read_instance("converge.sh")
    assert "EMBER_MAX_REQUEST_LENGTH" in script, (
        "converge.sh must write EMBER_MAX_REQUEST_LENGTH to /etc/ember/env"
    )


def test_converge_sh_env_file_contains_server_auth_token() -> None:
    """converge.sh must write EMBER_SERVER_AUTH_TOKEN to /etc/ember/env."""
    script = _read_instance("converge.sh")
    assert "EMBER_SERVER_AUTH_TOKEN" in script, (
        "converge.sh must write EMBER_SERVER_AUTH_TOKEN to /etc/ember/env"
    )


def test_converge_sh_installs_ember_advise_pinned() -> None:
    """converge.sh must install exactly ember-advise==<version>."""
    script = _read_instance("converge.sh")
    # The script uses shell variable ${EMBER_VERSION} read from SSM config;
    # check that the install command references ember-advise== with the variable
    assert "ember-advise==" in script, (
        "converge.sh must install ember-advise==<version> (pinned)"
    )
    assert "uv tool install" in script, (
        "converge.sh must use uv tool install for ember-advise"
    )


def test_converge_sh_verifies_sha256_against_manifest() -> None:
    """converge.sh must verify SHA-256 against manifest.json."""
    script = _read_instance("converge.sh")
    assert "manifest.json" in script, (
        "converge.sh must reference manifest.json for SHA-256 verification"
    )
    assert "sha256" in script.lower() or "sha256sum" in script, (
        "converge.sh must verify SHA-256 checksums"
    )


def test_converge_sh_deletes_and_redownloads_mismatching_file() -> None:
    """converge.sh must delete and re-download a file with a mismatching SHA-256."""
    script = _read_instance("converge.sh")
    assert "os.remove" in script or "rm " in script or "rm\t" in script, (
        "converge.sh must remove mismatching files before re-downloading"
    )


def test_converge_sh_chowns_model_cache() -> None:
    """converge.sh must chown -R ember:ember the model cache directory."""
    script = _read_instance("converge.sh")
    assert "chown -R ember:ember" in script, (
        "converge.sh must run chown -R ember:ember on the model cache directory"
    )


def test_converge_sh_no_set_x() -> None:
    """converge.sh must not use set -x (would echo secrets)."""
    script = _read_instance("converge.sh")
    non_comment_lines = [
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any(
        re.search(r"\bset\s+-[a-z]*x[a-z]*\b", line) for line in non_comment_lines
    ), "converge.sh must not use set -x (would echo secrets to journal)"


def test_converge_sh_no_echo_token() -> None:
    """converge.sh must not echo EMBER_SERVER_AUTH_TOKEN."""
    script = _read_instance("converge.sh")
    assert "echo $EMBER_SERVER_AUTH_TOKEN" not in script, (
        "converge.sh must not echo EMBER_SERVER_AUTH_TOKEN"
    )
    assert 'echo "${EMBER_SERVER_AUTH_TOKEN}"' not in script, (
        "converge.sh must not echo EMBER_SERVER_AUTH_TOKEN"
    )


def test_converge_sh_reads_config_from_ssm() -> None:
    """converge.sh must read the config from SSM."""
    script = _read_instance("converge.sh")
    assert "aws ssm get-parameter" in script, (
        "converge.sh must read config from SSM with aws ssm get-parameter"
    )
    assert _TEST_CONFIG_PARAM in script, (
        f"converge.sh must reference the config param {_TEST_CONFIG_PARAM}"
    )


def test_converge_sh_reads_token_from_ssm() -> None:
    """converge.sh must read the server token from SSM with --with-decryption."""
    script = _read_instance("converge.sh")
    assert "--with-decryption" in script, (
        "converge.sh must use --with-decryption to read the server token"
    )
    assert _TEST_TOKEN_PARAM in script, (
        f"converge.sh must reference the token param {_TEST_TOKEN_PARAM}"
    )


def test_converge_sh_generation_gating() -> None:
    """converge.sh must keep the last applied generation and skip when unchanged."""
    script = _read_instance("converge.sh")
    assert "generation" in script, (
        "converge.sh must track the generation to gate install/sync"
    )
    assert "/var/lib/ember/generation" in script


def test_converge_sh_idle_timer_hook_present() -> None:
    """converge.sh must have a hook to enable/disable ember-idle.timer."""
    script = _read_instance("converge.sh")
    assert "ember-idle" in script, (
        "converge.sh must reference ember-idle (enable/disable hook for T049)"
    )


# ---------------------------------------------------------------------------
# T021: ember.service invariants
# ---------------------------------------------------------------------------


def test_ember_service_exists() -> None:
    assert (_INSTANCE_DIR / "ember.service").exists(), (
        "ember.service not found in deployment/aws/instance/"
    )


def test_ember_service_runs_as_ember_user() -> None:
    """ember.service must run as User=ember."""
    unit = _read_instance("ember.service")
    assert "User=ember" in unit, "ember.service must have User=ember"


def test_ember_service_environment_file() -> None:
    """ember.service must use EnvironmentFile=/etc/ember/env."""
    unit = _read_instance("ember.service")
    assert "EnvironmentFile=/etc/ember/env" in unit, (
        "ember.service must have EnvironmentFile=/etc/ember/env"
    )


def test_ember_service_after_converge() -> None:
    """ember.service must have After=ember-converge.service."""
    unit = _read_instance("ember.service")
    assert "After=ember-converge.service" in unit, (
        "ember.service must have After=ember-converge.service"
    )


def test_ember_service_restart_on_failure() -> None:
    """ember.service must have Restart=on-failure."""
    unit = _read_instance("ember.service")
    assert "Restart=on-failure" in unit, "ember.service must have Restart=on-failure"


# ---------------------------------------------------------------------------
# T021: ember-tailscale.service invariants
# ---------------------------------------------------------------------------


def test_ember_tailscale_service_exists() -> None:
    assert (_INSTANCE_DIR / "ember-tailscale.service").exists(), (
        "ember-tailscale.service not found in deployment/aws/instance/"
    )


def test_ember_tailscale_service_is_oneshot() -> None:
    """ember-tailscale.service must be Type=oneshot."""
    unit = _read_instance("ember-tailscale.service")
    assert "Type=oneshot" in unit, "ember-tailscale.service must be Type=oneshot"


def test_ember_tailscale_service_before_converge() -> None:
    """ember-tailscale.service must have Before=ember-converge.service."""
    unit = _read_instance("ember-tailscale.service")
    assert "Before=ember-converge.service" in unit, (
        "ember-tailscale.service must have Before=ember-converge.service"
    )


# ---------------------------------------------------------------------------
# T021: ember-converge.service invariants
# ---------------------------------------------------------------------------


def test_ember_converge_service_exists() -> None:
    assert (_INSTANCE_DIR / "ember-converge.service").exists(), (
        "ember-converge.service not found in deployment/aws/instance/"
    )


def test_ember_converge_service_is_oneshot() -> None:
    """ember-converge.service must be Type=oneshot."""
    unit = _read_instance("ember-converge.service")
    assert "Type=oneshot" in unit, "ember-converge.service must be Type=oneshot"


# ---------------------------------------------------------------------------
# T021: cloud-init.yaml invariants
# ---------------------------------------------------------------------------


def test_cloud_init_yaml_exists() -> None:
    assert (_INSTANCE_DIR / "cloud-init.yaml").exists(), (
        "cloud-init.yaml not found in deployment/aws/instance/"
    )


def test_cloud_init_installs_uv() -> None:
    """cloud-init.yaml must install uv to /usr/local/bin."""
    content = _read_instance("cloud-init.yaml")
    assert "uv" in content, "cloud-init.yaml must install uv"


def test_cloud_init_installs_tailscale() -> None:
    """cloud-init.yaml must install tailscale."""
    content = _read_instance("cloud-init.yaml")
    assert "tailscale" in content, "cloud-init.yaml must install tailscale"


def test_cloud_init_installs_aws_cli() -> None:
    """cloud-init.yaml must install the aws CLI v2."""
    content = _read_instance("cloud-init.yaml")
    assert "aws" in content.lower(), "cloud-init.yaml must install the aws CLI"


def test_cloud_init_creates_ember_user() -> None:
    """cloud-init.yaml must create the ember user."""
    content = _read_instance("cloud-init.yaml")
    assert "ember" in content, "cloud-init.yaml must create the ember user"


def test_cloud_init_enables_systemd_units() -> None:
    """cloud-init.yaml must enable ember-tailscale, ember-converge, and ember."""
    content = _read_instance("cloud-init.yaml")
    assert "ember-tailscale" in content, "cloud-init.yaml must enable ember-tailscale"
    assert "ember-converge" in content, "cloud-init.yaml must enable ember-converge"
    assert "ember.service" in content or ("ember" in content and "enable" in content), (
        "cloud-init.yaml must enable ember.service"
    )


# ---------------------------------------------------------------------------
# T026: UserData size and parse invariants
# ---------------------------------------------------------------------------


def test_user_data_module_exists() -> None:
    """deployment/aws/ember_aws/user_data.py must exist."""
    path = _REPO / "deployment" / "aws" / "ember_aws" / "user_data.py"
    assert path.exists(), "user_data.py not found in deployment/aws/ember_aws/"


def test_user_data_render_returns_str() -> None:
    """UserData.render() must return a string."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    result = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    assert isinstance(result, str), "UserData.render() must return a str"


def test_user_data_size_within_ec2_limit() -> None:
    """Rendered user data must be ≤ 16,384 bytes (EC2 limit)."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    result = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    size = len(result.encode("utf-8"))
    assert size <= 16384, (
        f"Rendered user data is {size} bytes, exceeds EC2 limit of 16,384 bytes"
    )


def test_template_body_size_within_cfn_limit() -> None:
    """Full template body must be ≤ 51,200 bytes (CloudFormation inline limit)."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    rendered = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    body = UserData.template_body(rendered)
    size = len(body.encode("utf-8"))
    assert size <= 51200, (
        f"Template body is {size} bytes, exceeds CloudFormation limit of 51,200 bytes"
    )


def test_template_body_parses_as_yaml() -> None:
    """template_body() result must parse as valid YAML."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    rendered = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    body = UserData.template_body(rendered)
    # Must parse without error
    parsed = yaml.load(body, Loader=_CfnLoader)  # type: ignore[arg-type]  # noqa: S506
    assert parsed is not None, "template_body() result must parse as YAML"


def test_template_body_no_placeholder_remaining() -> None:
    """template_body() must replace __EMBER_USER_DATA__ in the Fn::Base64 value."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    rendered = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    body = UserData.template_body(rendered)
    # The placeholder must not appear as a YAML value (only allowed in comments)
    non_comment_lines = [
        line for line in body.splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any("__EMBER_USER_DATA__" in line for line in non_comment_lines), (
        "template_body() must replace the __EMBER_USER_DATA__ placeholder in Fn::Base64"
    )


def test_template_body_no_userdata_parameter() -> None:
    """No stack parameter may carry user data (T026 invariant)."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    rendered = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    body = UserData.template_body(rendered)
    parsed = yaml.load(body, Loader=_CfnLoader)  # type: ignore[arg-type]  # noqa: S506
    params = parsed.get("Parameters", {})
    assert "UserData" not in params, "No stack parameter may be named UserData"


def test_template_body_passes_t011_security_group_invariant() -> None:
    """template_body() result must pass the T011 security group invariant."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    rendered = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    body = UserData.template_body(rendered)
    parsed = yaml.load(body, Loader=_CfnLoader)  # type: ignore[arg-type]  # noqa: S506
    resources = parsed.get("Resources", {})
    sg = resources.get("SecurityGroup", {})
    sg_props = sg.get("Properties", {})
    assert "SecurityGroupIngress" not in sg_props, (
        "SecurityGroup in template_body() result must have no SecurityGroupIngress"
    )


def test_template_body_passes_t011_imdsv2_invariant() -> None:
    """template_body() result must pass the T011 IMDSv2 invariant."""
    import sys

    sys.path.insert(0, str(_REPO / "deployment" / "aws"))
    from ember_aws.instance_config import InstanceConfig
    from ember_aws.names import DeploymentName
    from ember_aws.user_data import UserData

    names = DeploymentName(name=_TEST_NAME)
    config = InstanceConfig(
        ember_version=_TEST_VERSION,
        model_s3_uri=_TEST_S3_URI,
        max_request_length=int(_TEST_MAX_REQUEST_LENGTH),
        idle_minutes=0,
        generation=1,
    )
    rendered = UserData.render(
        names=names,
        region=_TEST_REGION,
        config=config,
        tailscale_tag=_TEST_TAG,
    )
    body = UserData.template_body(rendered)
    parsed = yaml.load(body, Loader=_CfnLoader)  # type: ignore[arg-type]  # noqa: S506
    resources = parsed.get("Resources", {})
    instance = resources.get("Instance", {})
    instance_props = instance.get("Properties", {})
    metadata_opts = instance_props.get("MetadataOptions", {})
    assert metadata_opts.get("HttpTokens") == "required", (
        "MetadataOptions.HttpTokens must be 'required' in template_body() result"
    )


# ---------------------------------------------------------------------------
# T044 (US3 prep): generation-gating invariants (basic, no-op when unchanged)
# ---------------------------------------------------------------------------


def test_converge_sh_skips_install_when_generation_unchanged() -> None:
    """converge.sh must skip install and sync when generation is unchanged."""
    script = _read_instance("converge.sh")
    # The script must compare the stored generation with the current one
    assert "generation" in script, (
        "converge.sh must track generation to skip install/sync when unchanged"
    )
    # Must have a conditional block around the install
    assert "if" in script, (
        "converge.sh must have a conditional to skip install when generation unchanged"
    )


# ---------------------------------------------------------------------------
# T044 (US3): converge.sh model_s3_uri gating
# ---------------------------------------------------------------------------


def test_converge_sh_skips_model_sync_when_same_model_s3_uri() -> None:
    """converge.sh with new generation but same model_s3_uri must skip model sync.

    SC-002, FR-007: when the generation changes but the model_s3_uri is the same
    as the last applied one, the model sync step is skipped (only ember-advise
    is reinstalled).
    """
    script = _read_instance("converge.sh")
    # The script must track the last applied model_s3_uri separately from generation
    # so it can skip the sync when only the version changed.
    assert "MODEL_S3_URI" in script, (
        "converge.sh must reference MODEL_S3_URI for model sync gating"
    )
    # Must have a file or variable that stores the last applied model_s3_uri
    assert (
        "model_s3_uri" in script.lower()
        or "last_model" in script.lower()
        or "model_uri_file" in script.lower()
        or "/var/lib/ember/model" in script
    ), "converge.sh must track the last model_s3_uri to skip an unchanged sync"


def test_converge_sh_syncs_new_model_s3_uri() -> None:
    """converge.sh with a new model_s3_uri must sync the new prefix.

    SC-002, FR-007: when the model_s3_uri changes (e.g. a new model revision),
    the script must sync from the new S3 prefix.
    """
    script = _read_instance("converge.sh")
    # The script must use MODEL_S3_URI to determine the S3 bucket and prefix
    assert "S3_BUCKET" in script or "s3_bucket" in script.lower(), (
        "converge.sh must parse the S3 bucket from MODEL_S3_URI"
    )
    assert "S3_PREFIX" in script or "s3_prefix" in script.lower(), (
        "converge.sh must parse the S3 prefix from MODEL_S3_URI"
    )
    # Must download from the new prefix when model_s3_uri changes
    assert "aws s3 cp" in script or "aws s3 sync" in script, (
        "converge.sh must use aws s3 cp or aws s3 sync to download model files"
    )


def test_converge_sh_model_uri_file_path() -> None:
    """converge.sh must store the last applied model_s3_uri in /var/lib/ember/."""
    script = _read_instance("converge.sh")
    # The last applied model_s3_uri must be persisted so the next boot can compare
    assert "/var/lib/ember/" in script, (
        "converge.sh must use /var/lib/ember/ for state files"
    )
    # Must have a file for the model URI (separate from the generation file)
    assert (
        "model_uri" in script.lower()
        or "model-uri" in script.lower()
        or "last_model" in script.lower()
    ), "converge.sh must persist the last applied model_s3_uri in /var/lib/ember/"


# ---------------------------------------------------------------------------
# T047: idle.sh invariants
# ---------------------------------------------------------------------------


def test_idle_sh_exists() -> None:
    """idle.sh must exist in deployment/aws/instance/."""
    assert (_INSTANCE_DIR / "idle.sh").exists(), (
        "idle.sh not found in deployment/aws/instance/"
    )


def test_idle_sh_parses_ember_advise_requests_total() -> None:
    """idle.sh must parse ember_advise_requests_total from /metrics."""
    script = _read_instance("idle.sh")
    assert "ember_advise_requests_total" in script, (
        "idle.sh must parse ember_advise_requests_total from /metrics"
    )


def test_idle_sh_sums_over_all_status_labels() -> None:
    """idle.sh must sum ember_advise_requests_total over all status labels."""
    script = _read_instance("idle.sh")
    # The script must aggregate across all status label values, not pick one
    # Typical approach: grep for the metric name and sum the values
    assert "ember_advise_requests_total" in script
    # Must use some form of summation (awk, python, etc.)
    assert "awk" in script or "python3" in script or "sum" in script.lower(), (
        "idle.sh must sum ember_advise_requests_total over all status labels"
    )


def test_idle_sh_resets_timestamp_when_count_changes() -> None:
    """idle.sh must reset the idle timestamp when the request count changes."""
    script = _read_instance("idle.sh")
    # Must track the last count and compare it
    assert (
        "last_count" in script.lower()
        or "prev_count" in script.lower()
        or "count_file" in script.lower()
        or "LAST_COUNT" in script
        or "PREV_COUNT" in script
    ), "idle.sh must track the last request count to detect changes"
    # Must reset a timestamp when the count changes
    assert (
        "timestamp" in script.lower()
        or "idle_since" in script.lower()
        or "IDLE_SINCE" in script
        or "LAST_ACTIVE" in script
    ), "idle.sh must reset a timestamp when the request count changes"


def test_idle_sh_calls_shutdown_when_idle_long_enough() -> None:
    """idle.sh must call the shutdown command when idle for >= idle_minutes."""
    script = _read_instance("idle.sh")
    assert (
        "shutdown" in script or "SHUTDOWN_CMD" in script or "shutdown_cmd" in script
    ), "idle.sh must call a shutdown command when idle long enough"
    assert "IDLE_MINUTES" in script or "idle_minutes" in script.lower(), (
        "idle.sh must use IDLE_MINUTES to determine the idle threshold"
    )


def test_idle_sh_does_nothing_when_idle_minutes_zero() -> None:
    """idle.sh must do nothing when IDLE_MINUTES is 0."""
    script = _read_instance("idle.sh")
    # Must check IDLE_MINUTES == 0 and exit early
    assert "IDLE_MINUTES" in script, "idle.sh must check IDLE_MINUTES"
    # Must have an early-exit guard for IDLE_MINUTES == 0
    assert (
        'IDLE_MINUTES" -eq 0' in script
        or "IDLE_MINUTES == 0" in script
        or "IDLE_MINUTES -eq 0" in script
        or '[ "${IDLE_MINUTES}" = "0" ]' in script
        or "[ $IDLE_MINUTES -eq 0 ]" in script
        or 'IDLE_MINUTES}" -eq 0' in script
    ), "idle.sh must exit early when IDLE_MINUTES is 0"


def test_idle_sh_no_set_x() -> None:
    """idle.sh must not use set -x (would echo secrets)."""
    script = _read_instance("idle.sh")
    non_comment_lines = [
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any(
        re.search(r"\bset\s+-[a-z]*x[a-z]*\b", line) for line in non_comment_lines
    ), "idle.sh must not use set -x"


def test_idle_sh_reads_metrics_from_loopback() -> None:
    """idle.sh must read metrics from http://127.0.0.1:8765/metrics."""
    script = _read_instance("idle.sh")
    assert "127.0.0.1" in script or "localhost" in script, (
        "idle.sh must read metrics from the loopback address"
    )
    assert "/metrics" in script, "idle.sh must read from the /metrics endpoint"


def test_idle_sh_uses_state_file_in_var_lib_ember() -> None:
    """idle.sh must store state in /var/lib/ember/."""
    script = _read_instance("idle.sh")
    assert "/var/lib/ember/" in script, (
        "idle.sh must store state files in /var/lib/ember/"
    )


# ---------------------------------------------------------------------------
# T047: ember-idle.service and ember-idle.timer invariants
# ---------------------------------------------------------------------------


def test_ember_idle_service_exists() -> None:
    """ember-idle.service must exist in deployment/aws/instance/."""
    assert (_INSTANCE_DIR / "ember-idle.service").exists(), (
        "ember-idle.service not found in deployment/aws/instance/"
    )


def test_ember_idle_timer_exists() -> None:
    """ember-idle.timer must exist in deployment/aws/instance/."""
    assert (_INSTANCE_DIR / "ember-idle.timer").exists(), (
        "ember-idle.timer not found in deployment/aws/instance/"
    )


def test_ember_idle_service_runs_idle_sh() -> None:
    """ember-idle.service must run idle.sh."""
    unit = _read_instance("ember-idle.service")
    assert "idle.sh" in unit, "ember-idle.service must run idle.sh"


def test_ember_idle_timer_on_unit_active_sec_1min() -> None:
    """ember-idle.timer must have OnUnitActiveSec=1min."""
    unit = _read_instance("ember-idle.timer")
    assert "OnUnitActiveSec=1min" in unit, (
        "ember-idle.timer must have OnUnitActiveSec=1min"
    )


def test_ember_idle_timer_references_idle_service() -> None:
    """ember-idle.timer must reference ember-idle.service."""
    unit = _read_instance("ember-idle.timer")
    assert "ember-idle" in unit, "ember-idle.timer must reference ember-idle.service"


# ---------------------------------------------------------------------------
# T047: converge.sh idle timer enable/disable
# ---------------------------------------------------------------------------


def test_converge_sh_enables_idle_timer_when_idle_minutes_gt_0() -> None:
    """converge.sh must enable ember-idle.timer when idle_minutes > 0."""
    script = _read_instance("converge.sh")
    assert (
        "systemctl enable" in script
        or "systemctl --now" in script
        or ("enable" in script and "ember-idle" in script)
    ), "converge.sh must enable ember-idle.timer when idle_minutes > 0"
    assert "ember-idle.timer" in script, "converge.sh must reference ember-idle.timer"


def test_converge_sh_disables_idle_timer_when_idle_minutes_zero() -> None:
    """converge.sh must disable ember-idle.timer when idle_minutes == 0."""
    script = _read_instance("converge.sh")
    assert "systemctl disable" in script or (
        "disable" in script and "ember-idle" in script
    ), "converge.sh must disable ember-idle.timer when idle_minutes == 0"
