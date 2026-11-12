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
