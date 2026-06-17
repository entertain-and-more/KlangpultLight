"""tests.test_build_channels — Tests für sources.build_channels.build_channels().

TDD (Task 3b). Headless, kein sounddevice, kein GUI.

Szenarien:
  1. Default-Config (mic_1/mic_2 capture=True, system capture=False) → 2 Kanäle, kein System
  2. system capture=True + vorhandene LoopbackRoute → 3 Kanäle, System hat device_index + capture_method
  3. system capture=True, aber keine Route → 2 Kanäle (kein System-Kanal)
  4. build_channels mit leerem device_assignment → kein Crash
"""


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _make_wasapi_route(device_index: int = 7):
    """Erzeugt eine synthetische LoopbackRoute (wasapi_loopback)."""
    from sources.loopback_detector import LoopbackRoute
    return LoopbackRoute(
        name="Lautsprecher (Realtek)",
        method="wasapi_loopback",
        device_index=device_index,
        hostapi="Windows WASAPI",
        score=100,
    )


def _make_input_route(device_index: int = 3):
    """Erzeugt eine synthetische LoopbackRoute (input_device, CABLE)."""
    from sources.loopback_detector import LoopbackRoute
    return LoopbackRoute(
        name="CABLE Output (VB-Audio)",
        method="input_device",
        device_index=device_index,
        hostapi="Windows WASAPI",
        score=50,
    )


def _default_cfg():
    """Gibt die Default-SourcesConfig zurück (mic_1/mic_2 capture, system nicht)."""
    from sources.source_config import load_sources_config
    return load_sources_config(None)  # keine Datei → Defaults


def _cfg_mit_system_capture():
    """Gibt SourcesConfig zurück, bei der system.capture=True gesetzt ist."""
    cfg = _default_cfg()
    cfg.set_capture("system", True)
    return cfg


# ---------------------------------------------------------------------------
# Szenario 1: Default-Config → kein System-Kanal
# ---------------------------------------------------------------------------

def test_default_config_ohne_system():
    """Default-Config (system capture=False) → nur mic_1 und mic_2 als Kanäle."""
    from sources.build_channels import build_channels
    cfg = _default_cfg()
    channels = build_channels(cfg, device_assignment={}, loopback_route=None)
    ids = [c.source_id for c in channels]
    assert "mic_1" in ids
    assert "mic_2" in ids
    assert "system" not in ids
    assert len(channels) == 2


def test_default_config_kanalname_korrekt():
    """MixerChannel.name entspricht SourceEntry.name."""
    from sources.build_channels import build_channels
    cfg = _default_cfg()
    channels = build_channels(cfg, device_assignment={}, loopback_route=None)
    namen = {c.source_id: c.name for c in channels}
    assert namen["mic_1"] == "Mikrofon 1"
    assert namen["mic_2"] == "Mikrofon 2"


# ---------------------------------------------------------------------------
# Szenario 2: system capture=True + LoopbackRoute → System-Kanal vorhanden
# ---------------------------------------------------------------------------

def test_system_mit_wasapi_route():
    """system capture=True + WASAPI-Route → 3 Kanäle, System-Kanal mit korrekten Feldern."""
    from sources.build_channels import build_channels
    cfg = _cfg_mit_system_capture()
    route = _make_wasapi_route(device_index=7)
    channels = build_channels(cfg, device_assignment={}, loopback_route=route)
    ids = [c.source_id for c in channels]
    assert "system" in ids, "System-Kanal muss vorhanden sein, wenn Route + capture=True"
    assert len(channels) == 3

    system_ch = next(c for c in channels if c.source_id == "system")
    assert system_ch.device_index == 7
    assert system_ch.capture_method == "wasapi_loopback"


def test_system_mit_input_device_route():
    """system capture=True + CABLE-Route → System-Kanal mit method='input_device'."""
    from sources.build_channels import build_channels
    cfg = _cfg_mit_system_capture()
    route = _make_input_route(device_index=3)
    channels = build_channels(cfg, device_assignment={}, loopback_route=route)
    system_ch = next((c for c in channels if c.source_id == "system"), None)
    assert system_ch is not None
    assert system_ch.device_index == 3
    assert system_ch.capture_method == "input_device"


# ---------------------------------------------------------------------------
# Szenario 3: system capture=True, aber KEINE Route → kein System-Kanal
# ---------------------------------------------------------------------------

def test_system_capture_ohne_route_kein_kanal():
    """system capture=True, loopback_route=None → kein System-Kanal (keine Vorspiegelung)."""
    from sources.build_channels import build_channels
    cfg = _cfg_mit_system_capture()
    channels = build_channels(cfg, device_assignment={}, loopback_route=None)
    ids = [c.source_id for c in channels]
    assert "system" not in ids, (
        "Ohne Route darf kein System-Kanal erzeugt werden — Faktentreue-Regel"
    )
    assert len(channels) == 2


# ---------------------------------------------------------------------------
# Szenario 4: device_assignment für Mic-Kanäle → device_index gesetzt
# ---------------------------------------------------------------------------

def test_mic_device_index_aus_assignment():
    """device_assignment für mic_1 → MixerChannel.device_index korrekt."""
    from sources.build_channels import build_channels
    cfg = _default_cfg()
    assignment = {"mic_1": 2, "mic_2": 4}
    channels = build_channels(cfg, device_assignment=assignment, loopback_route=None)
    ch_map = {c.source_id: c for c in channels}
    assert ch_map["mic_1"].device_index == 2
    assert ch_map["mic_2"].device_index == 4


def test_mic_ohne_assignment_device_index_none():
    """Mic ohne assignment-Eintrag → device_index bleibt None."""
    from sources.build_channels import build_channels
    cfg = _default_cfg()
    channels = build_channels(cfg, device_assignment={}, loopback_route=None)
    for ch in channels:
        assert ch.device_index is None, (
            f"Ohne assignment soll device_index=None, aber {ch.source_id}.device_index={ch.device_index}"
        )


# ---------------------------------------------------------------------------
# Szenario 5: Leere SourcesConfig → leere Kanal-Liste
# ---------------------------------------------------------------------------

def test_leere_config_leere_kanalliste():
    """Leere SourcesConfig → build_channels gibt leere Liste zurück (kein Crash)."""
    from sources.build_channels import build_channels
    from sources.source_config import SourcesConfig
    cfg = SourcesConfig(sources=[])
    channels = build_channels(cfg, device_assignment={}, loopback_route=None)
    assert channels == []


# ---------------------------------------------------------------------------
# Szenario 6: Rückgabe-Typ ist immer list[MixerChannel]
# ---------------------------------------------------------------------------

def test_rueckgabe_ist_mixer_channel_liste():
    """build_channels gibt immer eine Liste von MixerChannel zurück."""
    from sources.build_channels import build_channels
    from audio.mixer_channel import MixerChannel
    cfg = _default_cfg()
    channels = build_channels(cfg, device_assignment={}, loopback_route=None)
    assert isinstance(channels, list)
    for ch in channels:
        assert isinstance(ch, MixerChannel), f"Erwartet MixerChannel, bekam {type(ch)}"
