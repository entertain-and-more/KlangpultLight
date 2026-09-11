#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Metadata, Manifest, CI, and Documentation Parity Contract Tests for KlangpultLight.

Run via:
    python -m pytest tests/test_metadata.py
    python tests/test_metadata.py
"""

import unittest
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python 3.10
    except ImportError:
        tomllib = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestKlangpultLightMetadata(unittest.TestCase):
    """Parity and integrity contract test suite for KlangpultLight."""

    def test_pyproject_toml_integrity(self):
        """Verify pyproject.toml configuration and metadata structure."""
        pyproject_file = PROJECT_ROOT / "pyproject.toml"
        self.assertTrue(pyproject_file.is_file(), "pyproject.toml must exist")
        text = pyproject_file.read_text(encoding="utf-8")
        self.assertIn('name = "klangpult-light"', text)
        self.assertIn('requires-python = ">=3.10"', text)
        self.assertIn("Lukas Geiger", text)
        self.assertIn("https://github.com/entertain-and-more/KlangpultLight", text)
        self.assertIn("tool.pytest.ini_options", text)

        if tomllib is not None:
            data = tomllib.loads(text)
            project = data.get("project", {})
            self.assertEqual(project.get("name"), "klangpult-light")
            self.assertEqual(project.get("version"), "0.1.0")
            urls = project.get("urls", {})
            self.assertIn("Homepage", urls)
            self.assertIn("Repository", urls)
            self.assertIn("Parent Organization", urls)
            self.assertIn("Ecosystem", urls)
            self.assertIn("Umbrella", urls)
            self.assertIn("Security", urls)
            self.assertIn("Changelog", urls)
            classifiers = project.get("classifiers", [])
            self.assertTrue(any("OS Independent" in c for c in classifiers))

    def test_core_documents_exist_and_non_empty(self):
        """Verify all core governance, marketing, and documentation files are present."""
        required = [
            "README.md",
            "README_de.md",
            "SECURITY.md",
            "LICENSE",
            "CHANGELOG.md",
            "KONZEPT.md",
            "TODO.md",
            "llms.txt",
            "MARKETING-LOG.txt",
            ".gitignore",
        ]
        for filename in required:
            filepath = PROJECT_ROOT / filename
            self.assertTrue(filepath.is_file(), f"{filename} must exist")
            self.assertGreater(
                filepath.stat().st_size, 50, f"{filename} must not be empty"
            )

    def test_security_policy_bilingual_integrity(self):
        """Verify SECURITY.md contains English and German policies, SLAs, and invariants."""
        sec_file = PROJECT_ROOT / "SECURITY.md"
        self.assertTrue(sec_file.is_file(), "SECURITY.md must exist")
        text = sec_file.read_text(encoding="utf-8")
        self.assertIn("# Security Policy / Sicherheitsrichtlinie", text)
        self.assertIn("## English", text)
        self.assertIn("## Deutsch", text)
        self.assertIn("security@ellmos.ai", text)
        self.assertIn("security@open-bricks.org", text)
        self.assertIn("support@lukasgeiger.com", text)
        self.assertIn("advisories/new", text)
        self.assertIn("Zero-Egress", text)
        self.assertIn("Local-First", text)
        self.assertIn("Unterstützte Versionen", text)
        self.assertIn("Supported Versions", text)
        self.assertIn("48 hours", text)
        self.assertIn("48 Stunden", text)
        self.assertIn("5 business days", text)
        self.assertIn("5 Werktagen", text)
        self.assertIn("127.0.0.1:8767", text)
        self.assertIn("127.0.0.1:8769", text)
        self.assertIn("127.0.0.1:8770", text)

    def test_ci_workflow_integrity(self):
        """Verify GitHub Actions CI workflow configuration, concurrency, and bytecode gate."""
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_file.is_file(), "CI workflow file must exist")
        text = ci_file.read_text(encoding="utf-8")
        self.assertIn("actions/checkout@v4", text)
        self.assertIn("actions/setup-python@v5", text)
        self.assertIn("cache: 'pip'", text)
        self.assertIn("ubuntu-latest", text)
        self.assertIn("windows-latest", text)
        self.assertIn("macos-latest", text)
        self.assertIn("cancel-in-progress: true", text)
        self.assertIn("python -m compileall -q .", text)
        self.assertIn("ruff check .", text)
        self.assertIn("test_metadata.py", text)

    def test_gitignore_hygiene(self):
        """Verify .gitignore hardens against sync conflicts, agent locks, and caches."""
        gitignore_file = PROJECT_ROOT / ".gitignore"
        self.assertTrue(gitignore_file.is_file(), ".gitignore must exist")
        text = gitignore_file.read_text(encoding="utf-8")
        self.assertIn("*-conflict-*", text)
        self.assertIn("*.sync-temp-*", text)
        self.assertIn("*.sync-conflict-*", text)
        self.assertIn("LOCK.*", text)
        self.assertIn("*.lock", text)
        self.assertIn(".pytest_cache/", text)
        self.assertIn(".ruff_cache/", text)
        self.assertIn(".coverage", text)

    def test_llms_txt_integrity(self):
        """Verify llms.txt context index currency, timestamp, and ecosystem markers."""
        llms_file = PROJECT_ROOT / "llms.txt"
        self.assertTrue(llms_file.is_file(), "llms.txt must exist")
        text = llms_file.read_text(encoding="utf-8")
        self.assertIn("entertain-and-more/KlangpultLight", text)
        self.assertIn("entertain-and-more", text)
        self.assertIn("open-bricks", text)
        self.assertIn("2026-09-09", text)
        self.assertIn("449", text)
        self.assertIn("MARKETING-LOG.txt", text)
        self.assertIn("SECURITY.md", text)
        self.assertIn("ci.yml", text)

    def test_bilingual_readme_parity_and_diagrams(self):
        """Verify README.md and README_de.md badges, 14-point quick nav, and dual Mermaid diagrams."""
        readme_en = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        readme_de = (PROJECT_ROOT / "README_de.md").read_text(encoding="utf-8")

        for text, name in [(readme_en, "README.md"), (readme_de, "README_de.md")]:
            self.assertIn("entertain--and--more", text, f"{name} must have ecosystem badge")
            self.assertIn("open--bricks", text, f"{name} must have umbrella badge")
            self.assertIn("SECURITY.md", text, f"{name} must reference SECURITY.md")
            self.assertIn("llms.txt", text, f"{name} must reference llms.txt")
            self.assertIn("MARKETING-LOG.txt", text, f"{name} must reference MARKETING-LOG.txt")
            self.assertIn("actions/workflows/ci.yml", text, f"{name} must have CI badge")
            self.assertIn("450%20", text, f"{name} must have 450 tests badge")
            self.assertIn("RunAsInvoker", text, f"{name} must have security badge")
            self.assertTrue("5d%20triage" in text or "5d%20Triage" in text, f"{name} must have 5d triage badge")
            self.assertIn("graph TD", text, f"{name} must have architecture graph")
            self.assertIn("sequenceDiagram", text, f"{name} must have lifecycle sequence diagram")
            self.assertIn("autonumber", text, f"{name} must use autonumber in sequence diagram")

            # Verify 14-point quick navigation presence
            self.assertIn("1. [", text, f"{name} must have numbered quick nav item 1")
            self.assertIn("14. [", text, f"{name} must have numbered quick nav item 14")

            # Verify 10 Governance Invariants table
            self.assertIn("Governance", text, f"{name} must have Governance Invariants section")
            self.assertIn("Zero-Egress", text, f"{name} must have Zero-Egress invariant")
            self.assertIn("RunAsInvoker", text, f"{name} must have RunAsInvoker invariant")

    def test_sibling_ecosystem_matrix(self):
        """Verify sibling projects table across the entertain-and-more gaming/media line and open-bricks."""
        readme_en = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        readme_de = (PROJECT_ROOT / "README_de.md").read_text(encoding="utf-8")
        for text in [readme_en, readme_de]:
            for sibling in [
                "BattleStage",
                "ChainReaction",
                "StreetRacer",
                "RealmWars",
                "GhostTrain",
                "RescueMe",
                "HauntedHouse",
                "MafiaCastle",
                "CuteStrike",
                "BattleChess3D",
                "system-auditor",
                "automation-master",
                "ExplorerPro",
                "CleanMarkdown",
                "ellmos-voice-io",
                "WikiStub-Seed",
                "open-bricks",
            ]:
                self.assertIn(sibling, text, f"Sibling {sibling} must be listed in ecosystem matrix")

    def test_port_configuration_parity(self):
        """Verify default bridge and planer port configurations."""
        readme_en = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        readme_de = (PROJECT_ROOT / "README_de.md").read_text(encoding="utf-8")
        for text in [readme_en, readme_de]:
            self.assertIn("8767", text)
            self.assertIn("8769", text)
            self.assertIn("8770", text)

    def test_changelog_entry_present(self):
        """Verify CHANGELOG.md contains release entries."""
        changelog_file = PROJECT_ROOT / "CHANGELOG.md"
        self.assertTrue(changelog_file.is_file(), "CHANGELOG.md must exist")
        text = changelog_file.read_text(encoding="utf-8")
        self.assertIn("## [0.1.4] - 2026-09-11", text)
        self.assertIn("TW-KLANGPULTLIGHT-12", text)
        self.assertIn("## [0.1.2] - 2026-09-09", text)
        self.assertIn("Pfad B", text)
        self.assertIn("14-Punkte-Schnellnavigation", text)
        self.assertIn("10 Governance- & Laufzeit-Invarianten", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
