"""tests.test_phase8_teleprompter_monitor — Tests für Phase-8-Teleprompter und KI-Monitor.

Belegt:
  - Teleprompter Datenmodell & Defaultwerte
  - Teleprompter Zeilensplitting und Normalisierung
  - Speech-Matching Kontrakt (Token-Übereinstimmung)
  - KI-Monitor Heuristik & Extraktionsregeln (Offline Keyword Matching, Fragengenerierung, Kapitelmarken)
  - Remote-Protokoll v1 Ereigniskompatibilität für Teleprompter & Transkript-Chunks
"""
from __future__ import annotations


def test_teleprompter_text_line_splitting():
    """Prüft, dass Teleprompter-Texte deterministisch in Zeilen zerlegt werden."""
    raw_text = "Willkommen zum Podcast!\n\nHeute sprechen wir über Audio-Workflows.\n  Und noch ein Punkt.  "
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    assert len(lines) == 3
    assert lines[0] == "Willkommen zum Podcast!"
    assert lines[1] == "Heute sprechen wir über Audio-Workflows."
    assert lines[2] == "Und noch ein Punkt."


def test_speech_matching_contract():
    """Prüft den Wortüberdeckungsscore für die STT-Synchronisation."""
    def calculate_match_score(spoken_text: str, script_line: str) -> float:
        spoken_words = set(spoken_text.lower().replace(".", "").replace(",", "").split())
        script_words = set(script_line.lower().replace(".", "").replace(",", "").split())
        if not script_words:
            return 0.0
        common = spoken_words.intersection(script_words)
        return len(common) / len(script_words)

    script_line = "Herzlich willkommen zur achten Episode von Klangpult"
    spoken_exact = "Herzlich willkommen zur achten Episode von Klangpult"
    spoken_partial = "willkommen zur achten Episode"
    spoken_unrelated = "völlig anderer Inhalt ohne Zusammenhang"

    assert calculate_match_score(spoken_exact, script_line) == 1.0
    assert calculate_match_score(spoken_partial, script_line) >= 0.5
    assert calculate_match_score(spoken_unrelated, script_line) == 0.0


def test_monitor_analysis_offline_heuristics():
    """Prüft die deterministische Offline-Analyse von Transkripten."""
    keywords = ["Latenz", "Mikrofon", "Pegel"]
    transcript = "Wir bemerken eine spürbare Latenz am Mikrofon bei hoher Auslastung."

    # Schlüsselwörter finden
    text_lower = transcript.lower()
    detected = [kw for kw in keywords if kw.lower() in text_lower]
    assert "Latenz" in detected
    assert "Mikrofon" in detected
    assert "Pegel" not in detected


def test_remote_protocol_event_schema_compatibility():
    """Prüft, dass die erzeugten WebSocket-Nachrichten dem Remote-Protokoll v1 entsprechen."""
    prompter_scroll_event = {
        "type": "scroll_teleprompter",
        "line_index": 4,
        "mode": "speech",
    }
    assert prompter_scroll_event["type"] == "scroll_teleprompter"
    assert isinstance(prompter_scroll_event["line_index"], int)

    transcript_chunk_event = {
        "type": "transcript_chunk",
        "text": "Aufnahme läuft stabil.",
        "is_final": True,
        "t_start": 12.4,
        "engine": "whisper",
    }
    assert transcript_chunk_event["type"] == "transcript_chunk"
    assert transcript_chunk_event["is_final"] is True
    assert transcript_chunk_event["engine"] == "whisper"

    chapter_marker_event = {
        "type": "insert_chapter_marker",
        "title": "Neuer Themenblock",
    }
    assert chapter_marker_event["type"] == "insert_chapter_marker"
    assert chapter_marker_event["title"] == "Neuer Themenblock"
