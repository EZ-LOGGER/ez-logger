# 🏀 Basketball Renamer v3

Menubar app for tagging and renaming basketball video files.
3-step flow: Player → Play → Rating

---

## Install & Build (One Time)

**Step 1** — Open Terminal (`Cmd+Space` → Terminal → Enter)

**Step 2** — Navigate to this folder:
```bash
cd ~/Downloads/BasketballRenamer3
```

**Step 3** — Make the build script executable:
```bash
chmod +x build.sh launch.sh
```

**Step 4** — Build the app:
```bash
bash build.sh
```
Takes 2-4 minutes. A Finder window opens automatically when done.

**Step 5** — Drag `Basketball Renamer.app` from the `dist/` folder into `/Applications`

**Step 6** — Launch from Spotlight (`Cmd+Space` → Basketball Renamer → Enter)
The 🏀 icon appears in your menubar.

---

## Daily Workflow

**1️⃣ Setup Session** — Set Sport, Opponent, Videographer, Phase, and Footage folder (once per game)

**2️⃣ Batch Rename** — Renames all videos in the folder using file creation timestamps

**3️⃣ Tag Mode** — Opens the tagging window:
- Click a file to select it
- SPACE → QuickLook preview
- ENTER → Start tagging (Step 1: Player)
- Press number key for Player (or any unassigned key to skip)
- Press number key for Play
- Press number key for Rating → file renamed ✅
- ESC → cancel current tag

---

## Filename Format

`SPORT_OPPONENT_YYYYMMDD_HHMMSS_VID_PHASE_PLAYER_PLAY_RATING.ext`

Example: `MBB_SYRACUSE_20260117_143022_ZK_2H_HAND_DRIVE_GOOD.mp4`

---

## Auto-Launch at Login
System Settings → General → Login Items → + → add Basketball Renamer.app

---

## Troubleshooting

**"Unidentified developer" warning:** Right-click → Open → Open

**Tag Mode window doesn't appear:** Make sure Basketball Renamer has Accessibility access:
System Settings → Privacy & Security → Accessibility → toggle on Basketball Renamer

**Permission denied on build.sh:** Run `chmod +x build.sh` first

---

## Updating
Get new version → run `bash build.sh` → drag new .app to Applications (replace old).
Your shortcuts and session settings are always preserved.
