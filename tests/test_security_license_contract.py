"""Automated security, dependency floor, and third-party license contract tests for KlangpultLight."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_license_file_and_spdx_metadata() -> None:
    """Verify LICENSE exists, asserts Freeware/Proprietary terms, and matches pyproject.toml."""
    lic_file = ROOT / "LICENSE"
    assert lic_file.is_file(), "LICENSE file must exist in project root"
    content = lic_file.read_text(encoding="utf-8")

    assert "Klangpult light" in content
    assert "Freeware License Agreement" in content
    assert "Lukas Geiger" in content
    assert "All rights reserved" in content

    pyproject_file = ROOT / "pyproject.toml"
    assert pyproject_file.is_file()
    pyproject_text = pyproject_file.read_text(encoding="utf-8")
    assert 'license = {text = "Freeware / Proprietary"}' in pyproject_text


def test_third_party_licenses_complete_and_accurate() -> None:
    """Verify THIRD_PARTY_LICENSES.txt and .md comprehensively cover runtime, build, and test packages."""
    txt_file = ROOT / "THIRD_PARTY_LICENSES.txt"
    assert txt_file.is_file(), "THIRD_PARTY_LICENSES.txt must exist"
    txt_content = txt_file.read_text(encoding="utf-8")

    md_file = ROOT / "THIRD_PARTY_LICENSES.md"
    assert md_file.is_file(), "THIRD_PARTY_LICENSES.md must exist"
    md_content = md_file.read_text(encoding="utf-8")

    required_packages = [
        ("PySide6", "LGPL-3.0"),
        ("sounddevice", "MIT"),
        ("numpy", "BSD-3-Clause"),
        ("soundfile", "BSD-3-Clause"),
        ("opencv-python", "Apache-2.0"),
        ("mss", "MIT"),
        ("websockets", "BSD-3-Clause"),
        ("jsonschema", "MIT"),
        ("pytest", "MIT"),
        ("ruff", "MIT"),
        ("setuptools", "MIT"),
        ("PyInstaller", "GPL-2.0"),
        ("FFmpeg", "LGPL-2.1"),
    ]

    for pkg, spdx_prefix in required_packages:
        assert pkg in txt_content, f"Package {pkg} missing from THIRD_PARTY_LICENSES.txt"
        assert spdx_prefix in txt_content, f"SPDX prefix {spdx_prefix} for {pkg} missing from THIRD_PARTY_LICENSES.txt"
        assert pkg in md_content, f"Package {pkg} missing from THIRD_PARTY_LICENSES.md"

    # Schema markers in text SBOM
    assert "License:" in txt_content
    assert "URL:" in txt_content
    assert "SPDX:" in txt_content
    assert "Notice:" in txt_content

    # Invariants and compliance in markdown notice
    assert "INV-LOCAL-01" in md_content
    assert "LGPL-3.0" in md_content
    assert "Dynamic linking" in md_content or "dynamically" in md_content


def test_dependency_vulnerability_floors() -> None:
    """Verify requirements.txt and pyproject.toml enforce patched dependency floors against CVEs."""
    req_file = ROOT / "requirements.txt"
    assert req_file.is_file(), "requirements.txt must exist"
    req_text = req_file.read_text(encoding="utf-8")

    assert re.search(r"^PySide6\s*>=\s*6\.6", req_text, re.MULTILINE)
    assert re.search(r"^sounddevice\s*>=\s*0\.4\.6", req_text, re.MULTILINE)
    assert re.search(r"^numpy\s*>=\s*1\.26", req_text, re.MULTILINE)
    assert re.search(r"^soundfile\s*>=\s*0\.12", req_text, re.MULTILINE)
    assert re.search(r"^opencv-python\s*>=\s*4\.9", req_text, re.MULTILINE)
    assert re.search(r"^mss\s*>=\s*9\.0", req_text, re.MULTILINE)
    assert re.search(r"^websockets\s*>=\s*12\.0", req_text, re.MULTILINE)
    assert re.search(r"^jsonschema\s*>=\s*4\.21", req_text, re.MULTILINE)
    assert re.search(r"^pytest\s*>=\s*8\.0", req_text, re.MULTILINE)
    assert re.search(r"^ruff\s*>=\s*0\.9\.0", req_text, re.MULTILINE)

    pyproject_file = ROOT / "pyproject.toml"
    assert pyproject_file.is_file()
    pyproject_text = pyproject_file.read_text(encoding="utf-8")

    assert "dependencies = [" in pyproject_text
    assert "PySide6>=6.6" in pyproject_text
    assert "numpy>=1.26" in pyproject_text
    assert "[project.optional-dependencies]" in pyproject_text
    assert "pytest>=8.0" in pyproject_text
    assert "ruff>=0.9.0" in pyproject_text
    assert "support@lukasgeiger.com" in pyproject_text


def test_gitignore_security_and_multi_host_hardening() -> None:
    """Verify .gitignore blocks private secrets, certificates, and multi-host conflict files."""
    gitignore_file = ROOT / ".gitignore"
    assert gitignore_file.is_file(), ".gitignore must exist"
    content = gitignore_file.read_text(encoding="utf-8")

    # Secrets and certificate protection
    for pat in [".env", "*.pfx", "*.p12", "*.pem", "*.key", "credentials.json", "secrets.*", "keyring/"]:
        assert pat in content, f"Secret pattern {pat} missing in .gitignore"

    # Multi-host sync hardening
    for host_pat in ["*-WORKSTATION*", "*-ASUS*", "*-LAPTOP*", "*.sync-conflict-*", "*.sync-temp-*", "*.conflict"]:
        assert host_pat in content, f"Sync conflict pattern {host_pat} missing in .gitignore"

    # Multi-agent lock system fail-closed patterns
    for lock_pat in ["LOCK", "LOCK.*", "LOCK*.txt"]:
        assert lock_pat in content, f"Lock pattern {lock_pat} missing in .gitignore"


def test_no_hardcoded_user_paths_in_python_code() -> None:
    """Verify no hardcoded personal user profile paths (e.g. C:\\Users\\lukas) exist in active Python source."""
    disallowed_regex = re.compile(r"""(?i)C:[/\\]Users[/\\](?:lukas|admin|administrator)[/\\]""", re.VERBOSE)

    python_files = [
        p for p in ROOT.rglob("*.py")
        if not any(part in str(p) for part in [".git", ".pytest_cache", ".ruff_cache", "workspace", "_archive", ".venv", "venv"])
    ]
    assert len(python_files) >= 10, "Expected at least 10 Python files to scan"

    violating_lines = []
    for py_file in python_files:
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if disallowed_regex.search(line):
                violating_lines.append(f"{py_file.name}:{idx}: {line.strip()}")

    assert not violating_lines, "Found hardcoded user paths in Python code:\n" + "\n".join(violating_lines)


def test_no_hardcoded_secrets_in_production_source() -> None:
    """Verify no leaked tokens, AWS credentials, private keys, or cleartext secrets in production source files."""
    secret_patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"),
        re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
        re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
    ]

    prod_files = [
        p for p in (ROOT / "Recorder").rglob("*.py")
        if "tests" not in str(p) and not any(part in str(p) for part in [".pytest_cache", "__pycache__"])
    ] + [
        p for p in (ROOT / "shared").rglob("*.py")
        if not any(part in str(p) for part in [".pytest_cache", "__pycache__"])
    ]
    assert len(prod_files) >= 5, "Expected at least 5 production Python files"

    violations = []
    for f in prod_files:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for idx, line in enumerate(text.splitlines(), 1):
            for pat in secret_patterns:
                if pat.search(line):
                    violations.append(f"{f.name}:{idx}: matches secret regex {pat.pattern}")

    assert not violations, "Found secret patterns in production source files:\n" + "\n".join(violations)


def test_zero_unauthorized_telemetry_or_tracking() -> None:
    """Verify production application code does not import or invoke unauthorized telemetry or tracking services."""
    disallowed_endpoints = [
        "google-analytics.com",
        "segment.io",
        "mixpanel.com",
        "sentry.io",
        "amplitude.com",
    ]

    prod_files = [
        p for p in (ROOT / "Recorder").rglob("*.py")
        if "tests" not in str(p) and not any(part in str(p) for part in [".pytest_cache", "__pycache__"])
    ]
    assert len(prod_files) >= 5

    violations = []
    for pf in prod_files:
        text = pf.read_text(encoding="utf-8", errors="ignore")
        for endpoint in disallowed_endpoints:
            if endpoint in text.lower():
                violations.append(f"{pf.name}: {endpoint}")

    assert not violations, f"Found unauthorized telemetry or tracking endpoints: {violations}"


def test_subprocess_execution_safety() -> None:
    """Verify Recorder source does not invoke unquoted or unsafe shell=True executions."""
    prod_files = [
        p for p in (ROOT / "Recorder").rglob("*.py")
        if "tests" not in str(p) and not any(part in str(p) for part in [".pytest_cache", "__pycache__"])
    ]
    assert len(prod_files) >= 5

    unsafe_shell_calls = []
    for pf in prod_files:
        content = pf.read_text(encoding="utf-8", errors="ignore")
        for idx, line in enumerate(content.splitlines(), 1):
            if "subprocess." in line and "shell=True" in line:
                unsafe_shell_calls.append(f"{pf.name}:{idx}: {line.strip()}")

    assert not unsafe_shell_calls, "Unsafe shell=True subprocess execution found:\n" + "\n".join(unsafe_shell_calls)


def test_security_policy_sla_and_contacts() -> None:
    """Verify SECURITY.md maintains strict SLA, non-elevation guarantees, and designated response channels."""
    sec_file = ROOT / "SECURITY.md"
    assert sec_file.is_file(), "SECURITY.md must exist"
    content = sec_file.read_text(encoding="utf-8")

    assert "security@ellmos.ai" in content
    assert "security@open-bricks.org" in content
    assert "support@lukasgeiger.com" in content
    assert "48" in content, "48h initial acknowledgment SLA missing"
    assert "5" in content, "5-day triage commitment missing"
    assert "Local-First" in content or "local-first" in content
    assert "Unprivileged Execution" in content or "unprivilegierte" in content or "User Mode" in content


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main(["-v", __file__]))
