#!/usr/bin/env python3
"""
Generate double-clickable macOS .app bundles so non-technical users never touch
a terminal. Each bundle is a tiny launcher that picks whichever local venv has
the needed dependencies and runs the right script. No PyInstaller, no multi-GB
bundling — it reuses the project's existing virtualenvs.

Run:  python make_mac_apps.py
Output: apps/Virtual Poker.app, apps/Poker Coach Overlay.app and
apps/Poker Coach Live.app
Then drag them to the Dock / Applications. First launch: right-click → Open
(unsigned app, macOS Gatekeeper).
"""

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APPS = ROOT / "apps"

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>{name}</string>
  <key>CFBundleDisplayName</key><string>{name}</string>
  <key>CFBundleIdentifier</key><string>com.virtualpoker.{ident}</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>run</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""

RUN = """#!/bin/bash
# Auto-generated launcher. Picks a venv that satisfies the imports, then runs.
REPO="{repo}"
cd "$REPO" || exit 1
IMPORTS="{imports}"
for PY in "$REPO/venv/bin/python" "$REPO/venv312/bin/python" python3; do
  if [ -x "$PY" ] || command -v "$PY" >/dev/null 2>&1; then
    if "$PY" -c "import $IMPORTS" >/dev/null 2>&1; then
      exec "$PY" {script} {args}
    fi
  fi
done
osascript -e 'display dialog "Dipendenze mancanti per {name}.\\n\\nApri il progetto e installa i requisiti:\\n  pip install -r requirements.txt" buttons {{"OK"}} with icon caution with title "{name}"'
exit 1
"""


def make_app(name: str, ident: str, script: str, args: str, imports: str):
    app = APPS / f"{name}.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (app / "Contents" / "Info.plist").write_text(PLIST.format(name=name, ident=ident))
    run = macos / "run"
    run.write_text(RUN.format(repo=str(ROOT), imports=imports, script=script,
                              args=args, name=name))
    run.chmod(run.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return app


def main():
    APPS.mkdir(exist_ok=True)
    a = make_app("Virtual Poker", "game", "poker_gui.py", "play --villains tag,station,lag",
                 "PyQt6, numpy")
    o = make_app("Poker Coach Overlay", "overlay", "coach_overlay_app.py", "",
                 "PyQt6")
    b = make_app("Poker Coach Live", "coach", "main_poker_vision_gto.py", "",
                 "torch, ultralytics, PyQt6")
    print(f"Created:\n  {a}\n  {o}\n  {b}")
    print("\nDrag them to /Applications or the Dock.")
    print("First launch: right-click the app -> Open (unsigned).")


if __name__ == "__main__":
    main()
