#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""scripts.create_desktop_shortcut — Desktop-Verknuepfung fuer Klangpult light erstellen.

Erstellt eine Windows-Desktopverknuepfung (.lnk) mit Icon (DesktopIcon.ico),
passendem Arbeitsverzeichnis und optionalem Dry-Run.

Aufruf:
    python scripts/create_desktop_shortcut.py
    python scripts/create_desktop_shortcut.py --dry-run
    python scripts/create_desktop_shortcut.py --target dist\KlangpultLightRecorder\KlangpultLightRecorder.exe
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_desktop_dir() -> Path:
    """Ermittelt das Desktop-Verzeichnis des aktuellen Benutzers."""
    # Zuerst per OneDrive/Userprofile pruefen
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        # Pruefe OneDrive-Desktop falls aktiv
        onedrive = os.environ.get("OneDrive")
        if onedrive and (Path(onedrive) / "Desktop").is_dir():
            return Path(onedrive) / "Desktop"
        cand = Path(userprofile) / "Desktop"
        if cand.is_dir():
            return cand

    home_desktop = Path.home() / "Desktop"
    if home_desktop.is_dir():
        return home_desktop

    return Path.home()


def resolve_default_target(root: Path = PROJECT_ROOT) -> Path:
    """Findet das beste Standard-Ausfuehrungsziel."""
    # 1. Root-EXE
    root_exe = root / "KlangpultLightRecorder.exe"
    if root_exe.is_file():
        return root_exe

    # 2. Onedir-EXE
    onedir_exe = root / "dist" / "KlangpultLightRecorder" / "KlangpultLightRecorder.exe"
    if onedir_exe.is_file():
        return onedir_exe

    # 3. Recorder dist EXE
    dist_exe = root / "Recorder" / "dist" / "KlangpultLightRecorder.exe"
    if dist_exe.is_file():
        return dist_exe

    # 4. START.bat
    start_bat = root / "START.bat"
    if start_bat.is_file():
        return start_bat

    return root / "KlangpultLightRecorder.exe"


def create_windows_shortcut(
    target: Path,
    shortcut_path: Path,
    working_dir: Path,
    icon_path: Optional[Path] = None,
    description: str = "Klangpult light — Desktop & Web Workstation",
    dry_run: bool = False,
) -> bool:
    """Erstellt eine .lnk-Verknuepfung ueber PowerShell WScript.Shell COM-Schnittstelle."""
    target_str = str(target.resolve())
    shortcut_str = str(shortcut_path.resolve())
    working_dir_str = str(working_dir.resolve())
    icon_str = str(icon_path.resolve()) if icon_path and icon_path.is_file() else target_str

    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_str}')
$Shortcut.TargetPath = '{target_str}'
$Shortcut.WorkingDirectory = '{working_dir_str}'
$Shortcut.Description = '{description}'
if ('{icon_str}' -ne '') {{
    $Shortcut.IconLocation = '{icon_str}'
}}
$Shortcut.Save()
"""

    if dry_run:
        print("[DRY-RUN] Desktop-Verknuepfung wuerde erstellt:")
        print(f"  Verknuepfung: {shortcut_str}")
        print(f"  Ziel:         {target_str}")
        print(f"  Arbeitsverz:  {working_dir_str}")
        print(f"  Icon:         {icon_str}")
        return True

    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return shortcut_path.is_file()
    except Exception as exc:
        print(f"[FEHLER] Verknuepfung konnte nicht erstellt werden: {exc}", file=sys.stderr)
        return False


def create_shortcut(
    target: Optional[Path] = None,
    name: str = "Klangpult light Recorder",
    icon_path: Optional[Path] = None,
    working_dir: Optional[Path] = None,
    desktop_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> bool:
    """Erstellt plattformuebergreifend eine Desktop-Verknuepfung."""
    resolved_target = target or resolve_default_target()
    resolved_desktop = desktop_dir or get_desktop_dir()
    resolved_working_dir = working_dir or resolved_target.parent
    resolved_icon = icon_path or (PROJECT_ROOT / "DesktopIcon.ico")

    system = platform.system().lower()
    if "windows" in system or os.name == "nt":
        shortcut_file = resolved_desktop / f"{name}.lnk"
        return create_windows_shortcut(
            target=resolved_target,
            shortcut_path=shortcut_file,
            working_dir=resolved_working_dir,
            icon_path=resolved_icon,
            dry_run=dry_run,
        )
    elif "linux" in system:
        desktop_entry = f"""[Desktop Entry]
Type=Application
Name={name}
Exec={resolved_target}
Path={resolved_working_dir}
Icon={resolved_icon}
Terminal=false
Categories=AudioVideo;Audio;
"""
        shortcut_file = resolved_desktop / f"{name}.desktop"
        if dry_run:
            print(f"[DRY-RUN] Linux Desktop Entry wuerde nach {shortcut_file} geschrieben:")
            print(desktop_entry)
            return True
        shortcut_file.write_text(desktop_entry, encoding="utf-8")
        try:
            shortcut_file.chmod(0o755)
        except OSError:
            pass
        return shortcut_file.is_file()
    else:
        # macOS or other
        if dry_run:
            print(f"[DRY-RUN] macOS Symlink wuerde nach {resolved_desktop / name} zeigen")
            return True
        try:
            sym = resolved_desktop / name
            if sym.is_symlink() or sym.is_file():
                sym.unlink()
            sym.symlink_to(resolved_target)
            return True
        except Exception:
            return False


def main():
    parser = argparse.ArgumentParser(description="Desktop-Verknuepfung fuer Klangpult light erstellen")
    parser.add_argument("--target", type=Path, default=None, help="Zielpfad zur EXE oder BAT")
    parser.add_argument("--name", type=str, default="Klangpult light Recorder", help="Name der Verknuepfung")
    parser.add_argument("--icon", type=Path, default=None, help="Pfad zum .ico Icon")
    parser.add_argument("--working-dir", type=Path, default=None, help="Arbeitsverzeichnis")
    parser.add_argument("--desktop-dir", type=Path, default=None, help="Desktop-Ordner")
    parser.add_argument("--dry-run", action="store_true", help="Nur simulieren ohne Datei zu schreiben")

    args = parser.parse_args()
    ok = create_shortcut(
        target=args.target,
        name=args.name,
        icon_path=args.icon,
        working_dir=args.working_dir,
        desktop_dir=args.desktop_dir,
        dry_run=args.dry_run,
    )
    if ok:
        print("[OK] Desktop-Verknuepfung erfolgreich verarbeitet.")
        sys.exit(0)
    else:
        print("[FEHLER] Desktop-Verknuepfung fehlgeschlagen.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
