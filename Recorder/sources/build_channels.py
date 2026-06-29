"""sources.build_channels — Erzeugt die MixerChannel-Liste aus der Quellen-Config.

Keine GUI-Imports. Reine Funktion, vollständig testbar.

Verdrahtungslogik:
  - Mic-/Line-Kanäle werden für alle enabled-Quellen angelegt und bei
    capture=False stumm geschaltet. Dadurch kann die GUI Quellen zur Laufzeit
    an-/abwählen, ohne die Engine neu aufzubauen.
  - Mic-Kanäle: device_index aus SourceEntry.device_index oder
    device_assignment[source_id] (int oder None).
  - System-Quelle (kind="system"): NUR wenn loopback_route vorhanden → device_index
    und capture_method aus der Route. Ohne Route kein System-Kanal (Faktentreue-Regel:
    kein Systemton-Mitschnitt vortäuschen).
"""
from __future__ import annotations

from typing import Optional

from audio.mixer_channel import MixerChannel
from sources.source_config import SourcesConfig
from sources.loopback_detector import LoopbackRoute


def build_channels(
    sources_config: SourcesConfig,
    device_assignment: dict,
    loopback_route: Optional[LoopbackRoute],
) -> list[MixerChannel]:
    """Erzeugt eine MixerChannel-Liste aus der Quellen-Konfiguration.

    Args:
        sources_config:   SourcesConfig mit allen konfigurierten Quellen.
        device_assignment: Dict source_id → sounddevice-Geräte-Index (int).
                           Fehlende Einträge → device_index bleibt None.
        loopback_route:   Beste erkannte LoopbackRoute oder None.
                          System-Quelle wird NUR mit vorhandener Route erzeugt.

    Returns:
        Liste von MixerChannel, reihenfolge-treu aus enabled_sources().
        System-Kanal ist nur enthalten, wenn loopback_route nicht None ist.
    """
    channels: list[MixerChannel] = []

    for eintrag in sources_config.enabled_sources():
        if eintrag.kind == "system":
            # System-Kanal: Loopback-Route ist Pflicht — kein Vortäuschen
            if loopback_route is None or not eintrag.capture:
                continue  # Ehrlich: kein Loopback verfügbar

            channels.append(MixerChannel(
                source_id=eintrag.source_id,
                name=eintrag.name,
                gain=eintrag.gain,
                device_index=loopback_route.device_index,
                capture_method=loopback_route.method,
            ))
        else:
            # Mic- und andere Kanäle: device_index aus assignment (None wenn fehlt)
            device_index = (
                eintrag.device_index
                if eintrag.device_index is not None
                else device_assignment.get(eintrag.source_id)
            )
            channels.append(MixerChannel(
                source_id=eintrag.source_id,
                name=eintrag.name,
                gain=eintrag.gain,
                mute=not eintrag.capture,
                device_index=device_index,
            ))

    return channels
