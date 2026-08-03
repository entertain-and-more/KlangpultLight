"""
test_planer_a11y.py — Static A11y & ARIA compliance tests for Klangpult light – Planer.
"""
import os

PLANER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "planer"))


def test_planer_util_no_native_confirm_or_alert():
    """Prüft, dass util.js keine nativen window.confirm oder window.alert Pfade aufruft."""
    util_path = os.path.join(PLANER_DIR, "app", "util.js")
    assert os.path.exists(util_path), "util.js muss existieren"

    with open(util_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "window.confirm(" not in content, "util.js darf kein window.confirm() nutzen"
    assert "window.alert(" not in content, "util.js darf kein window.alert() nutzen"
    assert "role=\"dialog\"" in content or "role: \"dialog\"" in content, "util.js Modal muss role='dialog' besitzen"
    assert "aria-modal" in content, "util.js Modal muss aria-modal besitzen"


def test_planer_projekte_a11y_attributes():
    """Prüft, dass projekte.js Tastatursemantik (tabIndex, keydown) und ARIA-Attribute besitzt."""
    projekte_path = os.path.join(PLANER_DIR, "app", "projekte.js")
    assert os.path.exists(projekte_path), "projekte.js muss existieren"

    with open(projekte_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "tabIndex: 0" in content, "Listeneinträge in projekte.js müssen tabIndex=0 besitzen"
    assert "role: \"button\"" in content or "role=\"button\"" in content, "Listeneinträge in projekte.js müssen role='button' besitzen"
    assert "aria-selected" in content, "projekte.js muss aria-selected zur Zustandssignalisierung nutzen"
    assert "aria-label" in content, "Aktionsbuttons in projekte.js müssen barrierefreie Namen (aria-label) besitzen"
    assert "Enter" in content and "Space" in content, "Listeneinträge müssen auf Enter/Space Tastaturevents reagieren"
    assert "alert(" not in content, "projekte.js darf keine nativen alert()-Dialoge aufrufen"


def test_planer_bibliothek_a11y_attributes():
    """Prüft, dass bibliothek.js Tastatursemantik und ARIA-Attribute für Aufnahmen und Audio-Player besitzt."""
    bib_path = os.path.join(PLANER_DIR, "app", "bibliothek.js")
    assert os.path.exists(bib_path), "bibliothek.js muss existieren"

    with open(bib_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "tabIndex: 0" in content, "Listeneinträge in bibliothek.js müssen tabIndex=0 besitzen"
    assert "role: \"button\"" in content or "role=\"button\"" in content, "Listeneinträge in bibliothek.js müssen role='button' besitzen"
    assert "aria-selected" in content, "bibliothek.js muss aria-selected besitzen"
    assert "aria-label" in content, "bibliothek.js muss aria-label besitzen"
    assert "Enter" in content and "Space" in content, "bibliothek.js muss Tastaturevents unterstützen"


def test_planer_index_html_semantics():
    """Prüft, dass index.html Barrierefreiheits-Basics hat (lang-Attribut, main-Landmarke, Title)."""
    index_path = os.path.join(PLANER_DIR, "index.html")
    assert os.path.exists(index_path), "index.html muss existieren"

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "<html lang=\"de\">" in content.lower() or "lang=\"de\"" in content, "index.html muss lang='de' Attribut haben"
    assert "<title>" in content and "</title>" in content, "index.html muss title-Tag haben"
    assert "main" in content or "role=\"main\"" in content, "index.html muss eine Haupt-Landmarke (main) besitzen"
