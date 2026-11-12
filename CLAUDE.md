# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**EZ Logger** is a macOS menubar app for logging and renaming sports video files, built with Python, `rumps` (menubar) and `pyobjc` (native AppKit UI), and packaged as a `.app` with `py2app`.

Clips are logged through **Player → [custom steps]**, appending labels to the filename. Base names come from configurable presets via `resolve_convention`.

All application logic is in one file, **`renamer.py`** (about 9,200 lines). Find things by symbol name; line numbers drift.

## Commands

```bash
# Run from source (no build)
bash launch.sh

# Tests: run after every change, from the project directory
cd ~/Desktop/BasketballRenamer3 && /opt/homebrew/bin/python3.11 -m pytest tests/ -v

# Single test
cd ~/Desktop/BasketballRenamer3 && /opt/homebrew/bin/python3.11 -m pytest tests/test_renamer.py::test_name -v

# Syntax check
/opt/homebrew/bin/python3.11 -m py_compile renamer.py

# Unsigned local build: dist/EZ Logger.app
bash build.sh

# Signed and notarized distribution build: dist/EZLogger-{VERSION}.dmg
bash build.sh --sign

# Publish a release
gh release create vX.X.X "dist/EZLogger-X.X.X.dmg" --title "EZ Logger vX.X.X" --notes "..."

# Live-reload browser preview of preview.html at http://localhost:8765
/opt/homebrew/bin/python3.11 preview_server.py
```

- Everything requires Homebrew Python 3.11 at `/opt/homebrew/bin/python3.11`.
- `--sign` needs the Developer ID Application certificate (`3XQ36X2RC9`) and the Keychain notarize profile `ez-logger-notarize`. It signs nested `.so`, `.dylib`, Python binaries **and Sparkle's plain `Autoupdate` binary** individually, because `--deep` alone fails notarization.
- `--sign` notarizes and staples the **app**. The DMG around it is not signed or stapled.
- The preview server only watches `renamer.py`. Touch it to reload after editing `preview.html`, which mirrors the AppKit layout in HTML/CSS. It needs `watchdog` for instant reloads and otherwise polls every second.

**Distribution target:** Apple Silicon only. In practice the build requires **macOS 26**: in the v1.0.2 DMG, 61 of 87 bundled binaries declare a minimum of 26.0 because they come from Homebrew Python, and `setup.py` sets no `LSMinimumSystemVersion`. Supporting older macOS would need a different Python build.

## Testing and verifying

- **Running from source uses real data.** It reads the real settings in `~` and renames real files. Set `HOME` to a temp folder to isolate a run, or point the app at a folder of copied clips.
- **Unit tests don't exercise the UI.** `tests/test_renamer.py` stubs `rumps`, `AppKit`, `Foundation`, `objc`, `Quartz` and others, so passing tests say nothing about clicks, focus or layout. They cover the pure logic: parsing, naming, stats, safe renames, batch selection, relabeling and Finder color merging.
- **For UI changes, drive the real window from a script** with `make_objc_classes()`, `BasketballRenamerApp()` and `open_tag_mode_v2`. Call `handle_key` for keys, and send real `NSEvent`s through `win.sendEvent_` for clicks. Calling a handler directly hides hit-testing bugs. Known traps:
  - A background test window isn't key, so it swallows the first click unless the view accepts first mouse.
  - `NSRunLoop` pumping doesn't deliver a queued mouse-up. Call `mouseUp_` directly.
  - `NSTableView`'s built-in click tracking doesn't respond to synthetic events.
  - Set `auto_open_on_launch: False` in seeded settings, or the launch timer opens a second window.
  - `screencapture -l` fails without Screen Recording permission. Render with `cacheDisplayInRect_toBitmapImageRep_` or the layer's `renderInContext_`. `cacheDisplay` shows translucent window areas as white.
- After any UI change, check adjacent elements for spacing, text clipping, overlap and highlight bounds.

## Data safety invariants

These must never be violated:

1. **All renames go through `SafeRenamer.safe_rename()`**, including undo. Never call `Path.rename()` or `os.rename()` directly. The only other moves are `SafeRenamer.safe_trash()` (to the Trash) and `SafeRenamer.safe_restore()` (back out of it, for undo).
2. **No silent overwrites.** `safe_rename` refuses if `dst` exists as a different inode, and the caller must handle the `(False, reason)` return. The `conflict_behavior` setting supports only `"ask"` and `"skip"`.
3. **Batch collisions are guarded.** `planned_names` stops two files in one batch sharing a target, and the 80% duplicate-stem check aborts when a naming convention has no unique fields.
4. **All JSON writes are atomic.** Use `save_json` (writes `.tmp`, then `os.replace`). Never open a config file for writing directly.
5. **Use `_save_setting(key, value)` for single settings.** `save_json(SETTINGS_FILE, partial_dict)` wipes every other setting.
6. **Never delete clips permanently.** `safe_trash` uses `NSFileManager.trashItemAtURL` through `_trash_file`. A volume with no Trash fails, and nothing falls back to `os.remove` or `unlink`. Nothing in the app empties the Trash.

`SafeRenamer.validate_file` also enforces the folder boundary after resolving symlinks, regular files only, top-level files only and video extensions only. `_log()` records every attempt and must never raise.

## Persistent state

All paths are in `~`; constants are at the top of `renamer.py`.

| File | Contents |
|------|----------|
| `.bball_renamer_v3_config.json` | Session, `naming_presets`, `sport_presets`, `active_preset`, `custom_steps` |
| `.bball_renamer_v3_shortcuts.json` | `{sport_key: {bank_id: [{key, label, ...}]}}` |
| `.bball_renamer_v3_settings.json` | All settings; `DEFAULT_SETTINGS` lists the keys |
| `.bball_renamer_undo.json` | Undo stack, capped by the `undo_stack_size` setting (default 50) |
| `.bball_renamer_v3_stats.json` | Append-only stat entries |
| `.bball_renamer_v3_rosters.json` | Roster cache per sport |
| `.bball_renamer_v3_rosters_meta.json` | Roster cache timestamps, checked against `roster_cache_days` |
| `.bball_renamer_v3_key_presets.json` | Named hotkey layouts per sport |
| `.ezlogger/rename_log.json` | Permanent log of every rename attempt |
| `.ezlogger/tag_records.json` | `{tagged_filename: {"base", "colors", "reject"}}`, so relabeling replaces old labels; `reject` marks clips to trash |
| `.ezlogger/crashes/` | Crash logs |
| `Library/LaunchAgents/com.bball.renamer.plist` | Login item, written by `_set_launch_at_login`; only works from a built `.app` |

## Structure

- **`SafeRenamer`**: the rename and validation layer.
- **`TagWindowV2`**: the only window. Sections are selected by `_on_nav_select` using `NAV_ITEMS` keys. Keys don't all match labels: `"tag"` is Log Mode, `"players"` is Team, `"session"` is Naming. The default section on open is `"session"` (Naming).
- **`BasketballRenamerApp`** (`rumps.App`): the entry point. Owns `session` and `shortcuts`, and handles `batch_rename`, `undo_last` and `switch_sport`. Opens the window shortly after launch and checks GitHub for updates on a background thread.
- **`make_objc_classes()`**: defines all pyobjc subclasses lazily, once, so nothing registers before `NSApplication` initializes.

`APP_VERSION` is the single source of the version string; `setup.py` reads it by regex. `_crash_handler` is `sys.excepthook`: it writes a local log and emails a report using a Gmail password from Keychain (service `ez-logger-crash-reporter`).

**NAV_ITEMS order** (Naming first, then Log Mode, divider, then the rest):
```python
NAV_ITEMS = [
    ("session",  "pencil",                    "Naming"),
    ("tag",      "bolt.fill",                "Log Mode"),
    ("players",  "person.2.fill",            "Team"),
    (None, None, None),                       # divider
    ("labels",   "list.bullet",              "Labels"),
    ("stats",    "chart.bar.fill",           "Stats"),
    ("settings", "slider.horizontal.3",      "Settings"),
    ("help",     "questionmark.circle.fill", "Help"),
]
```

**First-run tutorial:** `TutorialOverlay` (NSView subclass defined in `make_objc_classes()`) draws a scrim with a `kCGBlendModeClear` spotlight cutout. `TUTORIAL_STEPS` is a list of `(target_ref_attr, title, body)` tuples. Methods on `TagWindowV2`: `_start_tutorial`, `_show_tutorial_step`, `_dismiss_tutorial`, `_auto_start_tutorial`. Stored view refs: `_tutorial_folder_row`, `_tutorial_convention_sv`, `_tutorial_url_btn`. The `seen_tutorial` boolean in `DEFAULT_SETTINGS` gates auto-start; Settings has a "Replay Tutorial" `ActionButton` that calls `_dismiss_tutorial()` then `_start_tutorial()`.

## Naming and filenames

`resolve_convention(preset, file_path=None, session=None)` builds the stem from a preset's `fields` (`text`, `metadata`, `opponent`, `sport`) and returns it **with a trailing separator**. `_finalize_v2` appends tags directly to it, so don't remove the separator.

Presets live in two buckets: `naming_presets` (global, from `+ New` and `Dup`) and `sport_presets` (per sport, written only by ⚡ Import Schedule). `_convention_presets` combines them, and `_convention_global_count` marks the split that saves and deletes rely on.

**Relabeling:** `_finalize_v2` takes the base from `tag_base_stem(stem, record)`, so a new tag replaces old labels. Never derive the base by counting filename segments, because conventions vary in length. Clips with no record keep their whole name as the base.

**Batch Rename:** `_on_batch_rename` passes the Naming tab's selected clips (`_naming_selected`) to `batch_rename(_, only_names=...)`. An empty selection means the whole folder. After `batch_rename` or `undo_last`, call `_refresh_tag_window_files()`.

**Move to Trash:** `BasketballRenamerApp.trash_clips(paths, folder)` confirms with `_confirm_trash_alert` (Return is Cancel), calls `safe_trash` for each clip, drops their tag records and pushes a `{"type": "trash", "items": [{name, trash_path, record_before}]}` undo entry. `undo_last` sends that type to `_undo_trash`, and `undo_op_available` decides whether any entry can still be undone. The Naming tab's trash button acts on `trash_targets(files, _naming_selected, _rejected)`: the selection, else the rejects. ⌘⌫ in its Clips list acts on the selection only. `_refresh_files` rebuilds `_rejected` from tag records, and `_style_reject_cell` strikes those rows through in both file lists. A reject survives Batch Rename; logging the clip clears it.

## Steps and the logging state machine

- `self._steps` is always `["players"] + [s["id"] for s in custom_steps]`. Shortcut banks are keyed by step ID.
- `players` is the fixed first step and owns the roster, search and jersey logic.
- After any structural step change, call `_apply_steps_change()`.

Tag state is the ordered `_tag_parts` list plus `_custom_indices` (typed text, excluded from stats) and `_chain_boundary_indices` (where each chained player starts). Reset them together on every start, cancel and finalize.

Flow: `handle_key` → `_handle_shortcut_key_v2` → ENTER → `_advance_step_v2` → `_finalize_v2`.

| Input | Behavior |
|-------|----------|
| Shortcut key or pill click | Appends a label and stays on the step; several can accumulate |
| ENTER | Arms logging, advances, or finalizes on the last step; in custom mode, confirms typed text |
| BACKSPACE | Exits a branch level, else pops the last label; in custom mode, deletes a character |
| `=` / `+` | `_chain_to_player`: starts another player on the same clip |
| ⌥ Option | Toggles custom text mode; spaces are kept as typed |
| ESC | Closes search first, otherwise cancels the log |
| TAB | Next file, only when no step is active; doesn't wrap |
| X | `_toggle_reject_current`: marks or unmarks a reject, only when no step is active; marking moves to the next file |
| ⌘⌫ | `_trash_current_clip`, only when no step is active. `KeyTableView.keyDown_` catches it, since `handle_key` gets no modifiers |

- **Stats:** `_finalize_v2` calls `log_stat` once per chain segment, excluding custom text. Within a segment, player is `[0]`, rating is `[-1]`, and play is the middle parts joined.
- **Branches:** a shortcut's `children` open a sub-level through `_branch_stack` and `_branch_items`. The parent label is navigation only and is never added to the name. Nesting is one level deep. Search is off inside a branch.
- **Search:** only on the player step, so other steps' keys always reach their shortcuts. Always toggle with `_apply_search_mode(on)`; never set `_search_enabled`, `_player_search_mode` or `_players_bypass_hotkeys` individually. Change matching rules in the `_matches` function inside `_update_search_display`.
- **Finder colors:** a shortcut may hold `finder_color`, and a child without one uses its parent's. `_finalize_v2` applies colors after the rename. Non-color tags are always kept, a color failure never undoes the rename, and undo entries store `tags_before`.

## AppKit rules and traps

**Crashes and freezes on macOS 26:**
- Never pass a `CGImageRef` to an `NSImage` API; HDR sources crash. Thumbnails encode to JPEG with ImageIO on a background thread, then use `initWithData_` on the main thread.
- Use `quicklook()`, never `qlmanage -p`.
- Give `QLPreviewPanel` a data source only. `setDelegate_` freezes the main thread.
- `QLDataSource` methods need their explicit `objc.selector` signatures. Wrong types cause a SIGSEGV.

**Clicks and focus:**
- Transparent views still take clicks. Stacked shortcut cards must be **hidden as well as alpha 0**; `_set_cards_for_step` owns this.
- `PillButton` handlers receive `(view, event)`. A handler with the wrong signature fails silently on click.
- Use `PillButton`, not `NSView`, for `setClickHandler_`. Its `hitTest_` keeps labels from swallowing clicks.
- `SearchResultsTable` picks in its own `mouseDown_`, because the top match is already selected and a selection-change callback wouldn't fire. It refuses first responder so keys keep reaching the file list.
- Views rebuilt later land on top of earlier siblings. `_raise_search_panel` keeps the name dropdown above the step circles.

**Hover and press:**
- `add_hover_highlight(view)` lifts a view on hover. `PillButton.setClickHandler_`, `ActionButton` and `NavItemView` apply it automatically. A plain main-window button should be a `HoverButton` and call it. Pills with no handler stay unlit, so disabled controls don't look clickable.
- Controls that act on mouse down use `hover_dip`, because the action may open a dialog that swallows mouse up. `ActionButton` acts on release, so it uses `hover_press_down` and `hover_press_up`.
- Press motion is animation only and never changes the layer's model transform.

**Controls:**
- Dropdowns use `NSMenu` plus `MenuTarget`. The exception is the native `NSPopUpButton` for the Finder color in the Edit Shortcut alert, read on Save.
- ObjC doesn't retain `MenuTarget`. Keep each one alive in a list on `self`.
- Don't use `NSSegmentedControl` for tabs; its selection state doesn't update reliably. Follow `_switch_stats_tab`.
- In pyobjc method bodies, use `objc.super(_Class, self)`, not bare `super()`.

**Layout:**
- All layout is manual framing, with no Auto Layout. Never call `win.setFrameAutosaveName_()`; a restored frame lands in the wrong position.
- `_reposition_layout(W, H)` reframes all panels. `_on_window_resize_live` does per-section live reflow, and `_on_window_resize` does heavier rebuilds at drag end.
- `_populate_shortcut_pills(bank)` both lays out pills and sets `_sc_card_h`. Call it after changing shortcuts, rosters or sport, and don't set `_sc_card_h` anywhere else.
- Grids use unflipped coordinates. Anchor on `container_h = max(total_h, viewport_h)`, never `total_h`, or short lists sink to the bottom:
  ```python
  y = container_h - PAD - (row + 1) * PILL_H - row * GAP_V
  ```
- To scroll programmatically, use the clip view:
  ```python
  sv.contentView().scrollToPoint_((0, y))
  sv.reflectScrolledClipView_(sv.contentView())
  ```
- For right-anchored buttons use `autoresizingMask = 1|8`. Flexible right margin (`4`) alone makes them drift left.
- **Window snap / tile layout bug:** on macOS snap events `windowDidResize_` fires before AppKit has propagated autoresizing through the view tree, so `sv.frame().size.width` lags behind the new window size. In `_refresh_players_grid` and `_refresh_labels_grid`, always derive `cw` from `self.win.frame().size.width` minus the sidebar offset, falling back to `sv.frame()` only when that returns < 1.
- **Help TOC autoresizing:** the TOC panel has `setAutoresizingMask_(16)` (flexible height, anchored at y=0). TOC buttons inside it must have `setAutoresizingMask_(8)` (NSViewMinYMargin — flexible bottom) so they stay anchored to the top of the panel as it resizes. Without it they stay at their initial y positions when the panel grows/shrinks after a snap.

## Conventions

- Brand colors: `COLOR_CRIMSON` and `COLOR_TAN`. Convert with `_hex_color()` or `_hex_color_alpha()`.
- `self._settings` is a snapshot loaded once per window. Read from it rather than re-reading the file for each action.
- Help text lives only in `_help_content_sections()`, used by both the initial build and the resize rebuild. Use `("table", ...)` blocks for columns, never space padding.
- `is_video` and `batch_rename` exclude dotfiles, so macOS companion files aren't listed or renamed. The extension set is `VIDEO_EXTENSIONS`.
- `_update_sport_pill` is the single refresh for the Team header's sport label and player count.
- `LSUIElement` in `setup.py` is `False`, so the app shows a Dock icon. The `show_in_dock` setting mirrors this at runtime.

## Web scraping

Rosters and schedules are scraped from a school site using the `roster_base_url` setting, and no school URL is hardcoded.

- `_parse_roster_html` must call `html.unescape()` first. Sidearm encodes apostrophes, and names like `O'Connor` otherwise vanish.
- It deduplicates raw names **before** counting duplicate last names, because Sidearm repeats each player in the DOM. Only real duplicates get an initial (`A.COLBERT`).
- `scrape_schedule` strips poll rankings and qualifiers like `(exh)`.
- Add teams that abbreviate badly to `TEAM_ABBREVS`, and new sport URLs to `SLUG_TO_CODE`.
