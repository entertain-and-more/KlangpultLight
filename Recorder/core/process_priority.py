"""core.process_priority — Prozess-Priorität während Aufnahmen anheben.

Hebt unter Windows die Prozess-Priorität auf HIGH, damit das Betriebssystem den
Aufnahme-Prozess bei konkurrierender Last bevorzugt schedult und der Audio-Callback
nicht ausgehungert wird (Schutz gegen Stille-Aussetzer). Wird beim Aufnahmestart
aktiviert, beim Stopp zurückgesetzt — kein Dauer-CPU-Vorrang im Leerlauf.

Best-effort, ohne harte Abhängigkeit und ohne GUI-Import. Bewusst HIGH (nicht
REALTIME — REALTIME könnte das Betriebssystem selbst aushungern).
"""
import logging
import sys

_log = logging.getLogger(__name__)

_prev_priority = None
_boosted = False


def boost_priority() -> bool:
    """Hebt die Prozess-Priorität an. Gibt True bei Erfolg zurück."""
    global _prev_priority, _boosted
    if _boosted:
        return True
    try:
        if sys.platform == "win32":
            import ctypes
            HIGH_PRIORITY_CLASS = 0x00000080
            k = ctypes.windll.kernel32
            k.GetPriorityClass.restype = ctypes.c_ulong
            k.GetPriorityClass.argtypes = [ctypes.c_void_p]
            k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            h = ctypes.c_void_p(-1)  # GetCurrentProcess() = Pseudo-Handle (HANDLE)-1
            _prev_priority = k.GetPriorityClass(h)
            ok = bool(k.SetPriorityClass(h, HIGH_PRIORITY_CLASS))
            _boosted = ok
            _log.info("Aufnahme-Schutz: Prozess-Priorität HIGH (%s, vorher=%s)", ok, _prev_priority)
            return ok
        else:
            import os
            _prev_priority = os.getpriority(os.PRIO_PROCESS, 0)
            os.setpriority(os.PRIO_PROCESS, 0, max(-10, _prev_priority - 10))
            _boosted = True
            return True
    except Exception:
        _log.warning("Prozess-Priorität konnte nicht angehoben werden", exc_info=True)
        return False


def restore_priority() -> None:
    """Setzt die Prozess-Priorität auf den vorherigen Wert zurück."""
    global _prev_priority, _boosted
    if not _boosted:
        return
    try:
        if sys.platform == "win32" and _prev_priority:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            k.SetPriorityClass(ctypes.c_void_p(-1), _prev_priority)
            _log.info("Aufnahme-Schutz: Prozess-Priorität zurückgesetzt")
        elif sys.platform != "win32" and _prev_priority is not None:
            import os
            os.setpriority(os.PRIO_PROCESS, 0, _prev_priority)
    except Exception:
        _log.warning("Prozess-Priorität-Reset fehlgeschlagen", exc_info=True)
    finally:
        _prev_priority = None
        _boosted = False
