"""Tests für sources.loopback_detector — LoopbackDetector, LoopbackRoute, LOOPBACK_HINT.

Headless. Alle Tests nutzen detect_from() mit injizierten Mock-Daten.
Kein echter sounddevice-Aufruf in den Tests.

Mock-Dict-Schema entspricht sounddevice.query_devices():
  name: str
  index: int     ← globaler sounddevice-Geräte-Index (Schlüssel in realen Dicts)
  max_input_channels: int
  max_output_channels: int
  hostapi: int   ← Index in die hostapis-Liste

Mock-Dict-Schema für hostapis entspricht sounddevice.query_hostapis():
  name: str
"""


# ---------------------------------------------------------------------------
# Hilfsdaten
# ---------------------------------------------------------------------------

WASAPI_HOSTAPI_IDX = 0
WASAPI_HOSTAPI = {"name": "Windows WASAPI"}

MMSOUND_HOSTAPI_IDX = 1
MMSOUND_HOSTAPI = {"name": "Windows WDM-KS"}

HOSTAPIS = [WASAPI_HOSTAPI, MMSOUND_HOSTAPI]


def _input_device(name: str, hostapi_idx: int = 1, index: int = 0) -> dict:
    return {
        "name": name,
        "index": index,
        "max_input_channels": 2,
        "max_output_channels": 0,
        "hostapi": hostapi_idx,
    }


def _output_device(name: str, hostapi_idx: int = 1, index: int = 0) -> dict:
    return {
        "name": name,
        "index": index,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "hostapi": hostapi_idx,
    }


# ---------------------------------------------------------------------------
# Erkennung: virtuelles Eingabegerät (CABLE / VB-Audio)
# ---------------------------------------------------------------------------

def test_cable_output_erkannt():
    """Input 'CABLE Output (VB-Audio Virtual Cable)' → input_device-Route erkannt."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [_input_device("CABLE Output (VB-Audio Virtual Cable)")]
    outputs: list[dict] = []
    routen = detector.detect_from(inputs, outputs, HOSTAPIS)
    assert len(routen) == 1
    assert routen[0].method == "input_device"
    assert "cable" in routen[0].name.lower()


def test_has_loopback_true_bei_cable():
    """has_loopback(routes) ist True, wenn CABLE-Route vorhanden."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [_input_device("CABLE Output (VB-Audio Virtual Cable)")]
    routen = detector.detect_from(inputs, [], HOSTAPIS)
    assert detector.has_loopback(routen) is True


# ---------------------------------------------------------------------------
# Erkennung: Stereo Mix
# ---------------------------------------------------------------------------

def test_stereo_mix_erkannt():
    """Input 'Stereo Mix (Realtek …)' → input_device-Route erkannt."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [_input_device("Stereo Mix (Realtek High Definition Audio)")]
    routen = detector.detect_from(inputs, [], HOSTAPIS)
    assert len(routen) == 1
    assert routen[0].method == "input_device"


def test_stereo_mix_case_insensitive():
    """Name-Heuristik ist case-insensitiv (stereo mix / STEREO MIX)."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [_input_device("STEREO MIX (Realtek)")]
    routen = detector.detect_from(inputs, [], HOSTAPIS)
    assert len(routen) == 1


# ---------------------------------------------------------------------------
# Erkennung: WASAPI-Loopback (Ausgabegerät + WASAPI-HostAPI)
# ---------------------------------------------------------------------------

def test_wasapi_output_ergibt_loopback_route():
    """WASAPI-Ausgabegerät → wasapi_loopback-Route erkannt."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs: list[dict] = []
    outputs = [_output_device("Lautsprecher (Realtek)", hostapi_idx=WASAPI_HOSTAPI_IDX)]
    routen = detector.detect_from(inputs, outputs, HOSTAPIS)
    assert len(routen) == 1
    assert routen[0].method == "wasapi_loopback"
    assert routen[0].hostapi == "Windows WASAPI"


def test_wasapi_score_hoeher_als_stereo_mix():
    """WASAPI-Loopback hat höheren Score als Stereo-Mix-Route."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [_input_device("Stereo Mix (Realtek)")]
    outputs = [_output_device("Lautsprecher (Realtek)", hostapi_idx=WASAPI_HOSTAPI_IDX)]
    routen = detector.detect_from(inputs, outputs, HOSTAPIS)
    assert len(routen) >= 2
    wasapi_route = next(r for r in routen if r.method == "wasapi_loopback")
    stereo_route = next(r for r in routen if r.method == "input_device")
    assert wasapi_route.score > stereo_route.score


def test_non_wasapi_output_ignoriert():
    """Ausgabegerät ohne WASAPI-HostAPI erzeugt keine wasapi_loopback-Route."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs: list[dict] = []
    # hostapi_idx=1 = MMSOUND (kein WASAPI)
    outputs = [_output_device("Lautsprecher (WDM)", hostapi_idx=MMSOUND_HOSTAPI_IDX)]
    routen = detector.detect_from(inputs, outputs, HOSTAPIS)
    assert len(routen) == 0


# ---------------------------------------------------------------------------
# Keine Geräte → leere Liste, has_loopback False, best_route None
# ---------------------------------------------------------------------------

def test_keine_geraete_leere_liste():
    """detect_from mit leeren Listen → leere Routen-Liste."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    routen = detector.detect_from([], [], HOSTAPIS)
    assert routen == []


def test_has_loopback_false_bei_leer():
    """has_loopback([]) → False (kein Hardware-Aufruf für leere Liste)."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    assert detector.has_loopback([]) is False


def test_best_route_none_bei_leer():
    """best_route([]) → None."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    assert detector.best_route([]) is None


# ---------------------------------------------------------------------------
# LOOPBACK_HINT
# ---------------------------------------------------------------------------

def test_loopback_hint_nicht_leer():
    """LOOPBACK_HINT ist eine nicht-leere deutsche Hinweis-Botschaft."""
    from sources.loopback_detector import LOOPBACK_HINT
    assert isinstance(LOOPBACK_HINT, str)
    assert len(LOOPBACK_HINT.strip()) > 0


def test_loopback_hint_enthaelt_hinweis():
    """LOOPBACK_HINT enthält einen sinnvollen deutschen Inhalt (z. B. 'Stereo Mix' oder 'VB-CABLE')."""
    from sources.loopback_detector import LOOPBACK_HINT
    text = LOOPBACK_HINT.lower()
    assert any(w in text for w in ("stereo mix", "vb-cable", "vb-audio", "loopback")), (
        f"LOOPBACK_HINT scheint keinen sinnvollen Hinweis zu enthalten: {LOOPBACK_HINT!r}"
    )


# ---------------------------------------------------------------------------
# best_route — höchste Score zuerst
# ---------------------------------------------------------------------------

def test_best_route_hoechste_score():
    """best_route liefert die Route mit dem höchsten Score."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [_input_device("Stereo Mix (Realtek)")]
    outputs = [_output_device("Lautsprecher (Realtek)", hostapi_idx=WASAPI_HOSTAPI_IDX)]
    routen = detector.detect_from(inputs, outputs, HOSTAPIS)
    beste = detector.best_route(routen)
    assert beste is not None
    assert beste.method == "wasapi_loopback"


def test_best_route_bei_mehreren_inputs():
    """best_route wählt aus mehreren input_device-Routen die höher bewertete."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    # CABLE sollte höheren Score als Stereo Mix haben
    inputs = [
        _input_device("Stereo Mix (Realtek)"),
        _input_device("CABLE Output (VB-Audio Virtual Cable)"),
    ]
    routen = detector.detect_from(inputs, [], HOSTAPIS)
    beste = detector.best_route(routen)
    assert beste is not None
    assert "cable" in beste.name.lower()


# ---------------------------------------------------------------------------
# Sortierung nach Score absteigend
# ---------------------------------------------------------------------------

def test_routen_sortiert_score_absteigend():
    """detect_from liefert Routen sortiert nach score absteigend."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [
        _input_device("Stereo Mix (Realtek)"),
        _input_device("CABLE Output (VB-Audio)"),
    ]
    outputs = [_output_device("Lautsprecher", hostapi_idx=WASAPI_HOSTAPI_IDX)]
    routen = detector.detect_from(inputs, outputs, HOSTAPIS)
    scores = [r.score for r in routen]
    assert scores == sorted(scores, reverse=True), f"Nicht absteigend sortiert: {scores}"


# ---------------------------------------------------------------------------
# has_loopback / best_route mit routes=None rufen detect() auf (Rauchen-Test)
# ---------------------------------------------------------------------------

def test_has_loopback_none_kein_crash(monkeypatch):
    """has_loopback(None) ruft detect() auf und crasht nicht (sounddevice fehlt = OK)."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    # detect() gibt leere Liste zurück wenn sounddevice nicht verfügbar / leer
    monkeypatch.setattr(detector, "detect", lambda: [])
    result = detector.has_loopback(None)
    assert result is False


def test_best_route_none_kein_crash(monkeypatch):
    """best_route(None) ruft detect() auf und crasht nicht."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    monkeypatch.setattr(detector, "detect", lambda: [])
    result = detector.best_route(None)
    assert result is None


# ---------------------------------------------------------------------------
# device_index — echte sounddevice-Indizes aus dem Dict (nicht enumerate)
# ---------------------------------------------------------------------------

def test_device_index_input_aus_dict():
    """device_index einer input_device-Route entspricht dem 'index'-Wert im Dict (nicht enumerate)."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    # Zwei Input-Geräte mit nicht-sequenziellen Indizes (wie in echten sounddevice-Listen)
    inputs = [
        _input_device("Stereo Mix (Realtek)", index=3),
        _input_device("CABLE Output (VB-Audio)", index=5),
    ]
    routen = detector.detect_from(inputs, [], HOSTAPIS)
    assert len(routen) == 2
    indizes = {r.name: r.device_index for r in routen}
    assert indizes["Stereo Mix (Realtek)"] == 3, (
        f"Erwartet index=3, bekommen {indizes['Stereo Mix (Realtek)']}"
    )
    assert indizes["CABLE Output (VB-Audio)"] == 5, (
        f"Erwartet index=5, bekommen {indizes['CABLE Output (VB-Audio)']}"
    )


def test_device_index_output_aus_dict():
    """device_index einer wasapi_loopback-Route entspricht dem 'index'-Wert im Dict."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    outputs = [
        _output_device("Lautsprecher (Realtek)", hostapi_idx=WASAPI_HOSTAPI_IDX, index=1),
        _output_device("Headphones (WASAPI)", hostapi_idx=WASAPI_HOSTAPI_IDX, index=7),
    ]
    routen = detector.detect_from([], outputs, HOSTAPIS)
    assert len(routen) == 2
    indizes = {r.name: r.device_index for r in routen}
    assert indizes["Lautsprecher (Realtek)"] == 1
    assert indizes["Headphones (WASAPI)"] == 7


def test_device_index_gemischte_liste():
    """Gemischte inputs/outputs mit expliziten Indizes — alle Routes haben exakte Dict-Indizes."""
    from sources.loopback_detector import LoopbackDetector
    detector = LoopbackDetector()
    inputs = [
        _input_device("Stereo Mix (Realtek)", index=3),
    ]
    outputs = [
        _output_device("Lautsprecher", hostapi_idx=WASAPI_HOSTAPI_IDX, index=1),
    ]
    routen = detector.detect_from(inputs, outputs, HOSTAPIS)
    assert len(routen) == 2
    indizes = {r.method: r.device_index for r in routen}
    assert indizes["wasapi_loopback"] == 1
    assert indizes["input_device"] == 3
