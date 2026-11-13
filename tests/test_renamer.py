"""
Tests for pure functions in renamer.py.
Run: /opt/homebrew/bin/python3.11 -m pytest tests/ -v
"""
import sys
import types
import importlib
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytest

# ── Stub out heavy imports so renamer.py can load without a running NSApp ──────

def _make_stub(name):
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None)
    return mod

for _name in ("rumps", "AppKit", "Foundation", "objc", "CoreGraphics",
              "CoreMedia", "AVFoundation", "Quartz"):
    if _name not in sys.modules:
        sys.modules[_name] = _make_stub(_name)

# rumps.App needs to be a class so BasketballRenamerApp can inherit from it
import rumps as _rumps_stub
if not hasattr(_rumps_stub, "App"):
    class _App:
        def __init__(self, *a, **kw): pass
    _rumps_stub.App = _App
if not hasattr(_rumps_stub, "Timer"):
    _rumps_stub.Timer = MagicMock()
if not hasattr(_rumps_stub, "MenuItem"):
    _rumps_stub.MenuItem = MagicMock()

# Patch out module-level AppKit calls that fire on import
with patch.dict("sys.modules", sys.modules):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "renamer", Path(__file__).parent.parent / "renamer.py")
    renamer = importlib.util.module_from_spec(spec)
    # Prevent top-level make_objc_classes() / rumps.App() execution
    renamer.make_objc_classes = lambda: None  # type: ignore
    try:
        spec.loader.exec_module(renamer)
    except Exception:
        # If something fails at module level, expose what loaded so far
        pass

_parse_roster_html   = renamer._parse_roster_html
roster_to_shortcuts  = renamer.roster_to_shortcuts
compute_stats        = renamer.compute_stats
resolve_convention   = renamer.resolve_convention
is_video             = renamer.is_video
SafeRenamer          = renamer.SafeRenamer


# ── _parse_roster_html ──────────────────────────────────────────────────────

SIDEARM_HTML = """
<a aria-label="James Smith jersey number 10 full bio">Smith</a>
<a aria-label="James Smith jersey number 10 full bio">Smith</a>
<a aria-label="James Smith jersey number 10 full bio">Smith</a>
<a aria-label="Alex Jones jersey number 7 full bio">Jones</a>
<a aria-label="Alex Jones jersey number 7 full bio">Jones</a>
<a aria-label="Alex Jones jersey number 7 full bio">Jones</a>
"""

def test_parse_sidearm_no_duplicates():
    result = _parse_roster_html(SIDEARM_HTML)
    labels = [r[0] for r in result]
    assert len(labels) == len(set(labels)), "duplicate labels in result"
    assert len(result) == 2


def test_parse_sidearm_jersey_numbers():
    result = _parse_roster_html(SIDEARM_HTML)
    by_label = {r[0]: r[1] for r in result}
    assert by_label.get("SMITH") == "10"
    assert by_label.get("JONES") == "7"


SIDEARM_DUP_LAST = """
<a aria-label="Alex Colbert jersey number 22 full bio">Colbert</a>
<a aria-label="Alex Colbert jersey number 22 full bio">Colbert</a>
<a aria-label="Jordan Colbert jersey number 33 full bio">Colbert</a>
<a aria-label="Jordan Colbert jersey number 33 full bio">Colbert</a>
<a aria-label="Mike Taylor jersey number 1 full bio">Taylor</a>
<a aria-label="Mike Taylor jersey number 1 full bio">Taylor</a>
"""

def test_parse_sidearm_duplicate_last_names():
    result = _parse_roster_html(SIDEARM_DUP_LAST)
    labels = [r[0] for r in result]
    assert len(labels) == len(set(labels)), "duplicate labels"
    assert len(result) == 3
    # Duplicate last names must get first-initial prefix
    assert any("." in lbl for lbl in labels), "expected initial.LAST format"
    assert "TAYLOR" in labels


def test_parse_sidearm_suffix_stripped():
    html = '<a aria-label="John Williams Jr jersey number 5 full bio">Williams</a>' * 3
    result = _parse_roster_html(html)
    assert result[0][0] == "WILLIAMS"


def test_parse_empty_html():
    assert _parse_roster_html("") == []


# ── roster_to_shortcuts ─────────────────────────────────────────────────────

def test_roster_to_shortcuts_tuples():
    entries = [("SMITH", "10"), ("JONES", "7")]
    sc = roster_to_shortcuts(entries)
    assert sc[0] == {"key": "1", "label": "SMITH", "number": "10"}
    assert sc[1] == {"key": "2", "label": "JONES", "number": "7"}


def test_roster_to_shortcuts_strings():
    entries = ["SMITH", "JONES"]
    sc = roster_to_shortcuts(entries)
    assert sc[0]["number"] == ""
    assert sc[0]["label"] == "SMITH"


def test_roster_to_shortcuts_key_pool():
    # First 9 keys are digits 1-9, then letters
    entries = [("P", "") for _ in range(12)]
    sc = roster_to_shortcuts(entries)
    assert sc[0]["key"] == "1"
    assert sc[8]["key"] == "9"
    assert sc[9]["key"] == "a"


# ── compute_stats ───────────────────────────────────────────────────────────

STATS_DATA = [
    {"player": "SMITH", "play": "DRIVE", "rating": "GOOD",  "date": "2026-01-01", "opponent": "BC",   "sport": "MBB"},
    {"player": "JONES", "play": "DRIVE", "rating": "BAD",   "date": "2026-01-01", "opponent": "BC",   "sport": "MBB"},
    {"player": "SMITH", "play": "POST",  "rating": "GOOD",  "date": "2026-01-02", "opponent": "NU",   "sport": "MBB"},
    {"player": "",      "play": "ZONE",  "rating": "GREAT", "date": "2026-01-02", "opponent": "NU",   "sport": "MBB"},
]

def test_compute_stats_totals():
    s = compute_stats(STATS_DATA)
    assert s["total_clips"] == 4
    assert s["total_sessions"] == 2  # two distinct (date, opponent, sport) combos


def test_compute_stats_player_counts():
    s = compute_stats(STATS_DATA)
    assert s["players"]["SMITH"] == 2
    assert s["players"]["JONES"] == 1
    assert "" not in s["players"]


def test_compute_stats_top_player():
    s = compute_stats(STATS_DATA)
    assert s["top_player"][0] == "SMITH"


def test_compute_stats_empty():
    s = compute_stats([])
    assert s["total_clips"] == 0
    assert s["top_player"] == ("—", 0)


# ── resolve_convention ──────────────────────────────────────────────────────

def test_resolve_convention_text_fields():
    preset = {
        "separator": "_",
        "fields": [
            {"type": "text", "value": "MBB"},
            {"type": "text", "value": "SYRACUSE"},
        ]
    }
    result = resolve_convention(preset, file_path=None)
    assert result == "MBB_SYRACUSE_"


def test_resolve_convention_empty_fields():
    preset = {"separator": "_", "fields": []}
    assert resolve_convention(preset) == ""


def test_resolve_convention_skips_blank_values():
    preset = {
        "separator": "_",
        "fields": [
            {"type": "text", "value": "MBB"},
            {"type": "text", "value": ""},
            {"type": "text", "value": "OPP"},
        ]
    }
    result = resolve_convention(preset, file_path=None)
    assert result == "MBB_OPP_"


def test_resolve_convention_trailing_separator():
    preset = {
        "separator": "-",
        "fields": [{"type": "text", "value": "HELLO"}]
    }
    result = resolve_convention(preset, file_path=None)
    assert result.endswith("-")


# ── is_video ────────────────────────────────────────────────────────────────

def test_is_video_valid():
    assert is_video(Path("clip.mp4"))
    assert is_video(Path("highlight.MOV"))
    assert is_video(Path("game.mkv"))


def test_is_video_rejects_non_video():
    assert not is_video(Path("notes.txt"))
    assert not is_video(Path("photo.jpg"))


def test_is_video_rejects_dotfiles():
    assert not is_video(Path("._.clip.mp4"))
    assert not is_video(Path("._game.mov"))


# ── SafeRenamer ──────────────────────────────────────────────────────────────

import tempfile, os, stat


def _make_tree():
    """Return a TemporaryDirectory with a known video file inside."""
    d = tempfile.mkdtemp()
    video = Path(d) / "clip.mp4"
    video.touch()
    return d, video


def test_safe_file_outside_folder_rejected():
    d, _  = _make_tree()
    other = tempfile.mkdtemp()
    outside = Path(other) / "clip.mp4"
    outside.touch()
    ok, reason = SafeRenamer.validate_file(outside, Path(d))
    assert not ok
    assert "boundary" in reason


def test_safe_non_video_skipped():
    d = tempfile.mkdtemp()
    txt = Path(d) / "notes.txt"
    txt.touch()
    ok, reason = SafeRenamer.validate_file(txt, Path(d))
    assert not ok
    assert "extension" in reason


def test_safe_subfolder_skipped():
    d   = tempfile.mkdtemp()
    sub = Path(d) / "sub"
    sub.mkdir()
    f   = sub / "clip.mp4"
    f.touch()
    ok, reason = SafeRenamer.validate_file(f, Path(d))
    assert not ok
    assert "subfolder" in reason


def test_safe_directory_skipped_even_with_video_name():
    d    = tempfile.mkdtemp()
    fake = Path(d) / "footage.mp4"
    fake.mkdir()   # a directory named like a video file
    ok, reason = SafeRenamer.validate_file(fake, Path(d))
    assert not ok
    assert "directory" in reason


def test_safe_empty_folder_rejected():
    ok, err = SafeRenamer.validate_folder("")
    assert not ok
    ok2, err2 = SafeRenamer.validate_folder(None)
    assert not ok2
    ok3, err3 = SafeRenamer.validate_folder("/does/not/exist/xyz")
    assert not ok3
    assert "does not exist" in err3


def test_safe_symlink_outside_folder_rejected():
    d       = tempfile.mkdtemp()
    outside = tempfile.mkdtemp()
    real_f  = Path(outside) / "clip.mp4"
    real_f.touch()
    link    = Path(d) / "link.mp4"
    os.symlink(str(real_f), str(link))
    ok, reason = SafeRenamer.validate_file(link, Path(d))
    assert not ok
    assert "boundary" in reason


def test_safe_rename_round_trip():
    d, src = _make_tree()
    dst = Path(d) / "renamed.mp4"
    ok, err = SafeRenamer.safe_rename(src, dst, Path(d))
    assert ok, err
    assert dst.exists()
    assert not src.exists()


def test_undo_skips_missing_files_and_reports():
    """Simulate undo when some files have already been moved/deleted."""
    d   = tempfile.mkdtemp()
    fp  = Path(d)

    # Only "new_b.mp4" exists; "new_a.mp4" has been deleted.
    present = fp / "new_b.mp4"
    present.touch()

    renames = [
        {"old": "orig_a.mp4", "new": "new_a.mp4"},  # missing → should be skipped
        {"old": "orig_b.mp4", "new": "new_b.mp4"},  # present → should be restored
    ]

    restored, skipped, errors = 0, 0, []
    for r in renames:
        src = fp / r["new"]
        dst = fp / r["old"]
        if not src.exists():
            skipped += 1
            errors.append(r["new"])
            continue
        ok, err = SafeRenamer.safe_rename(src, dst, fp)
        if ok:
            restored += 1
        else:
            errors.append(err)

    assert restored == 1
    assert skipped  == 1
    assert (fp / "orig_b.mp4").exists()
    assert not (fp / "new_b.mp4").exists()


# ── No school-specific defaults ───────────────────────────────────────────────

def _isolate_roster_files(tmp_path, base_url):
    """Point roster and settings files at tmp_path, with base_url as the saved URL."""
    settings = tmp_path / "settings.json"
    settings.write_text(renamer.json.dumps({"roster_base_url": base_url}))
    return patch.multiple(
        renamer,
        SETTINGS_FILE=str(settings),
        ROSTERS_FILE=str(tmp_path / "rosters.json"),
        ROSTERS_META_FILE=str(tmp_path / "meta.json"),
    )

def test_fetch_roster_without_school_url_never_hits_network(tmp_path):
    with _isolate_roster_files(tmp_path, ""), \
         patch.object(renamer, "fetch_roster_from_url") as fetch:
        assert renamer.fetch_roster("MBB") == []
    fetch.assert_not_called()

@pytest.mark.parametrize("saved", ["https://example.edu", "https://example.edu/"])
def test_fetch_roster_uses_saved_school_url(tmp_path, saved):
    with _isolate_roster_files(tmp_path, saved), \
         patch.object(renamer, "fetch_roster_from_url", return_value=[("JONES", "1")]) as fetch:
        assert renamer.fetch_roster("WHK") == [("JONES", "1")]
    fetch.assert_called_once_with("https://example.edu/sports/womens-ice-hockey/roster")

def test_every_sport_has_a_roster_slug():
    assert set(renamer.SPORTS) == set(renamer.SLUG_TO_CODE.values())

def test_every_sport_has_play_and_rating_templates():
    assert set(renamer.SPORT_PLAY_TEMPLATES) == set(renamer.SPORTS)
    assert set(renamer.SPORT_RATING_TEMPLATES) == set(renamer.SPORTS)

@pytest.mark.parametrize("sport", sorted(renamer.SPORTS))
@pytest.mark.parametrize("bank, templates", [
    ("plays", renamer.SPORT_PLAY_TEMPLATES),
    ("ratings", renamer.SPORT_RATING_TEMPLATES),
])
def test_template_labels_and_keys_are_usable(sport, bank, templates):
    items = renamer.default_shortcuts(sport)[bank]
    labels = [sc["label"] for sc in items]
    keys = [sc["key"] for sc in items]
    assert labels == templates[sport], "every label gets a hotkey"
    assert labels and len(set(labels)) == len(labels)
    assert len(set(keys)) == len(keys) and all(len(k) == 1 for k in keys)
    assert not set(keys) & set("=+")
    assert all(label == label.upper() and "/" not in label and ":" not in label for label in labels)

def test_templates_match_the_sport():
    assert "LAYUP" in renamer.SPORT_PLAY_TEMPLATES["WBB"]
    assert "LAYUP" not in renamer.SPORT_PLAY_TEMPLATES["MHK"]
    assert "HOME RUN" in renamer.SPORT_PLAY_TEMPLATES["SB"]
    assert "FOUL" in renamer.SPORT_RATING_TEMPLATES["MBB"]
    assert "SAFE" in renamer.SPORT_RATING_TEMPLATES["BASE"]
    assert "SAFE" not in renamer.SPORT_RATING_TEMPLATES["FB"]

def test_unknown_sport_still_gets_usable_shortcuts():
    sc = renamer.default_shortcuts("NOPE")
    assert sc["players"] == [] and sc["plays"] == []
    assert [s["label"] for s in sc["ratings"]] == ["GOOD", "MISS"]

def test_default_shortcuts_returns_independent_copies():
    first = renamer.default_shortcuts("FB")
    first["plays"].append({"key": "z", "label": "EDITED"})
    first["plays"][0]["label"] = "EDITED"
    first["ratings"][0]["label"] = "EDITED"
    first["players"].append({"key": "1", "label": "EDITED"})
    second = renamer.default_shortcuts("FB")
    assert "EDITED" not in repr(second)

def test_defaults_have_no_school_or_personal_values():
    assert renamer.default_shortcuts("MBB")["players"] == []
    assert renamer.DEFAULT_SESSION["opponent"] == "OPP"
    assert renamer.DEFAULT_SESSION["videographer"] == "VID"
    assert "bceagles" not in Path(renamer.__file__).read_text()


# ── Search only applies to the player step ────────────────────────────────────

def _key_window(step, shortcuts, search_on=True, number_search=False):
    """A stand-in TagWindowV2 positioned on one step of the logging flow."""
    win = MagicMock()
    win._search_mode = False
    win._custom_mode = False
    win._branch_items = None
    win._search_enabled = search_on
    win._player_number_search = number_search
    win.step = step
    win.shortcuts = shortcuts
    win._steps = ["players", "plays", "ratings"]
    return win

RATING_BANKS = {
    "players": [{"key": "g", "label": "GREEN"}],
    "ratings": [{"key": "g", "label": "GOOD"}, {"key": "1", "label": "MISS"}],
}

def test_letter_on_rating_step_picks_shortcut_with_search_on():
    win = _key_window("ratings", RATING_BANKS)
    renamer.TagWindowV2.handle_key(win, "g")
    win._enter_search_mode.assert_not_called()
    win._handle_shortcut_key_v2.assert_called_once_with(RATING_BANKS["ratings"][0])

def test_number_on_rating_step_picks_shortcut_with_number_search_on():
    win = _key_window("ratings", RATING_BANKS, number_search=True)
    renamer.TagWindowV2.handle_key(win, "1")
    win._enter_search_mode.assert_not_called()
    win._handle_shortcut_key_v2.assert_called_once_with(RATING_BANKS["ratings"][1])

def test_letter_on_player_step_starts_search():
    win = _key_window("players", RATING_BANKS)
    renamer.TagWindowV2.handle_key(win, "g")
    win._enter_search_mode.assert_called_once_with("g")
    win._handle_shortcut_key_v2.assert_not_called()


# ── Clicking a shortcut pill ──────────────────────────────────────────────────

def test_pill_click_on_active_step_applies_shortcut():
    win = _key_window("ratings", RATING_BANKS)
    sc = RATING_BANKS["ratings"][0]
    renamer.TagWindowV2._on_shortcut_pill_click(win, "ratings", sc)
    win._handle_shortcut_key_v2.assert_called_once_with(sc)

def test_pill_click_on_other_step_does_nothing():
    win = _key_window("ratings", RATING_BANKS)
    renamer.TagWindowV2._on_shortcut_pill_click(win, "players", RATING_BANKS["players"][0])
    win._handle_shortcut_key_v2.assert_not_called()

def test_pill_click_ignored_while_typing_custom_label():
    win = _key_window("ratings", RATING_BANKS)
    win._custom_mode = True
    renamer.TagWindowV2._on_shortcut_pill_click(win, "ratings", RATING_BANKS["ratings"][0])
    win._handle_shortcut_key_v2.assert_not_called()


# ── Relabeling replaces earlier labels ────────────────────────────────────────

def test_relabel_drops_labels_from_short_base():
    record = {"base": "MBB_ND_20260101"}
    assert renamer.tag_base_stem("MBB_ND_20260101_SMITH_LAYUP_GOOD", record) == "MBB_ND_20260101"

def test_relabel_drops_labels_from_long_base():
    base = "MBB_ND_20260101_143022_AB_2H_CAM1"
    assert renamer.tag_base_stem(f"{base}_SMITH_GOOD", {"base": base}) == base

def test_clip_with_no_record_keeps_whole_name():
    assert renamer.tag_base_stem("MBB_ND_20260101_", None) == "MBB_ND_20260101"
    assert renamer.tag_base_stem("C0001", None) == "C0001"

def test_record_that_does_not_match_name_is_ignored():
    assert renamer.tag_base_stem("OTHER_NAME", {"base": "MBB_ND"}) == "OTHER_NAME"
    assert renamer.tag_base_stem("MBB_NDX_SMITH", {"base": "MBB_ND"}) == "MBB_NDX_SMITH"


# ── Selecting clips for Batch Rename ──────────────────────────────────────────

def test_batch_with_no_selection_uses_every_file():
    files = [Path("a.mp4"), Path("b.mp4")]
    assert renamer.select_batch_files(files, None) == files
    assert renamer.select_batch_files(files, set()) == files

def test_batch_with_selection_uses_only_selected():
    files = [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")]
    assert renamer.select_batch_files(files, {"a.mp4", "c.mp4"}) == [files[0], files[2]]

def test_batch_with_stale_selection_uses_nothing():
    assert renamer.select_batch_files([Path("a.mp4")], {"gone.mp4"}) == []


# ── Finder colors ─────────────────────────────────────────────────────────────

COLOR_BANKS = {
    "players": [{"key": "1", "label": "GOOD"}],
    "ratings": [
        {"key": "g", "label": "GOOD", "finder_color": "Red"},
        {"key": "r", "label": "REAX", "finder_color": "Blue"},
        {"key": "m", "label": "MISS"},
        {"key": "s", "label": "SAVE", "finder_color": "Green", "children": [
            {"key": "h", "label": "HIGH"},
            {"key": "l", "label": "LOW", "finder_color": "Purple"},
        ]},
    ],
}
COLOR_STEPS = ["players", "ratings"]

@pytest.mark.parametrize("parts, custom, expected", [
    (["SMITH", "GOOD"], set(), ["Red"]),
    (["SMITH", "REAX"], set(), ["Blue"]),
    (["SMITH", "MISS"], set(), []),
    (["SMITH", "HIGH"], set(), ["Green"]),
    (["SMITH", "LOW"], set(), ["Purple"]),
    (["SMITH", "GOOD", "JONES", "REAX"], set(), ["Red", "Blue"]),
    (["SMITH", "GOOD", "JONES", "GOOD"], set(), ["Red"]),
    (["SMITH", "GOOD"], {1}, []),
])
def test_finder_colors_for_tags(parts, custom, expected):
    assert renamer.finder_colors_for_tags(parts, custom, COLOR_BANKS, COLOR_STEPS) == expected

def test_player_bank_never_sets_a_color():
    banks = {"players": [{"key": "1", "label": "SMITH", "finder_color": "Red"}], "ratings": []}
    assert renamer.finder_colors_for_tags(["SMITH"], set(), banks, COLOR_STEPS) == []

def test_merged_tags_replace_colors_and_keep_other_tags():
    assert renamer.merged_finder_tags(["Blue", "Highlights"], ["Red"], []) == ["Highlights", "Red"]

def test_merged_tags_without_new_color_remove_only_app_colors():
    assert renamer.merged_finder_tags(["Red", "Blue"], [], ["Red"]) == ["Blue"]
    assert renamer.merged_finder_tags(["Blue"], [], []) == ["Blue"]


# ── Batch rename duplicate guard ──────────────────────────────────────────────

def test_names_ending_in_time_are_not_treated_as_duplicates():
    assert (renamer.batch_base_stem("MBB_20260101_120000_.mp4", False)
            != renamer.batch_base_stem("MBB_20260101_120501_.mp4", False))

def test_added_suffix_counts_as_a_duplicate():
    assert renamer.batch_base_stem("MBB_.mp4", False) == renamer.batch_base_stem("MBB__2.mp4", True)


# ── Rejects and Move to Trash ─────────────────────────────────────────────────

@pytest.fixture
def quiet_log(tmp_path):
    with patch.object(renamer, "RENAME_LOG_FILE", str(tmp_path / "log.json")):
        yield tmp_path / "log.json"


def _fake_trash(trash_dir):
    """Stand-in for Finder's trash call: moves the file into trash_dir."""
    def fn(path):
        dst = Path(trash_dir) / Path(path).name
        Path(path).rename(dst)
        return True, str(dst), ""
    return fn


def test_set_reject_marks_and_unmarks_without_losing_base():
    records = {"a.mp4": {"base": "A", "colors": []}}
    renamer.set_reject(records, "a.mp4", True)
    assert records["a.mp4"] == {"base": "A", "colors": [], "reject": True}
    renamer.set_reject(records, "a.mp4", False)
    assert records["a.mp4"] == {"base": "A", "colors": []}


def test_set_reject_drops_empty_record():
    records = {}
    renamer.set_reject(records, "b.mp4", True)
    assert records == {"b.mp4": {"reject": True}}
    renamer.set_reject(records, "b.mp4", False)
    assert records == {}


def test_rejected_names_only_lists_present_clips():
    records = {"a.mp4": {"reject": True}, "gone.mp4": {"reject": True},
               "c.mp4": {"base": "C"}}
    assert renamer.rejected_names(records, {"a.mp4", "c.mp4"}) == {"a.mp4"}


def test_trash_targets_prefers_selection_then_rejects():
    files = [Path("/f/a.mp4"), Path("/f/b.mp4"), Path("/f/c.mp4")]
    assert [f.name for f in renamer.trash_targets(files, {"b.mp4"}, {"c.mp4"})] == ["b.mp4"]
    assert [f.name for f in renamer.trash_targets(files, set(), {"c.mp4"})] == ["c.mp4"]
    assert renamer.trash_targets(files, set(), set()) == []


def test_trash_confirm_text_lists_five_then_counts_rest():
    title, body = renamer.trash_confirm_text([f"c{i}.mp4" for i in range(7)])
    assert title == "Move 7 clips to the Trash?"
    assert "c4.mp4" in body and "c5.mp4" not in body
    assert "+2 more" in body
    assert renamer.trash_confirm_text(["one.mp4"])[0] == "Move 1 clip to the Trash?"


def test_safe_trash_moves_file_and_logs(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    trash  = tmp_path / ".Trash"; trash.mkdir()
    clip = folder / "clip.mp4"; clip.touch()
    with patch.object(renamer, "_trash_file", _fake_trash(trash)):
        ok, path = SafeRenamer.safe_trash(clip, folder)
    assert ok and Path(path) == trash / "clip.mp4"
    assert not clip.exists()
    entry = renamer.json.loads(quiet_log.read_text().splitlines()[-1])
    assert entry["action"] == "trash" and entry["success"]


def test_safe_trash_refuses_files_it_could_not_rename(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    notes = folder / "notes.txt"; notes.touch()
    called = []
    with patch.object(renamer, "_trash_file", lambda p: called.append(p)):
        ok, reason = SafeRenamer.safe_trash(notes, folder)
    assert not ok and "extension" in reason
    assert called == [] and notes.exists()


def test_safe_trash_never_deletes_when_volume_has_no_trash(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    clip = folder / "clip.mp4"; clip.touch()
    with patch.object(renamer, "_trash_file",
                      lambda p: (False, "", "this drive has no Trash")):
        ok, reason = SafeRenamer.safe_trash(clip, folder)
    assert not ok and "no Trash" in reason
    assert clip.exists()


def test_safe_restore_round_trip(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    trash  = tmp_path / ".Trash"; trash.mkdir()
    clip = folder / "clip.mp4"; clip.write_text("x")
    with patch.object(renamer, "_trash_file", _fake_trash(trash)):
        _, path = SafeRenamer.safe_trash(clip, folder)
    ok, err = SafeRenamer.safe_restore(Path(path), folder / "clip.mp4", folder)
    assert ok, err
    assert clip.read_text() == "x"


def test_safe_restore_never_overwrites(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    trash  = tmp_path / ".Trash"; trash.mkdir()
    (trash / "clip.mp4").write_text("old")
    (folder / "clip.mp4").write_text("new")
    ok, err = SafeRenamer.safe_restore(trash / "clip.mp4", folder / "clip.mp4", folder)
    assert not ok and "already" in err
    assert (folder / "clip.mp4").read_text() == "new"
    assert (trash / "clip.mp4").exists()


def test_safe_restore_only_moves_out_of_trash(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    elsewhere = tmp_path / "other"; elsewhere.mkdir()
    (elsewhere / "clip.mp4").touch()
    ok, err = SafeRenamer.safe_restore(elsewhere / "clip.mp4", folder / "clip.mp4", folder)
    assert not ok and "not in the Trash" in err


def test_safe_restore_stays_inside_folder(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    (folder / "sub").mkdir()
    trash  = tmp_path / ".Trash"; trash.mkdir()
    (trash / "clip.mp4").touch()
    ok, err = SafeRenamer.safe_restore(trash / "clip.mp4", folder / "sub" / "clip.mp4", folder)
    assert not ok and "boundary" in err


def test_undo_op_available_for_trash_entries(tmp_path):
    present = tmp_path / "a.mp4"; present.touch()
    op = {"type": "trash", "items": [{"name": "a.mp4", "trash_path": str(present)}]}
    assert renamer.undo_op_available(op)
    present.unlink()
    assert not renamer.undo_op_available(op)


def _trash_app(tmp_path):
    app = renamer.BasketballRenamerApp.__new__(renamer.BasketballRenamerApp)
    app.session = {}
    app._refresh_undo_item = lambda: None
    app._refresh_tag_window_files = lambda: None
    return app


def test_trash_clips_and_undo_restore_records(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    trash  = tmp_path / ".Trash"; trash.mkdir()
    a = folder / "a.mp4"; a.touch()
    b = folder / "b.mp4"; b.touch()
    records_file = tmp_path / "records.json"
    records_file.write_text(renamer.json.dumps(
        {"a.mp4": {"base": "A", "reject": True}, "b.mp4": {"base": "B"}}))
    undo_file = tmp_path / "undo.json"
    app = _trash_app(tmp_path)
    with patch.multiple(renamer, TAG_RECORDS_FILE=str(records_file),
                        UNDO_FILE=str(undo_file),
                        SETTINGS_FILE=str(tmp_path / "settings.json"),
                        _trash_file=_fake_trash(trash)), \
         patch.object(renamer.rumps, "alert", MagicMock(return_value=True), create=True):
        assert app.trash_clips([a], folder, confirm=False) == 1
        assert not a.exists() and (trash / "a.mp4").exists()
        records = renamer.json.loads(records_file.read_text())
        assert "a.mp4" not in records and "b.mp4" in records
        stack = renamer.json.loads(undo_file.read_text())
        assert stack[-1]["type"] == "trash"

        app.undo_last(None)
        assert a.exists() and not (trash / "a.mp4").exists()
        records = renamer.json.loads(records_file.read_text())
        assert records["a.mp4"] == {"base": "A", "reject": True}
        assert renamer.json.loads(undo_file.read_text()) == []


def test_trash_clips_cancelled_moves_nothing(tmp_path, quiet_log):
    folder = tmp_path / "clips"; folder.mkdir()
    a = folder / "a.mp4"; a.touch()
    app = _trash_app(tmp_path)
    with patch.object(renamer, "_confirm_trash_alert", lambda names: False), \
         patch.object(renamer, "_trash_file", MagicMock()) as tf:
        assert app.trash_clips([a], folder) == 0
    tf.assert_not_called()
    assert a.exists()


# ── Keeping the file lists in sync with Finder ────────────────────────────────

def test_match_renames_follows_inode_to_new_name():
    old = {"a.mp4": 1, "b.mp4": 2, "c.mp4": 3}
    new = {"a.mp4": 1, "b_LAYUP.mp4": 2, "d.mp4": 4}
    assert renamer.match_renames(old, new) == {"b.mp4": "b_LAYUP.mp4"}


def test_match_renames_ignores_deletes_and_additions():
    assert renamer.match_renames({"a.mp4": 1}, {"b.mp4": 2}) == {}
    assert renamer.match_renames({}, {"b.mp4": 2}) == {}


def test_match_renames_ignores_name_swaps_onto_existing_names():
    # b's inode now sits under a name that already existed: not a clean rename
    old = {"a.mp4": 1, "b.mp4": 2}
    new = {"a.mp4": 2}
    assert renamer.match_renames(old, new) == {}


def test_move_records_for_renames_keeps_labels_and_rejects():
    records = {"b.mp4": {"base": "B", "colors": ["Red"], "reject": True}}
    assert renamer.move_records_for_renames(records, {"b.mp4": "b2.mp4"})
    assert records == {"b2.mp4": {"base": "B", "colors": ["Red"], "reject": True}}


def test_move_records_for_renames_never_overwrites():
    records = {"b.mp4": {"base": "B"}, "b2.mp4": {"base": "OTHER"}}
    assert not renamer.move_records_for_renames(records, {"b.mp4": "b2.mp4"})
    assert records["b2.mp4"] == {"base": "OTHER"}


def test_pick_selection_stays_on_same_clip_when_rows_shift():
    # A clip added above the selection must not move the selection to another clip
    assert renamer.pick_selection(["a.mp4", "aa.mp4", "b.mp4"], "b.mp4", {}, 1) == 2


def test_pick_selection_follows_rename():
    names = ["a.mp4", "b_LAYUP.mp4"]
    assert renamer.pick_selection(names, "b.mp4", {"b.mp4": "b_LAYUP.mp4"}, 1) == 1


def test_pick_selection_clamps_when_clip_is_gone():
    assert renamer.pick_selection(["a.mp4", "c.mp4"], "z.mp4", {}, 5) == 1
    assert renamer.pick_selection(["a.mp4", "c.mp4"], "b.mp4", {}, 1) == 1


def test_pick_selection_empty_or_nothing_selected():
    assert renamer.pick_selection([], "a.mp4", {}, 0) == -1
    assert renamer.pick_selection(["a.mp4"], None, {}, -1) == -1


# ── Per-sport steps, stats by step, custom sports ─────────────────────────────

def _fresh_session(**extra):
    s = {"sport": "MBB", "custom_steps": [{"id": "plays", "label": "Play"},
                                          {"id": "ratings", "label": "Rating"}]}
    s.update(extra)
    return s


def test_sport_steps_falls_back_to_legacy_list():
    s = _fresh_session()
    assert [x["id"] for x in renamer.sport_steps(s, "WBB")] == ["players", "plays", "ratings"]


def test_own_sport_steps_changes_only_that_sport():
    s = _fresh_session()
    own = renamer.own_sport_steps(s, "MBB")
    own.insert(2, {"id": "zone", "label": "Zone"})
    assert [x["id"] for x in renamer.sport_steps(s, "MBB")] == ["players", "plays", "zone", "ratings"]
    assert [x["id"] for x in renamer.sport_steps(s, "WBB")] == ["players", "plays", "ratings"]
    assert s["custom_steps"] == [{"id": "plays", "label": "Play"}, {"id": "ratings", "label": "Rating"}]


def test_stat_rows_player_first():
    rows = renamer.stat_rows_for_segment(
        ["SMITH", "LAYUP", "GOOD"], ["players", "plays", "ratings"],
        ["players", "plays", "ratings"], {"plays": "Play", "ratings": "Rating"})
    assert rows == [("SMITH", "LAYUP", "GOOD", {"Play": "LAYUP", "Rating": "GOOD"})]


def test_stat_rows_skipped_step_and_extra_step():
    order = ["players", "plays", "zone", "ratings"]
    rows = renamer.stat_rows_for_segment(["SMITH", "PAINT", "GOOD"],
                                         ["players", "zone", "ratings"], order)
    assert rows[0][:3] == ("SMITH", "PAINT", "GOOD")
    # Rating step skipped: the rating stays empty instead of taking the play
    rows = renamer.stat_rows_for_segment(["SMITH", "LAYUP"], ["players", "plays"], order)
    assert rows[0][:3] == ("SMITH", "LAYUP", "")


def test_stat_rows_player_moved_and_multiple_players():
    order = ["plays", "players", "ratings"]
    rows = renamer.stat_rows_for_segment(
        ["LAYUP", "SMITH", "JONES", "GOOD"], ["plays", "players", "players", "ratings"], order)
    assert [r[:3] for r in rows] == [("SMITH", "LAYUP", "GOOD"), ("JONES", "LAYUP", "GOOD")]


def test_stat_rows_player_off():
    rows = renamer.stat_rows_for_segment(["SERVE", "ACE"], ["plays", "ratings"], ["plays", "ratings"])
    assert rows[0][:3] == ("", "SERVE", "ACE")
    assert renamer.stat_rows_for_segment([], [], ["plays"]) == []


def test_custom_sport_registry_and_lookup():
    try:
        renamer.set_custom_sports([{"code": "mrug", "name": "Men's Rugby", "slug": "/mens-rugby/"},
                                   {"code": "MBB", "name": "Clash"},
                                   {"code": "MRUG", "name": "Dup"}])
        sports = renamer.all_sports()
        assert list(sports)[:len(renamer.SPORTS)] == list(renamer.SPORTS)
        assert sports["MRUG"]["custom"] and sports["MRUG"]["name"] == "Men's Rugby"
        assert sports["MRUG"]["emoji"] == renamer.DEFAULT_SPORT_EMOJI
        assert renamer.sport_slug("MRUG") == "mens-rugby"
        assert sports["MBB"]["custom"] is False
        assert renamer.sport_slug("MSOC") == "mens-soccer"
        assert renamer.sport_info("NOPE")["name"] == "NOPE"
    finally:
        renamer.set_custom_sports([])


def test_suggest_and_validate_sport_code():
    taken = set(renamer.SPORTS)
    assert renamer.suggest_sport_code("Men's Rugby", taken) == "MRUG"
    assert renamer.suggest_sport_code("Curling", taken) == "CURL"
    assert renamer.suggest_sport_code("Men's Soccer", taken) == "MSOC2"
    assert renamer.suggest_sport_code("", taken) == "SPORT"
    assert renamer.validate_sport_code("MRUG", taken) == ""
    assert renamer.validate_sport_code("MBB", taken)
    assert renamer.validate_sport_code("toolong7", taken)
    assert renamer.validate_sport_code("A B", taken)
    assert renamer.validate_sport_code("", taken)


def test_create_custom_sport_blank_and_copy():
    try:
        s = _fresh_session()
        data = {"MBB": {"players": [{"key": "1", "label": "SMITH"}],
                        "plays": [{"key": "a", "label": "LAYUP"}], "ratings": []}}
        renamer.create_custom_sport(s, data, {"code": "CURL", "name": "Curling"})
        assert [x["id"] for x in renamer.sport_steps(s, "CURL")] == ["players", "plays", "ratings"]
        assert data["CURL"] == {"players": [], "plays": [], "ratings": []}
        renamer.own_sport_steps(s, "MBB").insert(2, {"id": "zone", "label": "Zone"})
        data["MBB"]["zone"] = [{"key": "z", "label": "PAINT"}]
        renamer.create_custom_sport(s, data, {"code": "MB2", "name": "Copy"}, copy_from="MBB")
        assert [x["id"] for x in renamer.sport_steps(s, "MB2")] == ["players", "plays", "zone", "ratings"]
        assert data["MB2"]["players"] == []          # roster never copied
        assert data["MB2"]["zone"] == [{"key": "z", "label": "PAINT"}]
        data["MB2"]["zone"].append({"key": "y", "label": "WING"})
        assert len(data["MBB"]["zone"]) == 1         # deep copy
        assert set(renamer.all_sports()) >= {"CURL", "MB2"}
    finally:
        renamer.set_custom_sports([])


def test_remove_and_update_custom_sport():
    try:
        s = _fresh_session(sport_presets={"CURL": [{"name": "x"}], "MBB": []})
        data = {}
        renamer.create_custom_sport(s, data, {"code": "CURL", "name": "Curling"})
        assert renamer.update_custom_sport(s, "CURL", name="Ice Curling", emoji="", slug="/curling/")
        info = renamer.sport_info("CURL")
        assert (info["name"], info["emoji"], info["slug"]) == ("Ice Curling", renamer.DEFAULT_SPORT_EMOJI, "curling")
        rosters, meta, keyp = {"CURL": [1], "MBB": [2]}, {"CURL": "t"}, {"CURL": []}
        assert renamer.remove_custom_sport(s, data, rosters, meta, keyp, "CURL")
        assert "CURL" not in renamer.all_sports()
        assert "CURL" not in s["sport_steps"] and "CURL" not in data
        assert rosters == {"MBB": [2]} and meta == {} and keyp == {}
        assert s["sport_presets"] == {"MBB": []}
        assert not renamer.remove_custom_sport(s, data, rosters, meta, keyp, "MBB")
    finally:
        renamer.set_custom_sports([])


def test_stat_segments_split_and_skip_custom_text():
    segs = renamer.stat_segments(["SMITH", "LAYUP", "NOTE", "JONES", "DUNK"],
                                 ["players", "plays", "plays", "players", "plays"],
                                 {2}, [3], ["players", "plays", "ratings"])
    assert segs == [(["SMITH", "LAYUP"], ["players", "plays"]),
                    (["JONES", "DUNK"], ["players", "plays"])]


def test_stat_segments_share_steps_before_player():
    order = ["plays", "players", "zone", "ratings"]
    segs = renamer.stat_segments(["LAYUP", "SMITH", "JONES", "PAINT", "GOOD"],
                                 ["plays", "players", "players", "zone", "ratings"],
                                 set(), [2], order)
    assert segs[1] == (["LAYUP", "JONES", "PAINT", "GOOD"],
                       ["plays", "players", "zone", "ratings"])
    rows = renamer.stat_rows_for_segment(*segs[1], order)
    assert rows[0][:3] == ("JONES", "LAYUP_PAINT", "GOOD")


# ── Clip info columns ────────────────────────────────────────────────────────

@pytest.mark.parametrize("frame,quanta,drop,expected", [
    (0, 25, False, "00:00:00:00"),
    (900012, 25, False, "10:00:00:12"),
    (0, 30, True, "00:00:00;00"),
    (1799, 30, True, "00:00:59;29"),
    (1800, 30, True, "00:01:00;02"),       # ;00 and ;01 are dropped
    (17982, 30, True, "00:10:00;00"),      # every tenth minute keeps them
    (111582, 30, True, "01:02:03;04"),
    (3598, 60, True, "00:00:59;58"),
    (3600, 60, True, "00:01:00;04"),       # 60 fps drops four
    (1800, 30, False, "00:01:00:00"),
    (1800, 24, True, "00:01:15:00"),       # drop-frame only applies to 30/60
])
def test_frames_to_timecode(frame, quanta, drop, expected):
    assert renamer.frames_to_timecode(frame, quanta, drop) == expected


def test_frames_to_timecode_bad_input():
    assert renamer.frames_to_timecode(None, 30) == ""
    assert renamer.frames_to_timecode(10, 0) == ""
    assert renamer.frames_to_timecode(-1, 30) == ""


@pytest.mark.parametrize("fps,expected", [
    (23.976024627685547, "23.976"), (29.970029830932617, "29.97"), (59.94, "59.94"),
    (60.0, "60"), (25, "25"), (119.88, "119.88"), (12.5, "12.5"), (0, ""), (None, ""),
])
def test_format_fps(fps, expected):
    assert renamer.format_fps(fps) == expected


@pytest.mark.parametrize("secs,expected", [
    (0, "0:00"), (3.003, "0:03"), (62.9, "1:02"), (3725, "1:02:05"), (None, ""), (-1, ""),
])
def test_format_duration(secs, expected):
    assert renamer.format_duration(secs) == expected


@pytest.mark.parametrize("n,expected", [
    (512, "512 bytes"), (2_446_999, "2.4 MB"), (1_200_000_000, "1.2 GB"),
    (150_000_000, "150 MB"), (None, ""),
])
def test_format_bytes(n, expected):
    assert renamer.format_bytes(n) == expected


def test_file_info_value_loading_and_missing():
    assert renamer.file_info_value(None, "fps") == "…"
    assert renamer.file_info_value({}, "timecode") == "—"
    assert renamer.file_info_value({"has_audio": False}, "audio") == "None"


def test_file_info_value_fields():
    info = {"duration": 42.2, "fps": 29.97, "width": 1080, "height": 1920,
            "codec": "hvc1", "hdr": True, "tc_frame": 111582, "tc_quanta": 30,
            "tc_drop": True, "audio_channels": 2, "audio_rate": 48000.0,
            "size": 2_446_999, "recorded": datetime(2026, 11, 13, 19, 42)}
    v = lambda c: renamer.file_info_value(info, c)
    assert v("duration") == "0:42"
    assert v("timecode") == "01:02:03;04"
    assert v("resolution") == "1080×1920"
    assert v("codec") == "HEVC HDR"
    assert v("audio") == "2 ch · 48 kHz"
    assert v("recorded") == "Nov 13, 2026  19:42"
    assert renamer.file_info_value({"codec": "zzzz"}, "codec") == "ZZZZ"


def test_normalize_column_prefs():
    assert renamer.normalize_column_prefs(None) == {"visible": [], "widths": {}}
    p = renamer.normalize_column_prefs({
        "visible": ["size", "bogus", "duration"],
        "widths": {"size": 5, "fps": 9999, "duration": "wide", "bogus": 50, "codec": True}})
    assert p["visible"] == ["duration", "size"]       # canonical order, unknown dropped
    assert p["widths"] == {"size": renamer.FILE_INFO_MIN_W, "fps": renamer.FILE_INFO_MAX_W}


def test_toggle_info_column():
    p = renamer.toggle_info_column({"visible": ["fps"], "widths": {"fps": 60}}, "duration")
    assert p == {"visible": ["duration", "fps"], "widths": {"fps": 60}}
    p = renamer.toggle_info_column(p, "fps")
    assert p["visible"] == ["duration"] and p["widths"] == {"fps": 60}
    assert renamer.toggle_info_column(p, "nope")["visible"] == ["duration"]


def test_media_info_key_survives_rename(tmp_path):
    f = tmp_path / "a.mov"
    f.write_bytes(b"x" * 10)
    k1 = renamer.media_info_key(f)
    g = tmp_path / "b.mov"
    f.rename(g)   # test fixture only, not a clip
    assert renamer.media_info_key(g) == k1
    assert renamer.media_info_key(tmp_path / "missing.mov") is None


def test_clip_media_info_never_raises(tmp_path):
    f = tmp_path / "x.mov"
    f.write_bytes(b"not a movie")
    info = renamer.clip_media_info(f)    # AVFoundation is stubbed here
    assert info["size"] == 11 and info["duration"] is None and info["recorded"] is not None


# ── Sorting the file list ────────────────────────────────────────────────────

@pytest.mark.parametrize("sort,expected", [
    ("name_asc", ("name", True)), ("name_desc", ("name", False)),
    ("duration_desc", ("duration", False)), ("recorded_asc", ("recorded", True)),
    ("date_created", ("date_created", True)), ("bogus_asc", ("name", True)),
    (None, ("name", True)), ("", ("name", True)),
])
def test_parse_sort_order(sort, expected):
    assert renamer.parse_sort_order(sort) == expected


def test_next_sort_order():
    assert renamer.next_sort_order("name_asc", "name") == "name_desc"
    assert renamer.next_sort_order("name_desc", "name") == "name_asc"
    assert renamer.next_sort_order("name_desc", "duration") == "duration_asc"
    assert renamer.next_sort_order("duration_asc", "duration") == "duration_desc"
    assert renamer.next_sort_order("date_created", "name") == "name_asc"


def test_sort_order_label():
    assert renamer.sort_order_label("name_desc") == "Name Z → A"
    assert renamer.sort_order_label("timecode_asc") == "Timecode ↑"
    assert renamer.sort_order_label("fps_desc") == "FPS ↓"


class _St:
    def __init__(self, size=0, mtime=0.0, birth=0.0):
        self.st_size, self.st_mtime, self.st_birthtime = size, mtime, birth


def _entries(*specs):
    return [(Path(n), _St(**kw)) for n, kw in specs]


def test_sort_file_entries_by_name_and_dates():
    e = _entries(("b.mov", {"mtime": 1, "birth": 3}), ("a.mov", {"mtime": 2, "birth": 2}),
                 ("c.mov", {"mtime": 3, "birth": 1}))
    names = lambda es: [p.name for p, _ in es]
    assert names(renamer.sort_file_entries(e, "name_asc")) == ["a.mov", "b.mov", "c.mov"]
    assert names(renamer.sort_file_entries(e, "name_desc")) == ["c.mov", "b.mov", "a.mov"]
    assert names(renamer.sort_file_entries(e, "date_created")) == ["c.mov", "a.mov", "b.mov"]
    assert names(renamer.sort_file_entries(e, "date_modified")) == ["b.mov", "a.mov", "c.mov"]


def test_sort_file_entries_by_info_unknown_last():
    e = _entries(("a.mov", {}), ("b.mov", {}), ("c.mov", {}), ("d.mov", {}))
    info = {"a.mov": {"duration": 30.0}, "b.mov": None, "c.mov": {"duration": 5.0},
            "d.mov": {"duration": 30.0}}
    lookup = lambda p, st: info[p.name]
    names = lambda es: [p.name for p, _ in es]
    assert names(renamer.sort_file_entries(e, "duration_asc", lookup)) == ["c.mov", "a.mov", "d.mov", "b.mov"]
    # descending keeps the unknown clip last and ties in name order
    assert names(renamer.sort_file_entries(e, "duration_desc", lookup)) == ["a.mov", "d.mov", "c.mov", "b.mov"]


def test_sort_file_entries_by_size_and_timecode():
    e = _entries(("a.mov", {"size": 30}), ("b.mov", {"size": 10}), ("c.mov", {"size": 20}))
    names = lambda es: [p.name for p, _ in es]
    assert names(renamer.sort_file_entries(e, "size_desc")) == ["a.mov", "c.mov", "b.mov"]
    tc = {"a.mov": {"tc_frame": 90000, "tc_quanta": 25},     # 01:00:00:00
          "b.mov": {"tc_frame": 1800, "tc_quanta": 30},      # 00:01:00
          "c.mov": {"tc_frame": None}}
    assert names(renamer.sort_file_entries(e, "timecode_asc", lambda p, st: tc[p.name])) == \
        ["b.mov", "a.mov", "c.mov"]


def test_file_list_densities_shape():
    assert set(renamer.FILE_LIST_DENSITIES) == {"compact", "normal", "comfortable"}
    heights = [renamer.FILE_LIST_DENSITIES[k][0] for k in ("compact", "normal", "comfortable")]
    assert heights == sorted(heights) and renamer.FILE_LIST_DENSITIES["normal"][0] == 26.0


# ── Fitting the file list beside the Log Mode cards ──────────────────────────

COLS = [("duration", 62), ("timecode", 90), ("fps", 52)]


def test_fit_file_list_keeps_preferred_when_it_fits():
    assert renamer.fit_file_list(450, 600, COLS) == (450, ["duration", "timecode", "fps"])
    assert renamer.fit_file_list(450, 450, COLS) == (450, ["duration", "timecode", "fps"])


def test_fit_file_list_drops_columns_from_the_right_first():
    # 170 name + 24 chrome + (62+3) + (90+3) + (52+3) = 407
    assert renamer.fit_file_list(450, 407, COLS) == (407, ["duration", "timecode", "fps"])
    assert renamer.fit_file_list(450, 406, COLS) == (406, ["duration", "timecode"])
    assert renamer.fit_file_list(450, 300, COLS) == (300, ["duration"])
    assert renamer.fit_file_list(450, 258, COLS) == (258, [])


def test_fit_file_list_never_below_minimum():
    w, shown = renamer.fit_file_list(450, 90, COLS)
    assert w == renamer.FILE_LIST_MIN_W and shown == []
    assert renamer.fit_file_list(260, 100, []) == (renamer.FILE_LIST_MIN_W, [])


# ── Step circle scaling ──────────────────────────────────────────────────────

def test_step_circle_scale_default_size_unchanged():
    assert renamer.step_circle_scale(390, 220, 3) == 1.0


def test_step_circle_scale_grows_with_the_card_and_is_capped():
    assert renamer.step_circle_scale(390, 300, 3) > 1.0
    assert renamer.step_circle_scale(2000, 2000, 3) == 1.75


def test_step_circle_scale_limited_by_width_and_steps():
    tall = 500
    assert renamer.step_circle_scale(300, tall, 3) < renamer.step_circle_scale(390, tall, 3)
    assert renamer.step_circle_scale(390, tall, 6) < renamer.step_circle_scale(390, tall, 3)
    assert renamer.step_circle_scale(100, 100, 8) == 0.85     # floor
    assert renamer.step_circle_scale(390, 220, 0) == 1.0      # no steps doesn't divide by zero


# ── Update check ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("latest,current,newer", [
    ("1.0.7", "1.0.6", True), ("v1.0.7", "1.0.6", True), ("1.0.6", "1.0.6", False),
    ("1.0.10", "1.0.9", True), ("1.0.5", "1.0.6", False), ("1.1", "1.0.9", True),
    ("garbage", "1.0.6", False),
])
def test_is_newer_version(latest, current, newer):
    assert renamer.is_newer_version(latest, current) is newer
