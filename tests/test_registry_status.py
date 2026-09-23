import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_ROOT_REL = Path(__file__).resolve().parents[3]
SOFTWARE_ROOT_DEFAULT = Path.home() / "OneDrive" / ".TOPICS" / ".SOFTWARE"
PROJECT_PATH = "PRODUCTION/DEV_KlangpultLight"


def _get_software_root() -> Path | None:
    if (SOFTWARE_ROOT_REL / "releases.json").is_file():
        return SOFTWARE_ROOT_REL
    if (SOFTWARE_ROOT_DEFAULT / "releases.json").is_file():
        return SOFTWARE_ROOT_DEFAULT
    return None


def test_root_registry_matches_project_status_and_todo():
    import pytest

    software_root = _get_software_root()
    if not software_root:
        pytest.skip("Wurzel-Registrierungsdatei releases.json außerhalb der Testumgebung nicht auffindbar")

    releases = json.loads((software_root / "releases.json").read_text(encoding="utf-8"))
    projects = releases["projects"]
    entry = next((project for project in projects if project.get("path") == PROJECT_PATH), None)
    assert entry is not None, f"Registry-Eintrag für {PROJECT_PATH} in releases.json nicht gefunden"

    assert entry["name"] == "KlangpultLight"
    assert entry["lifecycle"] == "DEV"
    assert entry["visibility"] == "private"
    assert entry["status"] == "development"

    project_status = (software_root / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert (
        "| PRODUCTION | DEV | KlangpultLight | `PRODUCTION/DEV_KlangpultLight` |"
    ) in project_status

    todo = (PROJECT_ROOT / "TODO.md").read_text(encoding="utf-8")
    assert (
        "- [x] `Klangpult light` als `.SOFTWARE`-Projekt registrieren "
        "(releases.json / PROJECT_STATUS.md)"
    ) in todo
