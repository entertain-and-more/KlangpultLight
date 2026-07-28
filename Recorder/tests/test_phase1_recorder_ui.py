"""Direkter Offscreen-Vertrag für die schlanke Phase-1-Recorder-Oberfläche."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def headless_umgebung(monkeypatch):
    """GUI-Vertrag ohne Audio-/Video-Hardware ausführen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


@pytest.fixture
def qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


def test_quellen_pegel_aufnahmeliste_und_verifizierter_status(
    tmp_path, qt_app, monkeypatch
):
    """Die Phase-1-UI zeigt genau die drei vereinbarten Kernbereiche."""
    monkeypatch.delenv("PODCAST_RECORDER_MOCK_AUDIO", raising=False)

    from PySide6.QtWidgets import QGroupBox

    from audio.device_manager import AudioDevice
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.app_state import AppState
    from core.config import AppConfig
    from recordings.library import RecordingLibrary
    from ui.level_meter import LevelMeter
    from ui.main_window import MainWindow

    geraet = AudioDevice(
        index=7,
        name="Verifiziertes Testmikrofon",
        max_input_channels=2,
        default_samplerate=48000.0,
        verified=True,
        is_mock=True,
    )

    class FakeDeviceManager:
        def list_input_devices(self, verify=True):
            if verify:
                return [geraet]
            return [
                AudioDevice(
                    index=geraet.index,
                    name=geraet.name,
                    max_input_channels=geraet.max_input_channels,
                    default_samplerate=geraet.default_samplerate,
                    verified=False,
                )
            ]

        def verified_input_devices(self, refresh=False):
            return [geraet]

        def suggest_default_assignment(self):
            return {"mic_1": geraet, "mic_2": None, "system": None}

    config = AppConfig(
        mock_audio=False,
        workspace_dir=str(tmp_path),
        samplerate=48000,
        channels=2,
    )
    engine = AudioEngine(
        config=config,
        channels=[MixerChannel(source_id="mic_1", name="Mikrofon 1")],
    )
    fenster = MainWindow(
        config=config,
        device_manager=FakeDeviceManager(),
        engine=engine,
        library=RecordingLibrary(str(tmp_path)),
        state=AppState(),
    )

    try:
        titel = {
            box.title()
            for box in fenster.findChildren(QGroupBox)
            if box.title()
        }
        assert {"Quellen", "Aufnahmen"} <= titel
        assert fenster._btn_aufnahme.text() == "Aufnahme starten"
        assert len(fenster.findChildren(LevelMeter)) == 1
        assert fenster._aufnahme_tree.headerItem().text(0) == "Titel"
        assert fenster._aufnahme_tree.headerItem().text(1) == "Dauer"
        assert fenster._aufnahme_tree.headerItem().text(2) == "Erstellt"
        assert fenster._timer.isActive()
        assert "Mock-Audio aktiv" in fenster.statusBar().currentMessage()
        assert "1 verifizierte Quelle" in fenster.statusBar().currentMessage()
    finally:
        fenster.close()
        qt_app.processEvents()
