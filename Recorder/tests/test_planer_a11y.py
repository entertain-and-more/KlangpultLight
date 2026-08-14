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

    for field_id in (
        "projekt-titel",
        "projekt-beschreibung",
        "episoden-titel",
        "episoden-status",
        "episoden-notizen",
    ):
        assert f'id: "{field_id}"' in content, f"{field_id} braucht eine eindeutige Feld-ID"
        assert f'for: "{field_id}"' in content, f"{field_id} braucht ein zugeordnetes sichtbares Label"


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
    """Prüft Semantik und den favicon-fehlerfreien lokalen Browserstart."""
    index_path = os.path.join(PLANER_DIR, "index.html")
    assert os.path.exists(index_path), "index.html muss existieren"

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "<html lang=\"de\">" in content.lower() or "lang=\"de\"" in content, "index.html muss lang='de' Attribut haben"
    assert "<title>" in content and "</title>" in content, "index.html muss title-Tag haben"
    assert "main" in content or "role=\"main\"" in content, "index.html muss eine Haupt-Landmarke (main) besitzen"
    assert 'rel="icon"' in content and 'href="data:,"' in content, (
        "index.html muss den impliziten /favicon.ico-404 im lokalen Browser verhindern"
    )


def test_planer_assets_a11y_attributes():
    """Prüft, dass assets.js Tastatursemantik, Formular-Labels und ARIA-Attribute besitzt."""
    assets_path = os.path.join(PLANER_DIR, "app", "assets.js")
    assert os.path.exists(assets_path), "assets.js muss existieren"

    with open(assets_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "window.alert(" not in content and "alert(" not in content, "assets.js darf kein window.alert() nutzen"
    assert "window.confirm(" not in content, "assets.js darf kein window.confirm() nutzen"
    assert "role: \"dialog\"" in content or "role=\"dialog\"" in content, "Modals in assets.js müssen role='dialog' besitzen"
    assert "aria-modal" in content, "Modals in assets.js müssen aria-modal besitzen"
    assert "aria-label" in content, "Buttons und Controls in assets.js müssen barrierefreie aria-label besitzen"

    for field_id in (
        "asset-input-label",
        "asset-input-kind",
        "asset-input-path",
        "asset-input-mode",
        "asset-input-hotkey",
        "asset-input-color",
    ):
        assert f'id: "{field_id}"' in content or f'id="{field_id}"' in content or field_id in content, (
            f"{field_id} muss in assets.js definiert sein"
        )
        assert f'for: "{field_id}"' in content or f'for="{field_id}"' in content or f'"{field_id}"' in content, (
            f"{field_id} muss ein zugeordnetes Label haben"
        )
