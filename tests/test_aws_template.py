"""Tests for CloudFormation template invariants (T011).

Asserts every invariant in contracts/infrastructure.md by parsing
``deployment/aws/template.yaml`` and ``deployment/aws/cache-template.yaml``
with a YAML loader that tolerates CFN tags (``!Ref``, ``!Sub``, ``!GetAtt``,
``!If``, ``!Equals``, ``!Not``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# CFN-tag-tolerant YAML loader
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

_AWS_DIR = Path(__file__).parent.parent / "deployment" / "aws"
_TEMPLATE = _AWS_DIR / "template.yaml"
_CACHE_TEMPLATE = _AWS_DIR / "cache-template.yaml"


def _load(path: Path) -> dict[str, Any]:
    return yaml.load(path.read_text(), Loader=_CfnLoader)  # type: ignore[arg-type]  # noqa: S506


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_resources(tmpl: dict[str, Any]) -> dict[str, Any]:
    return tmpl.get("Resources", {})


def _resource(tmpl: dict[str, Any], logical_id: str) -> dict[str, Any]:
    return _all_resources(tmpl)[logical_id]


def _props(tmpl: dict[str, Any], logical_id: str) -> dict[str, Any]:
    return _resource(tmpl, logical_id).get("Properties", {})


def _flatten(obj: Any) -> list[Any]:
    """Recursively collect all leaf values from a nested structure."""
    if isinstance(obj, dict):
        result: list[Any] = []
        for v in obj.values():
            result.extend(_flatten(v))
        return result
    if isinstance(obj, list):
        result = []
        for item in obj:
            result.extend(_flatten(item))
        return result
    return [obj]


def _all_strings(obj: Any) -> list[str]:
    """Collect all string values AND keys from a nested structure."""
    if isinstance(obj, dict):
        result: list[str] = []
        for k, v in obj.items():
            if isinstance(k, str):
                result.append(k)
            result.extend(_all_strings(v))
        return result
    if isinstance(obj, list):
        result = []
        for item in obj:
            result.extend(_all_strings(item))
        return result
    if isinstance(obj, str):
        return [obj]
    return []


# ---------------------------------------------------------------------------
# template.yaml — security group
# ---------------------------------------------------------------------------


def test_template_exists() -> None:
    assert _TEMPLATE.exists(), f"template.yaml not found at {_TEMPLATE}"


def test_security_group_no_ingress_property() -> None:
    tmpl = _load(_TEMPLATE)
    sg_props = _props(tmpl, "SecurityGroup")
    assert "SecurityGroupIngress" not in sg_props, (
        "SecurityGroup must have no SecurityGroupIngress property"
    )


def test_no_standalone_security_group_ingress_resource() -> None:
    tmpl = _load(_TEMPLATE)
    for logical_id, resource in _all_resources(tmpl).items():
        assert resource.get("Type") != "AWS::EC2::SecurityGroupIngress", (
            f"Found standalone SecurityGroupIngress resource: {logical_id}"
        )


# ---------------------------------------------------------------------------
# template.yaml — IAM
# ---------------------------------------------------------------------------


def test_iam_no_managed_policy_arns() -> None:
    tmpl = _load(_TEMPLATE)
    role_props = _props(tmpl, "InstanceRole")
    assert "ManagedPolicyArns" not in role_props, (
        "InstanceRole must not have ManagedPolicyArns"
    )


def test_iam_no_star_resource() -> None:
    """No IAM statement may use a literal '*' resource."""
    tmpl = _load(_TEMPLATE)
    role_props = _props(tmpl, "InstanceRole")
    policies = role_props.get("Policies", [])
    for policy in policies:
        doc = policy.get("PolicyDocument", {})
        for stmt in doc.get("Statement", []):
            resource = stmt.get("Resource", "")
            if isinstance(resource, str):
                assert resource != "*", f"IAM statement has '*' resource: {stmt}"
            elif isinstance(resource, list):
                assert "*" not in resource, (
                    f"IAM statement has '*' in resource list: {stmt}"
                )


def test_iam_resources_scoped() -> None:
    """Every IAM Resource must be scoped to this deployment, cache, or account."""
    tmpl = _load(_TEMPLATE)
    role_props = _props(tmpl, "InstanceRole")
    policies = role_props.get("Policies", [])
    for policy in policies:
        doc = policy.get("PolicyDocument", {})
        for stmt in doc.get("Statement", []):
            resource = stmt.get("Resource", "")
            resources = [resource] if isinstance(resource, str) else resource
            for r in resources:
                strings = _all_strings(r)
                combined = " ".join(strings)
                assert any(
                    kw in combined
                    for kw in (
                        "DeploymentName",
                        "CacheBucket",
                        "ModelPrefix",
                        "AWS::Region",
                        "AWS::AccountId",
                    )
                ), (
                    "IAM Resource not scoped to this deployment, cache, or account:"
                    f" {r}"
                )


def test_iam_kms_decrypt_scoped_to_ssm() -> None:
    """The role decrypts SecureStrings through SSM only (R8)."""
    tmpl = _load(_TEMPLATE)
    role_props = _props(tmpl, "InstanceRole")
    statements = [
        stmt
        for policy in role_props.get("Policies", [])
        for stmt in policy.get("PolicyDocument", {}).get("Statement", [])
    ]

    decrypt = [
        stmt for stmt in statements if "kms:Decrypt" in _flatten(stmt.get("Action", []))
    ]
    assert len(decrypt) == 1, "expected exactly one kms:Decrypt statement"
    stmt = decrypt[0]
    condition = " ".join(_all_strings(stmt.get("Condition", {})))
    assert "kms:ViaService" in condition, (
        "kms:Decrypt must be conditioned on kms:ViaService"
    )
    assert "ssm." in condition, "the condition must constrain use to the SSM service"
    assert "amazonaws.com" in condition, "the condition must name the AWS domain"
    resources = _flatten(stmt.get("Resource", ""))
    assert "*" not in resources, "kms:Decrypt must not use a '*' resource"


def test_iam_names_are_region_scoped() -> None:
    """RoleName and InstanceProfileName embed the region (account-global names)."""
    tmpl = _load(_TEMPLATE)
    role_name = str(_props(tmpl, "InstanceRole").get("RoleName", ""))
    profile_name = str(_props(tmpl, "InstanceProfile").get("InstanceProfileName", ""))

    assert "AWS::Region" in role_name, (
        "the IAM role name must include the region: IAM names are account-global"
    )
    assert "AWS::Region" in profile_name, (
        "the instance profile name must include the region"
    )


def test_iam_list_bucket_scoped_to_model_prefix() -> None:
    """s3:ListBucket carries an s3:prefix condition; object reads stay separate."""
    tmpl = _load(_TEMPLATE)
    role_props = _props(tmpl, "InstanceRole")
    statements = [
        stmt
        for policy in role_props.get("Policies", [])
        for stmt in policy.get("PolicyDocument", {}).get("Statement", [])
    ]

    list_statements = [
        stmt
        for stmt in statements
        if "s3:ListBucket" in _flatten(stmt.get("Action", []))
    ]
    assert len(list_statements) == 1, "expected exactly one s3:ListBucket statement"
    condition = _flatten(list_statements[0].get("Condition", {}))
    assert any("ModelPrefix" in str(v) for v in condition), (
        "s3:ListBucket must be conditioned on the model prefix"
    )

    get_statements = [
        stmt
        for stmt in statements
        if "s3:GetObject" in _flatten(stmt.get("Action", []))
    ]
    assert get_statements, "expected an s3:GetObject statement"
    for stmt in get_statements:
        assert "s3:ListBucket" not in _flatten(stmt.get("Action", [])), (
            "s3:GetObject must be its own statement"
        )


# ---------------------------------------------------------------------------
# template.yaml — Instance metadata and storage
# ---------------------------------------------------------------------------


def test_imdsv2_required() -> None:
    tmpl = _load(_TEMPLATE)
    instance_props = _props(tmpl, "Instance")
    metadata_opts = instance_props.get("MetadataOptions", {})
    assert metadata_opts.get("HttpTokens") == "required", (
        "MetadataOptions.HttpTokens must be 'required' (IMDSv2)"
    )


def test_root_volume_gp3() -> None:
    tmpl = _load(_TEMPLATE)
    instance_props = _props(tmpl, "Instance")
    mappings = instance_props.get("BlockDeviceMappings", [])
    root = next(
        (m for m in mappings if m.get("DeviceName") in ("/dev/xvda", "/dev/sda1")),
        None,
    )
    assert root is not None, "No root block device mapping found"
    ebs = root.get("Ebs", {})
    assert ebs.get("VolumeType") == "gp3", "Root volume must be gp3"
    assert ebs.get("VolumeSize", 0) >= 100, "Root volume must be >= 100 GiB"
    assert ebs.get("Encrypted") is True, "Root volume must be Encrypted: true"
    assert ebs.get("DeleteOnTermination") is True, (
        "Root volume must have DeleteOnTermination: true"
    )


def test_root_volume_targets_dlami_root_device() -> None:
    """BlockDeviceMappings must resize the DLAMI root device, not add a volume.

    This DLAMI's RootDeviceName is /dev/sda1. A mapping for /dev/xvda created a
    second, unused volume while the 75 GiB root stayed put — the first live
    boot then hit AWS_ERROR_NO_SPACE partway through the model download.
    """
    tmpl = _load(_TEMPLATE)
    mappings = _props(tmpl, "Instance").get("BlockDeviceMappings", [])
    devices = {m.get("DeviceName") for m in mappings}
    assert "/dev/sda1" in devices, "must resize the DLAMI root device /dev/sda1"
    assert "/dev/xvda" not in devices, "must not add a second, unused /dev/xvda volume"


def test_instance_initiated_shutdown_behavior_stop() -> None:
    tmpl = _load(_TEMPLATE)
    instance_props = _props(tmpl, "Instance")
    assert instance_props.get("InstanceInitiatedShutdownBehavior") == "stop", (
        "InstanceInitiatedShutdownBehavior must be 'stop'"
    )


# ---------------------------------------------------------------------------
# template.yaml — Spot options
# ---------------------------------------------------------------------------


def test_spot_options_conditional() -> None:
    """InstanceMarketOptions must be conditional on Capacity == spot."""
    tmpl = _load(_TEMPLATE)
    instance_props = _props(tmpl, "Instance")
    # InstanceMarketOptions should be wrapped in an If condition
    market_opts = instance_props.get("InstanceMarketOptions")
    assert market_opts is not None, (
        "Instance must have InstanceMarketOptions (conditional on Capacity=spot)"
    )
    # The value should be an If intrinsic (represented as a list after CFN tag parsing)
    assert isinstance(market_opts, list), (
        "InstanceMarketOptions must be an !If conditional"
    )


def test_spot_options_persistent_stop() -> None:
    """Spot options must be persistent with interruption behavior stop."""
    tmpl = _load(_TEMPLATE)
    instance_props = _props(tmpl, "Instance")
    market_opts = instance_props.get("InstanceMarketOptions", [])
    # market_opts is [ConditionName, spot_value, no_value] after !If parsing
    if isinstance(market_opts, list) and len(market_opts) >= 2:
        spot_value = market_opts[1]
        if isinstance(spot_value, dict):
            spot_opts = spot_value.get("SpotOptions", {})
            assert spot_opts.get("SpotInstanceType") == "persistent", (
                "Spot options must be persistent"
            )
            assert spot_opts.get("InstanceInterruptionBehavior") == "stop", (
                "Spot interruption behavior must be stop"
            )


# ---------------------------------------------------------------------------
# template.yaml — Tags
# ---------------------------------------------------------------------------


def test_every_taggable_resource_has_deployment_tag() -> None:
    """Every taggable resource must carry ember:deployment and ember:managed-by tags."""
    tmpl = _load(_TEMPLATE)
    # Resources that support Tags in CFN (InstanceProfile does NOT support Tags)
    taggable_types = {
        "AWS::EC2::SecurityGroup",
        "AWS::IAM::Role",
        "AWS::EC2::Instance",
    }
    for logical_id, resource in _all_resources(tmpl).items():
        rtype = resource.get("Type", "")
        if rtype not in taggable_types:
            continue
        props = resource.get("Properties", {})
        tags = props.get("Tags", [])
        tag_keys = {t.get("Key") for t in tags if isinstance(t, dict)}
        assert "ember:deployment" in tag_keys, (
            f"Resource {logical_id} ({rtype}) missing ember:deployment tag"
        )
        assert "ember:managed-by" in tag_keys, (
            f"Resource {logical_id} ({rtype}) missing ember:managed-by tag"
        )


# ---------------------------------------------------------------------------
# template.yaml — Parameters and outputs (no secrets)
# ---------------------------------------------------------------------------


def test_no_secret_in_parameter_names() -> None:
    tmpl = _load(_TEMPLATE)
    for name in tmpl.get("Parameters", {}):
        lower = name.lower()
        assert "token" not in lower, f"Parameter name contains 'token': {name}"
        assert "secret" not in lower, f"Parameter name contains 'secret': {name}"
        assert "key" not in lower, f"Parameter name contains 'key': {name}"


def test_no_secret_in_output_names() -> None:
    tmpl = _load(_TEMPLATE)
    for name in tmpl.get("Outputs", {}):
        lower = name.lower()
        assert "token" not in lower, f"Output name contains 'token': {name}"
        assert "secret" not in lower, f"Output name contains 'secret': {name}"
        assert "key" not in lower, f"Output name contains 'key': {name}"


def test_no_userdata_parameter() -> None:
    tmpl = _load(_TEMPLATE)
    params = tmpl.get("Parameters", {})
    assert "UserData" not in params, "template.yaml must not have a UserData parameter"


def test_required_parameters_present() -> None:
    tmpl = _load(_TEMPLATE)
    params = tmpl.get("Parameters", {})
    required = {
        "DeploymentName",
        "InstanceType",
        "Capacity",
        "ImageId",
        "SubnetId",
        "VpcId",
        "CacheBucket",
        "ModelPrefix",
        "TailscaleTag",
    }
    for p in required:
        assert p in params, f"Required parameter {p!r} missing from template.yaml"


def test_image_id_parameter_type() -> None:
    tmpl = _load(_TEMPLATE)
    params = tmpl.get("Parameters", {})
    assert params.get("ImageId", {}).get("Type") == "AWS::EC2::Image::Id", (
        "ImageId parameter must have Type: AWS::EC2::Image::Id"
    )


def test_required_outputs_present() -> None:
    tmpl = _load(_TEMPLATE)
    outputs = tmpl.get("Outputs", {})
    assert "InstanceId" in outputs, "Output InstanceId missing"
    assert "RoleArn" in outputs, "Output RoleArn missing"


def test_userdata_placeholder_present() -> None:
    """template.yaml must contain the __EMBER_USER_DATA__ placeholder."""
    raw = _TEMPLATE.read_text()
    assert "__EMBER_USER_DATA__" in raw, (
        "template.yaml must contain the __EMBER_USER_DATA__ placeholder"
    )


# ---------------------------------------------------------------------------
# cache-template.yaml
# ---------------------------------------------------------------------------


def test_cache_template_exists() -> None:
    assert _CACHE_TEMPLATE.exists(), (
        f"cache-template.yaml not found at {_CACHE_TEMPLATE}"
    )


def test_cache_bucket_deletion_policy_retain() -> None:
    tmpl = _load(_CACHE_TEMPLATE)
    bucket_id = next(
        (
            lid
            for lid, r in _all_resources(tmpl).items()
            if r.get("Type") == "AWS::S3::Bucket"
        ),
        None,
    )
    assert bucket_id is not None, "No AWS::S3::Bucket resource in cache-template.yaml"
    resource = _resource(tmpl, bucket_id)
    assert resource.get("DeletionPolicy") == "Retain", (
        "Cache bucket must have DeletionPolicy: Retain"
    )
    assert resource.get("UpdateReplacePolicy") == "Retain", (
        "Cache bucket must have UpdateReplacePolicy: Retain"
    )


def test_cache_bucket_public_access_block() -> None:
    tmpl = _load(_CACHE_TEMPLATE)
    bucket_id = next(
        lid
        for lid, r in _all_resources(tmpl).items()
        if r.get("Type") == "AWS::S3::Bucket"
    )
    props = _props(tmpl, bucket_id)
    pab = props.get("PublicAccessBlockConfiguration", {})
    assert pab.get("BlockPublicAcls") is True
    assert pab.get("BlockPublicPolicy") is True
    assert pab.get("IgnorePublicAcls") is True
    assert pab.get("RestrictPublicBuckets") is True


def test_cache_bucket_sse_s3() -> None:
    tmpl = _load(_CACHE_TEMPLATE)
    bucket_id = next(
        lid
        for lid, r in _all_resources(tmpl).items()
        if r.get("Type") == "AWS::S3::Bucket"
    )
    props = _props(tmpl, bucket_id)
    enc = props.get("BucketEncryption", {})
    rules = enc.get("ServerSideEncryptionConfiguration", [])
    assert any(
        r.get("ServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256"
        for r in rules
    ), "Cache bucket must use SSE-S3 (AES256)"


def test_cache_bucket_owner_enforced() -> None:
    tmpl = _load(_CACHE_TEMPLATE)
    bucket_id = next(
        lid
        for lid, r in _all_resources(tmpl).items()
        if r.get("Type") == "AWS::S3::Bucket"
    )
    props = _props(tmpl, bucket_id)
    ownership = props.get("OwnershipControls", {})
    rules = ownership.get("Rules", [])
    assert any(r.get("ObjectOwnership") == "BucketOwnerEnforced" for r in rules), (
        "Cache bucket must have BucketOwnerEnforced ownership"
    )


def test_cache_bucket_tls_deny_policy() -> None:
    """Cache stack must have a bucket policy denying non-TLS access."""
    tmpl = _load(_CACHE_TEMPLATE)
    policy_id = next(
        (
            lid
            for lid, r in _all_resources(tmpl).items()
            if r.get("Type") == "AWS::S3::BucketPolicy"
        ),
        None,
    )
    assert policy_id is not None, (
        "cache-template.yaml must have an AWS::S3::BucketPolicy resource"
    )
    props = _props(tmpl, policy_id)
    doc = props.get("PolicyDocument", {})
    stmts = doc.get("Statement", [])
    # Find a Deny statement with aws:SecureTransport condition
    deny_stmts = [s for s in stmts if s.get("Effect") == "Deny"]
    assert deny_stmts, "Bucket policy must have at least one Deny statement"
    has_tls_condition = any(
        "SecureTransport" in " ".join(_all_strings(s.get("Condition", {})))
        for s in deny_stmts
    )
    assert has_tls_condition, (
        "Bucket policy Deny statement must reference aws:SecureTransport"
    )


def test_cache_template_output_bucket_name() -> None:
    tmpl = _load(_CACHE_TEMPLATE)
    outputs = tmpl.get("Outputs", {})
    assert "BucketName" in outputs, "cache-template.yaml must output BucketName"


def test_template_strings_are_ascii() -> None:
    """Every template string value must be ASCII.

    EC2 rejects non-ASCII in properties like ``GroupDescription`` ("Character
    sets beyond ASCII are not supported"), which fails a live CreateStack.
    """
    tmpl = _load(_TEMPLATE)
    offenders = [s for s in _all_strings(tmpl) if not s.isascii()]
    assert offenders == []
