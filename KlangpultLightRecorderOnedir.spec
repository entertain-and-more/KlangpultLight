# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec fuer den Klangpult light – Recorder (onedir).

Erzeugt ein entpacktes Verzeichnis (dist/KlangpultLightRecorder) mit schnellem Sofortstart
ohne temporaeres Entpacken zur Laufzeit.
"""

a = Analysis(
    ["Recorder/main.py"],
    pathex=["Recorder"],
    binaries=[],
    datas=[
        ("shared", "shared"),
        ("planer", "planer"),
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
    [],
    exclude_binaries=True,
    name="KlangpultLightRecorder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="DesktopIcon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="KlangpultLightRecorder",
)
