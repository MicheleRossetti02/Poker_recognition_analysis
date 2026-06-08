# Desktop apps (macOS) — no terminal

Two double-clickable apps so you (and friends on your Mac) never type a command.

## Build them

```bash
python make_mac_apps.py
```

Creates in `apps/`:

| App | What it does | Needs |
|---|---|---|
| **Virtual Poker.app** | The offline virtual-chip game (you vs bots, coach overlay) | `venv` (PyQt6) |
| **Poker Coach Live.app** | Reads your real poker screen and shows what to do (overlay) | `venv` (torch + ultralytics + PyQt6) + screen-recording permission |

The apps are tiny launchers that reuse the project's existing `venv` — no
multi-GB packaging. They contain absolute paths to **this** machine, so they
are not shared with friends (friends use the web app instead).

## Install / use

1. Open `apps/` in Finder.
2. Drag the apps to `/Applications` or the Dock.
3. First launch only: **right-click → Open** (unsigned app, macOS Gatekeeper).
4. For **Poker Coach Live**: macOS will ask for Screen Recording permission —
   allow it (System Settings → Privacy & Security → Screen Recording), then
   reopen the app.

## For friends (no install at all)

Send them the web link — runs in any browser, phone or PC, nothing to install:

**https://pokercoach-alpha.vercel.app**

## Rebuild after moving the project

The launchers hardcode the project path. If you move the folder, re-run
`python make_mac_apps.py` to regenerate them.
