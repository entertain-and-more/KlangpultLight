"""bridge — Lokaler Dienst-Layer des Klangpult light – Recorders.

Enthält:
    LibraryApiServer  — HTTP-Dienst (GET /api/library, GET /api/health)
    RemoteWsServer    — WebSocket-Dienst nach remote_protocol_v1
    BridgeService     — Bündel beider Dienste
"""
from bridge.library_api import LibraryApiServer
from bridge.remote_ws import RemoteWsServer
from bridge.bridge_service import BridgeService

__all__ = ["LibraryApiServer", "RemoteWsServer", "BridgeService"]
