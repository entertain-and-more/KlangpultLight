"""audio.device_manager — Eingabegeräte auflisten und verifizieren.

Kein GUI-Import. Mock-Pfad aktiv wenn:
  - Umgebungsvariable PODCAST_RECORDER_MOCK_AUDIO=1, oder
  - sounddevice nicht importierbar / keine Geräte vorhanden / Abfrage schlägt fehl.
"""
import os
from dataclasses import dataclass, field


@dataclass
class AudioDevice:
    """Repräsentiert ein Eingabegerät (real oder simuliert)."""
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float
    verified: bool
    is_mock: bool = False


def _mock_geraete() -> list[AudioDevice]:
    """Liefert zwei synthetische Mock-Geräte."""
    return [
        AudioDevice(
            index=0,
            name="Mock Mic 1",
            max_input_channels=2,
            default_samplerate=48000.0,
            verified=True,
            is_mock=True,
        ),
        AudioDevice(
            index=1,
            name="Mock Mic 2",
            max_input_channels=2,
            default_samplerate=48000.0,
            verified=True,
            is_mock=True,
        ),
    ]


class DeviceManager:
    """Verwaltet Audio-Eingabegeräte (Abfrage, Verifikation, Zuweisung)."""

    def _nutze_mock(self) -> bool:
        """Prüft zur Laufzeit, ob der Mock-Pfad aktiv ist."""
        if os.environ.get("PODCAST_RECORDER_MOCK_AUDIO", "").strip() == "1":
            return True
        try:
            import sounddevice as sd
            geraete = sd.query_devices()
            # Wenn die Liste leer ist, fallen wir auf Mock zurück
            if not geraete:
                return True
            return False
        except Exception:
            return True

    def list_input_devices(self, verify: bool = True) -> list[AudioDevice]:
        """Gibt alle verfügbaren Eingabegeräte zurück.

        Im Mock-Modus werden zwei synthetische Geräte geliefert.
        Bei verify=True wird jedes reale Gerät testweise geöffnet und
        nur als verified=True markiert, wenn das Öffnen erfolgreich ist.

        Args:
            verify: Ob Geräte testweise geöffnet werden sollen.

        Returns:
            Liste von AudioDevice-Objekten.
        """
        if self._nutze_mock():
            return _mock_geraete()

        import sounddevice as sd

        ergebnisse: list[AudioDevice] = []
        alle = sd.query_devices()

        for idx, info in enumerate(alle):
            if not isinstance(info, dict):
                continue
            if info.get("max_input_channels", 0) < 1:
                continue

            verifiziert = False
            if verify:
                # M-2: Gerät tatsächlich kurz öffnen (nicht nur check_input_settings),
                # um sicherzustellen, dass es wirklich nutzbar ist.
                try:
                    with sd.InputStream(
                        device=idx,
                        channels=min(int(info["max_input_channels"]), 2),
                        samplerate=float(info["default_samplerate"]),
                        blocksize=512,
                    ):
                        pass  # Öffnen erfolgreich → verified=True
                    verifiziert = True
                except Exception:
                    verifiziert = False
            else:
                verifiziert = False

            ergebnisse.append(
                AudioDevice(
                    index=idx,
                    name=str(info.get("name", f"Gerät {idx}")),
                    max_input_channels=int(info["max_input_channels"]),
                    default_samplerate=float(info.get("default_samplerate", 48000.0)),
                    verified=verifiziert,
                    is_mock=False,
                )
            )

        return ergebnisse

    def suggest_default_assignment(self) -> dict[str, AudioDevice | None]:
        """Belegt mic_1, mic_2 und system heuristisch mit verifizierten Geräten.

        mic_1/mic_2: Erste/zweite verifizierte Eingabegeräte.
        system: Bleibt None, wenn kein Loopback-Gerät erkennbar
                (Loopback-Logik kommt in einem späteren Task).

        Returns:
            dict mit Schlüsseln "mic_1", "mic_2", "system".
        """
        geraete = self.list_input_devices(verify=True)
        verifiziert = [g for g in geraete if g.verified]

        return {
            "mic_1": verifiziert[0] if len(verifiziert) > 0 else None,
            "mic_2": verifiziert[1] if len(verifiziert) > 1 else None,
            "system": None,  # Loopback-Erkennung folgt in späterem Task
        }
