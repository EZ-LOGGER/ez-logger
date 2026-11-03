# 🏀 EZ Logger

A keyboard-driven macOS app for logging and renaming sports video files. Built for video coordinators who need to tag and organize footage fast.

**[⬇ Download EZ Logger](https://github.com/EZ-LOGGER/ez-logger/releases/latest)**

---

## Install

1. Download `EZLogger-X.X.X.dmg` from the [latest release](https://github.com/EZ-LOGGER/ez-logger/releases/latest)
2. Open the DMG and drag **EZ Logger** into your `/Applications` folder
3. Launch from Spotlight (`Cmd+Space` → EZ Logger) or double-click in Applications

---

## What it does

EZ Logger gives you a keyboard-driven tagging window for sports video. After a batch rename stamps your files with timestamps, you work through the file list pressing hotkeys to log each clip through your configured steps — the filename is updated instantly with no clicking required.

**Key features:**
- Configurable labeling steps — define your own flow (Player, Play, Rating, or anything else) for any sport
- Shortcut banks per step with branching label trees
- Multi-action chains: tag one clip to multiple players with `=`
- Schedule import: pull opponents directly from your athletic department's schedule page (Sidearm Sports)
- Naming convention editor: fully configurable filename format with date/time metadata fields
- Stats tracking: per-player play/rating breakdowns across sessions
- Undo stack for the last 50 renames

---

## Workflow

**1. Setup Session** — Set sport, opponent, videographer, phase, and footage folder (once per game)

**2. Batch Rename** — Stamps all videos in the folder with file creation timestamps

**3. Tag** — Click a file, press ENTER to start tagging:
- ENTER → advance to next step (or save on the last step)
- Number/letter key → select a shortcut label
- `=` → chain to another player without saving
- ⌥ Option → type a custom label
- TAB → next file
- ESC → cancel

---

## Filename format

Filenames are built from your naming convention, configured in the **Naming** tab. The default format looks like:

`SPORT_OPP_YYYYMMDD_HHMMSS_PHASE_PLAYER_PLAY_RATING.ext`

Example: `MBB_SYR_20260215_143022_2H_HAND_DRIVE_GOOD.mp4`

Fields, separators, and metadata are all customizable. You can also import per-opponent presets directly from your schedule.

---

## System requirements

- macOS 12 (Monterey) or later
- Apple Silicon (M1 or later)

---

## Auto-launch at login

Settings → System → Launch at Login

---

## Support

Found a bug or have a feature request? [Open an issue](https://github.com/EZ-LOGGER/ez-logger/issues) on GitHub.
