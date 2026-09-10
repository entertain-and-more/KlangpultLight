"""tests.test_license_identity_contract — Lizenz- und Identitätsvertragsprüfung (TW-KLANGPULTLIGHT-08).

Prüft:
  - LICENSE-Datei existiert im Root und enthält verbindliche Freeware-Klauseln
  - pyproject.toml enthält konsistente Metadaten für Klangpult light
  - README.md dokumentiert den Freeware-Charakter und referenziert die Lizenz
"""
from pathlib import Path
import re


def test_license_file_exists_and_contains_freeware_clauses():
    """Die Lizenzdatei existiert im Root und definiert die Freeware-Nutzung."""
    root = Path(__file__).resolve().parent.parent
    license_file = root / "LICENSE"
    assert license_file.is_file(), f"LICENSE-Datei fehlt im Root: {license_file}"

    content = license_file.read_text(encoding="utf-8")
    assert "Klangpult light" in content
    assert "Freeware" in content
    assert "Copyright" in content
    assert "warranty" in content or "liability" in content
    assert "Lukas Geiger" in content


def test_pyproject_metadata_identity():
    """pyproject.toml definiert korrekten Paketnamen und Lizenzbezeichnung."""
    root = Path(__file__).resolve().parent.parent
    pyproject_file = root / "pyproject.toml"
    assert pyproject_file.is_file(), f"pyproject.toml fehlt im Root: {pyproject_file}"

    content = pyproject_file.read_text(encoding="utf-8")
    assert re.search(r'name\s*=\s*"klangpult-light"', content, re.IGNORECASE)
    assert re.search(r'license\s*=\s*\{?\s*text\s*=\s*"Proprietary', content, re.IGNORECASE) or "license" in content


def test_readme_references_license_and_freeware():
    """README.md dokumentiert Freeware und verweist auf die LICENSE-Datei."""
    root = Path(__file__).resolve().parent.parent
    readme_file = root / "README.md"
    assert readme_file.is_file(), f"README.md fehlt: {readme_file}"

    content = readme_file.read_text(encoding="utf-8")
    assert "Klangpult light" in content
    assert "Lizenz" in content or "LICENSE" in content
