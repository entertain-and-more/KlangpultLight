from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_planer_header_controls_expose_accessible_state():
    html = (ROOT / "planer" / "index.html").read_text(encoding="utf-8")
    main_js = (ROOT / "planer" / "app" / "main.js").read_text(encoding="utf-8")

    assert 'id="btn-reload"' in html
    assert 'type="button"' in html
    assert 'aria-label="Aktuelle Ansicht neu laden"' in html
    assert 'title="Aktuelle Ansicht neu laden"' in html

    assert 'id="status-indicator" role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-atomic="true"' in html

    assert 'navTabs.setAttribute("role", "tablist")' in main_js
    assert 'btn.setAttribute("role", "tab")' in main_js
    assert 'btn.setAttribute("aria-controls", `view-${id}`)' in main_js
    assert 'view.setAttribute("role", "tabpanel")' in main_js
    assert 'previousButton?.setAttribute("aria-selected", "false")' in main_js
    assert 'activeButton?.setAttribute("aria-selected", "true")' in main_js
    assert 'event.key === "ArrowRight"' in main_js
    assert 'event.key === "ArrowLeft"' in main_js
