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
