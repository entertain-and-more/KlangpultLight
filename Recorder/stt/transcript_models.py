"""stt.transcript_models — Datenmodell für Transkript-Fragmente.

Passend zu remote_protocol_v1.json (transcript_chunk).
Keine GUI-Importe. Keine Abhängigkeiten außer stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TranscriptChunk:
    """Ein einzelnes STT-Transkript-Fragment.

    Felder entsprechen dem ``transcript_chunk``-Typ in remote_protocol_v1.json:
    - ``text``:     Transkribierter Text.
    - ``is_final``: True = endgültiges Ergebnis, False = Zwischenergebnis.
    - ``t_start``:  Startzeit in Sekunden (relativ zur Aufnahme).
    - ``engine``:   Name der STT-Engine (z. B. ``"local"`` oder ``"cloud"``).
    """

    text: str
    is_final: bool = False
    t_start: float = 0.0
    engine: str = "local"
