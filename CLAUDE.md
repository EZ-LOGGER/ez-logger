# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A macOS menubar app for logging and renaming sports video files. Built with Python + `rumps` (menubar) + `pyobjc` (native AppKit UI). Packaged as a standalone `.app` via `py2app`. App name: **EZ Logger**.

The logging flow is: **Player → [custom steps] → final step**, appending labels to filenames. Naming is driven by configurable presets via `resolve_convention(preset, file_path)`.

## Commands

**Run directly (no .app build, for development):**
```bash
bash launch.sh
# or
/opt/homebrew/bin/python3.11 renamer.py
```

**Start the live-reload browser preview server:**
```bash
/opt/homebrew/bin/python3.11 preview_server.py
# then open http://localhost:8765
```
Requires `pip install watchdog` for instant reloads (falls back to 1s polling otherwise). The watcher only watches `renamer.py` — touch it to reload after editing `preview.html`.

**Build the distributable .app (unsigned, local dev):**
```bash
bash build.sh
```
Output is `dist/EZ Logger.app`. Requires Homebrew Python 3.11 at `/opt/homebrew/bin/python3.11`.

**Build signed, notarized, stapled DMG for distribution:**
```bash
bash build.sh --sign
```
Requires the Developer ID Application certificate (`3XQ36X2RC9`) and notarize credentials stored in Keychain under profile `ez-logger-notarize`. Output is `dist/EZLogger-{VERSION}.dmg`. Signs all nested `.so`/`.dylib`/Python binaries individually before signing the bundle — `--deep` alone is insufficient for notarization.

**Publish a release to GitHub:**
```bash
gh release create vX.X.X "dist/EZLogger-X.X.X.dmg" --title "EZ Logger vX.X.X" --notes "..."
```

**Distribution target:** Apple Silicon only (arm64), macOS 12+. No Intel/universal2 support needed.

**Syntax-check without running:**
```bash
/opt/homebrew/bin/python3.11 -m py_compile renamer.py
```

**Run tests (must be in project directory):**
```bash
cd ~/Desktop/BasketballRenamer3 && /opt/homebrew/bin/python3.11 -m pytest tests/ -v
```

**Run a single test:**
```bash
cd ~/Desktop/BasketballRenamer3 && /opt/homebrew/bin/python3.11 -m pytest tests/test_renamer.py::test_name -v
```

Run pytest after every change. Tests cover `_parse_roster_html`, `roster_to_shortcuts`, `compute_stats`, `resolve_convention`, and `is_video`. Install once with `pip install pytest` if missing.

## Architecture

All application logic lives in a single file: **`renamer.py`** (~8 400 lines).

### Module-top constants

`APP_VERSION` — single source of truth for the version string. Read by `setup.py` at build time (via regex), displayed in the window title and Help section, included in crash reports, and compared against GitHub releases by the update checker.

`CRASH_LOG_DIR` / `CRASH_EMAIL_TO` / `CRASH_EMAIL_FROM` — crash reporter config. `_crash_handler` is installed as `sys.excepthook` at module load; on any unhandled exception it writes a log to `~/.ezlogger/crashes/` and emails a report via Gmail SMTP SSL. The Gmail app-specific password is retrieved from macOS Keychain (service `ez-logger-crash-reporter`) — never hardcoded.

`UPDATE_CHECK_URL` — GitHub API endpoint for the latest release. `_check_for_updates_bg(callback)` fetches it in a background thread; if the remote tag is newer than `APP_VERSION` it calls `callback(version, url)`.

### Persistent state (ten JSON files in `~`)

| File | Contents |
|------|----------|
| `~/.bball_renamer_v3_config.json` | Session config + `naming_presets` list (global templates) + `sport_presets` dict + `active_preset` index + `custom_steps` list |
| `~/.bball_renamer_v3_shortcuts.json` | Per-sport shortcut banks: `{sport_key: {bank_id: [{key, label, ...}]}}` |
| `~/.bball_renamer_v3_settings.json` | All app settings — see `DEFAULT_SETTINGS` at module top for all keys (log mode, rename, display, stats, roster, system, undo groups) |
| `~/.bball_renamer_undo.json` | Undo stack (size set by `undo_stack_size` setting, default 50) |
| `~/.bball_renamer_v3_stats.json` | Append-only list of tagged-clip stat entries |
| `~/.bball_renamer_v3_rosters.json` | Per-sport roster cache: `{sport_code: [{key, label}]}` |
| `~/.bball_renamer_v3_rosters_meta.json` (`ROSTERS_META_FILE`) | Roster cache timestamps: `{sport_code: iso_datetime_str}` — used by `fetch_roster` to expire stale caches per `roster_cache_days` setting |
| `~/.bball_renamer_v3_key_presets.json` (`KEY_PRESETS_FILE`) | Named hotkey layouts per sport: `{sport_key: [{"name": str, "keys": {label: key}}, ...]}` — saved/loaded via 🔑 Keys ▾ button in Team header |
| `~/Library/LaunchAgents/com.bball.renamer.plist` | LaunchAgent for login-item support — written/removed by `_set_launch_at_login(on)` |
| `~/.ezlogger/rename_log.json` | Append-only permanent log of every rename (success + failures) |
| `~/.ezlogger/tag_records.json` (`TAG_RECORDS_FILE`) | `{tagged_filename: {"base": str, "colors": [str]}}` — the name before labels were added and the Finder colors the app applied, so relabeling replaces old labels. Clips tagged before this file existed have no record and keep their whole name as the base |

### Key classes (with approximate line offsets in `renamer.py`)

**`SafeRenamer`** (line ~320) — static class, single source of truth for all rename operations. Never call `Path.rename()` or `os.rename()` directly.

**`TagWindowV2`** (line ~1257) — the only UI (Adobe CC-inspired dark mode). 1380×720px, resizable. Layout: Sidebar (200px) → File list panel (260px) → Cards area. Sidebar auto-hides below 780px width (re-shows above 860px); file list hides below 680px (re-shows above 760px). All layout is manual AppKit framing — no Auto Layout.

**`StatsWindow`** (line ~7235) — dead code. Never instantiated; `BasketballRenamerApp.open_stats()` navigates the existing `TagWindowV2` to its stats section instead.

**`BasketballRenamerApp`** (line ~7725) (`rumps.App`) — menubar entry point. Auto-opens `TagWindowV2` 0.1s after launch via `rumps.Timer`. Owns `self.session` and `self.shortcuts`. Handles `batch_rename`, `undo_last`, `setup_session`, roster loading. Spawns a daemon thread at startup to check GitHub for a newer release (`_run_update_check`) and fires a `rumps.notification` if one is found.

### Menubar

Intentionally minimal — `TagWindowV2` opens automatically on launch. Items:
- Status line: `Sport | vs Opponent | Videographer | Phase | Folder` (read-only)
- `↩ Undo Rename` (⌘Z)
- `Open Window` — recovery path if window is closed
- `🔄 Load Roster from School Website` — dev utility
- `⚙️ Setup Session` — dev utility
- `Quit`

`_build_menu()` is called on init and after `switch_sport()` to rebuild the sport label in the status line.

### Naming convention system

`resolve_convention(preset, file_path=None, session=None)` builds the filename stem from a preset's `fields` list. Four field types exist:
- `text` — literal string value
- `metadata` — date/time from `video_creation_dt`
- `opponent` — uses the field's `value` if set (generated/locked preset); falls back to `session["opponent"]` if `session` is passed; falls back to `"OPP"` otherwise
- `sport` — uses `session["sport"]` if `session` is passed; falls back to `"SPT"`. Renders as a blue badge in the Naming section UI.

Fields are joined with the preset's `separator` and returned **with** a trailing separator (e.g. `"MBB_ND_20260101_"`). `batch_rename` passes `session=self.session` and always uses the active preset — it errors if no fields are defined. Pass `file_path=None` to use `datetime.now()`.

The tagging flow (`_finalize_v2`) appends the tag string directly: `f"{base}{tag_str}"`. Do not remove the trailing separator — it separates the stem from the tag.

`DATE_FORMATS` and `TIME_FORMATS` are module-level lists of `(label, strftime_format)` tuples used to populate Metadata field options. `METADATA_FIELDS` maps metadata keys to display names.

### Sport-scoped naming presets

Presets are split into two buckets stored in `~/.bball_renamer_v3_config.json`:
- **`naming_presets`** — global templates, always visible in the dropdown regardless of active sport. User-created via `+ New` or `Dup`.
- **`sport_presets`** — `{sport_key: [preset, ...]}` per-sport schedule presets, in schedule order. Written by "⚡ Import Schedule"; never by `+ New` or `Dup`.

`_convention_global_count` (instance variable on `TagWindowV2`) tracks how many entries in the combined `_convention_presets` list are global. The split point determines which bucket saves/deletes/duplicates operate on. `_save_presets_to_config()` splits `_convention_presets[:_convention_global_count]` → `naming_presets` and the tail → `sport_presets[sport_key]`.

`_refresh_convention_for_sport()` — rebuilds `_convention_presets` from the two buckets for the active sport and calls `_rebuild_convention_rows()`. Called from `_on_nav_select("session")` (entering the Naming tab) and from `switch_sport` (if the Naming tab is already open).

**Opponent field type** — renders in the Naming section as a crimson-tinted "OPPONENT" badge (no text input). Selecting "Opponent" from the field type dropdown creates `{"type": "opponent", "value": ""}`. "⚡ Import Schedule" clones the template, sets `value` to the team abbreviation, and writes the clone to `sport_presets[sport_key]`.

### Schedule import and team abbreviations

`scrape_schedule(sport_key, base_url)` — fetches `{base_url}/sports/{slug}/schedule`, parses opponent names from `title=` on `data-test-id="s-game-card-opponent-logo__link"` elements (Sidearm platform pattern), strips AP/Coaches poll ranking prefixes (`No. 16 Notre Dame` → `Notre Dame`) and parenthetical qualifiers (`UMass (exh)` → `UMass`), deduplicates, returns list in schedule order.

`abbrev_for_opponent(name)` — looks up `TEAM_ABBREVS` (exact match then case-insensitive), falls back to initials for multi-word unknowns (`"Long Name"` → `"LN"`), first 4 chars for single-word. `TEAM_ABBREVS` is a module-level dict covering all current ACC, Big Ten, Big 12, SEC, AAC, Mountain West members plus Ivy League and common independents (~100 entries). Add entries there for any team not resolving correctly.

"⚡ Import Schedule" button validates the active preset has an `opponent`-type field, runs `scrape_schedule` in a background thread, then calls `_on_import_schedule_done` on the main thread via `MainCaller`. Skips opponents whose preset name (`"vs NOTRE DAME"`) already exists in either bucket.

### Configurable labeling steps

The logging sequence is driven by `self._steps` (an instance variable on `TagWindowV2`), **not** the module-level `STEPS` constant (which is legacy/unused in instance methods). `self._steps` is always `["players"] + [s["id"] for s in custom_steps]`.

**`custom_steps`** is stored in `~/.bball_renamer_v3_config.json` as an ordered list of `{"id": str, "label": str}` dicts. The default is `[{"id": "plays", "label": "Play"}, {"id": "ratings", "label": "Rating"}]`, preserving backward compatibility with existing shortcuts data.

`_rebuild_steps()` — call this whenever `custom_steps` changes. Rebuilds `self._steps` and `self._step_labels_map` (`{step_id: label_str}`).

`_step_label(step_key)` — returns `(title, hint)` dynamically from `self._step_labels_map`. Used everywhere `STEP_LABELS` was used before.

`_apply_steps_change()` — the single entry point after any structural steps change (add/remove/rename/reorder). Calls `_rebuild_steps()`, `_rebuild_labels_rows()`, `_refresh_labels_grid()`, `_rebuild_sc_cards()`, `_build_step_circles()`, `_set_step_state(active=-1)`.

**`players` is always the fixed first step** — it owns roster/search/jersey machinery and cannot be removed or reordered. All other steps are user-configurable via the Labels section.

### Logging state machine (TagWindowV2)

Tag state is an ordered `_tag_parts` list (not a dict) so confirmed segments appear in the filename in entry order. Two parallel sets track metadata about positions in `_tag_parts`:
- `_custom_indices` — positions entered via ⌥ Option custom-insert (excluded from stats)
- `_chain_boundary_indices` — positions where a new chain starts (used to segment stats per player)

All three are reset together at every start, cancel (ESC), and finalize. Entry point: `_start_player_step()` (called when ENTER arms logging).

Key flow: `handle_key()` → `_handle_shortcut_key_v2()` → (user presses ENTER) → `_advance_step_v2()` → `_finalize_v2()`.

**Shortcut keys do NOT auto-advance** — pressing a shortcut appends to `_tag_parts` and updates the hint/preview, then stays on the current step. Multiple shortcuts can be pressed at the same step to accumulate labels. ENTER is the only way to advance.

**ENTER behavior:**
- `step is None` → arms tagging, starts player step
- `step is not None`, not custom mode → advances to next step (or finalizes if on last step)
- `_custom_mode` is True → confirms the typed text (calls `_confirm_custom_label_v2`) if non-empty; cancels custom mode if empty

**BACKSPACE behavior:**
- Not in custom mode, step active, mid-branch → exits one branch level (`_exit_branch()`)
- Not in custom mode, step active, at root → pops last item from `_tag_parts`; adjusts `_custom_indices` and `_chain_boundary_indices`
- In custom mode → falls through to `_handle_custom_input` to delete the last typed character

**`=` / `+` — multi-action chain key:**
- Available any time `step is not None` and not in custom mode
- Calls `_chain_to_player()`: records current `len(_tag_parts)` in `_chain_boundary_indices`, resets branch state, transitions to player step without clearing `_tag_parts`
- Preview shows accumulated labels + `_…` to signal more to come
- A `+ Player  (+)` `PillButton` in every non-player shortcut card does the same thing on click; refs live in `self._chain_btns = {bank: PillButton}`
- `_rebuild_sc_cards()` must clear `self._chain_btns = {}` since card views are removed

**Custom insert (⌥ Option key):**
- Option press → enters `_custom_mode`; typed text accumulates in `_custom_input`
- ENTER → confirms (text is appended to `_tag_parts` **with spaces preserved as typed** — no underscore substitution)
- Option re-press → cancels custom mode without confirming
- ESC → cancels entire log session

**TAB advances to the next file** — only when `self.step is None` (not mid-tag). Clamps at the last file, no wrap.

**Relabeling** — `_finalize_v2` builds names from `tag_base_stem(stem, record)`, using the base saved in `TAG_RECORDS_FILE`, so a new tag replaces earlier labels. Never derive the base by counting filename segments; naming conventions vary in length.

**Search is player-step only** — `handle_key` only enters search mode when `self.step == "players"`. On every other step, letter and number keys go straight to that step's shortcuts.

**Search results list** — `SearchResultsTable` picks a name in its own `mouseDown_`, not on a selection change, because the top match is already highlighted. It refuses first responder so keys keep reaching the file list.

**Clickable pills** — Log-section pills are `PillButton`s wired to `_on_shortcut_pill_click(bank, sc)`, which does the same thing as pressing the key. Clicking a player pill with no step active arms logging first.

**Finder colors** — a shortcut may hold `"finder_color"` (one of `FINDER_COLORS`), set from the pencil dialog in Labels; a branch child without its own color uses its parent's. Player and custom-text labels never set a color. `_finalize_v2` applies colors after the rename via `finder_colors_for_tags` + `merged_finder_tags` + `set_finder_tags`; non-color tags are always kept, and a color failure never undoes the rename. Tag undo entries store `tags_before` so `undo_last` can restore them.

`_finalize_v2` calls `log_stat` once **per chain segment**, splitting `_tag_parts` at `_chain_boundary_indices`. Within each segment, custom-text entries (in `_custom_indices`) are excluded. Positional mapping per segment: player = `[0]`, rating = `[-1]`, play = middle parts joined. This ensures every player in a multi-action clip is credited individually in stats.

### Branching label trees

Shortcuts can have an optional `"children": [...]` list — same schema as any shortcut bank. Pressing a parent shortcut with children pushes a branch frame onto `_branch_stack` and re-renders the current card with the child shortcuts instead of appending to `_tag_parts`.

**State variables (on `TagWindowV2`):**
- `_branch_stack: list` — stack of `{"parent_label": str, "prev_items": list|None}` frames
- `_branch_items: list|None` — current branch items; `None` means use the normal bank shortcuts

**Key methods:**
- `_enter_branch(parent_sc)` — pushes frame, sets `_branch_items = parent_sc["children"]`, updates card title to breadcrumb (`PLAY  ▸  SAVE`), calls `_populate_shortcut_pills(bank)`
- `_exit_branch()` — pops frame, restores `_branch_items`, restores card title, repopulates pills
- `_reset_branch_state()` — clears the entire stack and restores the card title; called from ESC and `_chain_to_player()`

**Interactions:**
- `_populate_shortcut_pills(bank)` uses `self._branch_items` when not `None` instead of `self.shortcuts.get(bank)`
- Search mode is disabled while inside a branch (`in_branch = self._branch_items is not None`)
- BACKSPACE at a branch level calls `_exit_branch()` instead of popping `_tag_parts`
- ESC calls `_reset_branch_state()` before clearing step state
- When a leaf child is pressed, its label is appended to `_tag_parts` normally (parent label is not appended — it's navigational only)

**Children data** are stored inline in the shortcut bank JSON: `{"key": "s", "label": "SAVE", "children": [{"key": "h", "label": "HIGH"}, ...]}`. Children have the same dict schema as top-level shortcuts but do not themselves support further nesting in the current implementation.

**Two search-mode flags** — `_search_enabled` is toggled by the top-bar switch within a session; `_players_bypass_hotkeys` is set from the persisted `player_search_mode` setting on launch. Both must be in sync: always use `_apply_search_mode(on)` to toggle them together, never set them individually.

`_apply_search_mode(on)` is the **single function** that toggles player search — never set `_search_enabled`, `_player_search_mode`, or `_players_bypass_hotkeys` individually.

**Search matching** (`_update_search_display`) — when the `player_number_search` setting is on and the typed prefix is all digits, matching switches to jersey-number prefix match (sorts by number). Otherwise it matches by name: normalises both the typed prefix and each label by stripping apostrophes, and also checks the bare last name when a label has a first-initial prefix (`COLBERT` matches `A.COLBERT`). The `_matches(sc)` inner function is the single place to update if search behaviour needs changing. Digit keys only enter search mode when `player_number_search` is enabled; letter keys always enter search mode when `_search_enabled` is True.

### ObjC class registration

All `pyobjc` subclasses are defined inside `make_objc_classes()`, called lazily once. This deferred pattern prevents registering ObjC classes before `NSApplication` initializes. Key classes: `KeyTableView`, `PillButton`, `ActionButton`, `MainCaller` (bounce callables to main thread), `FileListDelegate`, `SearchResultsDelegate`, `QLDataSource`, `WindowDelegate`, `FilePanelResizer`, `NowCardResizer`, `CardHeightResizer`.

**`FilePanelResizer`** — horizontal drag handle between the file list and cards area. Dragging adjusts `_file_list_w`. After repositioning, it calls `_populate_shortcut_pills(sc_current_bank)` so the player card refits to the new card width.

**`NowCardResizer`** — horizontal drag handle on the vertical divider inside the now-tagging card. Dragging adjusts `_now_left_ratio` (left-column fraction).

**`CardHeightResizer`** — vertical drag handle below a card. Two instances exist: one for the now-tagging card (`_attr="_now_card_h"`) and one for the shortcut card (`_attr="_sc_card_h"`). Dragging up shrinks the card (positive dy), dragging down grows it. For the sc-card handle, the max height is computed dynamically at drag time from the document view's actual content height (`doc_h + 50`), so the card can never grow larger than needed to show all pills. On `mouseUp_`, the now-card handle triggers `_populate_shortcut_pills` for all banks (to refit the sc-card to the new available space below); the sc-card handle only calls `_reposition_layout`.

`QLDataSource` methods use explicit `objc.selector` type signatures (`q@:@` and `@@:@q`) — pyobjc can't infer `NSInteger` for the index arg; getting it wrong causes SIGSEGV.

**Do not add a delegate to the QLPreviewPanel** — `setDataSource_` only. Adding `setDelegate_` with an unimplemented `previewPanel:sourceFrameOnScreenForPreviewItem:` freezes the main thread on macOS 26.

**`PillButton`** has a `hitTest_` override that always returns `self` for any click within its bounds, preventing NSTextField subviews from swallowing mouse events. Always use `objc.super(_PillButton, self)` (not bare `super()`) for super calls inside pyobjc ObjC method bodies. Use `PillButton` (not `NSView`) any time you need `setClickHandler_` — plain `NSView` does not have that method.

**Dropdown menus** use `NSMenu` + `MenuTarget` (a thin `NSObject` with a `_callback` slot) — not `NSPopUpButton`. The exception is the Finder color choice in the Edit Shortcut alert, a native `NSPopUpButton` read when Save is pressed. For `NSButton` target/action, use the same `MenuTarget` pattern: set `btn.setTarget_(t)` and `btn.setAction_("menuPicked:")`. Always keep `MenuTarget` instances alive by appending to a list on `self` (e.g. `self._toc_targets`, `self._btn_targets`) — ObjC won't retain them.

**Do not use `NSSegmentedControl` for tab switching.** Its visual selection state does not update reliably when wired through `MenuTarget`. Use two `ActionButton` instances and swap their colors manually via `configureTitle_bg_press_action_` — see `_switch_stats_tab` as the reference pattern.

### Layout / resize

`_reposition_layout(W, H)` is the single function that reframes all panels on window resize. `WindowDelegate.windowDidResize_` fires on every drag pixel → `_on_window_resize_live()` handles sidebar/file-list snap and calls `_reposition_layout`, then dispatches to the active section for live reflow (including `_populate_shortcut_pills` for the tag section). `windowDidEndLiveResize_` → `_on_window_resize()` handles heavier per-section rebuilds at drag-end: pill-grid column reflow (Team/Labels), stats refresh, session convention rebuild (`_rebuild_convention_rows(scroll_to="preserve")`), and help scroll rebuild when width changed by >4px.

**Per-section resize behavior** — `_on_window_resize_live` dispatches to the active section for live reflow. Also hides `_stats_btn_reset` when content width ≤ 480px to prevent tab/button overlap.
- `"tag"`: calls `_populate_shortcut_pills(sc_current_bank)` so the sc-card refits to the new card width
- `"players"` / `"labels"`: calls `_refresh_labels_grid()` (pill reflow); also updates the labels step-order doc width live so rows auto-stretch via `autoresizingMask=2`
- `"session"` (Naming): `_reposition_session_section` syncs the convention doc width live so rows stretch; `_on_window_resize` (drag-end) calls `_rebuild_convention_rows(scroll_to="preserve")` for a full column reflow
- `"stats"`: calls `_refresh_stats()` live so tiles and leaderboards reflow immediately
- `"settings"`: `_reposition_settings_section(cw, ch)` syncs `_settings_doc` width live; rows have `autoresizingMask=2` so they stretch automatically
- `"help"`: `_reposition_help_content_w(cw, ch)` keeps the content container width in sync live (prevents clipping); `_on_window_resize` calls `_rebuild_help_scroll(cw)` for a full text reflow when width changes by >4px

**Naming convention scroll** — `_reposition_session_section` always snaps to the top of the convention scroll view using `scrollToPoint_((0, max(0.0, doc_h - conv_h)))`. It never preserves the old scroll position (which would silently show the bottom in AppKit unflipped coords). `_rebuild_convention_rows` inflates `doc_h` to `max(natural_h, viewport_h)` so that `doc_h - conv_h` is always ≥ 0 and short lists don't snap to the bottom. `_rebuild_convention_rows(scroll_to=)` accepts `"top"` (default, snaps to top after rebuild) or `"preserve"` (keeps current scroll position — used by `_on_window_resize` at drag-end so the user's scroll position survives a resize).

**Resizable log-section cards** — the now-tagging card and shortcut card heights are user-adjustable via `CardHeightResizer` handles. Heights are stored in `self._now_card_h` (default 220, min 185, max 500) and `self._sc_card_h` (initialized 400, auto-fit overrides immediately). `_reposition_layout` reads these values to position both cards and their handles. `_populate_shortcut_pills` auto-fits the sc-card to its content height and **syncs `self._sc_card_h`** and the sc handle position — making it the source of truth for sc-card height. Do not set `_sc_card_h` from `_reposition_layout` independently; let `_populate_shortcut_pills` own it.

Step circles in the now-tagging card vertically center themselves using `_step_circles_card_h` (set by `_reposition_now_card_internals`). Circles rebuild when card dimensions change by more than 6px (tracked via `_last_step_circles_w` / `_last_step_circles_h`).

The Naming section layout: header (64px) → folder row (54px) → `_convention_sv` fills remaining height, with the Clips panel (280px) on the right. `_reposition_session_section(cw, ch)` handles this split. The panel hides, and its selection clears, when content width is below `NAMING_CLIPS_MIN_W`.

**Clip selection for Batch Rename** — the Clips panel is a multi-select `NSTableView` driven by `NamingClipsDelegate`. `_naming_selected` holds the chosen filenames, `_refresh_naming_clips()` (called from `_refresh_files`) drops names that no longer exist, and `_update_naming_selection_ui()` updates the status text and the `Batch Rename (N)` button. `_on_batch_rename` passes the set to `batch_rename(_, only_names=...)`; an empty selection renames the whole folder.

**Instance variables for live resize:**
- `self._settings_doc` — reference to the settings `NSScrollView` document view; set in `_build_settings_section`. Needed by `_reposition_settings_section` to update doc width live (rows have `autoresizingMask=2` and auto-stretch once the doc is the right width).
- `self._help_doc_container` — reference to the help content `NSView` document view; set in `_build_help_section`. Needed by `_reposition_help_content_w` to keep container width in sync live.
- `self._help_built_content_w` — the `content_w` used when the help scroll was last built; compared against current width in `_on_window_resize` to decide whether a full `_rebuild_help_scroll` is needed.

**Section reposition methods** (called from `_reposition_layout`):
- `_reposition_settings_section(cw, ch)` — updates `_settings_doc` frame width to `cw` when changed; rows stretch via mask.
- `_reposition_help_content_w(cw, ch)` — updates `_help_doc_container` frame width to `cw - TOC_W - 1` to prevent content clipping on narrow windows.
- `_rebuild_help_scroll(cw)` — full rebuild of the help `NSScrollView` at a new content width; re-measures all text blocks with the new `body_w`, rebuilds the container, and updates `_help_doc_container`, `_help_section_ys`, and `_help_built_content_w`.
- `_help_content_sections()` — extracted method returning the help content data structure (10 sections). Shared between `_build_help_section` (initial build) and `_rebuild_help_scroll` (resize rebuild). Edit help content here; do not duplicate it.

### Grid layout coordinate system

All three management grids (Team, Labels shortcuts) use **unflipped AppKit coordinates** (y=0 at bottom). Pills are positioned top-down using `container_h = max(total_h, viewport_h)` as the anchor:

```python
y = container_h - PAD - (row + 1) * PILL_H - row * GAP_V
```

The scroll is anchored to show the top: `scrollPoint_((0, max(0.0, container_h - viewport_h)))`.

**Never use `total_h` as the y-anchor** — when content is short (no scroll needed), `container_h > total_h`, and using `total_h` would push pills toward the bottom of the visible area.

### Programmatic scrolling

For scrolling a document view to a target position, use the clip view API — not `documentView().scrollPoint_()`:

```python
sv.contentView().scrollToPoint_((0, y))
sv.reflectScrolledClipView_(sv.contentView())
```

### Team tab and sport picker

The sidebar nav item formerly called "Players" is now **"Team"** (`NAV_ITEMS` key is still `"players"`). The Team section header contains:

- `self._sport_pill` / `self._sport_pill_lbl` — `PillButton` dropdown showing the active sport (e.g., `▸ 🏀 Men's Basketball ▾`)
- `self._players_count_lbl` — player count, updated alongside the pill

`_sport_picker_menu(pill, event)` opens an `NSMenu` listing all entries in `SPORTS`. Selecting one calls `self.app.switch_sport(sport_key)`, which saves the session, rebuilds the menubar menu, and fires `_load_roster_bg` in a background thread. After the roster loads, `_refresh_tag_window_players()` bounces back to the main thread and calls `_update_sport_pill(sport_key)` in addition to refreshing the grid and shortcut pills.

`_update_sport_pill(sport_key=None)` is the single function to refresh the pill label and player count — call it whenever the active sport or player list changes.

### Labels section (configurable steps management)

The **"Labels"** sidebar nav item replaces the old separate "Plays" and "Ratings" nav items. It manages all custom labeling steps (everything after Player).

**Layout (top-to-bottom):**
- Header (64px): "Labels" title + "+ Add Step" button
- Step-order list (220px scrollable): naming-convention–style rows — one row per step in the full sequence
- Shortcut sub-header (48px): "Shortcuts — [Step Name]" + "+ Add Shortcut" button
- Shortcut grid (fills remaining): pill grid for the selected step's shortcuts

**Step-order rows** mirror `_build_convention_field_row` from the Naming section:
- Row 0: "Player" (locked, `FIXED` badge, no controls)
- Rows 1…N: custom steps — numbered badge (`PillButton`, click to select), editable `NSTextField` for name (saves on end-edit via `NSControlTextDidEndEditingNotification`), ↑ ↓ × controls (24×24px `PillButton`, same geometry as naming convention)
- Active step gets a crimson border; observers stored in `self._labels_row_observers`

`_rebuild_labels_rows()` — clears observers + subviews, rebuilds all rows from current `custom_steps`. Call after any step config change or window resize.

`_labels_name_did_change(step_id, tf)` — inline rename handler: updates config, saves, calls `_rebuild_steps()` + `_build_step_circles()`, updates sc card title without full rebuild.

**Shortcut management pills** (built by `_refresh_labels_grid`) show three icon buttons per pill: branch (`arrow.triangle.branch`), pencil, trash. The label column width is reduced to `pill_w - lbl_x - 98` to fit all three. A small child-count badge (e.g. `3`) is shown to the right of the label text when a shortcut has children. Clicking the branch icon opens `_labels_open_children(idx)`.

`_labels_open_children(idx)` — opens a modal `NSPanel` (via `runModalForWindow_` / `stopModal()`) for managing the children of shortcut at `idx` in the active step's bank. Shows a scrollable list of existing children with per-row delete buttons, plus a key+label input row with an Add button. On Done, saves the updated children list back into `self.shortcuts[step_id][idx]["children"]` and calls `_save_shortcuts()`, `_refresh_labels_grid()`, `_populate_shortcut_pills(step_id)`.

The old `_build_plays_section` / `_build_ratings_section` methods remain in the file as dead code but are no longer called.

### Step circles in Log card

`_build_step_circles()` — clears and redraws the step indicator row in the Now-Tagging card from `self._steps`. Supports N steps dynamically: gap compresses as N grows (`gap = min(70, max(20, ...))`). Labels truncate to fit. Call after `_rebuild_steps()` when step count or names change.

Step circles container lives in `self._now_card`. `self._step_circles_left_w` stores the left-column width (420px) so `_build_step_circles()` can be called without parameters.

### Shortcut cards in Log section

`_build_shortcut_cards()` loops over `self._steps` (not the legacy `bank_titles` list). One card per step, all stacked at the same position. Inactive cards must be hidden as well as alpha 0, because a transparent view still receives clicks; `_set_cards_for_step` owns this. `_sc_cv`, `_sc_cx`, `_sc_cy` are stored so `_rebuild_sc_cards()` can recreate cards after steps change without rebuilding the whole window.

`_rebuild_sc_cards()` — removes existing card views, recreates from current `self._steps`. Resets `_sc_current_bank = "players"`.

### Player pills in Log section

`_populate_shortcut_pills(bank)` builds shortcut cards in the Log section. It also auto-sizes the sc-card to fit the content (capped at available space between now-card and window bottom), writes the result back to `self._sc_card_h`, and repositions `_sc_card_h_resizer`. This means `_populate_shortcut_pills` is the authoritative setter for sc-card height — calling it is equivalent to both laying out the pills and measuring the card. Always call it after loading a roster, switching sports, or changing shortcuts. For `bank == "players"`, jersey numbers are shown right-aligned in each pill:
- `show_nums = bank == "players" and any(sc.get("number", "") for sc in items)`
- `NUM_W, NUM_GAP = (32, 4)` when `show_nums` is True
- Column-width breakpoint and label width both account for `NUM_W + NUM_GAP` to prevent overlap
- Number label: 11pt monospaced weight 0.3, `COLOR_TAN` at 65% opacity

### Stats tab

Stats is a nav section in `TagWindowV2` (`NAV_ITEMS` key `"stats"`), not a separate window. `_on_nav_select("stats")` calls `_refresh_stats()` each time it's shown.

The section has two sub-tabs — **Overview** and **Players** — toggled by `_switch_stats_tab(idx)`. Active tab index is stored in `self._stats_active_tab`. `_switch_stats_tab` swaps `ActionButton` colors and shows/hides `_stats_overview_panel` / `_stats_players_sv`.

- **Overview**: rebuilt on every show by `_refresh_stats_overview()`. Clears all subviews and redraws stat tiles + three leaderboard columns (Top Players, Top Plays, Top Ratings).
- **Players**: scrollable list rebuilt by `_refresh_stats_players()`. Each row is clickable; clicking expands a detail card showing per-player play/rating breakdowns. `_stats_expanded_player` tracks which row is open.

`log_stat(session, player, play, rating)` — appends one entry dict to `STATS_FILE`. Called by `_finalize_v2` once **per chain segment** after every successful tag. **Only hotkey-assigned labels are recorded** — custom text entries (typed via ⌥ Option) are excluded. `_finalize_v2` splits `_tag_parts` at `_chain_boundary_indices`, then within each segment filters through `_custom_indices`; the filtered segment maps positionally: player = `[0]`, rating = `[-1]`, play = middle parts joined. Multi-action clips (chained with `=`) therefore credit each player separately in stats.

`compute_stats(data)` — aggregates a raw list of entries into `{total_clips, total_sessions, players, plays, ratings, top_player, top_play, top_rating, per_player}`. Uses `collections.Counter`.

**Stats scope filtering** — before calling `compute_stats`, `_refresh_stats_overview` and `_refresh_stats_players` filter `all_data` by `stats_scope` setting: `"all_time"` (no filter), `"today"` (date == today's YYYY-MM-DD), `"session"` (entry ts >= `self.app._session_start_ts`).

**Stats header controls** — `_build_stats_section` adds an "Export CSV" `ActionButton` to the right of the header alongside "Reset Stats". `_export_stats_csv()` writes sport-filtered stats to `~/Desktop/ez_logger_stats_{sport}_{YYYYMMDD_HHMMSS}.csv` (Desktop, with timestamp — not the footage folder). The sub-tab buttons (Overview / Players) use `autoresizingMask = 1|4|8` (flexible left + right margins, fixed height — centers horizontally as window widens). The Export and Reset buttons use `1|8` (flexible left margin, fixed height — stays right-anchored). Using `4` alone (flexible right margin) causes these buttons to drift left on resize.

`BasketballRenamerApp.open_stats()` navigates the existing `TagWindowV2` to the stats tab (or opens a new window if none exists).

### Help section

`_build_help_section` builds a TOC + scrollable content panel. The TOC uses **`NSButton`** (not `PillButton`) for each item, wired via `MenuTarget` target/action. Button titles use `NSAttributedString` with `NSMutableParagraphStyle` (10pt head indent) for left padding. Active state is shown by updating the button's layer background color and attributed title color.

`_help_scroll_to(idx)` updates the active TOC highlight and scrolls using `contentView().scrollToPoint_` + `reflectScrolledClipView_`. Section Y positions are stored in `self._help_section_ys` (AppKit unflipped coords) and measured at build time.

`BasketballRenamerApp.show_help` navigates to the in-app Help tab: it calls `self._tag_window_v2.show()` then `_on_nav_select("help")`. Falls back to opening a new `TagWindowV2` if none is open.

**To edit help content** — all section data lives in `_help_content_sections()`. Do not put it anywhere else; both the initial build and the resize-triggered `_rebuild_help_scroll` call this method so edits appear consistently at all window sizes.

**Help content structure** — each section's body is a list of typed blocks rendered by the content loop:
- `("para", text)` — plain paragraph, `b_font` secondary label color
- `("subhead", text)` — small bold all-caps category label, 10pt tertiary label color, with fixed pre/post gaps
- `("table", [(key, val), ...])` — two-column aligned grid: key column is fixed at 148px (`LABEL_W`), value column gets the remainder (`body_w - LABEL_W - COL_GAP`). Each row height is the max of the two cells. This gives true column alignment regardless of font.
- `("bullets", [text, ...])` — bullet list using `"·  " + item` prefix

Do not use space-padding for column alignment — it breaks in proportional fonts. Use `("table", ...)` blocks instead.

### SafeRenamer — file safety layer

`SafeRenamer` is the **single source of truth for all rename operations**. Never call `Path.rename()` or `os.rename()` directly — always go through `SafeRenamer.safe_rename()`. Both `batch_rename` and `_finalize_v2` (tag mode) use it, and so does `undo_last` when reversing files.

`SafeRenamer.validate_folder(folder)` — returns `(ok, error)`. Rejects empty/None/nonexistent paths before any scan begins.

`SafeRenamer.validate_file(file_path, folder_root)` — returns `(ok, reason)`. Enforces five rules using `os.path.realpath()` on both paths:
1. **Folder boundary** — resolved path must begin with `realpath(folder_root) + os.sep`
2. **Regular file only** — `os.path.isfile()`, rejects directories
3. **No recursion** — `os.path.relpath` must contain no `os.sep` (top-level files only)
4. **Video extension** — must be in `SafeRenamer.ALLOWED_EXTENSIONS`
5. **Symlink safety** — `realpath()` resolves symlinks before the boundary check, so a symlink pointing outside the folder is caught by rule 1

`SafeRenamer.validate_file` — error messages distinguish between the failure modes: `"is a directory, not a file"` for a directory masquerading as a video, `"file no longer exists (moved or deleted externally?)"` for a missing path, and `"not a regular file"` for pipes/devices/symlinks that resolve to a non-file.

`SafeRenamer.safe_rename(src, dst, folder_root, session)` — validates `src` and `dst` boundary, **refuses to overwrite** any existing file at `dst` (unless `dst` resolves to the same inode as `src`), executes `src.rename(dst)`, and calls `_log()` regardless of outcome.

`SafeRenamer._log()` — appends one JSON entry to `RENAME_LOG_FILE` (`~/.ezlogger/rename_log.json`). Each entry: `timestamp`, `sport`, `opponent`, `phase`, `old_path`, `new_path`, `success`, `error`. Never raises — logging must not crash the rename flow.

`batch_rename` plan is a list of `(src_path, new_name, was_deduped)` tuples. The plan-building loop tracks `planned_names` (a set) to prevent two files receiving the same target name within one batch. After the plan is built, an **80% duplicate-stem guard** aborts with a dialog if ≥ 80% of targets share the same base stem — the symptom of a naming convention with no unique fields. The preview panel (`_show_batch_rename_preview`) flags `was_deduped` entries in amber with a `"(suffix added — convention not unique)"` note. Conflict behavior supports only `"ask"` and `"skip"` — the `"overwrite"` option was removed.

### Undo stack

`_push_undo(op)` appends an operation dict (`type`, `folder`, `timestamp`, `renames`) to `UNDO_FILE`, capped at 50. Both `batch_rename` and `_finalize_v2` push to the stack. `undo_last` pops the top entry and reverses renames **through `SafeRenamer.safe_rename()`** — it skips files that no longer exist and reports them rather than aborting. ⌘Z works from both the menubar item (`key="z"`) and `KeyTableView.keyDown_` (checking `NSCommandKeyMask = 0x100000`).

### Roster scraping

`~/.bball_renamer_v3_rosters.json` (`ROSTERS_FILE`) is a per-sport cache: `{sport_code: [{"key": ..., "label": ...}]}`. `switch_sport` reads from this cache instantly rather than hitting the network.

`fetch_roster(sport_key)` checks the cache first; if a cache entry exists, it also checks `ROSTERS_META_FILE` for the cached timestamp — if the cache is older than `roster_cache_days` setting, it triggers a fresh scrape. On a cache miss it scrapes `{roster_base_url}/sports/{slug}/roster` using the saved `roster_base_url` setting, and returns `[]` if none is set. No school's URL is hardcoded.

`scrape_all_rosters(base_url, progress_cb)` — the main entry point for bulk fetching. Calls `discover_roster_links(base_url)` (scrapes root page for `/sports/*/roster` hrefs, fills gaps with `SLUG_TO_CODE` fallbacks), then parallel-fetches all sports (4 threads via `concurrent.futures`). Returns `{sport_code: [name, ...]}`.

`_parse_roster_html(html)` returns `[(label, number)]` tuples — sorted, deduplicated. It calls `html.unescape()` on the raw HTML first (Sidearm encodes apostrophes as `&#39;`; without this, names like `O'Connor` are silently dropped) and normalises curly apostrophes to ASCII before running any regex. It tries Sidearm Sports `aria-label="First Last jersey number N"` first, then a PrestoSports `roster-player-name` span fallback. Deduplication happens in two passes: (1) raw `(first, last)` pairs are deduplicated before counting, so multiple DOM elements per player (Sidearm emits 2–3 per player) don't inflate the duplicate-last-name counter; (2) only genuine duplicate last names get a first-initial prefix (`A.COLBERT`). `roster_to_shortcuts(entries)` accepts both `(label, number)` tuples and plain strings. Each shortcut dict has `{"key", "label", "number"}`. Jersey numbers appear in player pills as `#NN` to the right of the name label.

`SLUG_TO_CODE` maps URL slugs (e.g. `"mens-basketball"`) to internal sport codes (`"MBB"`). Unrecognized slugs are silently skipped.

**Team section UI:** three buttons on the right of the header — `🔗 domain.com` (opens URL dialog, saves to `SETTINGS_FILE["roster_base_url"]`), `+ Add Player`, `Fetch All Rosters ↓`. A status label below the separator shows the result of the last fetch. `_on_fetch_all_done(success, results)` is called on the main thread via `MainCaller` when `_scrape_all_bg` completes.

## Key Conventions

- Brand colors: `COLOR_CRIMSON = "#8c2232"`, `COLOR_TAN = "#dbcca6"`. Convert with `_hex_color()` / `_hex_color_alpha()`.
- Shortcut banks are always keyed by step ID. The `players` bank is fixed. Custom step banks use the `id` field from `custom_steps` (e.g. `"plays"`, `"ratings"`, or UUID-based ids like `"step_abc12345"`). `STEPS` and `STEP_LABELS` at module level are legacy — instance methods use `self._steps` and `self._step_label()`.
- `VIDEO_EXTENSIONS` (not `VIDEO_EXTS`) is the set of supported suffixes. `is_video(f)` checks it — and also filters out dotfiles (`p.name.startswith(".")`). Both `is_video` and `batch_rename`'s file scan exclude dotfiles to prevent hidden macOS companion files from appearing in the list or getting renamed.
- `quicklook(path)` / `close_quicklook()` use `QLPreviewPanel` via `NSBundle` — never `qlmanage -p` (crashes with SIGABRT on macOS 26).
- `video_creation_dt(path)` returns a `datetime` from AVFoundation container metadata, falling back to `file_timestamps` (`st_birthtime` → `st_mtime`).
- `ActionButton.configureTitle_bg_press_action_` clears all subviews before adding the new label — safe to call repeatedly to relabel.
- Thumbnail generation: `AVAssetImageGenerator` runs in a background thread. The CGImage is encoded to JPEG bytes in-memory using `CGImageDestinationCreateWithData` (ImageIO / `Quartz`), then passed to the main thread via `MainCaller` → `_render_thumb_from_data`, which creates the `NSImage` via `initWithData_`. **Never pass a CGImageRef directly to any NSImage API on macOS 26** — `NSBitmapImageRep.initWithCGImage_` and `NSImage.initWithCGImage_size_` both crash (SIGTRAP / translation fault) with HDR/wide-gamut sources. `lockFocus`/`CGContextDrawImage` draws the image upside-down. The ImageIO JPEG path avoids all of these.
- After `batch_rename` or `undo_last` completes, call `_refresh_tag_window_files()` on `BasketballRenamerApp` to reload the file list in any open log window.
- `_populate_shortcut_pills(bank)` builds shortcut cards in the Log section. Always call this after changing shortcuts or on window resize.
- `py2app` config is in `setup.py`. `LSUIElement` in `setup.py` is currently `False` (Dock icon is shown). Set it to `True` to make the app menubar-only with no Dock icon. The `show_in_dock` setting mirrors this at runtime via `NSApplication.setActivationPolicy_()`.
- `preview.html` mirrors the AppKit layout in HTML/CSS for all nav sections. Edits to it don't trigger SSE reload — touch `renamer.py` to force a browser refresh.
- After any UI change, visually verify adjacent elements for spacing, text clipping, overlap, and highlight bounds.
- **Never call `win.setFrameAutosaveName_()` on the main window.** NSWindow will silently restore a saved frame on next launch, which puts the window in the wrong position because the app uses manual AppKit framing (not Auto Layout). Window position is not persisted.

### Settings system

`DEFAULT_SETTINGS` (module top, line ~29) holds all settings keys with their defaults. `self._settings` (set in `TagWindowV2.__init__`) is a snapshot loaded once at window creation — always read from it, never re-read `SETTINGS_FILE` per action.

`save_json(path, data)` is **atomic** — it writes to `path + ".tmp"` then calls `os.replace()`, so a crash mid-write never corrupts the file.

`_save_setting(key, value)` is the **only** safe way to persist a single setting — it does a read-modify-write so other keys are never clobbered. Never call `save_json(SETTINGS_FILE, {...})` with a partial dict — that overwrites all other settings. (The old `_apply_search_mode` had this bug; it now uses `_save_setting`.)

**Settings section UI** (`_build_settings_section`) is a scrollable `NSScrollView` with a grouped layout. Seven groups top-to-bottom: Log Mode, Rename, Display, Stats, Roster, System, Undo. Each group has a `make_header` label and rows built by inner helpers: `make_toggle` (ActionButton), `make_dropdown` (PillButton + NSMenu), `make_numeric` (− label + buttons). ActionButton refs are stored in `self._settings_btns` keyed by setting key; MenuTarget refs are kept alive in `self._settings_mts`. Total height is computed from all rows; the document view is sized to content.

**Settings callbacks** for boolean toggles are created by `_make_toggle_cb(key)`. Special-case toggles have dedicated methods: `_toggle_player_search_setting` (calls `_apply_search_mode`), `_toggle_player_number_search_setting` (updates `_player_number_search`), `_toggle_show_jersey_numbers` (repopulates player pills), `_toggle_setting_dock` (calls `NSApp.setActivationPolicy_`), `_toggle_setting_login` (calls `_set_launch_at_login`).

**`player_number_search`** (Log Mode group) — when on, typing digits in search mode matches by jersey number prefix instead of name. Controlled by `_toggle_player_number_search_setting`; instance variable `self._player_number_search` is read by the key handler and `_update_search_display`.

`_set_launch_at_login(on)` — writes/removes `~/Library/LaunchAgents/com.bball.renamer.plist`. Only functional when running from a built `.app` — the `ProgramArguments` path points into the bundle.

`BasketballRenamerApp._session_start_ts` — set to `datetime.now().isoformat()` at startup. Used by the stats scope "Session" filter in `_refresh_stats_overview` and `_refresh_stats_players` to show only clips tagged in the current session.

### Hotkey presets

`KEY_PRESETS_FILE` (`~/.bball_renamer_v3_key_presets.json`) — `{sport_key: [{"name": str, "keys": {label: key}}, ...]}`. Named snapshots of the key→label mapping for the active sport's player bank.

`_players_keys_menu()` — opens an `NSMenu` from the `🔑 Keys ▾` button in the Team header: "Save Layout…", "Load Layout" (submenu of saved presets), "Delete Layout…". `_save_player_key_preset()` prompts for a name and stores the current `{label: key}` mapping. `_load_player_key_preset(preset)` remaps keys by matching labels; unmatched players keep their current key. `_delete_player_key_preset()` shows an NSAlert listing presets and deletes the selected one.

`_players_fetch_all` — before fetching, checks if any player has a non-default key; if so, shows an NSAlert offering "Save Keys First" (saves a preset then returns), "Fetch Anyway" (overwrites keys), or "Cancel".

### Data safety invariants

These rules must never be violated:

1. **All renames go through `SafeRenamer.safe_rename()`** — never call `Path.rename()` or `os.rename()` directly anywhere in the codebase.
2. **No silent overwrites** — `safe_rename` refuses to rename if `dst` already exists and resolves to a different inode than `src`. The caller must handle the `(False, reason)` return.
3. **Batch rename collision guard** — `planned_names` set prevents two files in one batch from targeting the same destination. The 80% duplicate-stem check aborts the batch if the naming convention lacks unique fields.
4. **All JSON writes are atomic** — `save_json` writes to `.tmp` then `os.replace()`. Never open a JSON config file in write mode directly.
5. **`_save_setting` for single-key updates** — never call `save_json(SETTINGS_FILE, partial_dict)`. That clobbers all unspecified settings.
