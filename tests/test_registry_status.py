import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_ROOT = Path(__file__).resolve().parents[3]
PROJECT_PATH = "ENTERTAINMENT/DEV_KlangpultLight"


def test_root_registry_matches_project_status_and_todo():
    import pytest
    rel_file = SOFTWARE_ROOT / "releases.json"
    if not rel_file.is_file():
        pytest.skip("Wurzel-Registrierungsdatei releases.json außerhalb der Standalone-Repo-Struktur nicht vorhanden")
    releases = json.loads(rel_file.read_text(encoding="utf-8"))
    projects = releases["projects"]
    entry = next(project for project in projects if project["path"] == PROJECT_PATH)

    assert entry["name"] == "KlangpultLight"
    assert entry["lifecycle"] == "DEV"
    assert entry["visibility"] == "private"
    assert entry["status"] == "development"
    assert entry["targets"] == []

    project_status = (SOFTWARE_ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert (
        "| ENTERTAINMENT | DEV | KlangpultLight | "
        "`ENTERTAINMENT/DEV_KlangpultLight` | ja |"
    ) in project_status

    todo = (PROJECT_ROOT / "TODO.md").read_text(encoding="utf-8")
    assert (
        "- [x] `Klangpult light` als `.SOFTWARE`-Projekt registrieren "
        "(releases.json / PROJECT_STATUS.md)"
    ) in todo
