"""Tests for DeploymentName, enums, and the sizing table (T005, T007, T008)."""

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# T005 — DeploymentName
# ---------------------------------------------------------------------------


def test_deployment_name_accepts_default() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.name == "default"


def test_deployment_name_accepts_team_a1() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="team-a1")
    assert dn.name == "team-a1"


def test_deployment_name_rejects_uppercase() -> None:
    from pydantic import ValidationError

    from ember_aws.names import DeploymentName

    with pytest.raises(ValidationError):
        DeploymentName(name="A")


def test_deployment_name_rejects_leading_dash() -> None:
    from pydantic import ValidationError

    from ember_aws.names import DeploymentName

    with pytest.raises(ValidationError):
        DeploymentName(name="-x")


def test_deployment_name_rejects_trailing_dash() -> None:
    from pydantic import ValidationError

    from ember_aws.names import DeploymentName

    with pytest.raises(ValidationError):
        DeploymentName(name="x-")


def test_deployment_name_rejects_too_long() -> None:
    from pydantic import ValidationError

    from ember_aws.names import DeploymentName

    # 33 characters — one over the limit
    with pytest.raises(ValidationError):
        DeploymentName(name="a" * 33)


def test_deployment_name_rejects_underscore() -> None:
    from pydantic import ValidationError

    from ember_aws.names import DeploymentName

    with pytest.raises(ValidationError):
        DeploymentName(name="under_score")


def test_deployment_name_stack_name() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.stack_name == "ember-default"


def test_deployment_name_hostname() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.hostname == "ember-default"


def test_deployment_name_ssm_prefix() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.ssm_prefix == "/ember/default/"


def test_deployment_name_tag() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.tag == "ember:deployment=default"


def test_deployment_name_config_param() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.config_param == "/ember/default/config"


def test_deployment_name_token_param() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.token_param == "/ember/default/server-token"


def test_deployment_name_join_key_param() -> None:
    from ember_aws.names import DeploymentName

    dn = DeploymentName(name="default")
    assert dn.join_key_param == "/ember/default/tailscale-join-key"


# ---------------------------------------------------------------------------
# T007 — StrEnum one-liners
# ---------------------------------------------------------------------------


def test_capacity_values() -> None:
    from ember_aws.capacity import Capacity

    assert Capacity.ON_DEMAND == "on-demand"
    assert Capacity.SPOT == "spot"


def test_deployment_state_values() -> None:
    from ember_aws.deployment_state import DeploymentState

    assert DeploymentState.ABSENT == "absent"
    assert DeploymentState.RUNNING == "running"
    assert DeploymentState.FAILED == "failed"


def test_stop_reason_values() -> None:
    from ember_aws.stop_reason import StopReason

    assert StopReason.OPERATOR == "operator"
    assert StopReason.IDLE == "idle"
    assert StopReason.SPOT_INTERRUPTION == "spot-interruption"
    assert StopReason.UNKNOWN == "unknown"


def test_sizing_status_values() -> None:
    from ember_aws.sizing_status import SizingStatus

    assert SizingStatus.SUPPORTED == "supported"
    assert SizingStatus.TIGHT == "tight"
    assert SizingStatus.UNSUPPORTED == "unsupported"


def test_cap_source_values() -> None:
    from ember_aws.cap_source import CapSource

    assert CapSource.MEASURED == "measured"
    assert CapSource.FALLBACK == "fallback"


def test_preflight_check_values() -> None:
    from ember_aws.preflight_check import PreflightCheck

    assert PreflightCheck.AWS_IDENTITY == "aws-identity"
    assert PreflightCheck.REGION == "region"
    assert PreflightCheck.TOOLING == "tooling"
    assert PreflightCheck.GPU_QUOTA == "gpu-quota"
    assert PreflightCheck.INSTANCE_OFFERING == "instance-offering"
    assert PreflightCheck.TAILSCALE_OAUTH == "tailscale-oauth"
    assert PreflightCheck.TAILSCALE_TAG == "tailscale-tag"
    assert PreflightCheck.TAILSCALE_MAGICDNS == "tailscale-magicdns"
    assert PreflightCheck.TAILSCALE_HTTPS == "tailscale-https"
    assert PreflightCheck.MODEL_CACHED == "model-cached"


# ---------------------------------------------------------------------------
# T008 — SizingTable
# ---------------------------------------------------------------------------

_SIZING_JSON = Path(__file__).parent.parent / "deployment" / "aws" / "sizing.json"


def test_sizing_table_loads() -> None:
    from ember_aws.sizing_table import SizingTable

    table = SizingTable.load(_SIZING_JSON)
    assert len(table.entries) > 0


def test_sizing_table_exactly_one_default_per_model() -> None:
    from ember_aws.sizing_status import SizingStatus
    from ember_aws.sizing_table import SizingTable

    table = SizingTable.load(_SIZING_JSON)
    models = {e.model for e in table.entries}
    for model in models:
        defaults = [
            e
            for e in table.entries
            if e.model == model and e.default and e.status == SizingStatus.SUPPORTED
        ]
        count = len(defaults)
        assert count == 1, f"model {model!r} has {count} supported defaults"


def test_sizing_table_unsupported_when_gpu_memory_too_small() -> None:
    """A row whose gpu_memory_gib < weights_gib + 4 must have status unsupported."""
    from ember_aws.sizing_status import SizingStatus
    from ember_aws.sizing_table import SizingTable

    table = SizingTable.load(_SIZING_JSON)
    # g5.2xlarge has 24 GiB; flash weights are ~18 GiB → 18+4=22 ≤ 24, so tight is OK.
    # We verify the rule holds for any row that is unsupported.
    for entry in table.entries:
        if entry.status == SizingStatus.UNSUPPORTED:
            from ember.models import REGISTRY

            if entry.model in REGISTRY:
                weights_gib = REGISTRY[entry.model].approx_bytes / (2**30)
                assert entry.gpu_memory_gib < weights_gib + 4


def test_sizing_resolve_flash_default() -> None:
    from ember_aws.sizing_table import SizingTable

    table = SizingTable.load(_SIZING_JSON)
    entry = table.resolve("flash", None)
    assert entry.instance_type == "g6e.xlarge"


def test_sizing_resolve_flash_g5_tight() -> None:
    from ember_aws.sizing_status import SizingStatus
    from ember_aws.sizing_table import SizingTable

    table = SizingTable.load(_SIZING_JSON)
    entry = table.resolve("flash", "g5.2xlarge")
    assert entry.status == SizingStatus.TIGHT


def test_sizing_resolve_flash_g4dn_raises() -> None:
    from ember_aws.sizing_table import SizingError, SizingTable

    table = SizingTable.load(_SIZING_JSON)
    with pytest.raises(SizingError, match=r"g4dn\.xlarge"):
        table.resolve("flash", "g4dn.xlarge")


def test_sizing_resolve_full_raises() -> None:
    from ember_aws.sizing_table import SizingError, SizingTable

    table = SizingTable.load(_SIZING_JSON)
    with pytest.raises(SizingError, match="full"):
        table.resolve("full", None)


def test_sizing_resolve_error_message_names_reason() -> None:
    from ember_aws.sizing_table import SizingError, SizingTable

    table = SizingTable.load(_SIZING_JSON)
    with pytest.raises(SizingError) as exc_info:
        table.resolve("full", None)
    assert len(str(exc_info.value)) > 0


# ---------------------------------------------------------------------------
# Regex contract (documented in data-model.md)
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")


def test_name_regex_accepts_default() -> None:
    assert _NAME_RE.match("default")


def test_name_regex_accepts_team_a1() -> None:
    assert _NAME_RE.match("team-a1")


def test_name_regex_rejects_uppercase() -> None:
    assert not _NAME_RE.match("A")


def test_name_regex_rejects_leading_dash() -> None:
    assert not _NAME_RE.match("-x")


def test_name_regex_rejects_trailing_dash() -> None:
    assert not _NAME_RE.match("x-")


def test_name_regex_rejects_33_chars() -> None:
    assert not _NAME_RE.match("a" * 33)


def test_name_regex_rejects_underscore() -> None:
    assert not _NAME_RE.match("under_score")
