"""UserData: render cloud-init YAML and inline it into the CloudFormation template.

``UserData.render()`` substitutes deployment-specific values into the
``deployment/aws/instance/cloud-init.yaml`` template and returns the rendered
cloud-init string.  ``UserData.template_body()`` replaces the
``__EMBER_USER_DATA__`` placeholder in ``template.yaml`` with the rendered
cloud-init as a YAML block scalar and returns the full template body that
``stack.py`` sends as ``TemplateBody``.

Size invariants (asserted by tests):
- Rendered user data ≤ 16,384 bytes (EC2 user-data limit).
- Full template body ≤ 51,200 bytes (CloudFormation inline ``TemplateBody`` limit).
"""

from __future__ import annotations

from pathlib import Path

from .instance_config import InstanceConfig
from .names import DeploymentName

_INSTANCE_DIR = Path(__file__).parent.parent / "instance"
_TEMPLATE_PATH = Path(__file__).parent.parent / "template.yaml"
_PLACEHOLDER = "__EMBER_USER_DATA__"

_EC2_USER_DATA_LIMIT = 16_384
_CFN_TEMPLATE_BODY_LIMIT = 51_200


class UserData:
    """Render cloud-init user data and inline it into the CloudFormation template.

    All methods are static; this class is a namespace for the two rendering
    operations.
    """

    @staticmethod
    def render(
        names: DeploymentName,
        region: str,
        config: InstanceConfig,
        tailscale_tag: str,
    ) -> str:
        """Render the cloud-init YAML with deployment-specific values substituted.

        Reads ``deployment/aws/instance/cloud-init.yaml`` and replaces every
        ``{{PLACEHOLDER}}`` with the corresponding value.  Never substitutes
        secrets (the server token is read from SSM at boot time by
        ``converge.sh``).

        Parameters
        ----------
        names : DeploymentName
            Validated deployment name with derived SSM paths.
        region : str
            AWS region (e.g. ``"us-east-1"``).
        config : InstanceConfig
            The desired instance configuration (version, S3 URI, cap, idle).
        tailscale_tag : str
            Tailscale ACL tag (e.g. ``"tag:ember"``).

        Returns
        -------
        str
            The rendered cloud-init YAML string.

        Raises
        ------
        ValueError
            If the rendered user data exceeds the EC2 16,384-byte limit.
        """
        template = (_INSTANCE_DIR / "cloud-init.yaml").read_text()
        rendered = (
            template.replace("{{DEPLOYMENT_NAME}}", names.name)
            .replace("{{REGION}}", region)
            .replace("{{TAILSCALE_TAG}}", tailscale_tag)
            .replace("{{EMBER_VERSION}}", config.ember_version)
            .replace("{{MODEL_S3_URI}}", config.model_s3_uri)
            .replace("{{MAX_REQUEST_LENGTH}}", str(config.max_request_length))
            .replace("{{CONFIG_PARAM}}", names.config_param)
            .replace("{{JOIN_KEY_PARAM}}", names.join_key_param)
            .replace("{{TOKEN_PARAM}}", names.token_param)
        )
        size = len(rendered.encode("utf-8"))
        if size > _EC2_USER_DATA_LIMIT:
            raise ValueError(
                f"Rendered user data is {size} bytes, exceeds EC2 limit of"
                f" {_EC2_USER_DATA_LIMIT} bytes"
            )
        return rendered

    @staticmethod
    def template_body(rendered: str) -> str:
        """Replace the ``__EMBER_USER_DATA__`` placeholder in ``template.yaml``.

        Inlines the rendered cloud-init as a YAML block scalar so the full
        template body can be sent as ``TemplateBody`` to CloudFormation.

        Parameters
        ----------
        rendered : str
            The rendered cloud-init YAML string from ``render()``.

        Returns
        -------
        str
            The full CloudFormation template body with user data inlined.

        Raises
        ------
        ValueError
            If the resulting template body exceeds the CloudFormation 51,200-byte
            inline ``TemplateBody`` limit.
        """
        raw = _TEMPLATE_PATH.read_text()
        indented = "\n".join(
            "          " + line if line else "" for line in rendered.splitlines()
        )
        body = raw.replace(
            f'Fn::Base64: "{_PLACEHOLDER}"',
            f"Fn::Base64: |\n{indented}",
        )
        size = len(body.encode("utf-8"))
        if size > _CFN_TEMPLATE_BODY_LIMIT:
            raise ValueError(
                f"Template body is {size} bytes, exceeds CloudFormation limit of"
                f" {_CFN_TEMPLATE_BODY_LIMIT} bytes"
            )
        return body
