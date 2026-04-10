"""
Compliance Engine
─────────────────
Evaluates regulatory documents for completeness and identifies
potential compliance risks with severity classification.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from backend.config import REQUIRED_SECTIONS

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Severity constants
# ─────────────────────────────────────────────────────────────────────────────

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"


# ─────────────────────────────────────────────────────────────────────────────
# ComplianceEngine
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceEngine:
    """Run a battery of compliance checks against detected document sections."""

    # Dosage units that are considered unambiguous
    _CLEAR_DOSE_UNITS = re.compile(
        r"\b(\d+\s*(?:mg|mcg|µg|g|ml|mL|IU|units?|tablets?|capsules?)"
        r"(?:\s*/\s*(?:day|kg|dose|hour|h))?)\b",
        re.IGNORECASE,
    )

    # Words that signal vagueness in dosage instructions
    _VAGUE_DOSE_WORDS = re.compile(
        r"\b(appropriate|suitable|as\s+directed|as\s+needed|titrate\s+as\s+appropriate"
        r"|at\s+the\s+discretion|variable)\b",
        re.IGNORECASE,
    )

    # Minimum word threshold for a "sufficient" warnings section
    _MIN_WARNINGS_WORDS = 50

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_checks(self, sections: dict[str, Any]) -> list[dict[str, str]]:
        """
        Execute all compliance checks and return a list of findings.

        Each finding is a dict::

            {
                "type":     "<check name>",
                "severity": "HIGH | MEDIUM | LOW",
                "message":  "<human-readable description>",
            }
        """
        findings: list[dict[str, str]] = []

        findings.extend(self._check_missing_sections(sections))
        findings.extend(self._check_warnings_sufficiency(sections))
        findings.extend(self._check_dosage_ambiguity(sections))
        findings.extend(self._check_contraindication_quality(sections))
        findings.extend(self._check_adverse_reactions_detail(sections))
        findings.extend(self._check_storage_specificity(sections))

        logger.info("Compliance check complete — %d findings", len(findings))
        return findings

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_missing_sections(
        self, sections: dict[str, Any]
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        for section_name in REQUIRED_SECTIONS:
            info = sections.get(section_name, {})
            if not info.get("found"):
                findings.append(
                    {
                        "type": "Missing Section",
                        "severity": HIGH,
                        "message": (
                            f"Required section '{section_name.title()}' is absent "
                            "from the document. This is a mandatory regulatory requirement."
                        ),
                    }
                )
        return findings

    # ------------------------------------------------------------------

    def _check_warnings_sufficiency(
        self, sections: dict[str, Any]
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        warnings_info = sections.get("warnings", {})
        if not warnings_info.get("found"):
            return findings  # already flagged as missing

        content = warnings_info.get("content", "")
        word_count = len(content.split())
        if word_count < self._MIN_WARNINGS_WORDS:
            findings.append(
                {
                    "type": "Insufficient Warnings",
                    "severity": HIGH,
                    "message": (
                        f"Warnings section contains only {word_count} words "
                        f"(minimum recommended: {self._MIN_WARNINGS_WORDS}). "
                        "Expand to include Black Box Warnings, serious adverse events, "
                        "and population-specific precautions."
                    ),
                }
            )
        return findings

    # ------------------------------------------------------------------

    def _check_dosage_ambiguity(
        self, sections: dict[str, Any]
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        dosage_info = sections.get("dosage", {})
        if not dosage_info.get("found"):
            return findings

        content = dosage_info.get("content", "")

        # Check for vague language
        vague_matches = self._VAGUE_DOSE_WORDS.findall(content)
        if vague_matches:
            unique_vague = list({m.lower() for m in vague_matches})
            findings.append(
                {
                    "type": "Ambiguous Dosage Units",
                    "severity": MEDIUM,
                    "message": (
                        f"Dosage section contains vague language: "
                        f"{', '.join(unique_vague)}. "
                        "Replace with precise numeric doses and units (e.g., '10 mg/day')."
                    ),
                }
            )

        # Check whether any clear numeric units are present
        if not self._CLEAR_DOSE_UNITS.search(content):
            findings.append(
                {
                    "type": "Missing Dosage Units",
                    "severity": HIGH,
                    "message": (
                        "Dosage section does not specify clear numeric doses with units "
                        "(e.g., mg, mcg, mL). Explicit quantification is required by "
                        "regulatory standards."
                    ),
                }
            )
        return findings

    # ------------------------------------------------------------------

    def _check_contraindication_quality(
        self, sections: dict[str, Any]
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        ci_info = sections.get("contraindications", {})
        if not ci_info.get("found"):
            return findings

        content = ci_info.get("content", "")
        word_count = len(content.split())

        if word_count < 20:
            findings.append(
                {
                    "type": "Sparse Contraindications",
                    "severity": MEDIUM,
                    "message": (
                        f"Contraindications section is very brief ({word_count} words). "
                        "Ensure all patient populations, drug interactions, and medical "
                        "conditions are explicitly listed."
                    ),
                }
            )
        return findings

    # ------------------------------------------------------------------

    def _check_adverse_reactions_detail(
        self, sections: dict[str, Any]
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        ar_info = sections.get("adverse reactions", {})
        if not ar_info.get("found"):
            return findings

        content = ar_info.get("content", "")
        # Look for incidence data (percentages or fractions)
        has_incidence = re.search(r"\d+\.?\d*\s*%", content)
        if not has_incidence:
            findings.append(
                {
                    "type": "Missing Incidence Data",
                    "severity": LOW,
                    "message": (
                        "Adverse Reactions section does not appear to contain "
                        "incidence rates (%). Regulatory guidelines recommend "
                        "including frequency data for each reaction."
                    ),
                }
            )
        return findings

    # ------------------------------------------------------------------

    def _check_storage_specificity(
        self, sections: dict[str, Any]
    ) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        storage_info = sections.get("storage", {})
        if not storage_info.get("found"):
            return findings

        content = storage_info.get("content", "")
        # Expect temperature mention
        has_temp = re.search(
            r"\b(\d+\s*°?\s*[CF]|room\s+temperature|refrigerat|frozen?|cool)\b",
            content,
            re.IGNORECASE,
        )
        if not has_temp:
            findings.append(
                {
                    "type": "Unspecified Storage Conditions",
                    "severity": MEDIUM,
                    "message": (
                        "Storage section does not specify temperature conditions. "
                        "Include explicit temperature range (e.g., '15–30 °C / 59–86 °F') "
                        "as required by pharmacopeial standards."
                    ),
                }
            )
        return findings