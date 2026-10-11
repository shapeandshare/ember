"""ComplianceFramework: catalogues a recipe's compliance references may cite."""

from __future__ import annotations

from enum import StrEnum


class ComplianceFramework(StrEnum):
    """External catalogues a recipe's compliance references may cite."""

    owasp_llm_top10 = "owasp_llm_top10"
    mitre_atlas = "mitre_atlas"
    nist_ai_rmf = "nist_ai_rmf"
    eu_ai_act = "eu_ai_act"
    iso_42001 = "iso_42001"
    enkrypt = "enkrypt"
