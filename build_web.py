#!/usr/bin/env python3
"""Copy the pure-python poker engine into web/py/ so Pyodide can load it.

Run before deploying the web app:  python build_web.py
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DST = ROOT / "web" / "py"
POKER_MODULES = [
    "__init__", "cards", "evaluator", "equity", "ranges", "range_model",
    "profiling", "engine", "table", "simulator", "tournament", "history",
    "coach",
    "render", "bots", "arena", "fast_equity",
]

def main():
    (DST / "poker").mkdir(parents=True, exist_ok=True)
    for m in POKER_MODULES:
        shutil.copy(ROOT / "poker" / f"{m}.py", DST / "poker" / f"{m}.py")
    shutil.copy(ROOT / "web_api.py", DST / "web_api.py")
    n = len(POKER_MODULES) + 1
    print(f"Copied {n} python files into {DST}")

if __name__ == "__main__":
    main()
