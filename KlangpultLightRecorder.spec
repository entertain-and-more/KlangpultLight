# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für den Klangpult light – Recorder (onefile).

Die EXE läuft als eigenständiger Desktop-Recorder direkt aus dem Projekt-Root.
Workspace-Daten sollen im EXE-Ordner landen, nicht in _MEIPASS oder Temp.
"""

a = Analysis(
    ["Recorder/main.py"],
    pathex=["Recorder"],
    binaries=[],
    datas=[
        ("shared", "shared"),
    ],
    hiddenimports=[
        "sounddevice",
        "soundfile",
        "websockets",
        "mss",
        "jsonschema",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "pytest",
        "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="KlangpultLightRecorder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon="DesktopIcon.ico",
)
