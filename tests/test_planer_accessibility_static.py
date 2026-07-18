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

    assert 'btn.setAttribute("aria-pressed", "false")' in main_js
    assert 'previousButton?.setAttribute("aria-pressed", "false")' in main_js
    assert 'previousButton?.removeAttribute("aria-current")' in main_js
    assert 'activeButton?.setAttribute("aria-pressed", "true")' in main_js
    assert 'activeButton?.setAttribute("aria-current", "page")' in main_js
