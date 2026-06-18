"""sources.loopback_detector — Erkennung von Loopback-Aufnahmewegen.

Keine GUI-Imports. Kernlogik (detect_from) ist rein funktional und
hardware-frei testbar per Dependency-Injection.

Zwei reale Aufnahmewege auf Windows:
  1. WASAPI-Loopback: Ausgabegerät mit sounddevice im Loopback-Modus öffnen.
  2. Virtuelles/Monitor-Eingabegerät: Input-Gerät, dessen Name auf
     einen Loopback- oder Virtual-Cable-Treiber hinweist.

Score-Tiers (absteigend):
  100  wasapi_loopback      — direktes WASAPI-Ausgabegerät (zuverlässigste Methode)
   50  input_device (Cable) — virtuelles Kabel (VB-CABLE, VoiceMeeter, BlackHole …)
   30  input_device (Mix)   — Stereo Mix / What U Hear / Monitor (Treiber-abhängig)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Öffentliche Hinweis-Botschaft (ehrlich, wenn kein Loopback-Weg gefunden)
# ---------------------------------------------------------------------------

LOOPBACK_HINT: str = (
    "Kein Loopback-Weg gefunden. Um Systemton aufzunehmen, stehen zwei Optionen zur Verfügung:\n"
    "1. Stereo Mix aktivieren: Soundkarte-Einstellungen → Aufnahmegeräte → "
    "Deaktivierte Geräte anzeigen → 'Stereo Mix' aktivieren.\n"
    "2. VB-CABLE installieren: https://vb-audio.com/Cable/ (kostenlos). "
    "Nach Installation erscheint 'CABLE Output' als Aufnahmegerät."
)

# ---------------------------------------------------------------------------
# Name-Heuristik für virtuelle Loopback-Eingabegeräte
# ---------------------------------------------------------------------------

# Höherer Score: virtuelle Kabel (zuverlässiger als Stereo Mix)
_CABLE_KEYWORDS: tuple[str, ...] = (
    "cable output",
    "vb-audio",
    "vb audio",
    "voicemeeter",
    "blackhole",
)

# Niedrigerer Score: Stereo Mix / What U Hear / Monitor (treiber-/hardware-abhängig)
_MIX_KEYWORDS: tuple[str, ...] = (
    "stereo mix",
    "stereomix",
    "what u hear",
    "loopback",
    "monitor of",
    "monitor",
)

_SCORE_WASAPI = 100
_SCORE_CABLE = 50
_SCORE_MIX = 30


# ---------------------------------------------------------------------------
# Datenmodell
# ---------------------------------------------------------------------------

@dataclass
class LoopbackRoute:
    """Eine erkannte Loopback-Aufnahmeroute.

    Felder:
        name:         Gerätename (wie von sounddevice gemeldet).
        method:       Aufnahmeverfahren: "wasapi_loopback" | "input_device".
        device_index: sounddevice-Geräte-Index.
        hostapi:      Name der Host-API (z. B. "Windows WASAPI").
        score:        Priorität (höher = bevorzugter Weg).
    """
    name: str
    method: str  # "wasapi_loopback" | "input_device"
    device_index: int
    hostapi: str = ""
    score: int = 0


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class LoopbackDetector:
    """Erkennt Loopback-Aufnahmewege (Systemton-Mitschnitt).

    Die Kernmethode detect_from() nimmt Geräte- und HostAPI-Listen als
    Parameter entgegen (Dependency-Injection) und ist vollständig
    hardware-frei testbar. detect() fragt sounddevice ab und delegiert.
    """

    # -- Kernlogik (testbar per Injection) -----------------------------------

    def detect_from(
        self,
        input_devices: list[dict],
        output_devices: list[dict],
        hostapis: list[dict],
    ) -> list[LoopbackRoute]:
        """Ermittelt Loopback-Routen aus injizierten Gerätedaten.

        Jedes Dict entspricht dem sounddevice-Schema:
            name (str), index (int, globaler sounddevice-Index),
            max_input_channels (int), max_output_channels (int),
            hostapi (int, Index in hostapis).

        Der Schlüssel "index" wird direkt übernommen — er entspricht der
        Position in der vollständigen sd.query_devices()-Liste und ist
        der richtige Index zum Öffnen eines Geräts. Fehlt "index" in einem
        Dict (z. B. in Unit-Tests die ihn nicht setzen), wird als Fallback
        None verwendet; Task 3b muss das dann behandeln.

        HostAPI-Dicts: {"name": str}.

        Returns:
            Liste von LoopbackRoute, absteigend nach score sortiert.
        """
        routen: list[LoopbackRoute] = []

        # --- Weg 1: WASAPI-Loopback (Ausgabegerät + WASAPI-HostAPI) --------
        for gerät in output_devices:
            api_name = self._hostapi_name(gerät, hostapis)
            if "wasapi" in api_name.lower():
                routen.append(LoopbackRoute(
                    name=gerät["name"],
                    method="wasapi_loopback",
                    # Echten sounddevice-Index aus dem Dict übernehmen
                    device_index=gerät.get("index", -1),
                    hostapi=api_name,
                    score=_SCORE_WASAPI,
                ))

        # --- Weg 2: Virtuelles/Monitor-Eingabegerät ------------------------
        for gerät in input_devices:
            name_lower = gerät["name"].lower()
            api_name = self._hostapi_name(gerät, hostapis)
            score = self._name_score(name_lower)
            if score > 0:
                routen.append(LoopbackRoute(
                    name=gerät["name"],
                    method="input_device",
                    # Echten sounddevice-Index aus dem Dict übernehmen
                    device_index=gerät.get("index", -1),
                    hostapi=api_name,
                    score=score,
                ))

        routen.sort(key=lambda r: r.score, reverse=True)
        return routen

    # -- Real-Wrapper --------------------------------------------------------

    def detect(self) -> list[LoopbackRoute]:
        """Fragt sounddevice ab und ermittelt Loopback-Routen.

        Falls sounddevice nicht installiert oder kein Gerät vorhanden ist,
        wird eine leere Liste zurückgegeben (kein Crash).

        Returns:
            Liste von LoopbackRoute, absteigend nach score sortiert.
        """
        try:
            import sounddevice as sd  # type: ignore[import-untyped]
            alle_geräte = sd.query_devices()
            hostapis = list(sd.query_hostapis())
        except Exception:
            # sounddevice nicht verfügbar oder kein Audiogerät vorhanden
            return []

        inputs: list[dict] = []
        outputs: list[dict] = []

        for gerät in alle_geräte:
            g = dict(gerät)
            if g.get("max_input_channels", 0) > 0:
                inputs.append(g)
            elif g.get("max_output_channels", 0) > 0:
                outputs.append(g)

        return self.detect_from(inputs, outputs, hostapis)

    # -- Hilfsmethoden -------------------------------------------------------

    def has_loopback(self, routes: Optional[list[LoopbackRoute]] = None) -> bool:
        """True, wenn mindestens eine Loopback-Route verfügbar ist.

        Args:
            routes: Vorberechnete Route-Liste oder None → detect() wird aufgerufen.
        """
        if routes is None:
            routes = self.detect()
        return len(routes) > 0

    def best_route(
        self, routes: Optional[list[LoopbackRoute]] = None
    ) -> Optional[LoopbackRoute]:
        """Gibt die am höchsten bewertete Loopback-Route zurück.

        Args:
            routes: Vorberechnete Route-Liste oder None → detect() wird aufgerufen.

        Returns:
            LoopbackRoute mit dem höchsten score, oder None wenn keine gefunden.
        """
        if routes is None:
            routes = self.detect()
        if not routes:
            return None
        return max(routes, key=lambda r: r.score)

    # -- Interne Helfer -------------------------------------------------------

    @staticmethod
    def _hostapi_name(gerät: dict, hostapis: list[dict]) -> str:
        """Löst den HostAPI-Index eines Geräts auf den HostAPI-Namen auf."""
        idx = gerät.get("hostapi", -1)
        if 0 <= idx < len(hostapis):
            return hostapis[idx].get("name", "")
        return ""

    @staticmethod
    def _name_score(name_lower: str) -> int:
        """Gibt den Score für einen Gerätenamen zurück (0 = kein Loopback-Gerät)."""
        for keyword in _CABLE_KEYWORDS:
            if keyword in name_lower:
                return _SCORE_CABLE
        for keyword in _MIX_KEYWORDS:
            if keyword in name_lower:
                return _SCORE_MIX
        return 0
