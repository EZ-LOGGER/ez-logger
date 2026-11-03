#!/usr/bin/env python3
"""
Basketball File Renamer v3
--------------------------
3-step logging flow:  Player → Play Description → Rating
Final filename: SPORT_OPPONENT_YYYYMMDD_HHMMSS_VID_PHASE_PLAYER_PLAY_RATING.ext
Player is optional — press ENTER to skip.
"""

import rumps
import json
import os
import re
import subprocess
import threading
import urllib.request
from pathlib import Path
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
CONFIG_FILE    = os.path.expanduser("~/.bball_renamer_v3_config.json")
SHORTCUTS_FILE = os.path.expanduser("~/.bball_renamer_v3_shortcuts.json")
SETTINGS_FILE  = os.path.expanduser("~/.bball_renamer_v3_settings.json")
UNDO_FILE      = os.path.expanduser("~/.bball_renamer_undo.json")
ROSTERS_FILE   = os.path.expanduser("~/.bball_renamer_v3_rosters.json")
STATS_FILE     = os.path.expanduser("~/.bball_renamer_v3_stats.json")
RENAME_LOG_FILE  = os.path.expanduser("~/.ezlogger/rename_log.json")
KEY_PRESETS_FILE = os.path.expanduser("~/.bball_renamer_v3_key_presets.json")

DEFAULT_SETTINGS = {
    "player_search_mode":      False,
    "player_number_search":    False,
    "roster_base_url":         "",
    # Log Mode
    "auto_advance_after_tag":  True,
    "file_sort_order":         "name_asc",
    "search_mode_threshold":   0,
    "arm_on_file_select":      False,
    # Rename
    "show_rename_preview":     True,
    "conflict_behavior":       "ask",
    "preserve_ext_case":       False,
    # Display
    "show_jersey_numbers":     True,
    "pill_density":            "auto",
    "file_list_width":         260,
    # Stats
    "record_stats":            True,
    "stats_scope":             "all_time",
    # Roster
    "auto_fetch_roster":       False,
    "roster_cache_days":       7,
    # System
    "show_in_dock":            True,
    "launch_at_login":         False,
    "auto_open_on_launch":     True,
    "sound_on_rename":         False,
    # Undo
    "undo_stack_size":         50,
}

# Maps athletics site URL slugs to internal sport codes
SLUG_TO_CODE = {
    "mens-basketball":   "MBB",
    "womens-basketball": "WBB",
    "mens-ice-hockey":   "MHK",
    "womens-ice-hockey": "WHK",
    "football":          "FB",
    "womens-lacrosse":   "WLAX",
    "baseball":          "BASE",
    "softball":          "SB",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".m4v", ".mxf", ".mpg", ".mpeg", ".mkv"}
PHASE_OPTIONS    = ["PRE","1H","2H","OT","POST","PRAC","SCOUT"]

DATE_FORMATS = [
    ("YYYYMMDD",   "%Y%m%d"),
    ("YYYY-MM-DD", "%Y-%m-%d"),
    ("MM-DD-YYYY", "%m-%d-%Y"),
    ("MMDDYYYY",   "%m%d%Y"),
    ("DD-MM-YYYY", "%d-%m-%Y"),
]
TIME_FORMATS = [
    ("HHMMSS",   "%H%M%S"),
    ("HH-MM-SS", "%H-%M-%S"),
    ("HH:MM:SS", "%H:%M:%S"),
]
METADATA_FIELDS = [
    ("date_created", "Date Created"),
    ("time_created", "Time Created"),
]
DEFAULT_NAMING_PRESETS = [{"name": "Default", "separator": "_", "fields": []}]

# ── Team abbreviation lookup (Power 6 + common independents) ──────────────────
TEAM_ABBREVS = {
    # ACC
    "Boston College": "BC", "Clemson": "CLEM", "Duke": "DUKE",
    "Florida State": "FSU", "Georgia Tech": "GT", "Louisville": "LOU",
    "Miami": "MIA", "NC State": "NCST", "North Carolina": "UNC",
    "Notre Dame": "ND", "Pittsburgh": "PITT", "Stanford": "STAN",
    "Syracuse": "SYR", "Virginia": "UVA", "Virginia Tech": "VT",
    "Wake Forest": "WAKE", "California": "CAL", "SMU": "SMU",
    # Big Ten
    "Illinois": "ILL", "Indiana": "IND", "Iowa": "IOWA",
    "Maryland": "UMD", "Michigan": "MICH", "Michigan State": "MSU",
    "Minnesota": "MINN", "Nebraska": "NEB", "Northwestern": "NW",
    "Ohio State": "OSU", "Penn State": "PSU", "Purdue": "PUR",
    "Rutgers": "RUT", "Wisconsin": "WIS", "UCLA": "UCLA",
    "USC": "USC", "Oregon": "ORE", "Washington": "WASH",
    # Big 12
    "Arizona": "ARIZ", "Arizona State": "ASU", "Baylor": "BAY",
    "BYU": "BYU", "Cincinnati": "CIN", "Colorado": "COLO",
    "Houston": "HOU", "Iowa State": "ISU", "Kansas": "KU",
    "Kansas State": "KSU", "Oklahoma State": "OKST", "TCU": "TCU",
    "Texas Tech": "TTU", "UCF": "UCF", "Utah": "UTAH",
    "West Virginia": "WVU",
    # SEC
    "Alabama": "ALA", "Arkansas": "ARK", "Auburn": "AUB",
    "Florida": "UFL", "Georgia": "UGA", "Kentucky": "UK",
    "LSU": "LSU", "Mississippi State": "MSST", "Missouri": "MIZ",
    "Ole Miss": "MISS", "South Carolina": "SCAR", "Tennessee": "TENN",
    "Texas A&M": "TAMU", "Texas": "TEX", "Vanderbilt": "VAN",
    "Oklahoma": "OU",
    # AAC
    "Charlotte": "CHAR", "East Carolina": "ECU", "FAU": "FAU",
    "Florida Atlantic": "FAU", "Memphis": "MEM", "Navy": "NAVY",
    "North Texas": "UNT", "Rice": "RICE", "South Florida": "USF",
    "Temple": "TEMP", "Tulane": "TUL", "Tulsa": "TLSA",
    "UTSA": "UTSA", "UAB": "UAB", "Wichita State": "WSU",
    # Mountain West
    "Air Force": "AF", "Boise State": "BSU", "Colorado State": "CSU",
    "Fresno State": "FRES", "Hawaii": "HAW", "Nevada": "NEV",
    "New Mexico": "UNM", "San Diego State": "SDSU",
    "San Jose State": "SJSU", "UNLV": "UNLV", "Utah State": "USU",
    "Wyoming": "WYO",
    # Independents & common opponents
    "Army": "ARMY", "Connecticut": "UCONN", "UConn": "UCONN",
    "Liberty": "LIB", "Massachusetts": "UMASS", "UMass": "UMASS",
    "New Mexico State": "NMST", "James Madison": "JMU",
    "Old Dominion": "ODU", "Kennesaw State": "KSU",
    # Ivy League
    "Harvard": "HARV", "Yale": "YALE", "Princeton": "PRIN",
    "Penn": "PENN", "Columbia": "COL", "Cornell": "CORN",
    "Brown": "BRWN", "Dartmouth": "DART",
    # Other common lax / hockey / basketball opponents
    "Albany": "ALB", "UAlbany": "ALB", "Loyola Maryland": "LOYO",
    "Fordham": "FORD", "Seton Hall": "SHU", "Georgetown": "GTWN",
    "Villanova": "NOVA", "Xavier": "XAV", "Marquette": "MU",
    "Providence": "PROV", "DePaul": "DEP", "St. John's": "STJ",
    "Creighton": "CREI", "Butler": "BUT", "UConn": "UCONN",
    "Denver": "DEN", "Ohio": "OHIO", "Colgate": "COLG",
    "Towson": "TOW", "Stony Brook": "SBU", "Vermont": "UVM",
    "New Hampshire": "UNH", "Maine": "ME", "Delaware": "DEL",
    "Drexel": "DREX", "Hofstra": "HOF", "William & Mary": "WM",
    "Elon": "ELON", "Coastal Carolina": "CCU", "Campbell": "CAM",
    "High Point": "HPU", "North Carolina A&T": "NCAT",
    "Jacksonville": "JAX", "Richmond": "RICH", "Lehigh": "LEH",
    "Bucknell": "BUCK", "Holy Cross": "HC", "Marist": "MAR",
    "Fairfield": "FAIR", "Quinnipiac": "QUIN", "Manhattan": "MAN",
    "Florida Gulf Coast": "FGCU", "Mercer": "MERC",
    "College of Charleston": "CHSN", "Furman": "FUR",
    "Wofford": "WOF", "Samford": "SAM", "Chattanooga": "UTC",
}

# ── Sport definitions ─────────────────────────────────────────────────────────
SPORTS = {
    "MBB":   {"label": "🏀  Men's Basketball",    "code": "MBB",   "emoji": "🏀", "url": "https://bceagles.com/sports/mens-basketball/roster"},
    "WBB":   {"label": "🏀  Women's Basketball",  "code": "WBB",   "emoji": "🏀", "url": "https://bceagles.com/sports/womens-basketball/roster"},
    "MHK":   {"label": "🏒  Men's Ice Hockey",    "code": "MHK",   "emoji": "🏒", "url": "https://bceagles.com/sports/mens-ice-hockey/roster"},
    "WHK":   {"label": "🏒  Women's Ice Hockey",  "code": "WHK",   "emoji": "🏒", "url": "https://bceagles.com/sports/womens-ice-hockey/roster"},
    "FB":    {"label": "🏈  Football",             "code": "FB",    "emoji": "🏈", "url": "https://bceagles.com/sports/football/roster"},
    "WLAX":  {"label": "🥍  Women's Lacrosse",    "code": "WLAX",  "emoji": "🥍", "url": "https://bceagles.com/sports/womens-lacrosse/roster"},
    "BASE":  {"label": "⚾  Baseball",             "code": "BASE",  "emoji": "⚾", "url": "https://bceagles.com/sports/baseball/roster"},
    "SB":    {"label": "🥎  Softball",             "code": "SB",    "emoji": "🥎", "url": "https://bceagles.com/sports/softball/roster"},
}
SPORT_OPTIONS = list(SPORTS.keys())

DEFAULT_SESSION = {
    "sport": "MBB", "opponent": "MIAMI",
    "videographer": "ZK", "phase": "PRE", "folder": "",
    "naming_presets": DEFAULT_NAMING_PRESETS,
    "active_preset": 0,
    "sport_presets": {},
    "custom_steps": [
        {"id": "plays",   "label": "Play"},
        {"id": "ratings", "label": "Rating"},
    ],
}

DEFAULT_SHORTCUTS = {
    "players": [
        {"key": "1", "label": "HAND"},
        {"key": "2", "label": "HASTINGS"},
        {"key": "3", "label": "SMITH"},
    ],
    "plays": [
        {"key": "1", "label": "LAYUP"},
        {"key": "2", "label": "THREE"},
        {"key": "3", "label": "POST UP"},
        {"key": "4", "label": "DRIVE"},
        {"key": "5", "label": "CLOSE UP"},
    ],
    "ratings": [
        {"key": "1", "label": "GOOD"},
        {"key": "2", "label": "MISS"},
        {"key": "3", "label": "FOUL"},
        {"key": "4", "label": "TO"},
    ],
}

# ── Brand colors  (#8c2232 crimson, #dbcca6 tan) ─────────────────────────────
def _parse_hex(hex_str: str):
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def _hex_color(hex_str: str):
    from AppKit import NSColor
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(*_parse_hex(hex_str), 1.0)

def _hex_color_alpha(hex_str: str, alpha: float):
    from AppKit import NSColor
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(*_parse_hex(hex_str), alpha)

COLOR_CRIMSON   = "#8c2232"   # step headers, armed indicator, success
COLOR_TAN       = "#dbcca6"   # active legend highlight, step label
COLOR_CRIMSON_D = "#6b1a26"   # darker variant for secondary use

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)   # atomic on macOS — old file survives if interrupted
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

def _save_setting(key, value):
    """Read-modify-write a single key in SETTINGS_FILE without clobbering other keys."""
    s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    s[key] = value
    save_json(SETTINGS_FILE, s)

def _set_launch_at_login(on):
    """Write or remove a LaunchAgent plist so EZ Logger starts at login."""
    import plistlib
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.bball.renamer.plist")
    if on:
        app_bundle = os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
        binary = os.path.join(app_bundle, "Contents/MacOS/EZ Logger")
        if os.path.exists(binary):
            plist = {
                "Label": "com.bball.renamer",
                "ProgramArguments": [binary],
                "RunAtLoad": True,
            }
            try:
                with open(plist_path, "wb") as f:
                    plistlib.dump(plist, f)
            except Exception:
                pass
    else:
        try:
            if os.path.exists(plist_path):
                os.remove(plist_path)
        except Exception:
            pass

def file_timestamps(path: Path):
    try:
        stat = path.stat()
        ts   = getattr(stat, "st_birthtime", None) or stat.st_mtime
        dt   = datetime.fromtimestamp(ts)
        return dt.strftime("%Y%m%d"), dt.strftime("%H%M%S")
    except Exception:
        now = datetime.now()
        return now.strftime("%Y%m%d"), now.strftime("%H%M%S")

def video_creation_dt(path: Path) -> datetime:
    """Return creation datetime from AVFoundation container metadata, falling back to file timestamps."""
    try:
        import AVFoundation
        from Foundation import NSURL
        url   = NSURL.fileURLWithPath_(str(path))
        asset = AVFoundation.AVURLAsset.URLAssetWithURL_options_(url, None)
        items = AVFoundation.AVMetadataItem.metadataItemsFromArray_withKey_keySpace_(
            asset.commonMetadata(),
            AVFoundation.AVMetadataCommonKeyCreationDate,
            AVFoundation.AVMetadataKeySpaceCommon,
        )
        if items and len(items) > 0:
            val = str(items[0].stringValue() or "").strip()
            if len(val) >= 19:
                return datetime.strptime(val[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    try:
        stat = path.stat()
        ts   = getattr(stat, "st_birthtime", None) or stat.st_mtime
        return datetime.fromtimestamp(ts)
    except Exception:
        return datetime.now()

def video_creation_datetime(path: Path):
    """Return (YYYYMMDD, HHMMSS) strings for the video's creation time."""
    dt = video_creation_dt(path)
    return dt.strftime("%Y%m%d"), dt.strftime("%H%M%S")

def resolve_convention(preset, file_path=None, session=None):
    """Build a filename stem from an ordered list of field tokens in a naming preset."""
    sep    = preset.get("separator", "_") or "_"
    fields = preset.get("fields", [])
    if not fields:
        return ""
    dt    = video_creation_dt(file_path) if file_path else datetime.now()
    parts = []
    date_map = {k: v for k, v in DATE_FORMATS}
    time_map = {k: v for k, v in TIME_FORMATS}
    for f in fields:
        ftype = f.get("type", "text")
        val   = ""
        if ftype == "text":
            val = f.get("value", "").strip()
        elif ftype == "sport":
            if session:
                val = session.get("sport", "").strip()
            if not val:
                val = "SPT"
        elif ftype == "opponent":
            val = f.get("value", "").strip()
            if not val and session:
                val = session.get("opponent", "").strip()
            if not val:
                val = "OPP"
        elif ftype == "metadata":
            fname   = f.get("field", "")
            fmt_key = f.get("format", "")
            if fname == "date_created":
                val = dt.strftime(date_map.get(fmt_key, "%Y%m%d"))
            elif fname == "time_created":
                val = dt.strftime(time_map.get(fmt_key, "%H%M%S"))
        if val:
            parts.append(val)
    if not parts:
        return ""
    return sep.join(parts) + sep

def is_video(p: Path):
    return p.suffix.lower() in VIDEO_EXTENSIONS and not p.name.startswith(".")


# ── SafeRenamer — single source of truth for all file rename operations ───────

class SafeRenamer:
    """All rename operations must go through safe_rename().
    Enforces folder boundary, video-only, no recursion, no directories,
    and requires an explicit session folder. Logs every attempt."""

    ALLOWED_EXTENSIONS = frozenset(VIDEO_EXTENSIONS)

    @staticmethod
    def validate_folder(folder) -> tuple[bool, str]:
        """Check that the session folder is usable. Returns (ok, error)."""
        if not folder:
            return False, "No session folder configured. Set a folder in Setup Session."
        real = os.path.realpath(str(folder))
        if not os.path.isdir(real):
            return False, f"Session folder does not exist: {folder}"
        return True, ""

    @staticmethod
    def validate_file(file_path: Path, folder_root: Path) -> tuple[bool, str]:
        """Check that a single file is safe to rename. Returns (ok, reason)."""
        real_file   = os.path.realpath(str(file_path))
        real_folder = os.path.realpath(str(folder_root))

        # Must be directly inside the folder (no subdirectory traversal)
        if not real_file.startswith(real_folder + os.sep):
            return False, "outside session folder boundary"

        # Must be a regular file — not a directory or missing
        if os.path.isdir(real_file):
            return False, "is a directory, not a file"
        if not os.path.exists(real_file):
            return False, "file no longer exists (moved or deleted externally?)"
        if not os.path.isfile(real_file):
            return False, "not a regular file"

        # Must be exactly one level deep (no recursion)
        rel = os.path.relpath(real_file, real_folder)
        if os.sep in rel:
            return False, "is inside a subfolder"

        # Extension must be in the approved video list
        ext = Path(real_file).suffix.lower()
        if ext not in SafeRenamer.ALLOWED_EXTENSIONS:
            return False, f"not a supported video extension ({ext or 'none'})"

        return True, ""

    @staticmethod
    def safe_rename(src: Path, dst: Path, folder_root: Path,
                    session: dict = None) -> tuple[bool, str]:
        """Execute a rename after all safety checks. Returns (ok, error_str).
        Logs the result to RENAME_LOG_FILE regardless of outcome."""
        ok, reason = SafeRenamer.validate_file(src, folder_root)
        if not ok:
            SafeRenamer._log(src, dst, session, success=False, error=reason)
            return False, reason

        # Destination must also be inside the folder boundary
        real_dst    = os.path.realpath(str(dst))
        real_folder = os.path.realpath(str(folder_root))
        if not real_dst.startswith(real_folder + os.sep):
            msg = "destination is outside session folder boundary"
            SafeRenamer._log(src, dst, session, success=False, error=msg)
            return False, msg

        # Refuse to silently overwrite an existing file at the destination
        if dst.exists() and dst.resolve() != src.resolve():
            msg = f"destination already exists: {dst.name}"
            SafeRenamer._log(src, dst, session, success=False, error=msg)
            return False, msg

        try:
            src.rename(dst)
            SafeRenamer._log(src, dst, session, success=True)
            return True, ""
        except Exception as e:
            SafeRenamer._log(src, dst, session, success=False, error=str(e))
            return False, str(e)

    @staticmethod
    def check_destination(src: Path, dst: Path) -> str:
        """Return a warning string if dst already exists and is not src, else ''."""
        if src.resolve() == dst.resolve():
            return ""
        if dst.exists():
            return f"{dst.name} already exists in this folder"
        return ""

    @staticmethod
    def _log(src: Path, dst: Path, session: dict, success: bool, error: str = ""):
        """Append one JSON-lines entry to RENAME_LOG_FILE (pure append, O(1))."""
        s = session or {}
        entry = {
            "timestamp": datetime.now().isoformat(),
            "sport":     s.get("sport", ""),
            "opponent":  s.get("opponent", ""),
            "phase":     s.get("phase", ""),
            "old_path":  str(src),
            "new_path":  str(dst),
            "success":   success,
            "error":     error,
        }
        try:
            os.makedirs(os.path.dirname(RENAME_LOG_FILE), exist_ok=True)
            with open(RENAME_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass  # logging must never crash the rename flow


_ql_panel = None   # QLPreviewPanel singleton
_ql_ds    = None   # data source object kept alive
_ql_url   = None   # current NSURL being previewed

def _init_ql_panel():
    global _ql_panel, _ql_ds
    if _ql_panel is not None:
        return True
    try:
        import objc
        make_objc_classes()
        QLPreviewPanel = objc.lookUpClass('QLPreviewPanel')
        _ql_ds    = QLDataSource.alloc().init()
        _ql_panel = QLPreviewPanel.sharedPreviewPanel()
        _ql_panel.setDataSource_(_ql_ds)
        return True
    except Exception:
        return False

def quicklook(path: str):
    global _ql_url
    if _init_ql_panel():
        from Foundation import NSURL
        _ql_url = NSURL.fileURLWithPath_(path)
        if _ql_panel.isVisible():
            _ql_panel.reloadData()
        else:
            _ql_panel.makeKeyAndOrderFront_(None)
    else:
        subprocess.Popen(["open", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def close_quicklook():
    if _ql_panel is not None and _ql_panel.isVisible():
        _ql_panel.orderOut_(None)

def pick_folder_dialog():
    script = '''
    tell application "Finder" to activate
    set chosen to choose folder with prompt "Select your game footage folder:"
    return POSIX path of chosen
    '''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


# ── Character normalization ───────────────────────────────────────────────────

def _asc(s):
    """Strip diacritics/accents and return an ASCII-only string.
    e.g. Šmrekar → Smrekar, Čović → Covic, Ñame → Name.
    Used before .upper() anywhere a value ends up in a filename or shortcut label.
    """
    import unicodedata
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')


# ── Roster scraper ────────────────────────────────────────────────────────────

def _parse_roster_html(html):
    """Extract sorted (label, number) tuples from a Sidearm or PrestoSports roster page."""
    import html as _html_mod
    from collections import Counter

    html = _html_mod.unescape(html).replace('’', "'").replace('ʼ', "'")
    # Sidearm: aria-label="First Last jersey number N full bio"
    # Use [^"]+ to match any Unicode name characters (handles diacritics like Š, Č, etc.)
    sidearm = re.findall(
        r'aria-label="([^"]+?)\s+jersey number\s+(\d+)', html)
    if sidearm:
        raw_players = [(name.strip(), num) for name, num in sidearm]
    else:
        # PrestoSports fallback: "Last, First" name spans + nearby jersey number
        name_matches = re.findall(
            r'class="[^"]*roster[^"]*player[^"]*name[^"]*"[^>]*>([^<]+)<', html)
        num_matches = re.findall(
            r'class="[^"]*(?:uni|number|jersey)[^"]*"[^>]*>\s*#?(\d+)\s*<', html)
        raw_players = []
        for i, n in enumerate(name_matches):
            # PrestoSports uses "Last, First" — convert to "First Last"
            if "," in n:
                parts = n.split(",", 1)
                full = f"{parts[1].strip()} {parts[0].strip()}"
            else:
                full = n.strip()
            num = num_matches[i] if i < len(num_matches) else ""
            raw_players.append((full, num))

    suffixes = {"II", "III", "IV", "V", "JR", "SR"}
    players = []  # [(first, last, number)]
    seen_raw = set()
    for full, number in raw_players:
        full = full.replace('’', "'")  # normalize curly apostrophe
        parts = full.strip().split()
        while len(parts) > 1 and parts[-1].upper().rstrip(".") in suffixes:
            parts.pop()
        if not parts:
            continue
        last  = _asc(parts[-1]).upper()
        first = _asc(parts[0]).upper() if len(parts) > 1 else ""
        if len(last) > 1 and (first, last) not in seen_raw:
            seen_raw.add((first, last))
            players.append((first, last, number))

    last_counts = Counter(last for _, last, _ in players)

    seen_labels, result = set(), []
    for first, last, number in players:
        if last_counts[last] > 1:
            initial = first[0] if first else "?"
            label = f"{initial}.{last}"
            if label in seen_labels and first:
                label = f"{first}_{last}"
        else:
            label = last
        if label not in seen_labels:
            seen_labels.add(label)
            result.append((label, number))

    return sorted(result, key=lambda t: t[0])


def abbrev_for_opponent(name):
    """Return a standard abbreviation for a college team name."""
    name = name.strip()
    if name in TEAM_ABBREVS:
        return TEAM_ABBREVS[name]
    for k, v in TEAM_ABBREVS.items():
        if k.lower() == name.lower():
            return v
    # Normalize diacritics before building initials so abbreviations stay ASCII
    name = _asc(name)
    words = name.split()
    if len(words) == 1:
        return words[0][:4].upper()
    return "".join(w[0] for w in words if w and w[0].isalpha()).upper()


def scrape_schedule(sport_key, base_url):
    """Return deduplicated opponent names from the Sidearm schedule page."""
    import html as _html_mod
    slug = next((s for s, c in SLUG_TO_CODE.items() if c == sport_key), None)
    if not slug:
        return []
    now         = datetime.now()
    season_year = now.year if now.month >= 8 else now.year - 1
    url = f"{base_url.rstrip('/')}/sports/{slug}/schedule?season={season_year}"
    ua  = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = _html_mod.unescape(r.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []
    raw  = re.findall(
        r'data-test-id="s-game-card-opponent-logo__link"[^>]*title="([^"]+)"', html)
    seen, result = set(), []
    for name in raw:
        name = re.sub(r'^No\.?\s*\d+\s*', '', name).strip()  # strip rankings
        name = re.sub(r'\s*\([^)]+\)\s*$', '', name).strip() # strip (exh), (neutral), etc.
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def fetch_roster_from_url(url):
    """Fetch player last names from any URL using _parse_roster_html."""
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        return _parse_roster_html(html)
    except Exception:
        return []


def discover_roster_links(base_url):
    """
    Fetch base_url root page and extract /sports/slug/roster hrefs.
    Returns {sport_code: full_url} for all recognized slugs.
    Falls back to constructing URLs for any known slug not found via discovery.
    """
    base = base_url.rstrip("/")
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    found = {}
    try:
        req = urllib.request.Request(base_url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        slugs = re.findall(r'href="(?:[^"]*)/sports/([^/"]+)/roster"', html)
        for slug in dict.fromkeys(slugs):  # dedupe, preserve order
            code = SLUG_TO_CODE.get(slug)
            if code and code not in found:
                found[code] = f"{base}/sports/{slug}/roster"
    except Exception:
        pass
    # Fill in known sports not surfaced by discovery
    for slug, code in SLUG_TO_CODE.items():
        if code not in found:
            found[code] = f"{base}/sports/{slug}/roster"
    return found


def scrape_all_rosters(base_url, progress_cb=None):
    """
    Scrape every known sport from base_url in parallel (max 4 threads).
    Returns {sport_code: [name, ...]} for sports with at least one player found.
    progress_cb(sport_code, done_count, total_count) called after each completes.
    """
    import concurrent.futures
    sport_urls = discover_roster_links(base_url)
    codes = list(sport_urls.keys())
    results = {}
    done = [0]

    def fetch_one(code):
        return code, fetch_roster_from_url(sport_urls[code])

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for code, names in ex.map(fetch_one, codes):
            if names:
                results[code] = names
            done[0] += 1
            if progress_cb:
                progress_cb(code, done[0], len(codes))

    return results


ROSTERS_META_FILE = os.path.expanduser("~/.bball_renamer_v3_rosters_meta.json")

def fetch_roster(sport_key, cache_days: int = 7):
    """Return last-name list for sport_key; checks local cache before scraping."""
    cache = load_json(ROSTERS_FILE, {})
    if sport_key in cache and cache[sport_key]:
        meta      = load_json(ROSTERS_META_FILE, {})
        cached_at = meta.get(sport_key, "")
        max_days  = cache_days
        if cached_at and max_days > 0:
            try:
                age_days = (datetime.now() - datetime.fromisoformat(cached_at)).days
                if age_days >= max_days:
                    pass  # fall through to re-scrape
                else:
                    return [sc["label"] for sc in cache[sport_key]]
            except Exception:
                pass
        else:
            return [sc["label"] for sc in cache[sport_key]]
    # Cache miss — scrape the hardcoded URL for this sport
    url = SPORTS[sport_key].get("url", "")
    if not url:
        return []
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        return _parse_roster_html(html)
    except Exception:
        return []

def roster_to_shortcuts(entries):
    shortcuts = []
    key_pool = [str(i) for i in range(1, 10)] + list("abcdefghijklmnopqrstuvwxyz")
    for i, entry in enumerate(entries):
        key = key_pool[i] if i < len(key_pool) else ""
        if isinstance(entry, tuple):
            label, number = entry
        else:
            label, number = entry, ""
        shortcuts.append({"key": key, "label": label, "number": number})
    return shortcuts

def log_stat(session, player, play, rating):
    """Append one tagged-clip event to STATS_FILE."""
    _now = datetime.now()
    entry = {
        "ts":       _now.isoformat(),
        "date":     _now.strftime("%Y-%m-%d"),
        "player":   player or "",
        "play":     play   or "",
        "rating":   rating or "",
        "sport":    session.get("sport",       "") if session else "",
        "opponent": session.get("opponent",    "") if session else "",
        "phase":    session.get("phase",       "") if session else "",
    }
    data = load_json(STATS_FILE, [])
    if not isinstance(data, list):
        data = []
    data.append(entry)
    save_json(STATS_FILE, data)


def compute_stats(data):
    """
    Aggregate a list of stat entries into summary dicts.
    Returns a dict with keys:
      total_clips, total_sessions,
      players  {name: count},
      plays    {name: count},
      ratings  {name: count},
      top_player, top_play, top_rating,
      per_player {name: {plays:{}, ratings:{}, total:int}}
    """
    from collections import Counter, defaultdict

    players  = Counter()
    plays    = Counter()
    ratings  = Counter()
    sessions = set()
    per_player = defaultdict(lambda: {"plays": Counter(), "ratings": Counter(), "total": 0})

    for e in data:
        p  = e.get("player", "").strip()
        pl = e.get("play",   "").strip()
        r  = e.get("rating", "").strip()

        if p:
            players[p]  += 1
            per_player[p]["total"] += 1
            if pl: per_player[p]["plays"][pl]   += 1
            if r:  per_player[p]["ratings"][r]  += 1
        if pl: plays[pl]   += 1
        if r:  ratings[r]  += 1

        sess_key = (e.get("date",""), e.get("opponent",""), e.get("sport",""))
        sessions.add(sess_key)

    def _top(counter):
        if not counter:
            return ("—", 0)
        name, count = counter.most_common(1)[0]
        return (name, count)

    return {
        "total_clips":   len(data),
        "total_sessions": len(sessions),
        "players":       dict(players),
        "plays":         dict(plays),
        "ratings":       dict(ratings),
        "top_player":    _top(players),
        "top_play":      _top(plays),
        "top_rating":    _top(ratings),
        "per_player":    {k: {"plays": dict(v["plays"]),
                              "ratings": dict(v["ratings"]),
                              "total": v["total"]}
                          for k, v in per_player.items()},
    }


def ask(title, msg, current=""):
    w = rumps.Window(title=title, message=msg, default_text=current,
                     ok="Next", cancel="Cancel", dimensions=(340, 24))
    r = w.run()
    return r.text.strip() if r.clicked else None

def _url_display_label(url):
    """Shorten a URL to its hostname for display on a button."""
    if not url:
        return "🔗  Set Roster URL"
    try:
        import urllib.parse
        host = urllib.parse.urlparse(url).netloc or url
        return f"🔗  {host}"
    except Exception:
        return f"🔗  {url[:30]}"

# ── ObjC class registration ───────────────────────────────────────────────────

_classes_made = False
KeyTableView  = None
NavItemView   = None
ActionButton  = None
PillButton    = None
MenuTarget    = None
MainCaller    = None
FileListDelegate     = None
QLDataSource         = None
SearchResultsDelegate = None
WindowDelegate       = None
FilePanelResizer     = None
NowCardResizer       = None
CardHeightResizer    = None

def make_objc_classes():
    global _classes_made, KeyTableView, NavItemView, ActionButton, PillButton, MenuTarget, MainCaller, FileListDelegate, QLDataSource, SearchResultsDelegate, WindowDelegate, FilePanelResizer, NowCardResizer, CardHeightResizer
    if _classes_made:
        return
    _classes_made = True

    import objc
    from AppKit import (
        NSObject, NSTableView, NSView, NSTextField, NSFont, NSColor,
        NSImage, NSImageView, NSMakeRect,
    )

    class _KeyTableView(NSTableView):
        owner = None

        def keyDown_(self, event):
            chars = event.characters() or ""
            # ⌘Z → undo (NSCommandKeyMask = 0x100000)
            if chars == "z" and (event.modifierFlags() & 0x100000):
                if self.owner and hasattr(self.owner, "handle_cmd_z"):
                    self.owner.handle_cmd_z()
                return
            if self.owner:
                self.owner.handle_key(chars)
            else:
                super().keyDown_(event)

        def flagsChanged_(self, event):
            if self.owner and event.keyCode() in (58, 61):
                # 0x80000 = NSEventModifierFlagOption; fire on press, not release
                if event.modifierFlags() & 0x80000:
                    self.owner.toggle_custom_mode()

        def acceptsFirstResponder(self):
            return True

    KeyTableView = _KeyTableView

    class _NavItemView(NSView):
        def initWithFrame_(self, frame):
            self = objc.super(_NavItemView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._selected = False
            self._key      = None
            self._owner    = None
            self._lbl      = None
            self._icon     = None
            self.setWantsLayer_(True)
            self.layer().setCornerRadius_(8.0)
            return self

        def configureKey_symbol_label_owner_(self, key, symbol, label, owner):
            self._key   = key
            self._owner = owner
            w = self.frame().size.width

            icon = NSImageView.alloc().initWithFrame_(NSMakeRect(14, 8, 20, 20))
            img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
            if img:
                icon.setImage_(img)
            icon.setContentTintColor_(NSColor.secondaryLabelColor())
            self.addSubview_(icon)
            self._icon = icon

            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(44, 9, w - 52, 18))
            lbl.setStringValue_(label)
            lbl.setBezeled_(False)
            lbl.setDrawsBackground_(False)
            lbl.setEditable_(False)
            lbl.setSelectable_(False)
            lbl.setFont_(NSFont.systemFontOfSize_(13))
            lbl.setTextColor_(NSColor.secondaryLabelColor())
            lbl.setAutoresizingMask_(2)
            self.addSubview_(lbl)
            self._lbl = lbl

            self._refresh_appearance()

        def setSelected_(self, sel):
            self._selected = bool(sel)
            self._refresh_appearance()

        def _refresh_appearance(self):
            if self._selected:
                bg = _hex_color_alpha("#8c2232", 0.30)
                self.layer().setBackgroundColor_(bg.CGColor())
                tan = _hex_color("#dbcca6")
                if self._lbl:  self._lbl.setTextColor_(tan)
                if self._icon: self._icon.setContentTintColor_(tan)
            else:
                self.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
                if self._lbl:  self._lbl.setTextColor_(NSColor.secondaryLabelColor())
                if self._icon: self._icon.setContentTintColor_(NSColor.secondaryLabelColor())

        def mouseDown_(self, event):
            if self._owner is not None:
                self._owner._on_nav_select(self._key)

    NavItemView = _NavItemView

    class _ActionButton(NSView):
        def initWithFrame_(self, frame):
            self = objc.super(_ActionButton, self).initWithFrame_(frame)
            if self is None:
                return None
            self._action  = None
            self._bg      = None
            self._bg_press = None
            self._pressed = False
            self.setWantsLayer_(True)
            self.layer().setCornerRadius_(8.0)
            return self

        def configureTitle_bg_press_action_(self, title, bg_hex, press_hex, action):
            self._action   = action
            self._bg       = bg_hex
            self._bg_press = press_hex
            for v in list(self.subviews()):
                v.removeFromSuperview()
            w = self.frame().size.width
            h = self.frame().size.height
            lbl = NSTextField.labelWithString_(title)
            lbl.setFont_(NSFont.boldSystemFontOfSize_(12))
            lbl.setTextColor_(NSColor.whiteColor())
            lbl.sizeToFit()
            lf = lbl.frame()
            lx = (w - lf.size.width) / 2
            ly = (h - lf.size.height) / 2
            lbl.setFrame_(NSMakeRect(lx, ly, lf.size.width, lf.size.height))
            self.addSubview_(lbl)
            self.layer().setBackgroundColor_(_hex_color(bg_hex).CGColor())

        def mouseDown_(self, event):
            self._pressed = True
            self.layer().setBackgroundColor_(_hex_color(self._bg_press).CGColor())

        def mouseUp_(self, event):
            was_pressed = self._pressed
            self._pressed = False
            self.layer().setBackgroundColor_(_hex_color(self._bg).CGColor())
            if was_pressed and self._action is not None:
                self._action()

    ActionButton = _ActionButton

    class _PillButton(NSView):
        def initWithFrame_(self, frame):
            self = objc.super(_PillButton, self).initWithFrame_(frame)
            if self is None:
                return None
            self._handler = None
            self.setWantsLayer_(True)
            self.layer().setCornerRadius_(13.0)
            return self

        def setClickHandler_(self, handler):
            self._handler = handler

        def hitTest_(self, point):
            result = objc.super(_PillButton, self).hitTest_(point)
            if result is not None:
                return self
            return None

        def mouseDown_(self, event):
            if self._handler is not None:
                self._handler(self, event)

    PillButton = _PillButton

    class _MenuTarget(NSObject):
        def menuPicked_(self, sender):
            cb = getattr(self, "_callback", None)
            if cb is not None:
                cb(sender.representedObject())

    MenuTarget = _MenuTarget

    class _MainCaller(NSObject):
        def fire_(self, _):
            cb = getattr(self, "_cb", None)
            if callable(cb):
                cb()

    MainCaller = _MainCaller

    class _FileListDelegate(NSObject):
        owner = None

        def numberOfRowsInTableView_(self, tv):
            return len(self.owner._files) if self.owner else 0

        def tableView_objectValueForTableColumn_row_(self, tv, col, row):
            if self.owner and row < len(self.owner._files):
                return self.owner._files[row].name
            return ""

        def tableView_willDisplayCell_forTableColumn_row_(self, tv, cell, col, row):
            cell.setLineBreakMode_(3)  # NSLineBreakByTruncatingHead — shows end of filename where labels are

        def tableViewSelectionDidChange_(self, notif):
            if not self.owner:
                return
            row = notif.object().selectedRow()
            if row >= 0:
                self.owner._on_file_selected(row)

    FileListDelegate = _FileListDelegate

    class _SearchResultsDelegate(NSObject):
        owner       = None
        _suppressed = False

        def numberOfRowsInTableView_(self, tv):
            if not self.owner:
                return 0
            return len(self.owner._search_matches)

        def tableView_objectValueForTableColumn_row_(self, tv, col, row):
            if not self.owner:
                return ""
            matches = self.owner._search_matches
            if 0 <= row < len(matches):
                return matches[row]["label"]
            return ""

        def tableView_willDisplayCell_forTableColumn_row_(self, tv, cell, col, row):
            cell.setTextColor_(NSColor.whiteColor())

        def tableViewSelectionDidChange_(self, notif):
            if not self.owner or self._suppressed:
                return
            row = notif.object().selectedRow()
            if row < 0 or row >= len(self.owner._search_matches):
                return
            self.owner._search_idx = row
            self.owner._confirm_search_selection()

    SearchResultsDelegate = _SearchResultsDelegate

    # Load QuickLookUI so QLPreviewPanel is available
    try:
        from Foundation import NSBundle
        import objc as _objc
        _ql_bundle = NSBundle.bundleWithPath_(
            '/System/Library/Frameworks/QuickLookUI.framework')
        _ql_bundle.load()
    except Exception:
        _objc = None

    class _QLDataSource(NSObject):
        def _ql_count(self, panel):
            return 1 if _ql_url else 0
        def _ql_item(self, panel, idx):
            return _ql_url

    if _objc is not None:
        _QLDataSource.numberOfPreviewItemsInPreviewPanel_ = _objc.selector(
            _QLDataSource._ql_count,
            selector=b'numberOfPreviewItemsInPreviewPanel:',
            signature=b'q@:@',
        )
        _QLDataSource.previewPanel_previewItemAtIndex_ = _objc.selector(
            _QLDataSource._ql_item,
            selector=b'previewPanel:previewItemAtIndex:',
            signature=b'@@:@q',
        )

    QLDataSource = _QLDataSource

    class _WindowDelegate(NSObject):
        owner = None  # TagWindowV2 instance
        _close_cb = None  # optional: called from windowShouldClose_ (e.g. modal panels)

        def windowShouldClose_(self, sender):
            if self._close_cb:
                self._close_cb()
            return True

        def windowDidResize_(self, notif):
            if self.owner:
                self.owner._on_window_resize_live()
                # Window snap / maximize fires windowDidResize_ without a live-resize
                # session, so windowDidEndLiveResize_ never fires — call the end-resize
                # handler here for that case.
                win = notif.object()
                if not win.inLiveResize():
                    self.owner._on_window_resize()

        def windowDidEndLiveResize_(self, notif):
            if self.owner:
                self.owner._on_window_resize()

    WindowDelegate = _WindowDelegate

    class _FilePanelResizer(NSView):
        """Thin drag handle on the right edge of the file-list panel.
        Drag left/right to resize the panel; cursor changes to resize arrows."""
        owner = None   # TagWindowV2

        def initWithFrame_(self, frame):
            self = objc.super(_FilePanelResizer, self).initWithFrame_(frame)
            if self is None:
                return None
            self._drag_start_x = 0.0
            self._drag_start_w = 260.0
            self.setWantsLayer_(True)
            # Invisible but interactable — no background
            self.layer().setBackgroundColor_(
                NSColor.clearColor().CGColor())
            return self

        def resetCursorRects(self):
            from AppKit import NSCursor
            self.addCursorRect_cursor_(
                self.bounds(), NSCursor.resizeLeftRightCursor())

        def acceptsFirstMouse_(self, event):
            return True

        def mouseDown_(self, event):
            self._drag_start_x = float(event.locationInWindow().x)
            self._drag_start_w = float(self.owner._file_list_w)

        def mouseDragged_(self, event):
            if self.owner is None:
                return
            dx  = event.locationInWindow().x - self._drag_start_x
            W   = self.owner.win.frame().size.width
            sidebar_w = self.owner.SIDEBAR_W if self.owner._sidebar_visible else 0
            max_w = max(160, W - sidebar_w - 440)   # always leave ≥440px for cards
            new_w = max(160, min(max_w, self._drag_start_w + dx))
            self.owner._file_list_w = new_w
            H = self.owner.win.contentView().frame().size.height
            self.owner._reposition_layout(W, H)
            # Refit player card for new card width (columns may change)
            bank = getattr(self.owner, "_sc_current_bank", "players")
            if hasattr(self.owner, "_sc_scrollviews"):
                self.owner._populate_shortcut_pills(bank)
            self.owner.win.contentView().displayIfNeeded()

        def mouseUp_(self, event):
            if self.owner is not None:
                _save_setting("file_list_width", int(self.owner._file_list_w))
                self.owner._settings["file_list_width"] = int(self.owner._file_list_w)

    FilePanelResizer = _FilePanelResizer

    class _NowCardResizer(NSView):
        """Drag handle on the vertical divider inside the now-tagging card.
        Dragging left/right adjusts _now_left_ratio."""
        owner = None

        def initWithFrame_(self, frame):
            self = objc.super(_NowCardResizer, self).initWithFrame_(frame)
            if self is None:
                return None
            self._drag_start_x     = 0.0
            self._drag_start_ratio = 0.60
            self.setWantsLayer_(True)
            self.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
            return self

        def resetCursorRects(self):
            from AppKit import NSCursor
            self.addCursorRect_cursor_(
                self.bounds(), NSCursor.resizeLeftRightCursor())

        def acceptsFirstMouse_(self, event):
            return True

        def mouseDown_(self, event):
            self._drag_start_x     = float(event.locationInWindow().x)
            self._drag_start_ratio = float(self.owner._now_left_ratio)

        def mouseDragged_(self, event):
            if self.owner is None:
                return
            dx      = event.locationInWindow().x - self._drag_start_x
            card_w  = float(self.owner._now_card.frame().size.width)
            card_h  = float(self.owner._now_card.frame().size.height)
            new_lw  = self._drag_start_ratio * card_w + dx
            ratio   = max(180.0 / max(card_w, 1),
                          min((card_w - 140.0) / max(card_w, 1),
                              new_lw / max(card_w, 1)))
            self.owner._now_left_ratio = ratio
            self.owner._reposition_now_card_internals(card_w, card_h)

    NowCardResizer = _NowCardResizer

    class _CardHeightResizer(NSView):
        """Horizontal drag handle between / below the log cards.
        Dragging up/down adjusts the target card's height via a callback."""
        owner    = None   # TagWindowV2
        _attr    = None   # e.g. "_now_card_h"
        _min_h   = 160
        _max_h   = 600

        def initWithFrame_(self, frame):
            self = objc.super(_CardHeightResizer, self).initWithFrame_(frame)
            if self is None:
                return None
            self._drag_start_y = 0.0
            self._drag_start_h = 220.0
            self.setWantsLayer_(True)
            self.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
            return self

        def resetCursorRects(self):
            from AppKit import NSCursor
            self.addCursorRect_cursor_(
                self.bounds(), NSCursor.resizeUpDownCursor())

        def acceptsFirstMouse_(self, event):
            return True

        def mouseDown_(self, event):
            self._drag_start_y = float(event.locationInWindow().y)
            self._drag_start_h = float(getattr(self.owner, self._attr, 220))

        def mouseDragged_(self, event):
            if self.owner is None or self._attr is None:
                return
            dy      = event.locationInWindow().y - self._drag_start_y
            # For the sc-card, cap max height at whatever is needed to show all pills
            effective_max = self._max_h
            if self._attr == "_sc_card_h":
                bank = getattr(self.owner, "_sc_current_bank", "players")
                sv   = getattr(self.owner, "_sc_scrollviews", {}).get(bank)
                if sv and sv.documentView():
                    doc_h = sv.documentView().frame().size.height
                    effective_max = doc_h + 50  # 50 = TITLE_PAD
            # Dragging up (positive dy) shrinks the card; down grows it
            new_h   = max(self._min_h, min(effective_max,
                          self._drag_start_h - dy))
            setattr(self.owner, self._attr, new_h)
            W = self.owner.win.frame().size.width
            H = self.owner.win.contentView().frame().size.height
            self.owner._reposition_layout(W, H)
            self.owner.win.contentView().displayIfNeeded()

        def mouseUp_(self, event):
            if self.owner is None:
                return
            W = self.owner.win.frame().size.width
            H = self.owner.win.contentView().frame().size.height
            if self._attr == "_now_card_h":
                # Now-card moved — refit the shortcut card to new available space
                for bank in getattr(self.owner, "_steps", []):
                    self.owner._populate_shortcut_pills(bank)
            self.owner._reposition_layout(W, H)
            self.owner.win.contentView().displayIfNeeded()

    CardHeightResizer = _CardHeightResizer

# ── Tag Window v2 (Adobe-CC inspired redesign) ───────────────────────────────

class TagWindowV2:
    NAV_ITEMS = [
        ("tag",      "bolt.fill",                "Log Mode"),
        ("players",  "person.2.fill",            "Team"),
        ("labels",   "list.bullet",              "Labels"),
        ("stats",    "chart.bar.fill",           "Stats"),
        (None, None, None),
        ("session",  "pencil",                    "Naming"),
        ("settings", "slider.horizontal.3",      "Settings"),
        ("help",     "questionmark.circle.fill", "Help"),
    ]

    # Responsive layout breakpoints
    SIDEBAR_W        = 200
    FILE_LIST_W      = 260
    TOP_H            = 56
    SIDEBAR_HIDE_W   = 780   # hide sidebar below this window width
    SIDEBAR_SHOW_W   = 860   # re-show sidebar above this (80px hysteresis)
    FILE_LIST_HIDE_W = 680   # hide file list below this
    FILE_LIST_SHOW_W = 760   # re-show file list above this

    def __init__(self, folder, shortcuts, app=None):
        self.folder    = Path(folder) if folder else None
        self.shortcuts = shortcuts
        self.app       = app
        self.nav_items = {}
        self.current_section = "tag"
        self._sidebar_visible   = True
        self._file_list_visible = True
        self._now_left_ratio    = 0.60               # left-column fraction in now-tagging card
        self._now_card_h        = 220                # user-resizable height of log card
        self._sc_card_h         = 400                # user-resizable height; auto-fit overrides on first populate
        # App settings (persisted) — load all keys at once
        _s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        self._settings = {k: _s.get(k, v) for k, v in DEFAULT_SETTINGS.items()}
        self._player_search_mode     = self._settings["player_search_mode"]
        self._player_number_search   = self._settings.get("player_number_search", False)
        self._file_list_w            = self._settings.get("file_list_width", self.FILE_LIST_W)
        # Tagging state
        self.step                    = None
        self._tag_parts              = []
        self._custom_indices         = set()   # indices of custom-text parts (excluded from stats)
        self._custom_mode            = False
        self._custom_input           = ""
        self._step_before_custom     = None
        self._players_bypass_hotkeys = self._player_search_mode
        # Branching label-tree state
        self._branch_stack           = []    # [{"parent_label", "prev_items"}] stack
        self._branch_items           = None  # overrides bank items when inside a branch
        # Multi-action chaining state
        self._chain_boundary_indices = set() # _tag_parts indices where new chains start
        self._chain_btns             = {}    # {bank: PillButton} for "+ Player (+)" buttons
        # Search-mode state
        self._search_enabled     = False   # toggled by top-bar switch
        self._search_mode        = False
        self._search_text        = ""
        self._search_matches     = []
        self._search_idx         = 0
        self._rebuild_steps()
        self._build_window()

    def _rebuild_steps(self):
        config  = self.app.session if self.app else DEFAULT_SESSION
        custom  = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        self._steps = ["players"] + [s["id"] for s in custom]
        self._step_labels_map = {"players": "Player"}
        for s in custom:
            self._step_labels_map[s["id"]] = s["label"]

    def _step_label(self, step_key):
        label    = self._step_labels_map.get(step_key, step_key.title())
        step_num = self._steps.index(step_key) + 1 if step_key in self._steps else "?"
        title    = f"Step {step_num} — {label.upper()}"
        hint     = f"Press your {label.lower()} key  (or ENTER to skip)"
        return title, hint

    def _build_step_circles(self):
        from AppKit import NSView, NSTextField, NSFont, NSMakeRect
        if not hasattr(self, "_now_card"):
            return
        card     = self._now_card
        LEFT_W   = getattr(self, "_step_circles_left_w", 420)
        card_h   = getattr(self, "_step_circles_card_h",
                           self._now_card_h if hasattr(self, "_now_card_h") else 220)
        circle_d  = 32
        # Center circles vertically between the preview text (card_h-68) and hint (32)
        mid_y     = (32 + (card_h - 68)) / 2
        circles_y = int(mid_y - circle_d / 2)

        # Remove any existing circle/line views from previous build
        for c, nl in self._now_step_circles:
            c.removeFromSuperview()
            nl.removeFromSuperview()
        for lbl in self._now_step_labels:
            lbl.removeFromSuperview()
        for ln in getattr(self, "_now_step_lines", []):
            ln.removeFromSuperview()
        self._now_step_circles = []
        self._now_step_labels  = []
        self._now_step_lines   = []

        n   = len(self._steps)
        gap = min(70, max(20, int((LEFT_W - 40 - circle_d * n) / max(1, n - 1))))
        row_w = circle_d * n + gap * (n - 1)
        row_x = (LEFT_W - row_w) / 2

        for i, step_key in enumerate(self._steps):
            label = self._step_labels_map.get(step_key, step_key.title()).upper()
            x = row_x + i * (circle_d + gap)
            if i < n - 1:
                line = NSView.alloc().initWithFrame_(NSMakeRect(
                    x + circle_d, circles_y + circle_d / 2 - 0.5, gap, 1))
                line.setWantsLayer_(True)
                line.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.15).CGColor())
                card.addSubview_(line)
                self._now_step_lines.append(line)

            c = PillButton.alloc().initWithFrame_(
                NSMakeRect(x, circles_y, circle_d, circle_d))
            c.layer().setCornerRadius_(circle_d / 2)
            c.layer().setBorderWidth_(1.5)
            c.setClickHandler_(
                lambda v, e, idx=i: self._set_step_state(active=idx))
            card.addSubview_(c)

            num_lbl = NSTextField.labelWithString_(str(i + 1))
            num_lbl.setFont_(NSFont.boldSystemFontOfSize_(13))
            num_lbl.sizeToFit()
            nf = num_lbl.frame()
            num_lbl.setFrame_(NSMakeRect(
                (circle_d - nf.size.width) / 2,
                (circle_d - nf.size.height) / 2,
                nf.size.width, nf.size.height))
            c.addSubview_(num_lbl)

            # Truncate label to fit — wider gap → more room
            max_chars = max(4, gap // 7)
            display   = label[:max_chars] if len(label) > max_chars else label
            step_lbl  = NSTextField.labelWithString_(display)
            step_lbl.setFont_(NSFont.systemFontOfSize_(10))
            step_lbl.setAlignment_(2)
            lbl_w = circle_d + min(60, gap - 10)
            step_lbl.setFrame_(NSMakeRect(
                x - (lbl_w - circle_d) / 2, circles_y - 18, lbl_w, 14))
            card.addSubview_(step_lbl)

            self._now_step_circles.append((c, num_lbl))
            self._now_step_labels.append(step_lbl)

    def _build_window(self):
        make_objc_classes()
        from AppKit import (
            NSWindow, NSColor, NSAppearance, NSApplication,
            NSVisualEffectView, NSTextField, NSFont, NSView,
            NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable, NSWindowStyleMaskFullSizeContentView,
            NSBackingStoreBuffered, NSMakeRect,
        )

        NSApplication.sharedApplication()

        W, H = 1380, 720
        rect  = NSMakeRect(80, 80, W, H)
        style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                 | NSWindowStyleMaskResizable | NSWindowStyleMaskFullSizeContentView)
        self.win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, NSBackingStoreBuffered, False
        )
        self.win.setTitle_("EZ Logger")
        self.win.setReleasedWhenClosed_(False)
        self.win.setTitlebarAppearsTransparent_(True)
        try:
            self.win.setAppearance_(
                NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        except Exception:
            pass
        self.win.setBackgroundColor_(_hex_color("#1a1a1c"))

        cv = self.win.contentView()
        SIDEBAR_W = 200
        self._SIDEBAR_W = SIDEBAR_W

        # Sidebar — vibrancy/blur
        self._sidebar = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, SIDEBAR_W, H))
        self._sidebar.setMaterial_(7)        # NSVisualEffectMaterialSidebar
        self._sidebar.setBlendingMode_(0)    # NSVisualEffectBlendingModeBehindWindow
        self._sidebar.setState_(1)           # NSVisualEffectStateActive
        self._sidebar.setAutoresizingMask_(16)  # heightSizable
        cv.addSubview_(self._sidebar)

        # Nav items, top-anchored
        item_y = H - 56
        for key, symbol, label in self.NAV_ITEMS:
            if key is None:
                sep = NSView.alloc().initWithFrame_(
                    NSMakeRect(20, item_y - 8, SIDEBAR_W - 40, 1))
                sep.setWantsLayer_(True)
                sep.layer().setBackgroundColor_(
                    NSColor.separatorColor().CGColor())
                sep.setAutoresizingMask_(8)
                self._sidebar.addSubview_(sep)
                item_y -= 20
                continue
            item = NavItemView.alloc().initWithFrame_(
                NSMakeRect(8, item_y - 36, SIDEBAR_W - 16, 36))
            item.configureKey_symbol_label_owner_(key, symbol, label, self)
            item.setAutoresizingMask_(8)  # MinYMargin
            self._sidebar.addSubview_(item)
            self.nav_items[key] = item
            item_y -= 40

        self.nav_items["tag"].setSelected_(True)

        # ── Top bar ───────────────────────────────────────────────────────────
        TOP_H = 56
        cx = SIDEBAR_W
        cw = W - SIDEBAR_W
        topbar = NSView.alloc().initWithFrame_(
            NSMakeRect(cx, H - TOP_H, cw, TOP_H))
        topbar.setAutoresizingMask_(2 | 8)  # widthSizable + minYMargin (anchored to top)
        cv.addSubview_(topbar)
        self._topbar = topbar

        # bottom 1px hairline separator
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, 1))
        sep.setWantsLayer_(True)
        sep.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        sep.setAutoresizingMask_(2)  # widthSizable
        topbar.addSubview_(sep)

        # Batch Rename action button (right side)
        BTN_W, BTN_H = 130, 30
        btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 24 - BTN_W, (TOP_H - BTN_H) / 2, BTN_W, BTN_H))
        btn.configureTitle_bg_press_action_(
            "Batch Rename", "#8c2232", "#6b1a26", self._on_batch_rename)
        btn.setAutoresizingMask_(1)  # MinXMargin (right-anchored)
        topbar.addSubview_(btn)
        self._batch_btn = btn

        # Search toggle button (left of Batch Rename)
        TOG_W = 124
        tog = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 24 - BTN_W - 10 - TOG_W, (TOP_H - BTN_H) / 2,
                       TOG_W, BTN_H))
        tog.configureTitle_bg_press_action_(
            "⌨  Search  OFF", "#3a3a3c", "#2c2c2e", self._toggle_search_mode)
        tog.setAutoresizingMask_(1)  # right-anchored
        topbar.addSubview_(tog)
        self._search_toggle_btn = tog

        # Session status indicator (left side of top bar)
        SES_W, SES_H = 200, 28
        ses_btn = PillButton.alloc().initWithFrame_(
            NSMakeRect(16, (TOP_H - SES_H) / 2, SES_W, SES_H))
        ses_btn.layer().setCornerRadius_(6.0)
        ses_btn.layer().setBackgroundColor_(_hex_color("#3a3a3c").CGColor())
        ses_btn.layer().setBorderWidth_(0.5)
        ses_btn.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.15).CGColor())
        ses_btn.setAutoresizingMask_(8)  # minYMargin (top-anchored)
        ses_btn.setClickHandler_(self._on_session_status_btn)
        topbar.addSubview_(ses_btn)
        self._session_status_btn = ses_btn

        ses_lbl = NSTextField.labelWithString_("...")
        ses_lbl.setFont_(NSFont.systemFontOfSize_(12))
        ses_lbl.setTextColor_(NSColor.secondaryLabelColor())
        ses_lbl.setLineBreakMode_(4)   # NSLineBreakByTruncatingTail
        ses_lbl.setFrame_(NSMakeRect(10, (SES_H - 16) / 2, SES_W - 20, 16))
        ses_btn.addSubview_(ses_lbl)
        self._session_status_lbl = ses_lbl
        self._update_session_status_btn()

        # Now Tagging card (Tag Mode section)
        self._build_now_tagging_card(cv, W, H, SIDEBAR_W, TOP_H)

        # Three shortcut cards below
        self._build_shortcut_cards(cv, W, H, SIDEBAR_W, TOP_H)

        # File list panel (tag section, left of cards)
        self._build_file_list(cv, W, H, SIDEBAR_W, TOP_H)

        # Placeholder for non-Log Mode sections
        cx = SIDEBAR_W
        cw = W - SIDEBAR_W
        self._placeholder_title = NSTextField.alloc().initWithFrame_(
            NSMakeRect(cx, H/2, cw, 32))
        self._placeholder_title.setStringValue_("Players")
        self._placeholder_title.setBezeled_(False)
        self._placeholder_title.setDrawsBackground_(False)
        self._placeholder_title.setEditable_(False)
        self._placeholder_title.setSelectable_(False)
        self._placeholder_title.setAlignment_(2)
        self._placeholder_title.setFont_(NSFont.systemFontOfSize_(24))
        self._placeholder_title.setTextColor_(NSColor.labelColor())
        self._placeholder_title.setAutoresizingMask_(2 | 8 | 32)
        self._placeholder_title.setHidden_(True)
        cv.addSubview_(self._placeholder_title)

        self._placeholder_sub = NSTextField.alloc().initWithFrame_(
            NSMakeRect(cx, H/2 - 28, cw, 20))
        self._placeholder_sub.setStringValue_(
            "Section coming soon")
        self._placeholder_sub.setBezeled_(False)
        self._placeholder_sub.setDrawsBackground_(False)
        self._placeholder_sub.setEditable_(False)
        self._placeholder_sub.setSelectable_(False)
        self._placeholder_sub.setAlignment_(2)
        self._placeholder_sub.setFont_(NSFont.systemFontOfSize_(13))
        self._placeholder_sub.setTextColor_(NSColor.secondaryLabelColor())
        self._placeholder_sub.setAutoresizingMask_(2 | 8 | 32)
        self._placeholder_sub.setHidden_(True)
        cv.addSubview_(self._placeholder_sub)

        # Players section (full management UI)
        self._build_players_section(cv, W, H, SIDEBAR_W, TOP_H)

        # Labels section (manages all custom steps)
        self._build_labels_section(cv, W, H, SIDEBAR_W, TOP_H)

        # Session settings section
        self._build_session_section(cv, W, H, SIDEBAR_W, TOP_H)

        # Stats section
        self._build_stats_section(cv, W, H, SIDEBAR_W, TOP_H)

        # App settings section
        self._build_settings_section(cv, W, H, SIDEBAR_W, TOP_H)

        # Help reference section
        self._build_help_section(cv, W, H, SIDEBAR_W, TOP_H)

        # Hamburger button — shown when sidebar is hidden
        TOG_BTN_W = 32
        TOG_BTN_H = 28
        tog_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(8, H - TOP_H + (TOP_H - TOG_BTN_H) / 2,
                       TOG_BTN_W, TOG_BTN_H))
        tog_btn.configureTitle_bg_press_action_(
            "☰", "#3a3a3c", "#2c2c2e", self._toggle_sidebar)
        tog_btn.setAutoresizingMask_(8)  # MinYMargin — stays near top
        tog_btn.setHidden_(True)
        cv.addSubview_(tog_btn)
        self._sidebar_toggle_btn = tog_btn

        # Window resize delegate — reflows pill grids when live resize ends
        self._win_delegate = WindowDelegate.alloc().init()
        self._win_delegate.owner = self
        self.win.setDelegate_(self._win_delegate)

        from AppKit import NSMakeSize
        self.win.setContentMinSize_(NSMakeSize(480, 400))

        self.win.makeKeyAndOrderFront_(None)

        # Initial layout pass to handle any saved window size below breakpoints
        self._on_window_resize_live()

    def _on_window_resize(self):
        sec = getattr(self, "current_section", "tag")
        if sec == "players" and hasattr(self, "_players_grid_container"):
            self._refresh_players_grid()
        elif sec == "labels" and hasattr(self, "_labels_steps_doc"):
            self._rebuild_labels_rows()
            self._refresh_labels_grid()
        elif sec == "stats" and hasattr(self, "_stats_overview_panel"):
            self._refresh_stats()
        elif sec == "session" and hasattr(self, "_convention_sv"):
            self._rebuild_convention_rows(scroll_to="preserve")
        # Help: rebuild content when the available width has changed meaningfully
        if hasattr(self, "_help_scroll") and hasattr(self, "_help_section"):
            TOC_W = 200.0
            sidebar_w = self._SIDEBAR_W if self._sidebar_visible else 0.0
            cur_cw = self.win.frame().size.width - sidebar_w
            new_content_w = cur_cw - TOC_W - 1.0
            built_w = getattr(self, "_help_built_content_w", new_content_w)
            if abs(new_content_w - built_w) > 4:
                self._rebuild_help_scroll(cur_cw)

    def _on_window_resize_live(self):
        W = self.win.frame().size.width
        H = self.win.contentView().frame().size.height

        # Sidebar show/hide
        if self._sidebar_visible and W < self.SIDEBAR_HIDE_W:
            self._sidebar_visible = False
            self._sidebar.setHidden_(True)
            if hasattr(self, "_sidebar_toggle_btn"):
                self._sidebar_toggle_btn.setHidden_(False)
        elif not self._sidebar_visible and W >= self.SIDEBAR_SHOW_W:
            self._sidebar_visible = True
            self._sidebar.setHidden_(False)
            if hasattr(self, "_sidebar_toggle_btn"):
                self._sidebar_toggle_btn.setHidden_(True)

        # File list show/hide (tag section only)
        if self.current_section == "tag":
            if self._file_list_visible and W < self.FILE_LIST_HIDE_W:
                self._file_list_visible = False
                if hasattr(self, "_file_list_panel"):
                    self._file_list_panel.setHidden_(True)
            elif not self._file_list_visible and W >= self.FILE_LIST_SHOW_W:
                self._file_list_visible = True
                if hasattr(self, "_file_list_panel"):
                    self._file_list_panel.setHidden_(False)

        # Always reposition — cards must re-center on every resize pixel
        self._reposition_layout(W, H)

        sec = self.current_section
        # Reflow content live for each active section.
        # Pill/grid rebuilds are gated on a 3px width threshold — column count
        # only changes at ~108px intervals, so rebuilding every drag pixel is waste.
        # Stats is skipped entirely here; _on_window_resize (drag-end) handles it.
        _last_w = getattr(self, "_last_live_reflow_w", -999)
        _w_changed = abs(W - _last_w) >= 3
        if _w_changed:
            self._last_live_reflow_w = W
        if sec == "tag" and hasattr(self, "_sc_cards") and _w_changed:
            self._populate_shortcut_pills(self._sc_current_bank)
        elif sec == "players" and hasattr(self, "_players_grid_container") and _w_changed:
            self._refresh_players_grid()
        elif sec == "labels" and hasattr(self, "_labels_grid_container"):
            if _w_changed:
                self._refresh_labels_grid()
            if hasattr(self, "_labels_steps_sv") and hasattr(self, "_labels_steps_doc"):
                from AppKit import NSMakeRect as _NMR
                new_w = self._labels_steps_sv.frame().size.width
                if new_w > 0:
                    doc = self._labels_steps_doc
                    doc.setFrame_(_NMR(0, 0, new_w, doc.frame().size.height))

        # Hide reset button when content is too narrow to avoid tab overlap
        # Threshold: tabs (224px centered) + reset (100px) + margins need ~480px content width
        if hasattr(self, "_stats_btn_reset"):
            sidebar_w = self._SIDEBAR_W if self._sidebar_visible else 0.0
            stats_cw  = W - sidebar_w
            self._stats_btn_reset.setHidden_(stats_cw <= 480)

    def _reposition_layout(self, W, H):
        from AppKit import NSMakeRect

        cx = self.SIDEBAR_W if self._sidebar_visible else 0
        cw = W - cx
        ch = H - self.TOP_H

        # Topbar
        if hasattr(self, "_topbar"):
            self._topbar.setAutoresizingMask_(0)
            self._topbar.setFrame_(NSMakeRect(cx, H - self.TOP_H, cw, self.TOP_H))
            self._topbar.setAutoresizingMask_(2 | 8)

        # Management sections — all fill the content area below the topbar
        for attr in ("_players_section", "_labels_section",
                     "_session_section", "_stats_section",
                     "_settings_section", "_help_section"):
            if hasattr(self, attr):
                v = getattr(self, attr)
                v.setAutoresizingMask_(0)
                v.setFrame_(NSMakeRect(cx, 0, cw, ch))
                v.setAutoresizingMask_(2 | 16)

        # Placeholder labels
        for attr in ("_placeholder_title", "_placeholder_sub"):
            if hasattr(self, attr):
                v = getattr(self, attr)
                f = v.frame()
                v.setAutoresizingMask_(0)
                v.setFrame_(NSMakeRect(cx, f.origin.y, cw, f.size.height))
                v.setAutoresizingMask_(2 | 8 | 32)

        # File-list panel — shift x and update width from the user-dragged value
        if hasattr(self, "_file_list_panel"):
            f = self._file_list_panel.frame()
            self._file_list_panel.setFrame_(
                NSMakeRect(cx + 12, f.origin.y, self._file_list_w, f.size.height))

        # Drag handle — sits on the right edge of the file-list panel
        if hasattr(self, "_fl_resize_handle"):
            f = self._fl_resize_handle.frame()
            handle_x = cx + 12 + self._file_list_w - 3
            self._fl_resize_handle.setFrame_(
                NSMakeRect(handle_x, f.origin.y, f.size.width, f.size.height))

        # Re-center now-tagging card and shortcut cards
        fl_w = self._file_list_w if self._file_list_visible else 0
        cards_x = cx + fl_w + 20
        available_w = W - cards_x
        # Fill available width (no hard cap) — internals reflow via _reposition_now_card_internals
        effective_card_w = max(400, available_w - 40)
        self._effective_card_w = effective_card_w
        cx_card = cards_x + (available_w - effective_card_w) / 2

        # Compute vertical positions from user-adjustable heights
        now_card_h = self._now_card_h
        sc_card_h  = self._sc_card_h
        now_card_y = H - self.TOP_H - 32 - now_card_h
        sc_card_y  = now_card_y - 20 - sc_card_h
        handle_h   = 12

        if hasattr(self, "_now_card"):
            self._now_card.setFrame_(NSMakeRect(cx_card, now_card_y, effective_card_w, now_card_h))
            self._reposition_now_card_internals(effective_card_w, now_card_h)

        if hasattr(self, "_now_card_h_resizer"):
            self._now_card_h_resizer.setFrame_(
                NSMakeRect(cx_card, now_card_y - handle_h, effective_card_w, handle_h))

        if hasattr(self, "_sc_cards"):
            for card in self._sc_cards.values():
                card.setFrame_(NSMakeRect(cx_card, sc_card_y, effective_card_w, sc_card_h))
            # Update scroll views inside each card to fill new height, keeping top anchor
            for bank, sv in getattr(self, "_sc_scrollviews", {}).items():
                new_sv_h = max(10, sc_card_h - 50)
                sv.setFrame_(NSMakeRect(12, 14, effective_card_w - 24, new_sv_h))
                doc = sv.documentView()
                if doc:
                    doc_h = doc.frame().size.height
                    sv.contentView().scrollToPoint_((0, max(0.0, doc_h - new_sv_h)))
                    sv.reflectScrolledClipView_(sv.contentView())
            for bank, lbl in getattr(self, "_sc_titles", {}).items():
                lbl.setFrame_(NSMakeRect(20, sc_card_h - 30, effective_card_w - 40, 14))

        if hasattr(self, "_sc_card_h_resizer"):
            self._sc_card_h_resizer.setFrame_(
                NSMakeRect(cx_card, sc_card_y - handle_h, effective_card_w, handle_h))

        if hasattr(self, "_convention_sv"):
            self._reposition_session_section(cw, ch)

        if hasattr(self, "_settings_doc"):
            self._reposition_settings_section(cw, ch)

        if hasattr(self, "_help_doc_container"):
            self._reposition_help_content_w(cw, ch)

        if hasattr(self, "win"):
            self.win.contentView().setNeedsDisplay_(True)

    def _toggle_sidebar(self):
        W = self.win.frame().size.width
        H = self.win.contentView().frame().size.height
        self._sidebar_visible = not self._sidebar_visible
        self._sidebar.setHidden_(not self._sidebar_visible)
        if hasattr(self, "_sidebar_toggle_btn"):
            self._sidebar_toggle_btn.setHidden_(self._sidebar_visible)
        self._reposition_layout(W, H)

    def _on_nav_select(self, key):
        for k, item in self.nav_items.items():
            item.setSelected_(k == key)
        self.current_section = key
        labels = {k: lbl for k, _, lbl in self.NAV_ITEMS if k}

        is_tag      = (key == "tag")
        is_players  = (key == "players")
        is_labels   = (key == "labels")
        is_stats    = (key == "stats")
        is_session  = (key == "session")
        is_settings = (key == "settings")
        is_help     = (key == "help")

        if is_tag and hasattr(self, "_session_status_btn"):
            self._update_session_status_btn()
        if hasattr(self, "_now_card"):
            self._now_card.setHidden_(not is_tag)
        if hasattr(self, "_now_card_h_resizer"):
            self._now_card_h_resizer.setHidden_(not is_tag)
        if hasattr(self, "_sc_card_h_resizer"):
            self._sc_card_h_resizer.setHidden_(not is_tag)
        if hasattr(self, "_file_list_panel"):
            self._file_list_panel.setHidden_(not is_tag)
        if hasattr(self, "_sc_cards"):
            if not is_tag:
                for card in self._sc_cards.values():
                    card.setHidden_(True)
            else:
                self._set_cards_for_step(None)
                self._set_active_shortcut_card("players")
        if hasattr(self, "_players_section"):
            self._players_section.setHidden_(not is_players)
        if hasattr(self, "_labels_section"):
            self._labels_section.setHidden_(not is_labels)
            if is_labels:
                self._refresh_labels_grid()
        if hasattr(self, "_stats_section"):
            self._stats_section.setHidden_(not is_stats)
            if is_stats:
                self._refresh_stats()
        if hasattr(self, "_session_section"):
            self._session_section.setHidden_(not is_session)
            if is_session:
                self._refresh_convention_for_sport()
        if hasattr(self, "_settings_section"):
            self._settings_section.setHidden_(not is_settings)
        if hasattr(self, "_help_section"):
            self._help_section.setHidden_(not is_help)
        if hasattr(self, "_placeholder_title"):
            show_placeholder = not any([
                is_tag, is_players, is_labels, is_stats,
                is_session, is_settings, is_help
            ])
            self._placeholder_title.setHidden_(not show_placeholder)
            self._placeholder_sub.setHidden_(not show_placeholder)
            if show_placeholder:
                self._placeholder_title.setStringValue_(labels.get(key, key))

        # Sync file-list visibility state and reposition layout for new section
        if hasattr(self, "_file_list_panel"):
            self._file_list_visible = is_tag and not self._file_list_panel.isHidden()
        W = self.win.frame().size.width
        H = self.win.contentView().frame().size.height
        self._reposition_layout(W, H)

        # Scroll convention view to top after layout so the frame is finalized first
        if is_session and hasattr(self, "_convention_sv"):
            sv = self._convention_sv
            doc = sv.documentView()
            if doc:
                doc_h = doc.frame().size.height
                viewport_h = sv.contentView().frame().size.height
                sv.contentView().scrollToPoint_((0, max(0.0, doc_h - viewport_h)))
                sv.reflectScrolledClipView_(sv.contentView())

    # ── Top bar helpers ───────────────────────────────────────────────────────

    def _on_batch_rename(self):
        if not self.app:
            return
        s         = self.app.session
        sport_key = s.get("sport", "")
        global_p  = s.get("naming_presets", DEFAULT_NAMING_PRESETS) or list(DEFAULT_NAMING_PRESETS)
        sport_p   = s.get("sport_presets", {}).get(sport_key, [])
        presets   = global_p + sport_p
        act_idx   = int(s.get("active_preset", 0))
        if act_idx >= len(presets):
            act_idx = 0
        preset = presets[act_idx] if presets else None
        if not preset or not preset.get("fields"):
            from AppKit import NSAlert
            alert = NSAlert.alloc().init()
            alert.setMessageText_("No Naming Convention")
            alert.setInformativeText_(
                "Batch Rename needs a naming template.\n"
                "Open the Naming tab to create one first.")
            alert.addButtonWithTitle_("Open Naming Tab")
            alert.addButtonWithTitle_("Cancel")
            if alert.runModal() == 1000:  # first button
                self._on_nav_select("session")
            return
        self.app.batch_rename(None)

    def _on_session_status_btn(self):
        self._on_nav_select("session")

    def _update_session_status_btn(self):
        if not hasattr(self, "_session_status_lbl"):
            return
        if not self.app:
            return
        from AppKit import NSColor
        s         = self.app.session
        sport_key = s.get("sport", "MBB")
        opponent  = s.get("opponent", "").strip()
        emoji     = SPORTS.get(sport_key, {}).get("emoji", "🏀")
        if opponent:
            text  = f"{emoji}  {sport_key}  ·  vs  {opponent}"
            bg    = _hex_color("#3a3a3c").CGColor()
            tc    = NSColor.secondaryLabelColor()
        else:
            text  = "⚙  Configure session →"
            bg    = _hex_color("#4a1a26").CGColor()
            tc    = _hex_color(COLOR_CRIMSON)
        self._session_status_lbl.setStringValue_(text)
        self._session_status_lbl.setTextColor_(tc)
        self._session_status_btn.layer().setBackgroundColor_(bg)

    def _toggle_search_mode(self):
        self._apply_search_mode(not self._search_enabled)

    def _apply_search_mode(self, on: bool):
        self._search_enabled         = on
        self._player_search_mode     = on
        self._players_bypass_hotkeys = on
        self._settings["player_search_mode"] = on
        if not on and self._search_mode:
            self._exit_search_mode()
        _save_setting("player_search_mode", on)
        entry = self._settings_btns.get("player_search_mode") if hasattr(self, "_settings_btns") else None
        if entry and isinstance(entry, tuple):
            btn, cb = entry
            if on:
                btn.configureTitle_bg_press_action_("ON", "#8c2232", "#6b1a26", cb)
            else:
                btn.configureTitle_bg_press_action_("OFF", "#3a3a3c", "#2c2c2e", cb)
        if hasattr(self, "_search_toggle_btn"):
            if on:
                self._search_toggle_btn.configureTitle_bg_press_action_(
                    "⌨  Search  ON", "#8c2232", "#6b1a26", self._toggle_search_mode)
            else:
                self._search_toggle_btn.configureTitle_bg_press_action_(
                    "⌨  Search  OFF", "#3a3a3c", "#2c2c2e", self._toggle_search_mode)
        if hasattr(self, "_settings_search_toggle"):
            if on:
                self._settings_search_toggle.configureTitle_bg_press_action_(
                    "Search  ON", "#8c2232", "#6b1a26", self._toggle_player_search_setting)
            else:
                self._settings_search_toggle.configureTitle_bg_press_action_(
                    "Search  OFF", "#3a3a3c", "#2c2c2e", self._toggle_player_search_setting)

    # ── Now Tagging card ──────────────────────────────────────────────────────

    def _build_now_tagging_card(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect,
            NSImage, NSImageView,
        )

        # ── Card (two-column: left = filename/preview/circles/hint, right = thumb)
        CARD_W   = 700
        CARD_H   = self._now_card_h
        LEFT_W   = 420
        RIGHT_W  = 260
        FILE_LIST_W = 260
        cards_x  = SIDEBAR_W + FILE_LIST_W + 20
        cx_card  = cards_x + ((W - cards_x) - CARD_W) / 2
        cy_card  = H - TOP_H - 32 - CARD_H

        card = NSView.alloc().initWithFrame_(
            NSMakeRect(cx_card, cy_card, CARD_W, CARD_H))
        card.setWantsLayer_(True)
        card.layer().setCornerRadius_(14.0)
        card.layer().setBackgroundColor_(_hex_color("#252528").CGColor())
        card.layer().setBorderWidth_(0.5)
        card.layer().setBorderColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        card.setAutoresizingMask_(8)  # minY only — x-position managed by _reposition_layout
        cv.addSubview_(card)
        self._now_card = card

        # ── Filename — inside card, top of left column ───────────────────────
        self._now_filename = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 190, LEFT_W - 40, 18))
        self._now_filename.setStringValue_(
            "Select a file from the list to begin")
        self._now_filename.setBezeled_(False)
        self._now_filename.setDrawsBackground_(False)
        self._now_filename.setEditable_(False)
        self._now_filename.setSelectable_(False)
        self._now_filename.setAlignment_(2)
        self._now_filename.setFont_(
            NSFont.monospacedSystemFontOfSize_weight_(12, 0))
        self._now_filename.setTextColor_(NSColor.labelColor())
        card.addSubview_(self._now_filename)

        # thin separator below filename
        fn_sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 184, LEFT_W, 1))
        fn_sep.setWantsLayer_(True)
        fn_sep.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        card.addSubview_(fn_sep)
        self._now_fn_sep = fn_sep

        # Vertical divider between columns — starts below filename separator
        div = NSView.alloc().initWithFrame_(NSMakeRect(LEFT_W, 24, 1, 160))
        div.setWantsLayer_(True)
        div.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.06).CGColor())
        card.addSubview_(div)
        self._now_div = div

        # ── Left column: tag preview (top), step circles (center), hint (bottom)
        # Preview text — below filename separator
        self._now_tag_preview = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 152, LEFT_W - 40, 22))
        self._now_tag_preview.setStringValue_("—")
        self._now_tag_preview.setBezeled_(False)
        self._now_tag_preview.setDrawsBackground_(False)
        self._now_tag_preview.setEditable_(False)
        self._now_tag_preview.setSelectable_(False)
        self._now_tag_preview.setFont_(
            NSFont.monospacedSystemFontOfSize_weight_(13, 0.3))
        self._now_tag_preview.setTextColor_(_hex_color("#dbcca6"))
        self._now_tag_preview.setAlignment_(2)
        card.addSubview_(self._now_tag_preview)

        # Step circles — dynamic, stored so _build_step_circles can rebuild them
        self._step_circles_left_w = LEFT_W
        self._now_step_circles = []
        self._now_step_labels  = []
        self._now_step_lines   = []
        self._build_step_circles()

        # Hint — bottom of left column
        hint = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 18, LEFT_W - 40, 14))
        hint.setStringValue_(
            "Select a file · then press  ↵ ENTER  to log it")
        hint.setBezeled_(False)
        hint.setDrawsBackground_(False)
        hint.setEditable_(False)
        hint.setSelectable_(False)
        hint.setFont_(NSFont.systemFontOfSize_(11))
        hint.setTextColor_(NSColor.secondaryLabelColor())
        hint.setAlignment_(2)
        card.addSubview_(hint)
        self._now_hint = hint

        # ── Search results overlay (shown only during search mode) ────────────
        from AppKit import NSScrollView, NSTableView, NSTableColumn
        SR_X = 20
        SR_Y = 34          # sits above hint (hint y=18 + h=14 + 2)
        SR_W = LEFT_W - 40  # 380
        SR_H = 56           # ~3 rows at 18px

        sr_scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(SR_X, SR_Y, SR_W, SR_H))
        sr_scroll.setHasVerticalScroller_(True)
        sr_scroll.setAutohidesScrollers_(True)
        sr_scroll.setWantsLayer_(True)
        sr_scroll.layer().setCornerRadius_(8.0)
        sr_scroll.layer().setBackgroundColor_(_hex_color("#1e1e20").CGColor())
        sr_scroll.layer().setBorderWidth_(0.5)
        sr_scroll.layer().setBorderColor_(
            _hex_color_alpha("#ffffff", 0.18).CGColor())
        sr_scroll.setHidden_(True)

        sr_table = NSTableView.alloc().initWithFrame_(
            NSMakeRect(0, 0, SR_W, SR_H))
        sr_table.setRowHeight_(18.0)
        sr_table.setHeaderView_(None)
        sr_table.setGridStyleMask_(0)
        sr_table.setBackgroundColor_(_hex_color("#1e1e20"))
        sr_table.setSelectionHighlightStyle_(0)

        sr_col = NSTableColumn.alloc().initWithIdentifier_("match")
        sr_col.setWidth_(SR_W - 6)
        sr_col.setEditable_(False)
        sr_table.addTableColumn_(sr_col)

        sr_delegate = SearchResultsDelegate.alloc().init()
        sr_delegate.owner = self
        sr_table.setDataSource_(sr_delegate)
        sr_table.setDelegate_(sr_delegate)

        sr_scroll.setDocumentView_(sr_table)
        card.addSubview_(sr_scroll)

        self._search_results_scroll    = sr_scroll
        self._search_results_table     = sr_table
        self._search_results_delegate  = sr_delegate

        # ── Right column: thumbnail ──────────────────────────────────────────
        THUMB_W, THUMB_H = 224, 126
        thumb_x = LEFT_W + ((RIGHT_W - THUMB_W) / 2)
        thumb_y = (CARD_H - THUMB_H) / 2

        thumb = NSView.alloc().initWithFrame_(
            NSMakeRect(thumb_x, thumb_y, THUMB_W, THUMB_H))
        thumb.setWantsLayer_(True)
        thumb.layer().setCornerRadius_(8.0)
        thumb.layer().setBackgroundColor_(_hex_color("#1a1a1c").CGColor())
        thumb.layer().setBorderWidth_(0.5)
        thumb.layer().setBorderColor_(
            _hex_color_alpha("#ffffff", 0.10).CGColor())
        card.addSubview_(thumb)

        # play icon centered
        icon_size = 40
        icon = NSImageView.alloc().initWithFrame_(NSMakeRect(
            (THUMB_W - icon_size) / 2, (THUMB_H - icon_size) / 2,
            icon_size, icon_size))
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "play.rectangle.fill", None)
        if img:
            icon.setImage_(img)
        icon.setContentTintColor_(NSColor.tertiaryLabelColor())
        thumb.addSubview_(icon)

        # Image view for actual video thumbnail (hidden until loaded)
        thumb_imgview = NSImageView.alloc().initWithFrame_(
            NSMakeRect(0, 0, THUMB_W, THUMB_H))
        thumb_imgview.setImageScaling_(0)  # NSImageScaleProportionallyDown
        thumb_imgview.setWantsLayer_(True)
        thumb_imgview.layer().setCornerRadius_(8.0)
        thumb_imgview.layer().setMasksToBounds_(True)
        thumb_imgview.setHidden_(True)
        thumb.addSubview_(thumb_imgview)

        self._now_thumb      = thumb
        self._now_thumb_icon = icon
        self._now_thumb_img  = thumb_imgview
        self._thumb_for_path = None

        # No drag handle — thumbnail column is not user-resizable

        # ── Resize handle between now-card and shortcut card ─────────────────
        handle_h = 12
        nc_h_resizer = CardHeightResizer.alloc().initWithFrame_(
            NSMakeRect(cx_card, cy_card - handle_h, CARD_W, handle_h))
        nc_h_resizer.owner  = self
        nc_h_resizer._attr  = "_now_card_h"
        nc_h_resizer._min_h = 185
        nc_h_resizer._max_h = 500
        cv.addSubview_(nc_h_resizer)
        self._now_card_h_resizer = nc_h_resizer

        # initial state
        self._set_step_state(active=0)

    def _reposition_now_card_internals(self, card_w, card_h):
        """Reposition all internal elements of the now-tagging card when its size changes."""
        from AppKit import NSMakeRect
        left_w  = max(180, int(card_w * self._now_left_ratio))
        right_w = card_w - left_w - 1

        if hasattr(self, "_now_filename"):
            self._now_filename.setFrame_(
                NSMakeRect(20, card_h - 30, left_w - 40, 18))

        if hasattr(self, "_now_fn_sep"):
            self._now_fn_sep.setFrame_(
                NSMakeRect(0, card_h - 36, left_w, 1))

        if hasattr(self, "_now_div"):
            self._now_div.setFrame_(
                NSMakeRect(left_w, 24, 1, card_h - 48))

        if hasattr(self, "_now_tag_preview"):
            self._now_tag_preview.setFrame_(
                NSMakeRect(20, card_h - 68, left_w - 40, 22))

        if hasattr(self, "_now_hint"):
            self._now_hint.setFrame_(
                NSMakeRect(20, 18, left_w - 40, 14))

        if hasattr(self, "_search_results_scroll"):
            sr_h = self._search_results_scroll.frame().size.height
            self._search_results_scroll.setFrame_(
                NSMakeRect(20, 34, left_w - 40, sr_h))

        # Thumbnail — fill right column with uniform padding on all 4 sides, maintain 16:9
        if hasattr(self, "_now_thumb"):
            THUMB_PAD = 16
            avail_w = max(40, right_w - 2 * THUMB_PAD)
            avail_h = max(24, card_h - 2 * THUMB_PAD)
            if avail_w / max(avail_h, 1) > 16 / 9:
                thumb_h = avail_h
                thumb_w = int(thumb_h * 16 / 9)
            else:
                thumb_w = avail_w
                thumb_h = int(thumb_w * 9 / 16)
            thumb_x = left_w + 1 + (right_w - thumb_w) / 2
            thumb_y = (card_h - thumb_h) / 2
            self._now_thumb.setFrame_(
                NSMakeRect(thumb_x, thumb_y, thumb_w, thumb_h))
            if hasattr(self, "_now_thumb_img"):
                self._now_thumb_img.setFrame_(
                    NSMakeRect(0, 0, thumb_w, thumb_h))
            if hasattr(self, "_now_thumb_icon"):
                icon_sz = min(40, max(20, thumb_w // 4))
                self._now_thumb_icon.setFrame_(NSMakeRect(
                    (thumb_w - icon_sz) / 2, (thumb_h - icon_sz) / 2,
                    icon_sz, icon_sz))

        # Rebuild step circles when left_w or card_h shifts meaningfully
        self._step_circles_left_w = left_w
        self._step_circles_card_h = card_h
        old_w = getattr(self, "_last_step_circles_w", 0)
        old_h = getattr(self, "_last_step_circles_h", 0)
        if abs(old_w - left_w) > 6 or abs(old_h - card_h) > 6:
            self._last_step_circles_w = left_w
            self._last_step_circles_h = card_h
            self._build_step_circles()

    # ── Shortcut cards ────────────────────────────────────────────────────────

    def _build_shortcut_cards(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect,
            NSScrollView,
        )

        TOTAL_W  = 700                   # match Now Tagging card width
        CARD_H   = self._sc_card_h
        FILE_LIST_W = 260
        cards_x  = SIDEBAR_W + FILE_LIST_W + 20
        cx       = cards_x + ((W - cards_x) - TOTAL_W) / 2

        self._sc_total_w      = TOTAL_W
        self._sc_current_bank = "players"

        # Position below Now Tagging card
        now_card_h = self._now_card_h
        now_card_y = H - TOP_H - 32 - now_card_h
        cy         = now_card_y - 20 - CARD_H

        self._sc_cv              = cv   # stored for rebuild
        self._sc_cx              = cx
        self._sc_cy              = cy
        self._sc_cards           = {}
        self._sc_titles          = {}
        self._sc_pill_containers = {}
        self._sc_scrollviews     = {}

        for bank in self._steps:
            title = self._step_labels_map.get(bank, bank).upper()
            card = NSView.alloc().initWithFrame_(
                NSMakeRect(cx, cy, TOTAL_W, CARD_H))
            card.setWantsLayer_(True)
            card.layer().setCornerRadius_(14.0)
            card.layer().setBackgroundColor_(_hex_color("#252528").CGColor())
            card.layer().setBorderWidth_(0.5)
            card.layer().setBorderColor_(
                _hex_color_alpha("#ffffff", 0.08).CGColor())
            card.setAutoresizingMask_(8)  # minY only — x-position managed by _reposition_layout
            # Stack all cards at the same position; only current bank is opaque
            card.setAlphaValue_(1.0 if bank == "players" else 0.0)
            cv.addSubview_(card)
            self._sc_cards[bank] = card

            # Title
            title_lbl = NSTextField.labelWithString_(title)
            title_lbl.setFont_(NSFont.boldSystemFontOfSize_(11))
            title_lbl.setTextColor_(NSColor.secondaryLabelColor())
            title_lbl.setFrame_(NSMakeRect(20, CARD_H - 30, TOTAL_W - 40, 14))
            card.addSubview_(title_lbl)
            self._sc_titles[bank] = title_lbl

            # Scroll view for pills
            sv = NSScrollView.alloc().initWithFrame_(
                NSMakeRect(12, 14, TOTAL_W - 24, CARD_H - 50))
            sv.setHasVerticalScroller_(True)
            sv.setAutohidesScrollers_(True)
            sv.setBorderType_(0)
            sv.setDrawsBackground_(False)
            card.addSubview_(sv)
            self._sc_scrollviews[bank] = sv

            container = NSView.alloc().initWithFrame_(
                NSMakeRect(0, 0, sv.bounds().size.width, 0))
            sv.setDocumentView_(container)
            self._sc_pill_containers[bank] = container

            self._populate_shortcut_pills(bank)

        # Initial active card styling
        self._set_active_shortcut_card("players")

        # ── Resize handle below shortcut card ───────────────────────────────
        handle_h = 12
        sc_h_resizer = CardHeightResizer.alloc().initWithFrame_(
            NSMakeRect(cx, cy - handle_h, TOTAL_W, handle_h))
        sc_h_resizer.owner  = self
        sc_h_resizer._attr  = "_sc_card_h"
        sc_h_resizer._min_h = 120
        sc_h_resizer._max_h = 600
        cv.addSubview_(sc_h_resizer)
        self._sc_card_h_resizer = sc_h_resizer

    def _rebuild_sc_cards(self):
        """Remove existing shortcut cards and rebuild from current self._steps."""
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect, NSScrollView,
        )
        cv      = getattr(self, "_sc_cv", None)
        if cv is None:
            return
        cx      = self._sc_cx
        cy      = self._sc_cy
        TOTAL_W = self._sc_total_w
        CARD_H  = self._sc_card_h

        for card in list(self._sc_cards.values()):
            card.removeFromSuperview()
        self._sc_cards           = {}
        self._sc_titles          = {}
        self._sc_pill_containers = {}
        self._sc_scrollviews     = {}
        self._chain_btns         = {}  # card views removed above; reset refs

        for bank in self._steps:
            title = self._step_labels_map.get(bank, bank).upper()
            card = NSView.alloc().initWithFrame_(
                NSMakeRect(cx, cy, TOTAL_W, CARD_H))
            card.setWantsLayer_(True)
            card.layer().setCornerRadius_(14.0)
            card.layer().setBackgroundColor_(_hex_color("#252528").CGColor())
            card.layer().setBorderWidth_(0.5)
            card.layer().setBorderColor_(
                _hex_color_alpha("#ffffff", 0.08).CGColor())
            card.setAutoresizingMask_(8)
            card.setAlphaValue_(1.0 if bank == "players" else 0.0)
            cv.addSubview_(card)
            self._sc_cards[bank] = card

            title_lbl = NSTextField.labelWithString_(title)
            title_lbl.setFont_(NSFont.boldSystemFontOfSize_(11))
            title_lbl.setTextColor_(NSColor.secondaryLabelColor())
            title_lbl.setFrame_(NSMakeRect(20, CARD_H - 30, TOTAL_W - 40, 14))
            card.addSubview_(title_lbl)
            self._sc_titles[bank] = title_lbl

            sv = NSScrollView.alloc().initWithFrame_(
                NSMakeRect(12, 14, TOTAL_W - 24, CARD_H - 50))
            sv.setHasVerticalScroller_(True)
            sv.setAutohidesScrollers_(True)
            sv.setBorderType_(0)
            sv.setDrawsBackground_(False)
            card.addSubview_(sv)
            self._sc_scrollviews[bank] = sv

            container = NSView.alloc().initWithFrame_(
                NSMakeRect(0, 0, sv.bounds().size.width, 0))
            sv.setDocumentView_(container)
            self._sc_pill_containers[bank] = container

            self._populate_shortcut_pills(bank)

        self._sc_current_bank = "players"
        self._set_active_shortcut_card("players")

    # ── Tagging key handling ──────────────────────────────────────────────────

    def handle_key(self, chars: str):
        if not chars:
            return
        key = chars[0]

        # Search mode intercepts all keys
        if self._search_mode:
            self._handle_search_key(chars)
            return

        # Arrow keys → move file list selection
        if key in ('', ''):  # up / down arrow
            if not self._files:
                return
            delta = -1 if key == '' else 1
            new_idx = max(0, min(len(self._files) - 1,
                                 self._selected_file_idx + delta))
            if new_idx != self._selected_file_idx:
                from AppKit import NSIndexSet
                self._file_list_table.selectRowIndexes_byExtendingSelection_(
                    NSIndexSet.indexSetWithIndex_(new_idx), False)
                self._file_list_table.scrollRowToVisible_(new_idx)
                self._on_file_selected(new_idx)
            return

        # TAB → advance to next file (only when not mid-tag)
        if key == "\t":
            if self.step is None and self._files:
                new_idx = min(len(self._files) - 1, self._selected_file_idx + 1)
                if new_idx != self._selected_file_idx:
                    from AppKit import NSIndexSet
                    self._file_list_table.selectRowIndexes_byExtendingSelection_(
                        NSIndexSet.indexSetWithIndex_(new_idx), False)
                    self._file_list_table.scrollRowToVisible_(new_idx)
                    self._on_file_selected(new_idx)
            return

        # SPACE → QuickLook (or space typed into custom label)
        if key == " ":
            if self._custom_mode and self.step is not None:
                self._handle_custom_input(key)
                return
            if self._selected_file_idx >= 0 and self._files:
                f = self._files[self._selected_file_idx]
                close_quicklook()
                quicklook(str(f))
                self._set_v2_hint("Previewing…  ENTER to start logging")
            return

        # ENTER → arm tagging, skip/advance current step, or confirm custom insert
        if key in ("\r", "\n"):
            if self._custom_mode:
                label = self._custom_input.strip()
                if label:
                    self._confirm_custom_label_v2(label)
                else:
                    # Empty input — cancel custom mode, return to step
                    self._custom_mode        = False
                    self._custom_input       = ""
                    self.step                = self._step_before_custom
                    self._step_before_custom = None
                    if self.step:
                        title, hint = self._step_label(self.step)
                        self._set_v2_hint(f"⚡ {title}  —  {hint}")
                        self._now_tag_preview.setStringValue_(
                            "_".join(self._tag_parts) or "…")
                return
            if self._selected_file_idx < 0 or not self._files:
                return
            if self.step is None:
                self._reset_tag_state()
                self._start_player_step()
            elif self.step is not None:
                if self.step == self._steps[-1]:
                    self._finalize_v2()
                else:
                    self._advance_step_v2("—")
            return

        # ESC → cancel
        if key == "\x1b":
            self._reset_branch_state()   # restore card title if mid-branch
            self.step                    = None
            self._tag_parts              = []
            self._custom_indices         = set()
            self._custom_mode            = False
            self._custom_input           = ""
            self._step_before_custom     = None
            self._chain_boundary_indices = set()
            self._branch_stack           = []
            self._branch_items           = None
            self._search_mode            = False
            self._search_text            = ""
            self._search_matches         = []
            self._search_idx             = 0
            self._hide_search_panel()
            self._set_v2_hint("Select a file · then press  ↵ ENTER  to log it")
            self._now_tag_preview.setStringValue_("—")
            self._set_step_state(active=-1)
            return

        # BACKSPACE → pop last tag part (or exit branch); in custom mode falls
        # through so _handle_custom_input can delete the last typed character
        if key == "\x7f" and not self._custom_mode:
            if self.step is not None:
                if self._branch_stack:
                    self._exit_branch()
                elif self._tag_parts:
                    popped_idx = len(self._tag_parts) - 1
                    self._tag_parts.pop()
                    self._custom_indices         = {i for i in self._custom_indices
                                                    if i < popped_idx}
                    self._chain_boundary_indices = {i for i in self._chain_boundary_indices
                                                    if i < popped_idx}
                    self._now_tag_preview.setStringValue_(
                        "_".join(self._tag_parts) or "…")
                    self._set_v2_hint(
                        "⌫  Removed last label  ·  press a key or ENTER to advance")
            return

        # + → chain: start a new player sequence on the same clip
        if key in ("+", "=") and self.step is not None and not self._custom_mode:
            self._chain_to_player()
            return

        # Shortcut key or custom input
        if self.step is not None:
            if self._custom_mode:
                self._handle_custom_input(key)
            else:
                bank  = self.step
                items = (self._branch_items if self._branch_items is not None
                         else self.shortcuts.get(bank, []))
                sc = next((s for s in items
                           if s["key"].lower() == key.lower()), None)
                in_branch = self._branch_items is not None
                digit_search = key.isdigit() and self._player_number_search
                if len(key) == 1 and (key.isalpha() or digit_search) and self._search_enabled and not in_branch:
                    self._enter_search_mode(key)
                elif sc is not None:
                    self._handle_shortcut_key_v2(sc)

    def _handle_shortcut_key_v2(self, sc: dict):
        bank     = self.step
        children = sc.get("children", [])
        if children:
            self._enter_branch(sc)
            return
        label = sc["label"]
        self._tag_parts.append(label.replace(" ", "_"))
        self._now_tag_preview.setStringValue_("_".join(self._tag_parts) or "—")
        step_lbl = self._step_labels_map.get(bank, bank.title())
        self._set_v2_hint(
            f"⚡ {step_lbl}  —  ✔ {label}  ·  press another key or ENTER to advance"
        )

    def handle_cmd_z(self):
        if self.app:
            self.app.undo_last(None)

    # ── Branch helpers ────────────────────────────────────────────────────────

    def _reset_branch_state(self):
        """Clear branch stack and restore card title for current step's bank."""
        if not self._branch_stack and self._branch_items is None:
            return
        bank = self.step
        self._branch_stack = []
        self._branch_items = None
        if bank and bank in getattr(self, "_sc_titles", {}):
            step_lbl = self._step_labels_map.get(bank, bank.title())
            self._sc_titles[bank].setStringValue_(step_lbl.upper())
            self._populate_shortcut_pills(bank)

    def _reset_tag_state(self):
        """Full reset of all tagging session state. Call after finalize, skip, or cancel."""
        self._tag_parts              = []
        self._custom_indices         = set()
        self._custom_input           = ""
        self._chain_boundary_indices = set()
        self._search_mode            = False
        self._search_text            = ""
        self._search_matches         = []
        self._search_idx             = 0
        self._reset_branch_state()
        self.step = None

    def _enter_branch(self, parent_sc):
        """Push a branch and re-render the current card with the parent's children."""
        self._branch_stack.append({
            "parent_label": parent_sc["label"],
            "prev_items":   self._branch_items,
        })
        self._branch_items = parent_sc["children"]
        bank = self.step
        if bank in getattr(self, "_sc_titles", {}):
            step_lbl = self._step_labels_map.get(bank, bank.title())
            breadcrumb = "  ▸  ".join(
                [step_lbl.upper()] + [f["parent_label"].upper() for f in self._branch_stack]
            )
            self._sc_titles[bank].setStringValue_(breadcrumb)
        self._populate_shortcut_pills(bank)
        self._set_v2_hint(
            f"⚡ {parent_sc['label']} branch  —  choose a label  ·  ⌫ to go back"
        )

    def _exit_branch(self):
        """Pop one branch level and restore the card."""
        if not self._branch_stack:
            return
        frame = self._branch_stack.pop()
        self._branch_items = frame["prev_items"]
        bank = self.step
        if bank in getattr(self, "_sc_titles", {}):
            step_lbl = self._step_labels_map.get(bank, bank.title())
            if self._branch_stack:
                breadcrumb = "  ▸  ".join(
                    [step_lbl.upper()] + [f["parent_label"].upper() for f in self._branch_stack]
                )
                self._sc_titles[bank].setStringValue_(breadcrumb)
            else:
                self._sc_titles[bank].setStringValue_(step_lbl.upper())
        self._populate_shortcut_pills(bank)
        if self._branch_stack:
            top = self._branch_stack[-1]["parent_label"]
            self._set_v2_hint(
                f"⚡ {top} branch  —  choose a label  ·  ⌫ to go back"
            )
        else:
            bank_lbl = self._step_labels_map.get(bank, bank.title())
            self._set_v2_hint(
                f"⚡ {bank_lbl}  —  choose a label  ·  ENTER to advance"
            )

    # ── Chaining helper ───────────────────────────────────────────────────────

    def _chain_to_player(self):
        """Close current action and restart at player step without finalizing."""
        # Clear any active branch on the current bank before switching
        current_bank = self.step
        if self._branch_stack or self._branch_items is not None:
            self._branch_stack = []
            self._branch_items = None
            if current_bank and current_bank in getattr(self, "_sc_titles", {}):
                step_lbl = self._step_labels_map.get(current_bank, current_bank.title())
                self._sc_titles[current_bank].setStringValue_(step_lbl.upper())
                self._populate_shortcut_pills(current_bank)
        # Mark chain boundary at the current end of tag parts
        self._chain_boundary_indices.add(len(self._tag_parts))
        # Transition to player step without clearing the accumulated preview
        self.step = "players"
        self._set_step_state(active=0)   # triggers card cross-fade via _set_cards_for_step
        if self._players_bypass_hotkeys and not self._search_enabled:
            self._toggle_search_mode()
        title, hint = self._step_label("players")
        search_note = "  ·  ⌨ type to search" if self._search_enabled else ""
        self._set_v2_hint(f"⚡ + Chain  —  {title}: {hint}{search_note}")
        # Keep preview showing accumulated labels so the user knows they're still there
        acc = "_".join(self._tag_parts)
        self._now_tag_preview.setStringValue_(f"{acc}_…" if acc else "…")

    def _start_player_step(self):
        self.step = "players"
        self._set_step_state(active=0)
        if self._players_bypass_hotkeys:
            # Force search on so typing immediately filters the full roster
            if not self._search_enabled:
                self._toggle_search_mode()
            self._set_v2_hint("Type player name to search  ·  ⌥ for custom insert")
            self._now_tag_preview.setStringValue_("…")
        else:
            title, hint = self._step_label("players")
            search_note = "  ·  ⌨ type to search" if self._search_enabled else ""
            self._set_v2_hint(f"⚡ {title}  —  {hint}{search_note}")
            self._now_tag_preview.setStringValue_("…")

    def toggle_custom_mode(self):
        if self._custom_mode:
            # Option re-press cancels custom mode without confirming
            self._custom_mode        = False
            self._custom_input       = ""
            self.step                = self._step_before_custom
            self._step_before_custom = None
            if self.step:
                title, hint = self._step_label(self.step)
                self._set_v2_hint(f"⚡ {title}  —  {hint}")
                self._now_tag_preview.setStringValue_(
                    "_".join(self._tag_parts) or "…")
        else:
            if self.step is None:
                return
            if self._search_mode:
                self._exit_search_mode()
            self._custom_mode        = True
            self._custom_input       = ""
            self._step_before_custom = self.step
            self._set_v2_hint("⌥ Custom insert — type label, ENTER to confirm  ·  ⌥ to cancel")
            self._now_tag_preview.setStringValue_("INSERT  —  type label▌")

    def _handle_custom_input(self, key: str):
        if key == "\x7f":
            self._custom_input = self._custom_input[:-1]
        elif len(key) == 1 and key.isprintable():
            self._custom_input += key
        display = self._custom_input if self._custom_input else "…"
        self._now_tag_preview.setStringValue_(f"INSERT  —  {display}▌")

    def _confirm_custom_label_v2(self, label: str):
        self._custom_indices.add(len(self._tag_parts))
        self._tag_parts.append(label)
        self._custom_input       = ""
        self._custom_mode        = False
        self.step                = self._step_before_custom
        self._step_before_custom = None
        # Bypass mode: player name was typed — advance straight to plays
        if self._players_bypass_hotkeys and self.step == "players":
            self._advance_step_v2(f"Player: {label}")
            return
        if self.step:
            title, _ = self._step_label(self.step)
            self._set_v2_hint(
                f"⚡ {title}  —  ✔ {label}  ·  press another key or ENTER to advance"
            )
            self._now_tag_preview.setStringValue_("_".join(self._tag_parts) or "—")
        else:
            self._set_v2_hint(f"✔ Insert: {label}")

    # ── Search / autocomplete ─────────────────────────────────────────────────

    def _show_search_panel(self):
        if hasattr(self, "_search_results_scroll"):
            self._search_results_scroll.setHidden_(False)

    def _hide_search_panel(self):
        if hasattr(self, "_search_results_scroll"):
            self._search_results_scroll.setHidden_(True)

    def _refresh_search_panel(self):
        if not hasattr(self, "_search_results_table"):
            return
        from AppKit import NSIndexSet
        tv       = self._search_results_table
        delegate = self._search_results_delegate
        delegate._suppressed = True
        tv.reloadData()
        if self._search_matches:
            idx_set = NSIndexSet.indexSetWithIndex_(self._search_idx)
            tv.selectRowIndexes_byExtendingSelection_(idx_set, False)
            tv.scrollRowToVisible_(self._search_idx)
        else:
            tv.deselectAll_(None)
        delegate._suppressed = False

    def _confirm_search_selection(self):
        if not self._search_matches:
            return
        sc    = self._search_matches[self._search_idx]
        bank  = self.step
        label = sc["label"]
        self._exit_search_mode()
        self._tag_parts.append(label.replace(" ", "_"))
        self._now_tag_preview.setStringValue_("_".join(self._tag_parts) or "—")
        step_lbl = self._step_labels_map.get(bank, bank.title())
        self._set_v2_hint(
            f"⚡ {step_lbl}  —  ✔ {label}  ·  press another key or ENTER to advance"
        )

    def _enter_search_mode(self, initial_char: str):
        self._search_mode    = True
        self._search_text    = initial_char.upper()
        self._search_matches = []
        self._search_idx     = 0
        self._show_search_panel()
        self._update_search_display()

    def _exit_search_mode(self):
        self._search_mode    = False
        self._search_text    = ""
        self._search_matches = []
        self._search_idx     = 0
        self._hide_search_panel()
        if self.step:
            title, hint = self._step_label(self.step)
            self._set_v2_hint(f"⚡ {title}  —  {hint}")
        self._now_tag_preview.setStringValue_("_".join(self._tag_parts) or "…")

    def _update_search_display(self):
        bank   = self.step
        items  = self.shortcuts.get(bank, [])
        prefix = self._search_text.upper().replace("'", "")

        # When number-search is enabled and the typed text is all digits,
        # match by jersey number (prefix match); otherwise match by name.
        by_number = (self._player_number_search
                     and prefix.isdigit()
                     and len(prefix) > 0)

        def _matches(sc):
            if by_number:
                num = sc.get("number", "").strip().lstrip("0") or sc.get("number", "").strip()
                return num.startswith(prefix) or sc.get("number", "").strip().startswith(prefix)
            label = sc["label"]
            norm = label.upper().replace("'", "")
            if norm.startswith(prefix):
                return True
            # also match bare last name when label has an initial prefix (e.g. "A.COLBERT")
            if len(norm) > 2 and norm[1] == ".":
                return norm[2:].startswith(prefix)
            return False

        self._search_matches = sorted(
            [s for s in items if _matches(s)],
            key=lambda s: (s.get("number", "999").zfill(3) if by_number else s["label"])
        )
        if self._search_matches:
            self._search_idx = max(0, min(self._search_idx,
                                          len(self._search_matches) - 1))
            sc  = self._search_matches[self._search_idx]
            n   = len(self._search_matches)
            pos = f"  ({self._search_idx + 1} of {n})" if n > 1 else ""
            nav = "  ·  ↑↓ browse" if n > 1 else ""
            num_tag = f"  #{sc['number']}" if by_number and sc.get("number") else ""
            self._set_v2_hint(
                f"⌨  {self._search_text}  →  {sc['label']}{num_tag}{pos}{nav}"
                f"  ·  ENTER confirm  ·  ESC cancel"
            )
        else:
            self._search_idx = 0
            self._set_v2_hint(
                f"⌨  {self._search_text}  —  no match  ·  ESC cancel"
            )
        preview = self._tag_parts + [f"[{self._search_text}…]"]
        self._now_tag_preview.setStringValue_("_".join(preview))
        self._refresh_search_panel()

    def _handle_search_key(self, chars: str):
        key = chars[0] if chars else ""

        if key in ("\r", "\n"):
            self._confirm_search_selection()
            return

        if key == "\x1b":
            self._exit_search_mode()
            return

        if key == "":   # ↓ arrow
            if self._search_matches:
                self._search_idx = (self._search_idx + 1) % len(self._search_matches)
                self._update_search_display()
            return

        if key == "":   # ↑ arrow
            if self._search_matches:
                self._search_idx = (self._search_idx - 1) % len(self._search_matches)
                self._update_search_display()
            return

        if key == "\x7f":     # backspace
            if self._search_text:
                self._search_text = self._search_text[:-1]
                self._search_idx  = 0
                if self._search_text:
                    self._update_search_display()
                else:
                    self._exit_search_mode()
            return

        if len(key) == 1 and key.isprintable():
            self._search_text += key.upper()
            self._search_idx   = 0
            self._update_search_display()

    def _advance_step_v2(self, confirmed_text: str):
        current_idx = self._steps.index(self.step)
        next_idx    = current_idx + 1
        if next_idx >= len(self._steps):
            self._finalize_v2()
            return
        self.step          = self._steps[next_idx]
        title, hint        = self._step_label(self.step)
        self._custom_input = ""
        search_note = "  ·  ⌨ type to search" if self._search_enabled else ""
        self._set_v2_hint(f"⚡ {title}  —  {hint}{search_note}")
        self._now_tag_preview.setStringValue_("_".join(self._tag_parts) or "—")
        self._set_step_state(active=next_idx, completed=tuple(range(next_idx)))

    def _finalize_v2(self):
        from AppKit import NSIndexSet
        if self._selected_file_idx < 0 or not self._files:
            return
        f = self._files[self._selected_file_idx]
        close_quicklook()

        tag_str  = "_".join(self._tag_parts)
        stem     = f.stem
        seg      = stem.split("_")
        base     = "_".join(seg[:6]) if len(seg) >= 6 else stem
        base     = base.rstrip("_")
        new_name = f"{base}_{tag_str}{f.suffix}" if tag_str else f"{base}{f.suffix}"
        new_path = f.parent / new_name

        old_name    = f.name
        folder_root = f.parent

        conflict = SafeRenamer.check_destination(f, new_path)
        if conflict:
            cb = self._settings.get("conflict_behavior", "ask")
            if cb == "skip":
                self._reset_tag_state()
                self._refresh_files()
                return
            else:  # ask (overwrite option removed — would destroy existing footage)
                from AppKit import NSAlert
                alert = NSAlert.alloc().init()
                alert.setMessageText_("File Already Exists")
                alert.setInformativeText_(
                    f"{new_path.name} already exists in this folder.\n\n"
                    "Skip leaves both files unchanged. Cancel returns you to the tag screen.")
                alert.addButtonWithTitle_("Skip")
                alert.addButtonWithTitle_("Cancel")
                resp = alert.runModal()
                if resp == 1000:  # Skip
                    self._reset_tag_state()
                    self._refresh_files()
                    return
                if resp == 1001:  # Cancel
                    self._set_v2_hint("❌  Rename cancelled — file already exists.")
                    return

        ok, err = SafeRenamer.safe_rename(
            f, new_path, folder_root,
            self.app.session if self.app else None)
        if not ok:
            self._set_v2_hint(f"❌  {err}")
            self.step = None
            return
        if self.app:
            self.app._push_undo({
                "type": "tag",
                "folder": str(f.parent),
                "timestamp": datetime.now().isoformat(),
                "renames": [{"old": old_name, "new": new_name}],
            }, max_stack=self._settings.get("undo_stack_size", 50))
            # Log stat — split at chain boundaries, hotkey parts only per segment
            boundaries = sorted(self._chain_boundary_indices)
            seg_starts = [0] + boundaries
            seg_ends   = boundaries + [len(self._tag_parts)]
            for start, end in zip(seg_starts, seg_ends):
                seg = [self._tag_parts[i] for i in range(start, end)
                       if i not in self._custom_indices]
                if not seg:
                    continue
                if self._settings.get("record_stats", True):
                    log_stat(
                        self.app.session,
                        seg[0]              if len(seg) >= 1 else "",
                        "_".join(seg[1:-1]) if len(seg) >= 3 else "",
                        seg[-1]             if len(seg) >= 2 else "",
                    )

        self._now_tag_preview.setStringValue_(f"✓  {new_name}")
        self._set_v2_hint("↵  ENTER to log this file  ·  SPACE to preview  ·  TAB for next")

        self._reset_tag_state()
        self._set_step_state(active=-1)
        self._refresh_files()

        # Sound feedback
        if self._settings.get("sound_on_rename", False):
            try:
                from AppKit import NSSound
                NSSound.soundNamed_("Glass").play()
            except Exception:
                pass

        # Auto-advance to next file
        if self._settings.get("auto_advance_after_tag", True) and self._files:
            next_row = min(self._selected_file_idx, len(self._files) - 1)
            self._selected_file_idx = next_row
            self._file_list_table.selectRowIndexes_byExtendingSelection_(
                NSIndexSet.indexSetWithIndex_(next_row), False)
            self._file_list_table.scrollRowToVisible_(next_row)
            self._on_file_selected(next_row)

    def _set_v2_hint(self, text: str):
        if hasattr(self, "_now_hint"):
            self._now_hint.setStringValue_(text)

    # ── File list panel ───────────────────────────────────────────────────────

    def _build_file_list(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSScrollView, NSTableColumn,
            NSTextField, NSFont, NSColor, NSMakeRect, NSIndexSet,
        )

        FILE_LIST_W = 260
        panel_x = SIDEBAR_W + 12
        panel_y = 12
        panel_h = H - TOP_H - 24

        panel = NSView.alloc().initWithFrame_(
            NSMakeRect(panel_x, panel_y, FILE_LIST_W, panel_h))
        panel.setWantsLayer_(True)
        panel.layer().setCornerRadius_(8.0)
        panel.layer().setBackgroundColor_(_hex_color("#252528").CGColor())
        panel.layer().setBorderWidth_(0.5)
        panel.layer().setBorderColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        panel.setAutoresizingMask_(16)  # heightSizable — bottom stays fixed at y=12
        cv.addSubview_(panel)
        self._file_list_panel = panel

        # Header label — sizeToFit measures real text size, then frame is
        # positioned exactly centered in the 36px header strip above the scroll view
        HEADER_STRIP_H = 36  # matches scroll_y=8 + scroll_h=panel_h-44 → top at panel_h-36
        hdr = NSTextField.labelWithString_("VIDEO FILES")
        hdr.setFont_(NSFont.boldSystemFontOfSize_(13))
        hdr.setTextColor_(_hex_color(COLOR_TAN))
        hdr.sizeToFit()
        lbl_sz = hdr.frame().size
        hdr.setFrame_(NSMakeRect(
            (FILE_LIST_W - lbl_sz.width) / 2,
            panel_h - HEADER_STRIP_H + (HEADER_STRIP_H - lbl_sz.height) / 2,
            lbl_sz.width, lbl_sz.height))
        hdr.setAutoresizingMask_(8)  # MinYMargin — stays pinned to top of panel
        panel.addSubview_(hdr)

        # Scroll + table
        scroll_y = 8
        scroll_h = panel_h - 44
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, scroll_y, FILE_LIST_W, scroll_h))
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        scroll.setDrawsBackground_(False)
        scroll.setAutoresizingMask_(2 | 16)  # widthSizable + heightSizable
        panel.addSubview_(scroll)

        table = KeyTableView.alloc().initWithFrame_(
            NSMakeRect(0, 0, FILE_LIST_W, scroll_h))
        table.owner = self
        table.setBackgroundColor_(_hex_color("#252528"))
        table.setRowHeight_(26)
        table.setGridStyleMask_(0)
        table.setUsesAlternatingRowBackgroundColors_(False)
        table.setSelectionHighlightStyle_(1)  # NSTableViewSelectionHighlightStyleRegular
        table.setHeaderView_(None)

        col = NSTableColumn.alloc().initWithIdentifier_("name")
        col.setWidth_(FILE_LIST_W - 20)
        col.setEditable_(False)
        table.addTableColumn_(col)

        scroll.setDocumentView_(table)

        self._files            = []
        self._selected_file_idx = -1
        self._file_list_delegate = FileListDelegate.alloc().init()
        self._file_list_delegate.owner = self
        table.setDataSource_(self._file_list_delegate)
        table.setDelegate_(self._file_list_delegate)
        self._file_list_table = table

        self._build_empty_state_overlay(panel, FILE_LIST_W, panel_h)
        self._refresh_files()
        self.win.makeFirstResponder_(table)

        # Drag-resize handle — a thin invisible strip on the right edge of the panel.
        # 8px wide so it's easy to grab; spans full panel height.
        handle = FilePanelResizer.alloc().initWithFrame_(
            NSMakeRect(panel_x + FILE_LIST_W - 3, panel_y, 8, panel_h))
        handle.owner = self
        handle.setAutoresizingMask_(16)  # heightSizable
        cv.addSubview_(handle)
        self._fl_resize_handle = handle

    def _build_empty_state_overlay(self, panel, FILE_LIST_W, panel_h):
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect
        scroll_y = 8
        scroll_h = panel_h - 44
        ov = NSView.alloc().initWithFrame_(NSMakeRect(0, scroll_y, FILE_LIST_W, scroll_h))
        ov.setWantsLayer_(True)
        ov.layer().setBackgroundColor_(_hex_color("#252528").CGColor())
        ov.setAutoresizingMask_(2 | 16)   # widthSizable + heightSizable — mirrors scroll view
        panel.addSubview_(ov)

        mid = scroll_h / 2

        icon = NSTextField.labelWithString_("📁")
        icon.setFont_(NSFont.systemFontOfSize_(32))
        icon.setAlignment_(2)   # NSTextAlignmentCenter
        icon.sizeToFit()
        isz = icon.frame().size
        icon.setFrame_(NSMakeRect((FILE_LIST_W - isz.width) / 2, mid + 20, isz.width, isz.height))
        icon.setAutoresizingMask_(1 | 4 | 2 | 8)   # all margins flexible → stays centered
        ov.addSubview_(icon)

        msg = NSTextField.labelWithString_("No folder selected")
        msg.setFont_(NSFont.systemFontOfSize_(12))
        msg.setTextColor_(NSColor.labelColor())
        msg.setAlignment_(2)
        msg.sizeToFit()
        msz = msg.frame().size
        msg.setFrame_(NSMakeRect((FILE_LIST_W - msz.width) / 2, mid - 6, msz.width, msz.height))
        msg.setAutoresizingMask_(1 | 4 | 2 | 8)
        ov.addSubview_(msg)

        btn_w, btn_h = 140, 28
        btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect((FILE_LIST_W - btn_w) / 2, mid - 50, btn_w, btn_h))
        btn.configureTitle_bg_press_action_(
            "Open Folder", COLOR_CRIMSON, "#6b1a26", self._session_choose_folder)
        btn.setAutoresizingMask_(1 | 4 | 2 | 8)
        ov.addSubview_(btn)

        self._empty_state_overlay = ov
        self._empty_state_msg     = msg

    def _refresh_files(self):
        if self.folder and self.folder.is_dir():
            sort = self._settings.get("file_sort_order", "name_asc")
            if sort == "name_desc":
                key_fn, rev = (lambda f: f.name), True
            elif sort == "date_created":
                key_fn = lambda f: getattr(f.stat(), "st_birthtime", f.stat().st_mtime)
                rev = False
            elif sort == "date_modified":
                key_fn, rev = (lambda f: f.stat().st_mtime), False
            else:
                key_fn, rev = (lambda f: f.name), False
            self._files = sorted(
                [f for f in self.folder.iterdir() if is_video(f)],
                key=key_fn, reverse=rev)
        else:
            self._files = []
        if hasattr(self, "_file_list_table"):
            self._file_list_table.reloadData()
        if hasattr(self, "_empty_state_overlay"):
            show_empty = not bool(self._files)
            self._empty_state_overlay.setHidden_(not show_empty)
            if show_empty and hasattr(self, "_empty_state_msg"):
                no_folder = not self.folder or not self.folder.is_dir()
                self._empty_state_msg.setStringValue_(
                    "No folder selected" if no_folder else "No video files found")

    def _on_file_selected(self, row):
        self._selected_file_idx = row
        if not (self._files and row < len(self._files)):
            return
        f = self._files[row]
        if hasattr(self, "_now_filename"):
            self._now_filename.setStringValue_(f.name)
        # Reset thumbnail to placeholder, then load in background
        self._thumb_for_path = str(f)
        if hasattr(self, "_now_thumb_img"):
            self._now_thumb_img.setHidden_(True)
        if hasattr(self, "_now_thumb_icon"):
            self._now_thumb_icon.setHidden_(False)
        threading.Thread(target=self._load_thumb, args=(f,), daemon=True).start()
        if self._settings.get("arm_on_file_select", False) and self.step is None:
            self._start_player_step()
        elif self.step is None:
            self._set_v2_hint("↵  ENTER to log this file  ·  SPACE to preview  ·  TAB for next")

    def _load_thumb(self, path):
        # Generate CGImage in background, encode to JPEG bytes via ImageIO
        # (thread-safe, no AppKit, no color-space issues), then create NSImage
        # from bytes on main thread.  Every NSImage/CGImage API that accepts a
        # CGImageRef directly crashes on macOS 26 with HDR/wide-gamut sources.
        try:
            import AVFoundation, CoreMedia
            from Foundation import NSURL, NSMutableData
            import threading as _threading
            url   = NSURL.fileURLWithPath_(str(path))
            asset = AVFoundation.AVURLAsset.URLAssetWithURL_options_(url, None)
            gen   = AVFoundation.AVAssetImageGenerator.assetImageGeneratorWithAsset_(asset)
            gen.setAppliesPreferredTrackTransform_(True)
            gen.setRequestedTimeToleranceBefore_(CoreMedia.CMTimeMakeWithSeconds(2.0, 600))
            gen.setRequestedTimeToleranceAfter_(CoreMedia.CMTimeMakeWithSeconds(2.0, 600))
            req_time = CoreMedia.CMTimeMakeWithSeconds(1.0, 600)
            done     = _threading.Event()
            result_box = [None]

            def _handler(cgimg, actual_time, error):
                result_box[0] = cgimg
                done.set()

            gen.generateCGImageAsynchronouslyForTime_completionHandler_(req_time, _handler)
            done.wait(timeout=10.0)

            cgimg = result_box[0]
            if not cgimg or getattr(self, "_thumb_for_path", None) != str(path):
                return

            # Encode CGImage → JPEG bytes using ImageIO (handles any color space)
            try:
                from Quartz import (CGImageDestinationCreateWithData,
                                    CGImageDestinationAddImage,
                                    CGImageDestinationFinalize)
            except ImportError:
                from ImageIO import (CGImageDestinationCreateWithData,
                                     CGImageDestinationAddImage,
                                     CGImageDestinationFinalize)
            data = NSMutableData.data()
            dest = CGImageDestinationCreateWithData(data, "public.jpeg", 1, None)
            if not dest:
                return
            CGImageDestinationAddImage(dest, cgimg, None)
            if CGImageDestinationFinalize(dest) and len(data) > 0:
                caller = MainCaller.alloc().init()
                caller._cb = lambda d=data: self._render_thumb_from_data(d)
                caller.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "fire:", None, False)
        except Exception:
            pass

    def _render_thumb_from_data(self, data):
        try:
            from AppKit import NSImage
            img = NSImage.alloc().initWithData_(data)
            if img:
                self._set_thumb_image(img)
        except Exception:
            pass

    def _set_thumb_image(self, img):
        if hasattr(self, "_now_thumb_img"):
            self._now_thumb_img.setImage_(img)
            self._now_thumb_img.setHidden_(False)
        if hasattr(self, "_now_thumb_icon"):
            self._now_thumb_icon.setHidden_(True)

    def _populate_shortcut_pills(self, bank):
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect
        container = self._sc_pill_containers[bank]
        for v in list(container.subviews()):
            v.removeFromSuperview()

        sv          = self._sc_scrollviews[bank]
        items       = (self._branch_items if self._branch_items is not None
                       else self.shortcuts.get(bank, []))
        PILL_H      = 28
        ROW_GAP     = 6
        COL_GAP     = 8
        MIN_PILL_W  = 100
        TITLE_PAD   = 50  # title label + top/bottom padding inside card
        show_nums   = (bank == "players"
                       and self._settings.get("show_jersey_numbers", True)
                       and any(sc.get("number", "") for sc in items))
        NUM_W, NUM_GAP = (32, 4) if show_nums else (0, 0)

        card_w      = getattr(self, "_effective_card_w", None)
        sv_w        = sv.frame().size.width or container.frame().size.width
        if card_w:
            sv_w = card_w - 24  # 12px inset on each side
            sv.setFrame_(NSMakeRect(12, 14, sv_w, sv.frame().size.height))
        container_w = sv_w

        # Columns: max that both fits the window (MIN_PILL_W) and shows labels untruncated.
        # 12pt system font ≈ 7.2px/char. Iterate up from 2; stop when pills get too narrow.
        density = self._settings.get("pill_density", "auto") if bank == "players" else "auto"
        max_cols_by_w = max(2, int((card_w or container_w + 24 + COL_GAP) / (MIN_PILL_W + COL_GAP)))
        if density == "compact":
            max_cols_by_w = max(max_cols_by_w, 7)
        elif density == "large":
            max_cols_by_w = min(max_cols_by_w, 3)
        cols = 2
        for c in range(2, min(6 if density == "auto" else 7, max_cols_by_w) + 1):
            cw = (container_w - COL_GAP * (c - 1)) / c
            if density == "auto" and items and any(
                    len(sc["label"]) * 7.2 > cw - 46 - NUM_W - NUM_GAP for sc in items):
                break
            cols = c
        col_w = (container_w - COL_GAP * (cols - 1)) / cols

        font_size = 11 if density == "compact" else (14 if density == "large" else 12)
        _font   = NSFont.systemFontOfSize_(font_size)
        PILL_H  = 40 if density == "compact" else (52 if density == "large" else 28)
        label_h = 16

        n_rows     = (len(items) + cols - 1) // cols if items else 1
        content_h  = n_rows * PILL_H + max(n_rows - 1, 0) * ROW_GAP
        if not items and bank == "players":
            content_h = max(content_h, 80)   # room for the empty-state message
        new_card_h = content_h + TITLE_PAD
        container.setFrame_(NSMakeRect(0, 0, container_w, content_h))

        # Resize the card: anchor top just below the now-tagging card, grow downward.
        card = self._sc_cards.get(bank)
        if card:
            cf = card.frame()
            if hasattr(self, "_now_card"):
                now_y       = self._now_card.frame().origin.y
                card_top    = now_y - 20           # 20px gap below now-tagging card
                available_h = max(60, card_top - 20)  # 20px bottom margin
            else:
                card_top    = cf.origin.y + cf.size.height
                available_h = new_card_h
            actual_h    = min(new_card_h, available_h)
            actual_sv_h = actual_h - TITLE_PAD
            card_origin_y = card_top - actual_h
            card.setFrame_(NSMakeRect(cf.origin.x, card_origin_y, cf.size.width, actual_h))
            sv.setFrame_(NSMakeRect(12, 14, sv_w, actual_sv_h))
            # Keep _sc_card_h in sync so _reposition_layout uses the correct height
            self._sc_card_h = actual_h
            if hasattr(self, "_sc_card_h_resizer"):
                self._sc_card_h_resizer.setFrame_(
                    NSMakeRect(cf.origin.x, card_origin_y - 12, cf.size.width, 12))
        else:
            actual_h    = new_card_h
            actual_sv_h = content_h
        title_lbl = self._sc_titles.get(bank)
        if title_lbl:
            title_lbl.setFrame_(NSMakeRect(20, actual_h - 30, sv_w - 116, 14))

        # + Player (+) chain button — shown on every non-player card, top-right corner
        if bank != "players" and card:
            chain_btn = self._chain_btns.get(bank)
            if chain_btn is None:
                chain_btn = PillButton.alloc().initWithFrame_(NSMakeRect(0, 0, 110, 22))
                chain_btn.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.06).CGColor())
                chain_btn.layer().setBorderWidth_(0.5)
                chain_btn.layer().setBorderColor_(
                    _hex_color_alpha("#ffffff", 0.18).CGColor())
                chain_btn.layer().setCornerRadius_(6.0)
                c_lbl = NSTextField.labelWithString_("+ Player  (+)")
                c_lbl.setFont_(NSFont.systemFontOfSize_(10))
                c_lbl.setTextColor_(NSColor.secondaryLabelColor())
                c_lbl.sizeToFit()
                cz = c_lbl.frame()
                c_lbl.setFrame_(NSMakeRect(
                    (110 - cz.size.width) / 2,
                    (22 - cz.size.height) / 2,
                    cz.size.width, cz.size.height))
                chain_btn.addSubview_(c_lbl)
                chain_btn.setClickHandler_(lambda v, e: self._chain_to_player())
                card.addSubview_(chain_btn)
                self._chain_btns[bank] = chain_btn
            chain_btn.setFrame_(NSMakeRect(cf.size.width - 122, actual_h - 30, 110, 22))

        for i, sc in enumerate(items):
            row = i // cols
            col = i % cols
            x   = col * (col_w + COL_GAP)
            y   = content_h - (row + 1) * PILL_H - row * ROW_GAP

            pill = NSView.alloc().initWithFrame_(NSMakeRect(x, y, col_w, PILL_H))
            pill.setWantsLayer_(True)
            pill.layer().setCornerRadius_(7.0)
            pill.layer().setBackgroundColor_(
                _hex_color_alpha("#ffffff", 0.05).CGColor())
            pill.layer().setBorderWidth_(0.5)
            pill.layer().setBorderColor_(
                _hex_color_alpha("#ffffff", 0.08).CGColor())

            has_key = bool(sc.get("key", ""))
            key_bg = NSView.alloc().initWithFrame_(
                NSMakeRect(8, (PILL_H - 20) / 2, 22, 20))
            key_bg.setWantsLayer_(True)
            key_bg.layer().setCornerRadius_(5.0)
            key_bg.layer().setBackgroundColor_(
                _hex_color_alpha("#000000", 0.15 if not has_key else 0.30).CGColor())
            pill.addSubview_(key_bg)

            key_text = sc["key"].upper() if has_key else "·"
            key_color = "#dbcca6" if has_key else "#666666"
            key_lbl = NSTextField.labelWithString_(key_text)
            key_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.5))
            key_lbl.setTextColor_(_hex_color(key_color))
            key_lbl.sizeToFit()
            kf = key_lbl.frame()
            key_lbl.setFrame_(NSMakeRect(
                (22 - kf.size.width) / 2,
                (20 - kf.size.height) / 2,
                kf.size.width, kf.size.height))
            key_bg.addSubview_(key_lbl)

            lbl = NSTextField.labelWithString_(sc["label"])
            lbl.setFont_(_font)
            lbl.setTextColor_(NSColor.labelColor() if has_key else NSColor.secondaryLabelColor())
            lbl.setFrame_(NSMakeRect(38, (PILL_H - label_h) / 2, col_w - 46 - NUM_W - NUM_GAP, label_h))
            lbl.setLineBreakMode_(5)
            pill.addSubview_(lbl)

            if show_nums and sc.get("number", ""):
                num_lbl = NSTextField.labelWithString_(f"#{sc['number']}")
                num_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.3))
                num_lbl.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.65))
                num_lbl.setAlignment_(2)  # NSTextAlignmentRight
                num_lbl.setFrame_(NSMakeRect(col_w - 6 - NUM_W, (PILL_H - label_h) / 2, NUM_W, label_h))
                pill.addSubview_(num_lbl)

            container.addSubview_(pill)

        if not items and bank == "players":
            mid = content_h / 2
            msg1 = NSTextField.labelWithString_("No players in roster")
            msg1.setFont_(NSFont.systemFontOfSize_(12))
            msg1.setTextColor_(NSColor.labelColor())
            msg1.setAlignment_(2)
            msg1.sizeToFit()
            m1sz = msg1.frame().size
            msg1.setFrame_(NSMakeRect(
                (container_w - m1sz.width) / 2, mid + 6, m1sz.width, m1sz.height))
            container.addSubview_(msg1)

            msg2 = NSTextField.labelWithString_("Team tab → Fetch Rosters or + Add Player")
            msg2.setFont_(NSFont.systemFontOfSize_(10))
            msg2.setTextColor_(NSColor.secondaryLabelColor())
            msg2.setAlignment_(2)
            msg2.sizeToFit()
            m2sz = msg2.frame().size
            msg2.setFrame_(NSMakeRect(
                (container_w - m2sz.width) / 2, mid - 16, m2sz.width, m2sz.height))
            container.addSubview_(msg2)

        sv.documentView().scrollPoint_((0, content_h))

    def _set_active_shortcut_card(self, bank):
        from AppKit import NSColor
        if bank is None:
            bank = self._sc_current_bank
        crimson = _hex_color("#8c2232")
        tan     = _hex_color("#dbcca6")
        for k, card in self._sc_cards.items():
            if k == bank:
                card.layer().setBorderColor_(crimson.CGColor())
                card.layer().setBorderWidth_(1.5)
                self._sc_titles[k].setTextColor_(tan)
            else:
                card.layer().setBorderColor_(
                    _hex_color_alpha("#ffffff", 0.08).CGColor())
                card.layer().setBorderWidth_(0.5)
                self._sc_titles[k].setTextColor_(
                    NSColor.secondaryLabelColor())

    def _set_cards_for_step(self, active_bank):
        """Show one card at a time, cross-fading between steps.
        active_bank=None → restore current card visibility (no animation).
        active_bank='players'|'plays'|'ratings' → fade out old, fade in new."""
        from AppKit import NSAnimationContext

        if active_bank is None:
            # Returning to tag section from another nav item — restore alphas
            for bank, card in self._sc_cards.items():
                card.setHidden_(False)
                card.setAlphaValue_(1.0 if bank == self._sc_current_bank else 0.0)
            return

        if active_bank == self._sc_current_bank:
            return

        old_bank = self._sc_current_bank
        self._sc_current_bank = active_bank

        # Reflow the incoming card for the current window width before showing it
        self._populate_shortcut_pills(active_bank)

        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(0.25)
        self._sc_cards[old_bank].animator().setAlphaValue_(0.0)
        self._sc_cards[active_bank].animator().setAlphaValue_(1.0)
        NSAnimationContext.endGrouping()

    def _set_step_state(self, active=-1, completed=()):
        """active = index of current step (0,1,2 or -1 for none).
           completed = tuple of completed step indices."""
        from AppKit import NSColor
        crimson = _hex_color("#8c2232")
        tan     = _hex_color("#dbcca6")
        for i, (circle, num_lbl) in enumerate(self._now_step_circles):
            if i in completed:
                circle.layer().setBackgroundColor_(tan.CGColor())
                circle.layer().setBorderColor_(tan.CGColor())
                num_lbl.setTextColor_(_hex_color("#1a1a1c"))
                self._now_step_labels[i].setTextColor_(NSColor.labelColor())
            elif i == active:
                circle.layer().setBackgroundColor_(crimson.CGColor())
                circle.layer().setBorderColor_(crimson.CGColor())
                num_lbl.setTextColor_(NSColor.whiteColor())
                self._now_step_labels[i].setTextColor_(tan)
            else:
                circle.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.04).CGColor())
                circle.layer().setBorderColor_(
                    _hex_color_alpha("#ffffff", 0.20).CGColor())
                num_lbl.setTextColor_(NSColor.tertiaryLabelColor())
                self._now_step_labels[i].setTextColor_(
                    NSColor.tertiaryLabelColor())

        # Sync shortcut cards with active step
        if hasattr(self, "_sc_cards"):
            bank_for_step = (self._steps[active]
                             if 0 <= active < len(self._steps) else None)
            self._set_cards_for_step(bank_for_step)
            self._set_active_shortcut_card(bank_for_step)

    # ── Players section ───────────────────────────────────────────────────────

    def _build_players_section(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect, NSScrollView,
        )

        cx = float(SIDEBAR_W)
        cw = float(W - SIDEBAR_W)
        ch = float(H - TOP_H)

        section = NSView.alloc().initWithFrame_(NSMakeRect(cx, 0, cw, ch))
        section.setWantsLayer_(True)
        section.setAutoresizingMask_(2 | 16)
        section.setHidden_(True)
        cv.addSubview_(section)
        self._players_section = section
        self._players_content_w = cw

        HEADER_H = 64.0
        header_y  = ch - HEADER_H

        from AppKit import NSFont as _NSFont2
        title_lbl = NSTextField.labelWithString_("Team")
        title_lbl.setFont_(NSFont.boldSystemFontOfSize_(22))
        title_lbl.setTextColor_(NSColor.labelColor())
        title_lbl.sizeToFit()
        tf = title_lbl.frame()
        title_lbl.setFrame_(NSMakeRect(
            32, header_y + (HEADER_H - tf.size.height) / 2,
            tf.size.width, tf.size.height))
        title_lbl.setAutoresizingMask_(8)
        section.addSubview_(title_lbl)

        # Sport selector pill
        PILL_W = 190.0
        PILL_H_HDR = 28.0
        pill_x = 32 + tf.size.width + 14
        sport_pill = PillButton.alloc().initWithFrame_(NSMakeRect(
            pill_x, header_y + (HEADER_H - PILL_H_HDR) / 2, PILL_W, PILL_H_HDR))
        sport_pill.layer().setCornerRadius_(8.0)
        sport_pill.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
        sport_pill.layer().setBorderWidth_(0.5)
        sport_pill.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.18).CGColor())
        sport_pill.setAutoresizingMask_(8)
        active_sport = self.app.session.get("sport", "MBB") if self.app else "MBB"
        sport_info   = SPORTS.get(active_sport, SPORTS["MBB"])
        sport_label  = f"▸  {sport_info['emoji']}  {sport_info['label'].split('  ',1)[-1]}  ▾"
        sport_pill_lbl = NSTextField.labelWithString_(sport_label)
        sport_pill_lbl.setFont_(NSFont.systemFontOfSize_(12))
        sport_pill_lbl.setTextColor_(NSColor.labelColor())
        sport_pill_lbl.setFrame_(NSMakeRect(8, (PILL_H_HDR - 16) / 2, PILL_W - 16, 16))
        sport_pill.addSubview_(sport_pill_lbl)
        section.addSubview_(sport_pill)
        self._sport_pill     = sport_pill
        self._sport_pill_lbl = sport_pill_lbl
        sport_pill.setClickHandler_(lambda v, e: self._sport_picker_menu(v, e))

        count = len(self.shortcuts.get("players", []))
        self._players_count_lbl = NSTextField.labelWithString_(
            f"{count} player{'s' if count != 1 else ''}")
        self._players_count_lbl.setFont_(NSFont.systemFontOfSize_(13))
        self._players_count_lbl.setTextColor_(NSColor.secondaryLabelColor())
        self._players_count_lbl.sizeToFit()
        cf = self._players_count_lbl.frame()
        self._players_count_lbl.setFrame_(NSMakeRect(
            pill_x + PILL_W + 10,
            header_y + (HEADER_H - cf.size.height) / 2,
            cf.size.width + 4, cf.size.height))
        self._players_count_lbl.setAutoresizingMask_(8)
        section.addSubview_(self._players_count_lbl)

        BTN_H      = 30.0
        FETCH_W    = 158.0
        KEYS_W     = 92.0
        ADD_W      = 118.0
        URL_BTN_W  = 180.0

        fetch_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - FETCH_W,
                       header_y + (HEADER_H - BTN_H) / 2,
                       FETCH_W, BTN_H))
        fetch_btn.configureTitle_bg_press_action_(
            "Fetch All Rosters ↓", "#3a3a3c", "#2c2c2e",
            self._players_fetch_all)
        fetch_btn.setAutoresizingMask_(1 | 8)
        section.addSubview_(fetch_btn)
        self._fetch_all_btn = fetch_btn

        keys_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - FETCH_W - 10 - KEYS_W,
                       header_y + (HEADER_H - BTN_H) / 2,
                       KEYS_W, BTN_H))
        keys_btn.configureTitle_bg_press_action_(
            "🔑  Keys  ▾", "#3a3a3c", "#2c2c2e",
            self._players_keys_menu)
        keys_btn.setAutoresizingMask_(1 | 8)
        section.addSubview_(keys_btn)
        self._keys_btn = keys_btn

        add_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - FETCH_W - 10 - KEYS_W - 10 - ADD_W,
                       header_y + (HEADER_H - BTN_H) / 2,
                       ADD_W, BTN_H))
        add_btn.configureTitle_bg_press_action_(
            "+ Add Player", "#8c2232", "#6b1a26",
            self._players_add)
        add_btn.setAutoresizingMask_(1 | 8)
        section.addSubview_(add_btn)

        # URL button — shows saved domain or "Set Roster URL"
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS) if self.app else DEFAULT_SETTINGS
        saved_url = settings.get("roster_base_url", "").strip()
        url_label = _url_display_label(saved_url)
        url_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - FETCH_W - 10 - KEYS_W - 10 - ADD_W - 10 - URL_BTN_W,
                       header_y + (HEADER_H - BTN_H) / 2,
                       URL_BTN_W, BTN_H))
        url_btn.configureTitle_bg_press_action_(
            url_label, "#2c2c2e", "#232325",
            self._players_set_url)
        url_btn.setAutoresizingMask_(1 | 8)
        section.addSubview_(url_btn)
        self._url_btn = url_btn

        # Status label — shows progress/result of last fetch
        self._roster_status_lbl = NSTextField.labelWithString_("")
        self._roster_status_lbl.setFont_(NSFont.systemFontOfSize_(11))
        self._roster_status_lbl.setTextColor_(NSColor.secondaryLabelColor())
        # separator sits at header_y - 1; status label sits 4px below it
        STATUS_H = 20.0
        sep_y    = header_y - 1
        status_y = sep_y - 4 - STATUS_H
        self._roster_status_lbl.setFrame_(NSMakeRect(32, status_y, cw - 64, STATUS_H))
        self._roster_status_lbl.setAutoresizingMask_(2 | 8)
        section.addSubview_(self._roster_status_lbl)

        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, sep_y, cw, 1))
        sep.setWantsLayer_(True)
        sep.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        sep.setAutoresizingMask_(2 | 8)
        section.addSubview_(sep)

        grid_top = status_y - 8
        sv = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, 16, cw, grid_top - 16))
        sv.setHasVerticalScroller_(True)
        sv.setAutohidesScrollers_(True)
        sv.setBorderType_(0)
        sv.setDrawsBackground_(False)
        sv.setAutoresizingMask_(2 | 16)
        section.addSubview_(sv)
        self._players_scrollview = sv

        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, 0))
        sv.setDocumentView_(container)
        self._players_grid_container = container

        self._refresh_players_grid()

    def _sport_picker_menu(self, pill, event):
        from AppKit import NSMenu, NSMenuItem, NSPoint
        if not hasattr(self, "_sport_picker_mt"):
            self._sport_picker_mt = MenuTarget.alloc().init()

        def on_pick(sport_key):
            if self.app:
                self.app.switch_sport(sport_key)
            self._update_sport_pill(sport_key)

        self._sport_picker_mt._callback = on_pick
        active = self.app.session.get("sport", "MBB") if self.app else "MBB"
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        for key, info in SPORTS.items():
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                info["label"], "menuPicked:", "")
            mi.setTarget_(self._sport_picker_mt)
            mi.setRepresentedObject_(key)
            if key == active:
                mi.setState_(1)
            menu.addItem_(mi)
        menu.popUpMenuPositioningItem_atLocation_inView_(None, NSPoint(0, 0), pill)

    def _update_sport_pill(self, sport_key=None):
        if sport_key is None and self.app:
            sport_key = self.app.session.get("sport", "MBB")
        if sport_key is None:
            sport_key = "MBB"
        info = SPORTS.get(sport_key, SPORTS["MBB"])
        label = f"▸  {info['emoji']}  {info['label'].split('  ',1)[-1]}  ▾"
        if hasattr(self, "_sport_pill_lbl") and self._sport_pill_lbl is not None:
            self._sport_pill_lbl.setStringValue_(label)
        if hasattr(self, "_labels_sport_pill_lbl") and self._labels_sport_pill_lbl is not None:
            self._labels_sport_pill_lbl.setStringValue_(label)
        count = len(self.shortcuts.get("players", []))
        if hasattr(self, "_players_count_lbl") and self._players_count_lbl is not None:
            self._players_count_lbl.setStringValue_(
                f"{count} player{'s' if count != 1 else ''}")

    # Returns (cols, font_size, pill_h, badge_size, needs_scroll)
    # Tries increasing column counts and decreasing font until rows fit in
    # the viewport AND the pill is wide enough for the longest name.
    # Falls back to scroll when neither condition can be met at 11pt.
    def _compute_grid_layout(self, n_items, viewport_h, usable_w,
                             max_name_len=8, pad=40.0, gap_v=10.0,
                             gap_h=16.0, max_cols=6):
        SIZE_STEPS = [
            (14, 52.0, 32.0),  # (font_pt, pill_h, badge)
            (12, 44.0, 28.0),
            (11, 40.0, 26.0),
        ]
        for font_size, pill_h, badge in SIZE_STEPS:
            lbl_x      = 12 + badge + 12          # key badge left pad + badge w + gap
            min_lbl_w  = max_name_len * font_size * 0.70  # ~0.7 char-width ratio
            min_pill_w = lbl_x + min_lbl_w + 70   # 70 = edit+delete icon area
            for cols in range(2, max_cols + 1):
                rows    = (n_items + cols - 1) // cols
                total_h = rows * pill_h + max(rows - 1, 0) * gap_v + pad * 2
                if total_h > viewport_h:
                    continue
                pill_w = (usable_w - gap_h * (cols - 1)) / cols
                if pill_w < min_pill_w:
                    continue
                return (cols, font_size, pill_h, badge, False)
        # Scroll fallback: find max cols that still fits the longest name at 11pt
        badge      = 26.0
        lbl_x      = 12 + badge + 12
        min_pill_w = lbl_x + max_name_len * 11 * 0.70 + 70
        best_cols  = 2
        for cols in range(max_cols, 1, -1):
            if (usable_w - gap_h * (cols - 1)) / cols >= min_pill_w:
                best_cols = cols
                break
        return (best_cols, 11, 40.0, 26.0, True)

    def _refresh_players_grid(self):
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect

        container = self._players_grid_container
        for v in list(container.subviews()):
            v.removeFromSuperview()

        items = self.shortcuts.get("players", [])
        sv    = self._players_scrollview
        cw    = sv.frame().size.width
        if cw < 1:
            cw = self._players_content_w

        PAD   = 40.0
        GAP_H = 16.0
        GAP_V = 10.0

        usable_w     = cw - PAD * 2
        viewport_h   = sv.frame().size.height
        max_name_len = max((len(sc["label"]) for sc in items), default=8)
        COLS, font_size, PILL_H, BADGE, _ = (
            self._compute_grid_layout(len(items), viewport_h, usable_w,
                                      max_name_len, PAD, GAP_V, GAP_H)
            if items else (2, 14, 52.0, 32.0, False)
        )
        # Scroll is always available (autohides); layout still tries to fit without it

        pill_w = (usable_w - GAP_H * (COLS - 1)) / COLS

        rows    = (len(items) + COLS - 1) // COLS if items else 0
        total_h = (rows * PILL_H + max(rows - 1, 0) * GAP_V + PAD * 2
                   if rows else viewport_h)
        container_h = max(total_h, viewport_h)
        container.setFrame_(NSMakeRect(0, 0, cw, container_h))

        count = len(items)
        if hasattr(self, "_players_count_lbl"):
            self._players_count_lbl.setStringValue_(
                f"{count} player{'s' if count != 1 else ''}")
            self._players_count_lbl.sizeToFit()

        if not items:
            empty = NSTextField.labelWithString_(
                "No players yet — click \"+ Add Player\" or \"Fetch All Rosters ↓\" above.")
            empty.setFont_(NSFont.systemFontOfSize_(14))
            empty.setTextColor_(NSColor.tertiaryLabelColor())
            empty.setAlignment_(2)
            empty.setFrame_(NSMakeRect(PAD, (container_h - 22) / 2, cw - PAD * 2, 22))
            container.addSubview_(empty)
            return

        for i, sc in enumerate(items):
            row = i // COLS
            col = i % COLS
            x   = PAD + col * (pill_w + GAP_H)
            y   = container_h - PAD - (row + 1) * PILL_H - row * GAP_V

            pill = NSView.alloc().initWithFrame_(NSMakeRect(x, y, pill_w, PILL_H))
            pill.setWantsLayer_(True)
            pill.layer().setCornerRadius_(10.0)
            pill.layer().setBackgroundColor_(
                _hex_color_alpha("#ffffff", 0.05).CGColor())
            pill.layer().setBorderWidth_(0.5)
            pill.layer().setBorderColor_(
                _hex_color_alpha("#ffffff", 0.10).CGColor())

            key_bg = NSView.alloc().initWithFrame_(
                NSMakeRect(12, (PILL_H - BADGE) / 2, BADGE, BADGE))
            key_bg.setWantsLayer_(True)
            key_bg.layer().setCornerRadius_(8.0)
            key_bg.layer().setBackgroundColor_(
                _hex_color_alpha("#8c2232", 0.45).CGColor())
            pill.addSubview_(key_bg)

            key_lbl = NSTextField.labelWithString_(sc["key"].upper())
            key_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(font_size, 0.6))
            key_lbl.setTextColor_(_hex_color("#dbcca6"))
            key_lbl.sizeToFit()
            kf = key_lbl.frame()
            key_lbl.setFrame_(NSMakeRect(
                (BADGE - kf.size.width) / 2,
                (BADGE - kf.size.height) / 2,
                kf.size.width, kf.size.height))
            key_bg.addSubview_(key_lbl)

            number     = sc.get("number", "")
            NUM_W      = 36.0 if number else 0.0
            NUM_GAP    = 6.0  if number else 0.0
            lbl_x      = 12 + BADGE + 12
            lbl_w      = pill_w - lbl_x - 70 - NUM_W - NUM_GAP
            lbl_h      = font_size + 4

            name_lbl = NSTextField.labelWithString_(sc["label"])
            name_lbl.setFont_(NSFont.systemFontOfSize_(font_size))
            name_lbl.setTextColor_(NSColor.labelColor())
            name_lbl.setFrame_(NSMakeRect(lbl_x, (PILL_H - lbl_h) / 2, lbl_w, lbl_h))
            name_lbl.setLineBreakMode_(5)
            pill.addSubview_(name_lbl)

            if number:
                num_lbl = NSTextField.labelWithString_(f"#{number}")
                num_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(
                    max(9.0, font_size - 2), 0.3))
                num_lbl.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.6))
                num_lbl.setAlignment_(2)
                num_x = pill_w - 70 - NUM_W
                num_lbl.setFrame_(NSMakeRect(num_x, (PILL_H - lbl_h) / 2, NUM_W, lbl_h))
                pill.addSubview_(num_lbl)

            self._make_icon_btn(
                pill, pill_w - 58, (PILL_H - 22) / 2, 22, 22,
                "pencil", lambda idx=i: self._players_edit(idx))
            self._make_icon_btn(
                pill, pill_w - 30, (PILL_H - 22) / 2, 22, 22,
                "trash", lambda idx=i: self._players_delete(idx))

            container.addSubview_(pill)

        sv.documentView().scrollPoint_((0, max(0.0, container_h - viewport_h)))

    def _make_icon_btn(self, parent, x, y, w, h, symbol, action):
        from AppKit import NSButton, NSImage, NSColor, NSMakeRect
        btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
        btn.setBordered_(False)
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
        if img:
            btn.setImage_(img)
            btn.setContentTintColor_(NSColor.secondaryLabelColor())
        target = MenuTarget.alloc().init()
        target._callback = lambda _: action()
        btn.setTarget_(target)
        btn.setAction_("menuPicked:")
        parent.addSubview_(btn)
        if not hasattr(self, "_btn_targets"):
            self._btn_targets = []
        self._btn_targets.append(target)
        return btn

    def _players_add(self):
        from AppKit import NSAlert, NSTextField, NSView, NSMakeRect, NSFont
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Add Player")
        alert.setInformativeText_("Enter the shortcut key and player name.")
        alert.addButtonWithTitle_("Add")
        alert.addButtonWithTitle_("Cancel")

        panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 60))
        key_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 32, 300, 24))
        key_field.setPlaceholderString_("Shortcut key  (e.g.  1,  2,  q,  w)")
        key_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(key_field)
        name_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        name_field.setPlaceholderString_("Player name  (e.g.  HAND,  SMITH)")
        name_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(name_field)
        alert.setAccessoryView_(panel)
        alert.window().setInitialFirstResponder_(key_field)

        if alert.runModal() == 1000:
            key   = key_field.stringValue().strip()[:1]
            label = _asc(name_field.stringValue().strip()).upper()
            if key and label:
                items = self.shortcuts.setdefault("players", [])
                items.append({"key": key, "label": label})
                self.app._save_shortcuts()
                self._refresh_players_grid()

    def _players_edit(self, idx):
        from AppKit import NSAlert, NSTextField, NSView, NSMakeRect, NSFont
        items = self.shortcuts.get("players", [])
        if not (0 <= idx < len(items)):
            return
        sc = items[idx]

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Edit Player")
        alert.setInformativeText_(f"Editing: {sc['label']}")
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")

        panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 60))
        key_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 32, 300, 24))
        key_field.setStringValue_(sc["key"])
        key_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(key_field)
        name_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        name_field.setStringValue_(sc["label"])
        name_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(name_field)
        alert.setAccessoryView_(panel)

        if alert.runModal() == 1000:
            key   = key_field.stringValue().strip()[:1]
            label = _asc(name_field.stringValue().strip()).upper()
            if key and label:
                items[idx] = {"key": key, "label": label}
                items.sort(key=lambda sc: (0, int(sc["key"])) if sc.get("key", "").isdigit() else (1, sc.get("key", "").lower()))
                self.shortcuts["players"] = items
                self.app._save_shortcuts()
                self._refresh_players_grid()

    def _players_delete(self, idx):
        from AppKit import NSAlert
        items = self.shortcuts.get("players", [])
        if not (0 <= idx < len(items)):
            return
        sc = items[idx]

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Delete Player")
        alert.setInformativeText_(f"Delete [{sc['key']}]  {sc['label']}?")
        alert.addButtonWithTitle_("Delete")
        alert.addButtonWithTitle_("Cancel")

        if alert.runModal() == 1000:
            items.pop(idx)
            self.shortcuts["players"] = items
            self.app._save_shortcuts()
            self._refresh_players_grid()

    def _players_load_roster(self):
        if not self.app:
            return
        sport_key = self.app.session.get("sport", "MBB")

        _cache_days = self._settings.get("roster_cache_days", 7)

        def bg():
            names = fetch_roster(sport_key, cache_days=_cache_days)

            def on_main():
                KEY_POOL_SIZE = 35
                bypass = self._players_bypass_hotkeys  # keep if already set by settings
                if names and len(names) > KEY_POOL_SIZE and not self._players_bypass_hotkeys:
                    from AppKit import NSAlert
                    alert = NSAlert.alloc().init()
                    alert.setMessageText_(
                        f"{len(names)} players found — only {KEY_POOL_SIZE} hotkeys available")
                    alert.setInformativeText_(
                        f"Assign hotkeys to the first {KEY_POOL_SIZE} players and use "
                        f"search for the rest, or skip hotkeys and type each player "
                        f"name during logging.")
                    alert.addButtonWithTitle_("Assign hotkeys to first 35")
                    alert.addButtonWithTitle_("Skip hotkeys — type names")
                    bypass = (alert.runModal() != 1000)

                self._players_bypass_hotkeys = bypass
                if names:
                    shortcuts = roster_to_shortcuts(names)
                    self.shortcuts["players"] = shortcuts
                    if hasattr(self.app, "shortcuts"):
                        self.app.shortcuts["players"] = shortcuts
                    self.app._save_shortcuts()
                self._refresh_players_grid()
                self._populate_shortcut_pills("players")

            if MainCaller:
                caller = MainCaller.alloc().init()
                caller._cb = on_main
                caller.performSelectorOnMainThread_withObject_waitUntilDone_(
                    b"fire:", None, False)

        threading.Thread(target=bg, daemon=True).start()

    def _players_set_url(self):
        """Open a dialog to set/change the roster base URL, then save to settings."""
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        current  = settings.get("roster_base_url", "")
        w = rumps.Window(
            title="Set Roster URL",
            message="Paste the athletics website base URL\n(e.g. https://bceagles.com)",
            default_text=current,
            ok="Save", cancel="Cancel",
            dimensions=(400, 24),
        )
        r = w.run()
        if not r.clicked:
            return
        url = r.text.strip().rstrip("/")
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        settings["roster_base_url"] = url
        save_json(SETTINGS_FILE, settings)
        if hasattr(self, "_url_btn") and self._url_btn:
            self._url_btn.configureTitle_bg_press_action_(
                _url_display_label(url), "#2c2c2e", "#232325",
                self._players_set_url)

    # ── Hotkey preset helpers ─────────────────────────────────────────────────

    def _players_keys_menu(self):
        from AppKit import NSMenu, NSMenuItem, NSPoint
        if not hasattr(self, "_keys_menu_mt"):
            self._keys_menu_mt = MenuTarget.alloc().init()
        sport_key = self.app.session.get("sport", "MBB") if self.app else "MBB"
        presets   = load_json(KEY_PRESETS_FILE, {}).get(sport_key, [])

        def on_pick(action):
            if action == "__save__":
                self._save_player_key_preset()
            elif action == "__delete__":
                self._delete_player_key_preset()
            elif isinstance(action, int):
                self._load_player_key_preset(presets[action])

        self._keys_menu_mt._callback = on_pick
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        save_mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Save Current Keys…", "menuPicked:", "")
        save_mi.setTarget_(self._keys_menu_mt)
        save_mi.setRepresentedObject_("__save__")
        menu.addItem_(save_mi)

        if presets:
            menu.addItem_(NSMenuItem.separatorItem())
            for i, p in enumerate(presets):
                mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    p.get("name", f"Preset {i+1}"), "menuPicked:", "")
                mi.setTarget_(self._keys_menu_mt)
                mi.setRepresentedObject_(i)
                menu.addItem_(mi)
            menu.addItem_(NSMenuItem.separatorItem())
            del_mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Delete a Preset…", "menuPicked:", "")
            del_mi.setTarget_(self._keys_menu_mt)
            del_mi.setRepresentedObject_("__delete__")
            menu.addItem_(del_mi)

        btn = self._keys_btn if hasattr(self, "_keys_btn") else None
        if btn:
            menu.popUpMenuPositioningItem_atLocation_inView_(
                None, __import__("AppKit").NSPoint(0, 0), btn)

    def _save_player_key_preset(self):
        from AppKit import NSAlert, NSTextField as NSTF, NSMakeRect
        sport_key = self.app.session.get("sport", "MBB") if self.app else "MBB"
        players   = list(self.shortcuts.get("players", []))
        if not players:
            return
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Save Key Preset")
        alert.setInformativeText_("Name this hotkey layout for the current roster:")
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")
        tf = NSTF.alloc().initWithFrame_(NSMakeRect(0, 0, 260, 24))
        tf.setPlaceholderString_("e.g. 2026-27 Season")
        alert.setAccessoryView_(tf)
        alert.window().setInitialFirstResponder_(tf)
        if alert.runModal() != 1000:
            return
        name = tf.stringValue().strip() or "Key Preset"
        keys_map = {sc["label"]: sc.get("key", "") for sc in players}
        all_presets = load_json(KEY_PRESETS_FILE, {})
        sport_list  = all_presets.get(sport_key, [])
        sport_list.append({"name": name, "keys": keys_map})
        all_presets[sport_key] = sport_list
        save_json(KEY_PRESETS_FILE, all_presets)
        if hasattr(self, "_roster_status_lbl"):
            self._roster_status_lbl.setStringValue_(f'✅  Saved key preset “{name}”')

    def _load_player_key_preset(self, preset):
        keys_map = preset.get("keys", {})
        players  = list(self.shortcuts.get("players", []))
        changed  = 0
        for sc in players:
            saved_key = keys_map.get(sc["label"])
            if saved_key and sc.get("key") != saved_key:
                sc["key"] = saved_key
                changed  += 1
        if not changed:
            return
        self.shortcuts["players"] = players
        if self.app:
            self.app._save_shortcuts()
        self._refresh_players_grid()
        self._populate_shortcut_pills("players")
        if hasattr(self, "_roster_status_lbl"):
            self._roster_status_lbl.setStringValue_(
                f"✅  Loaded “{preset.get('name', 'preset')}” — {changed} key(s) restored")

    def _delete_player_key_preset(self):
        from AppKit import NSAlert
        sport_key   = self.app.session.get("sport", "MBB") if self.app else "MBB"
        all_presets = load_json(KEY_PRESETS_FILE, {})
        sport_list  = all_presets.get(sport_key, [])
        if not sport_list:
            return
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Delete Key Preset")
        alert.setInformativeText_("Choose a preset to delete:")
        for p in sport_list:
            alert.addButtonWithTitle_(p.get("name", "Preset"))
        alert.addButtonWithTitle_("Cancel")
        resp = alert.runModal()
        cancel_idx = 1000 + len(sport_list)
        if resp == cancel_idx:
            return
        del_idx = resp - 1000
        if 0 <= del_idx < len(sport_list):
            removed = sport_list.pop(del_idx)
            all_presets[sport_key] = sport_list
            save_json(KEY_PRESETS_FILE, all_presets)
            if hasattr(self, "_roster_status_lbl"):
                self._roster_status_lbl.setStringValue_(
                    f"Deleted preset “{removed.get('name', '')}”")

    def _players_fetch_all(self):
        """Fetch all rosters from the saved base URL."""
        if not self.app:
            return
        # Warn if the current players bank has customised keys
        current_players = list(self.shortcuts.get("players", []))
        if current_players:
            default_keys = ["1","2","3","4","5","6","7","8","9"] + \
                           [chr(c) for c in range(ord("a"), ord("z") + 1)]
            is_custom = any(
                sc.get("key", "") != default_keys[i]
                for i, sc in enumerate(current_players)
                if i < len(default_keys)
            )
            if is_custom:
                from AppKit import NSAlert
                alert = NSAlert.alloc().init()
                alert.setMessageText_("Custom Hotkeys Detected")
                alert.setInformativeText_(
                    "Fetching rosters will reset all player hotkeys to "
                    "the default sequence (1, 2, 3…).\n\n"
                    "Save your current key layout first using 🔑 Keys ▾.")
                alert.addButtonWithTitle_("Save Keys First")
                alert.addButtonWithTitle_("Fetch Anyway")
                alert.addButtonWithTitle_("Cancel")
                resp = alert.runModal()
                if resp == 1002:  # Cancel
                    return
                if resp == 1000:  # Save Keys First
                    self._save_player_key_preset()
                    return  # let user review the save before fetching
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        base_url = settings.get("roster_base_url", "").strip()
        if not base_url:
            self._players_set_url()
            settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
            base_url = settings.get("roster_base_url", "").strip()
            if not base_url:
                return
        # Update button to show fetching state
        if hasattr(self, "_fetch_all_btn") and self._fetch_all_btn:
            self._fetch_all_btn.configureTitle_bg_press_action_(
                "Fetching…", "#2c2c2e", "#232325", lambda: None)
        if hasattr(self, "_roster_status_lbl") and self._roster_status_lbl:
            self._roster_status_lbl.setStringValue_("Fetching rosters…")
        self.app.load_all_rosters(base_url)

    def _on_fetch_all_done(self, success, results):
        """Called on the main thread when _scrape_all_bg completes."""
        if hasattr(self, "_fetch_all_btn") and self._fetch_all_btn:
            self._fetch_all_btn.configureTitle_bg_press_action_(
                "Fetch All Rosters ↓", "#3a3a3c", "#2c2c2e",
                self._players_fetch_all)
        if hasattr(self, "_roster_status_lbl") and self._roster_status_lbl:
            if success and results:
                parts = [f"{SPORTS[c]['emoji']} {len(n)}" for c, n in results.items() if c in SPORTS]
                summary = "  ·  ".join(parts[:6])
                if len(parts) > 6:
                    summary += f"  +{len(parts)-6} more"
                self._roster_status_lbl.setStringValue_(f"✅  {summary}")
            else:
                self._roster_status_lbl.setStringValue_("❌  No rosters found — check URL")
        self._refresh_players_grid()
        self._populate_shortcut_pills("players")

    # ── Labels section (configurable steps management) ────────────────────────

    def _build_labels_section(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect, NSScrollView,
        )
        cx = float(SIDEBAR_W)
        cw = float(W - SIDEBAR_W)
        ch = float(H - TOP_H)

        section = NSView.alloc().initWithFrame_(NSMakeRect(cx, 0, cw, ch))
        section.setWantsLayer_(True)
        section.setAutoresizingMask_(2 | 16)
        section.setHidden_(True)
        cv.addSubview_(section)
        self._labels_section   = section
        self._labels_content_w = cw

        HEADER_H  = 64.0
        STEPS_H   = 220.0   # scrollable step-order list
        SUBHDR_H  = 48.0    # shortcut sub-header bar
        header_y  = ch - HEADER_H

        # ── Header ────────────────────────────────────────────────────────────
        title_lbl = NSTextField.labelWithString_("Labels")
        title_lbl.setFont_(NSFont.boldSystemFontOfSize_(22))
        title_lbl.setTextColor_(NSColor.labelColor())
        title_lbl.sizeToFit()
        tf = title_lbl.frame()
        title_lbl.setFrame_(NSMakeRect(
            32, header_y + (HEADER_H - tf.size.height) / 2,
            tf.size.width, tf.size.height))
        title_lbl.setAutoresizingMask_(8)
        section.addSubview_(title_lbl)

        # Sport selector pill (mirrors Team section)
        PILL_W     = 190.0
        PILL_H_HDR = 28.0
        pill_x     = 32 + tf.size.width + 14
        labels_sport_pill = PillButton.alloc().initWithFrame_(NSMakeRect(
            pill_x, header_y + (HEADER_H - PILL_H_HDR) / 2, PILL_W, PILL_H_HDR))
        labels_sport_pill.layer().setCornerRadius_(8.0)
        labels_sport_pill.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        labels_sport_pill.layer().setBorderWidth_(0.5)
        labels_sport_pill.layer().setBorderColor_(
            _hex_color_alpha("#ffffff", 0.18).CGColor())
        labels_sport_pill.setAutoresizingMask_(8)
        active_sport = self.app.session.get("sport", "MBB") if self.app else "MBB"
        sport_info   = SPORTS.get(active_sport, SPORTS["MBB"])
        sport_lbl_str = f"▸  {sport_info['emoji']}  {sport_info['label'].split('  ',1)[-1]}  ▾"
        labels_sport_pill_lbl = NSTextField.labelWithString_(sport_lbl_str)
        labels_sport_pill_lbl.setFont_(NSFont.systemFontOfSize_(12))
        labels_sport_pill_lbl.setTextColor_(NSColor.labelColor())
        labels_sport_pill_lbl.setFrame_(NSMakeRect(8, (PILL_H_HDR - 16) / 2, PILL_W - 16, 16))
        labels_sport_pill.addSubview_(labels_sport_pill_lbl)
        section.addSubview_(labels_sport_pill)
        self._labels_sport_pill     = labels_sport_pill
        self._labels_sport_pill_lbl = labels_sport_pill_lbl
        labels_sport_pill.setClickHandler_(
            lambda v, e: self._sport_picker_menu(v, e))

        BTN_H      = 30.0
        ADD_STEP_W = 108.0
        add_step_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - ADD_STEP_W,
                       header_y + (HEADER_H - BTN_H) / 2,
                       ADD_STEP_W, BTN_H))
        add_step_btn.configureTitle_bg_press_action_(
            "+ Add Step", "#8c2232", "#6b1a26", self._labels_add_step)
        add_step_btn.setAutoresizingMask_(1 | 8)
        section.addSubview_(add_step_btn)

        def _sep(y):
            s = NSView.alloc().initWithFrame_(NSMakeRect(0, y, cw, 1))
            s.setWantsLayer_(True)
            s.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
            s.setAutoresizingMask_(2 | 8)
            section.addSubview_(s)

        _sep(header_y - 1)

        # ── Step-order list (scrollable rows, naming-convention style) ────────
        steps_y = header_y - 1 - STEPS_H
        steps_sv = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, steps_y, cw, STEPS_H))
        steps_sv.setHasVerticalScroller_(True)
        steps_sv.setAutohidesScrollers_(True)
        steps_sv.setBorderType_(0)
        steps_sv.setDrawsBackground_(False)
        steps_sv.setAutoresizingMask_(2 | 8)
        section.addSubview_(steps_sv)
        self._labels_steps_sv = steps_sv

        steps_doc = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, STEPS_H))
        steps_sv.setDocumentView_(steps_doc)
        self._labels_steps_doc = steps_doc

        _sep(steps_y - 1)

        # ── Shortcut sub-header ───────────────────────────────────────────────
        subhdr_y = steps_y - 1 - SUBHDR_H
        subhdr = NSView.alloc().initWithFrame_(NSMakeRect(0, subhdr_y, cw, SUBHDR_H))
        subhdr.setWantsLayer_(True)
        subhdr.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.02).CGColor())
        subhdr.setAutoresizingMask_(2 | 8)
        section.addSubview_(subhdr)

        self._labels_subhdr_lbl = NSTextField.labelWithString_("Shortcuts")
        self._labels_subhdr_lbl.setFont_(NSFont.boldSystemFontOfSize_(13))
        self._labels_subhdr_lbl.setTextColor_(NSColor.labelColor())
        self._labels_subhdr_lbl.setFrame_(NSMakeRect(32, (SUBHDR_H - 17) / 2, 300, 17))
        subhdr.addSubview_(self._labels_subhdr_lbl)

        ADD_SC_W  = 126.0
        COPY_W    = 108.0
        COPY_GAP  = 8.0
        copy_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - ADD_SC_W - COPY_GAP - COPY_W,
                       (SUBHDR_H - BTN_H) / 2, COPY_W, BTN_H))
        copy_btn.configureTitle_bg_press_action_(
            "Copy to  →", "#3a3a3c", "#2c2c2e", self._labels_copy_to_sport)
        copy_btn.setAutoresizingMask_(1 | 8)
        subhdr.addSubview_(copy_btn)
        self._labels_copy_btn = copy_btn

        add_sc_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - ADD_SC_W, (SUBHDR_H - BTN_H) / 2, ADD_SC_W, BTN_H))
        add_sc_btn.configureTitle_bg_press_action_(
            "+ Add Shortcut", "#3a3a3c", "#2c2c2e", self._labels_add_shortcut)
        add_sc_btn.setAutoresizingMask_(1 | 8)
        subhdr.addSubview_(add_sc_btn)

        _sep(subhdr_y - 1)

        # ── Shortcut grid (fills remaining space) ─────────────────────────────
        grid_h = subhdr_y - 1 - 16
        sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 16, cw, grid_h))
        sv.setHasVerticalScroller_(True)
        sv.setAutohidesScrollers_(True)
        sv.setBorderType_(0)
        sv.setDrawsBackground_(False)
        sv.setAutoresizingMask_(2 | 16)
        section.addSubview_(sv)
        self._labels_scrollview = sv

        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, 0))
        sv.setDocumentView_(container)
        self._labels_grid_container = container

        # ── Init state ────────────────────────────────────────────────────────
        config = self.app.session if self.app else DEFAULT_SESSION
        custom = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        self._labels_active_step  = custom[0]["id"] if custom else None
        self._labels_row_observers = []

        self._rebuild_labels_rows()
        self._refresh_labels_grid()

    def _rebuild_labels_rows(self):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect,
            NSNotificationCenter,
        )
        steps_sv  = getattr(self, "_labels_steps_sv",  None)
        steps_doc = getattr(self, "_labels_steps_doc", None)
        if steps_sv is None or steps_doc is None:
            return

        # Clear old observers
        if self._labels_row_observers:
            nc = NSNotificationCenter.defaultCenter()
            for obs in self._labels_row_observers:
                nc.removeObserver_(obs)
        self._labels_row_observers = []

        for v in list(steps_doc.subviews()):
            v.removeFromSuperview()

        config = self.app.session if self.app else DEFAULT_SESSION
        custom = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])

        # Full ordered step list: Player (locked) + custom steps
        all_steps = [{"id": "players", "label": "Player", "_locked": True}] + \
                    [dict(s) for s in custom]

        cw      = steps_sv.frame().size.width or self._labels_content_w
        ROW_H   = 44.0
        ROW_GAP = 8.0
        PAD_X   = 32.0
        FORM_W  = cw - PAD_X * 2

        # Control button geometry (matches naming convention field rows)
        CTRL_W   = 24.0
        CTRL_H   = 24.0
        CTRL_GAP = 4.0
        n_ctrls  = 3   # ↑ ↓ ×
        ctrl_block_w = n_ctrls * CTRL_W + (n_ctrls - 1) * CTRL_GAP + 10

        n        = len(all_steps)
        total_h  = max(n * ROW_H + max(n - 1, 0) * ROW_GAP + 16,
                       steps_sv.frame().size.height)
        steps_doc.setFrame_(NSMakeRect(0, 0, cw, total_h))

        # Build rows top-down (AppKit unflipped: y=0 at bottom)
        y = total_h - 8.0

        for i, step in enumerate(all_steps):
            step_id  = step["id"]
            locked   = step.get("_locked", False)
            is_active = (step_id == self._labels_active_step) and not locked

            y -= ROW_H
            row = NSView.alloc().initWithFrame_(NSMakeRect(PAD_X, y, FORM_W, ROW_H))
            row.setWantsLayer_(True)
            row.layer().setCornerRadius_(10.0)

            if locked:
                row.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.02).CGColor())
                row.layer().setBorderWidth_(0.5)
                row.layer().setBorderColor_(
                    _hex_color_alpha("#ffffff", 0.06).CGColor())
            elif is_active:
                row.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.06).CGColor())
                row.layer().setBorderWidth_(1.0)
                row.layer().setBorderColor_(
                    _hex_color_alpha("#8c2232", 0.70).CGColor())
            else:
                row.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.04).CGColor())
                row.layer().setBorderWidth_(0.5)
                row.layer().setBorderColor_(
                    _hex_color_alpha("#ffffff", 0.08).CGColor())

            # Step number badge — PillButton so it can act as the row select target
            NUM_W = 28.0
            num_bg = PillButton.alloc().initWithFrame_(
                NSMakeRect(10, (ROW_H - CTRL_H) / 2, NUM_W, CTRL_H))
            num_bg.setWantsLayer_(True)
            num_bg.layer().setCornerRadius_(5.0)
            num_bg.layer().setBackgroundColor_(
                _hex_color_alpha("#8c2232" if is_active else "#ffffff",
                                  0.35 if is_active else 0.08).CGColor())
            num_lbl = NSTextField.labelWithString_(str(i + 1))
            num_lbl.setFont_(NSFont.boldSystemFontOfSize_(11))
            num_lbl.setTextColor_(
                _hex_color(COLOR_TAN) if is_active else NSColor.secondaryLabelColor())
            num_lbl.setAlignment_(1)
            num_lbl.setFrame_(NSMakeRect(0, (CTRL_H - 14) / 2, NUM_W, 14))
            num_bg.addSubview_(num_lbl)
            if not locked:
                num_bg.setClickHandler_(
                    lambda v, e, sid=step_id: self._labels_select_step(sid))
            row.addSubview_(num_bg)

            if locked:
                # Read-only label
                fixed_lbl = NSTextField.labelWithString_(step["label"])
                fixed_lbl.setFont_(NSFont.systemFontOfSize_(13))
                fixed_lbl.setTextColor_(NSColor.tertiaryLabelColor())
                fixed_lbl.setFrame_(NSMakeRect(NUM_W + 18, (ROW_H - 17) / 2,
                                               FORM_W - NUM_W - 20, 17))
                row.addSubview_(fixed_lbl)

                lock_lbl = NSTextField.labelWithString_("FIXED")
                lock_lbl.setFont_(NSFont.systemFontOfSize_(10))
                lock_lbl.setTextColor_(NSColor.tertiaryLabelColor())
                lock_lbl.setAlignment_(2)  # right
                lock_lbl.setFrame_(NSMakeRect(FORM_W - 60, (ROW_H - 14) / 2, 50, 14))
                row.addSubview_(lock_lbl)
            else:
                # Editable name field
                ctrl_x    = FORM_W - ctrl_block_w
                tf_x      = NUM_W + 18
                tf_w      = ctrl_x - tf_x - 8

                tf_bg = NSView.alloc().initWithFrame_(
                    NSMakeRect(tf_x, (ROW_H - 28) / 2, tf_w, 28))
                tf_bg.setWantsLayer_(True)
                tf_bg.layer().setCornerRadius_(6.0)
                tf_bg.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.08).CGColor())
                tf_bg.layer().setBorderWidth_(0.5)
                tf_bg.layer().setBorderColor_(
                    _hex_color_alpha("#ffffff", 0.18).CGColor())
                row.addSubview_(tf_bg)

                tf = NSTextField.alloc().initWithFrame_(
                    NSMakeRect(8, (28 - 18) / 2, tf_w - 16, 18))
                tf.setStringValue_(step["label"])
                tf.setFont_(NSFont.systemFontOfSize_(13))
                tf.setTextColor_(NSColor.labelColor())
                tf.setPlaceholderString_("Step name…")
                tf.setBezeled_(False)
                tf.setDrawsBackground_(False)
                tf.setEditable_(True)
                tf.setSelectable_(True)
                tf_bg.addSubview_(tf)

                # Save name on end-edit via notification
                obs = MainCaller.alloc().init()
                obs._cb = (lambda sid=step_id, t=tf:
                           self._labels_name_did_change(sid, t))
                NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
                    obs, "fire:", "NSControlTextDidEndEditingNotification", tf)
                self._labels_row_observers.append(obs)

                # ↑ ↓ × controls
                n_custom = len(custom)
                custom_idx = next((ci for ci, s in enumerate(custom)
                                   if s["id"] == step_id), None)
                for ci, (sym, action, enabled) in enumerate([
                    ("↑", lambda sid=step_id: self._labels_move_step(sid, -1),
                     custom_idx is not None and custom_idx > 0),
                    ("↓", lambda sid=step_id: self._labels_move_step(sid,  1),
                     custom_idx is not None and custom_idx < n_custom - 1),
                    ("×", lambda sid=step_id: self._labels_delete_step(sid),
                     n_custom > 1),
                ]):
                    bx   = ctrl_x + ci * (CTRL_W + CTRL_GAP)
                    cbtn = PillButton.alloc().initWithFrame_(
                        NSMakeRect(bx, (ROW_H - CTRL_H) / 2, CTRL_W, CTRL_H))
                    cbtn.layer().setCornerRadius_(5.0)
                    cbtn.layer().setBackgroundColor_(
                        _hex_color_alpha("#ffffff", 0.08 if enabled else 0.03).CGColor())
                    clbl = NSTextField.labelWithString_(sym)
                    clbl.setFont_(NSFont.systemFontOfSize_(12))
                    clbl.setTextColor_(
                        NSColor.labelColor() if enabled else NSColor.tertiaryLabelColor())
                    clbl.setAlignment_(1)
                    clbl.setFrame_(NSMakeRect(0, (CTRL_H - 16) / 2, CTRL_W, 16))
                    cbtn.addSubview_(clbl)
                    row.addSubview_(cbtn)
                    if enabled:
                        cbtn.setClickHandler_(lambda v, e, a=action: a())

            steps_doc.addSubview_(row)
            y -= ROW_GAP

        # Update sub-header to reflect active step name
        config  = self.app.session if self.app else DEFAULT_SESSION
        custom  = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        active  = self._labels_active_step
        step_cfg = next((s for s in custom if s["id"] == active), None)
        step_lbl = step_cfg["label"] if step_cfg else ""
        if hasattr(self, "_labels_subhdr_lbl") and step_lbl:
            self._labels_subhdr_lbl.setStringValue_(
                f"Shortcuts  —  {step_lbl}")

        # Scroll to show top
        steps_sv.contentView().scrollToPoint_((0, max(0.0, total_h - steps_sv.frame().size.height)))
        steps_sv.reflectScrolledClipView_(steps_sv.contentView())

    def _labels_select_step(self, step_id):
        self._labels_active_step = step_id
        self._rebuild_labels_rows()
        self._refresh_labels_grid()

    def _labels_copy_to_sport(self):
        from AppKit import NSMenu, NSMenuItem, NSPoint
        step_id = getattr(self, "_labels_active_step", None)
        if not step_id or not self.app:
            return
        items = self.shortcuts.get(step_id, [])
        if not items:
            rumps.alert("Nothing to Copy",
                        "The selected step has no shortcuts to copy.")
            return
        current_sport = self.app.session.get("sport", "MBB")

        if not hasattr(self, "_labels_copy_mt"):
            self._labels_copy_mt = MenuTarget.alloc().init()

        config = self.app.session if self.app else DEFAULT_SESSION
        custom = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        step_cfg  = next((s for s in custom if s["id"] == step_id), None)
        step_name = step_cfg["label"] if step_cfg else step_id

        def on_pick(target_sport):
            import copy
            sc_data = self.app._shortcuts_data
            if target_sport not in sc_data:
                sc_data[target_sport] = {}
            sc_data[target_sport][step_id] = copy.deepcopy(items)
            self.app._save_shortcuts()
            target_label = SPORTS[target_sport]["label"].split("  ", 1)[-1].strip()
            rumps.alert("Copied",
                        f"{len(items)} {step_name} shortcut{'s' if len(items) != 1 else ''} "
                        f"copied to {target_label}.")

        self._labels_copy_mt._callback = on_pick
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        for key, info in SPORTS.items():
            if key == current_sport:
                continue
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                info["label"], "menuPicked:", "")
            mi.setTarget_(self._labels_copy_mt)
            mi.setRepresentedObject_(key)
            menu.addItem_(mi)

        btn = getattr(self, "_labels_copy_btn", None)
        if btn is not None:
            menu.popUpMenuPositioningItem_atLocation_inView_(
                None, NSPoint(0, 0), btn)

    def _labels_name_did_change(self, step_id, tf):
        name = tf.stringValue().strip()
        if not name:
            return
        config  = self.app.session if self.app else DEFAULT_SESSION
        custom  = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        step    = next((s for s in custom if s["id"] == step_id), None)
        if step is None or step["label"] == name:
            return
        step["label"] = name
        if self.app:
            save_json(CONFIG_FILE, self.app.session)
        self._rebuild_steps()
        self._build_step_circles()
        if step_id in getattr(self, "_sc_titles", {}):
            self._sc_titles[step_id].setStringValue_(name.upper())
        if hasattr(self, "_labels_subhdr_lbl"):
            self._labels_subhdr_lbl.setStringValue_(f"Shortcuts  —  {name}")

    def _refresh_labels_grid(self):
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect

        container = getattr(self, "_labels_grid_container", None)
        if container is None:
            return
        for v in list(container.subviews()):
            v.removeFromSuperview()

        step_id = getattr(self, "_labels_active_step", None)
        if step_id is None:
            return

        items = self.shortcuts.get(step_id, [])
        sv    = self._labels_scrollview
        cw    = sv.frame().size.width
        if cw < 1:
            cw = self._labels_content_w

        PAD   = 40.0
        GAP_H = 16.0
        GAP_V = 10.0

        usable_w     = cw - PAD * 2
        viewport_h   = sv.frame().size.height
        max_name_len = max((len(sc["label"]) for sc in items), default=8)
        COLS, font_size, PILL_H, BADGE, _ = (
            self._compute_grid_layout(len(items), viewport_h, usable_w,
                                      max_name_len, PAD, GAP_V, GAP_H)
            if items else (2, 14, 52.0, 32.0, False)
        )

        pill_w = (usable_w - GAP_H * (COLS - 1)) / COLS
        rows    = (len(items) + COLS - 1) // COLS if items else 0
        total_h = (rows * PILL_H + max(rows - 1, 0) * GAP_V + PAD * 2
                   if rows else viewport_h)
        container_h = max(total_h, viewport_h)
        container.setFrame_(NSMakeRect(0, 0, cw, container_h))

        config  = self.app.session if self.app else DEFAULT_SESSION
        custom  = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        step_cfg = next((s for s in custom if s["id"] == step_id), None)
        step_lbl = step_cfg["label"] if step_cfg else step_id

        if not items:
            empty = NSTextField.labelWithString_(
                f'No {step_lbl.lower()} shortcuts yet — click "+ Add Shortcut" above.')
            empty.setFont_(NSFont.systemFontOfSize_(14))
            empty.setTextColor_(NSColor.tertiaryLabelColor())
            empty.setAlignment_(2)
            empty.setFrame_(NSMakeRect(PAD, (container_h - 22) / 2, cw - PAD * 2, 22))
            container.addSubview_(empty)
            sv.documentView().scrollPoint_((0, 0))
            return

        for i, sc in enumerate(items):
            row = i // COLS
            col = i % COLS
            x   = PAD + col * (pill_w + GAP_H)
            y   = container_h - PAD - (row + 1) * PILL_H - row * GAP_V

            pill = NSView.alloc().initWithFrame_(NSMakeRect(x, y, pill_w, PILL_H))
            pill.setWantsLayer_(True)
            pill.layer().setCornerRadius_(10.0)
            pill.layer().setBackgroundColor_(
                _hex_color_alpha("#ffffff", 0.05).CGColor())
            pill.layer().setBorderWidth_(0.5)
            pill.layer().setBorderColor_(
                _hex_color_alpha("#ffffff", 0.10).CGColor())

            key_bg = NSView.alloc().initWithFrame_(
                NSMakeRect(12, (PILL_H - BADGE) / 2, BADGE, BADGE))
            key_bg.setWantsLayer_(True)
            key_bg.layer().setCornerRadius_(8.0)
            key_bg.layer().setBackgroundColor_(
                _hex_color_alpha("#8c2232", 0.45).CGColor())
            pill.addSubview_(key_bg)

            key_lbl = NSTextField.labelWithString_(sc["key"].upper())
            key_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(font_size, 0.6))
            key_lbl.setTextColor_(_hex_color("#dbcca6"))
            key_lbl.sizeToFit()
            kf = key_lbl.frame()
            key_lbl.setFrame_(NSMakeRect(
                (BADGE - kf.size.width) / 2,
                (BADGE - kf.size.height) / 2,
                kf.size.width, kf.size.height))
            key_bg.addSubview_(key_lbl)

            name_lbl = NSTextField.labelWithString_(sc["label"])
            name_lbl.setFont_(NSFont.systemFontOfSize_(font_size))
            name_lbl.setTextColor_(NSColor.labelColor())
            lbl_x = 12 + BADGE + 12
            lbl_w = pill_w - lbl_x - 98  # 3 buttons: tree + pencil + trash
            lbl_h = font_size + 4
            name_lbl.setFrame_(NSMakeRect(lbl_x, (PILL_H - lbl_h) / 2, lbl_w, lbl_h))
            name_lbl.setLineBreakMode_(5)
            pill.addSubview_(name_lbl)

            # Show child count badge if this shortcut has children
            child_count = len(sc.get("children", []))
            if child_count:
                badge_lbl = NSTextField.labelWithString_(str(child_count))
                badge_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(9, 0.5))
                badge_lbl.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.8))
                badge_lbl.sizeToFit()
                bf = badge_lbl.frame()
                badge_lbl.setFrame_(NSMakeRect(
                    lbl_x + lbl_w + 2, (PILL_H - bf.size.height) / 2,
                    bf.size.width, bf.size.height))
                pill.addSubview_(badge_lbl)

            self._make_icon_btn(
                pill, pill_w - 86, (PILL_H - 22) / 2, 22, 22,
                "arrow.triangle.branch",
                lambda idx=i: self._labels_open_children(idx))
            self._make_icon_btn(
                pill, pill_w - 58, (PILL_H - 22) / 2, 22, 22,
                "pencil", lambda idx=i: self._labels_edit_shortcut(idx))
            self._make_icon_btn(
                pill, pill_w - 30, (PILL_H - 22) / 2, 22, 22,
                "trash", lambda idx=i: self._labels_delete_shortcut(idx))

            container.addSubview_(pill)

        sv.documentView().scrollPoint_((0, max(0.0, container_h - viewport_h)))

    def _labels_add_shortcut(self):
        from AppKit import NSAlert, NSTextField, NSView, NSMakeRect, NSFont
        step_id = getattr(self, "_labels_active_step", None)
        if step_id is None:
            return
        config  = self.app.session if self.app else DEFAULT_SESSION
        custom  = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        step_cfg = next((s for s in custom if s["id"] == step_id), None)
        step_lbl = step_cfg["label"] if step_cfg else "Item"

        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"Add {step_lbl}")
        alert.setInformativeText_("Enter the shortcut key and label.")
        alert.addButtonWithTitle_("Add")
        alert.addButtonWithTitle_("Cancel")

        panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 60))
        key_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 32, 300, 24))
        key_field.setPlaceholderString_("Shortcut key  (e.g.  1,  2,  q,  w)")
        key_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(key_field)
        name_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        name_field.setPlaceholderString_(f"{step_lbl} label  (e.g.  LAYUP,  WIDE,  GOOD)")
        name_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(name_field)
        alert.setAccessoryView_(panel)
        alert.window().setInitialFirstResponder_(key_field)

        if alert.runModal() == 1000:
            key   = key_field.stringValue().strip()[:1]
            label = _asc(name_field.stringValue().strip()).upper()
            if key and label:
                items = self.shortcuts.setdefault(step_id, [])
                items.append({"key": key, "label": label})
                self.app._save_shortcuts()
                self._refresh_labels_grid()
                self._populate_shortcut_pills(step_id)

    def _labels_edit_shortcut(self, idx):
        from AppKit import NSAlert, NSTextField, NSView, NSMakeRect, NSFont
        step_id = getattr(self, "_labels_active_step", None)
        if step_id is None:
            return
        items = self.shortcuts.get(step_id, [])
        if not (0 <= idx < len(items)):
            return
        sc = items[idx]

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Edit Shortcut")
        alert.setInformativeText_(f"Editing: {sc['label']}")
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")

        panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 60))
        key_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 32, 300, 24))
        key_field.setStringValue_(sc["key"])
        key_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(key_field)
        name_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        name_field.setStringValue_(sc["label"])
        name_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(name_field)
        alert.setAccessoryView_(panel)

        if alert.runModal() == 1000:
            key   = key_field.stringValue().strip()[:1]
            label = _asc(name_field.stringValue().strip()).upper()
            if key and label:
                items[idx] = {"key": key, "label": label}
                items.sort(key=lambda sc: (0, int(sc["key"])) if sc.get("key", "").isdigit() else (1, sc.get("key", "").lower()))
                self.shortcuts[step_id] = items
                self.app._save_shortcuts()
                self._refresh_labels_grid()
                self._populate_shortcut_pills(step_id)

    def _labels_delete_shortcut(self, idx):
        from AppKit import NSAlert
        step_id = getattr(self, "_labels_active_step", None)
        if step_id is None:
            return
        items = self.shortcuts.get(step_id, [])
        if not (0 <= idx < len(items)):
            return
        sc = items[idx]

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Delete Shortcut")
        alert.setInformativeText_(f"Delete [{sc['key']}]  {sc['label']}?")
        alert.addButtonWithTitle_("Delete")
        alert.addButtonWithTitle_("Cancel")

        if alert.runModal() == 1000:
            items.pop(idx)
            self.shortcuts[step_id] = items
            self.app._save_shortcuts()
            self._refresh_labels_grid()
            self._populate_shortcut_pills(step_id)

    def _labels_open_children(self, idx):
        """Open a modal panel to manage children shortcuts for shortcut[idx]."""
        from AppKit import (
            NSApplication, NSPanel, NSView, NSTextField, NSScrollView,
            NSFont, NSColor, NSMakeRect, NSButton,
            NSBackingStoreBuffered, NSWindowStyleMaskTitled,
            NSWindowStyleMaskClosable,
        )
        step_id = getattr(self, "_labels_active_step", None)
        if step_id is None:
            return
        items = self.shortcuts.get(step_id, [])
        if not (0 <= idx < len(items)):
            return
        parent_sc = items[idx]
        children  = list(parent_sc.get("children", []))

        W, H = 460.0, 400.0
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, H), style, NSBackingStoreBuffered, False)
        panel.setTitle_(f"Children of  [{parent_sc['key']}]  {parent_sc['label']}")
        panel.center()
        panel.setReleasedWhenClosed_(False)
        cv = panel.contentView()

        # ── Child list (scrollable) ───────────────────────────────────────────
        BTN_AREA_H = 100.0
        list_h = H - BTN_AREA_H - 16
        sv = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(16, BTN_AREA_H, W - 32, list_h))
        sv.setHasVerticalScroller_(True)
        sv.setAutohidesScrollers_(True)
        sv.setBorderType_(0)
        sv.setDrawsBackground_(False)
        cv.addSubview_(sv)

        list_container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, W - 32, 0))
        sv.setDocumentView_(list_container)

        row_refs  = []   # keep refs for "delete" closures
        row_targets = []

        def _rebuild_list():
            for v in list(list_container.subviews()):
                v.removeFromSuperview()
            row_refs.clear()
            row_targets.clear()
            ROW_H   = 34.0
            PAD     = 0.0
            total_h = max(len(children) * ROW_H, list_h)
            list_container.setFrame_(NSMakeRect(0, 0, W - 32, total_h))

            for j, ch in enumerate(children):
                y   = total_h - (j + 1) * ROW_H
                row = NSView.alloc().initWithFrame_(NSMakeRect(PAD, y, W - 32 - PAD * 2, ROW_H))
                row.setWantsLayer_(True)
                row.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.03 if j % 2 == 0 else 0.0).CGColor())

                key_lbl = NSTextField.labelWithString_(ch.get("key", "·").upper())
                key_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0.6))
                key_lbl.setTextColor_(_hex_color(COLOR_TAN))
                key_lbl.setFrame_(NSMakeRect(12, (ROW_H - 16) / 2, 24, 16))
                row.addSubview_(key_lbl)

                name_lbl = NSTextField.labelWithString_(ch.get("label", ""))
                name_lbl.setFont_(NSFont.systemFontOfSize_(13))
                name_lbl.setTextColor_(NSColor.labelColor())
                name_lbl.setFrame_(NSMakeRect(44, (ROW_H - 16) / 2, W - 32 - 44 - 36, 16))
                name_lbl.setLineBreakMode_(5)
                row.addSubview_(name_lbl)

                del_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - 32 - 30, (ROW_H - 18) / 2, 18, 18))
                del_btn.setBordered_(False)
                from AppKit import NSImage
                img = NSImage.imageWithSystemSymbolName_accessibilityDescription_("minus.circle", None)
                if img:
                    del_btn.setImage_(img)
                    del_btn.setContentTintColor_(NSColor.tertiaryLabelColor())
                t = MenuTarget.alloc().init()
                t._j = j
                def _del(_, jj=j):
                    children.pop(jj)
                    _rebuild_list()
                t._callback = _del
                del_btn.setTarget_(t)
                del_btn.setAction_("menuPicked:")
                row.addSubview_(del_btn)
                row_targets.append(t)
                row_refs.append(row)
                list_container.addSubview_(row)

            sv.contentView().scrollToPoint_((0, max(0.0, total_h - list_h)))
            sv.reflectScrolledClipView_(sv.contentView())

        _rebuild_list()

        # ── Add child row ─────────────────────────────────────────────────────
        sep = NSView.alloc().initWithFrame_(NSMakeRect(16, BTN_AREA_H - 1, W - 32, 1))
        sep.setWantsLayer_(True)
        sep.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.10).CGColor())
        cv.addSubview_(sep)

        hint = NSTextField.labelWithString_("Add a child shortcut:")
        hint.setFont_(NSFont.systemFontOfSize_(11))
        hint.setTextColor_(NSColor.secondaryLabelColor())
        hint.setFrame_(NSMakeRect(16, BTN_AREA_H - 22, W - 32, 14))
        cv.addSubview_(hint)

        key_f = NSTextField.alloc().initWithFrame_(NSMakeRect(16, BTN_AREA_H - 52, 60, 24))
        key_f.setPlaceholderString_("Key")
        key_f.setFont_(NSFont.systemFontOfSize_(13))
        cv.addSubview_(key_f)

        lbl_f = NSTextField.alloc().initWithFrame_(NSMakeRect(84, BTN_AREA_H - 52, W - 84 - 72, 24))
        lbl_f.setPlaceholderString_("Label  (e.g. High, Low, Kick)")
        lbl_f.setFont_(NSFont.systemFontOfSize_(13))
        cv.addSubview_(lbl_f)

        add_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - 68, BTN_AREA_H - 52, 52, 24))
        add_btn.setTitle_("Add")
        add_btn.setBezelStyle_(1)
        t_add = MenuTarget.alloc().init()
        def _add_child(_):
            k = key_f.stringValue().strip()[:1]
            l = _asc(lbl_f.stringValue().strip()).upper()
            if k and l:
                children.append({"key": k, "label": l})
                key_f.setStringValue_("")
                lbl_f.setStringValue_("")
                _rebuild_list()
        t_add._callback = _add_child
        add_btn.setTarget_(t_add)
        add_btn.setAction_("menuPicked:")
        cv.addSubview_(add_btn)
        row_targets.append(t_add)

        # ── Done button ───────────────────────────────────────────────────────
        done_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - 84, 12, 68, 28))
        done_btn.setTitle_("Done")
        done_btn.setBezelStyle_(1)
        done_btn.setKeyEquivalent_("\r")
        t_done = MenuTarget.alloc().init()
        t_done._callback = lambda _: NSApplication.sharedApplication().stopModal()
        done_btn.setTarget_(t_done)
        done_btn.setAction_("menuPicked:")
        cv.addSubview_(done_btn)
        row_targets.append(t_done)

        # Stop the modal if the user closes via the red X button instead of Done
        panel_delegate = WindowDelegate.alloc().init()
        panel_delegate._close_cb = lambda: NSApplication.sharedApplication().stopModal()
        panel.setDelegate_(panel_delegate)

        NSApplication.sharedApplication().runModalForWindow_(panel)
        panel.setDelegate_(None)
        panel.orderOut_(None)

        # Save updated children back into the shortcut
        items[idx] = dict(parent_sc, children=children)
        self.shortcuts[step_id] = items
        self.app._save_shortcuts()
        self._refresh_labels_grid()
        self._populate_shortcut_pills(step_id)

    def _labels_add_step(self):
        from AppKit import NSAlert, NSTextField, NSView, NSMakeRect, NSFont
        import uuid
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Add Labeling Step")
        alert.setInformativeText_("Enter a name for this step (e.g. Shot Type, Move Type).")
        alert.addButtonWithTitle_("Add")
        alert.addButtonWithTitle_("Cancel")

        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        field.setPlaceholderString_("Step name")
        field.setFont_(NSFont.systemFontOfSize_(13))
        alert.setAccessoryView_(field)
        alert.window().setInitialFirstResponder_(field)

        if alert.runModal() == 1000:
            name = field.stringValue().strip()
            if not name:
                return
            new_id   = f"step_{uuid.uuid4().hex[:8]}"
            config   = self.app.session if self.app else DEFAULT_SESSION
            custom   = config.get("custom_steps", list(DEFAULT_SESSION["custom_steps"]))
            # Insert before the last step (treat last as "rating-like" finale)
            insert_at = max(0, len(custom) - 1)
            custom.insert(insert_at, {"id": new_id, "label": name})
            if self.app:
                self.app.session["custom_steps"] = custom
                save_json(CONFIG_FILE, self.app.session)
            self._labels_active_step = new_id
            self._apply_steps_change()

    def _labels_delete_step(self, step_id):
        from AppKit import NSAlert
        config  = self.app.session if self.app else DEFAULT_SESSION
        custom  = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        step    = next((s for s in custom if s["id"] == step_id), None)
        if step is None or len(custom) <= 1:
            return

        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"Delete step \"{step['label']}\"?")
        alert.setInformativeText_("All shortcuts in this step will also be removed.")
        alert.addButtonWithTitle_("Delete")
        alert.addButtonWithTitle_("Cancel")

        if alert.runModal() == 1000:
            custom.remove(step)
            self.shortcuts.pop(step_id, None)
            if self.app:
                save_json(CONFIG_FILE, self.app.session)
            self.app._save_shortcuts()
            self._labels_active_step = custom[0]["id"] if custom else None
            self._apply_steps_change()

    def _labels_move_step(self, step_id, direction):
        config = self.app.session if self.app else DEFAULT_SESSION
        custom = config.get("custom_steps", DEFAULT_SESSION["custom_steps"])
        idx    = next((i for i, s in enumerate(custom) if s["id"] == step_id), None)
        if idx is None:
            return
        new_idx = idx + direction
        if not (0 <= new_idx < len(custom)):
            return
        custom[idx], custom[new_idx] = custom[new_idx], custom[idx]
        if self.app:
            save_json(CONFIG_FILE, self.app.session)
        self._apply_steps_change()

    def _apply_steps_change(self):
        """Rebuild all step-dependent UI after custom_steps changes."""
        self._rebuild_steps()
        self._rebuild_labels_rows()
        self._refresh_labels_grid()
        self._rebuild_sc_cards()
        self._build_step_circles()
        self._set_step_state(active=-1)
        if hasattr(self, "_sc_cards"):
            for card in self._sc_cards.values():
                sec = getattr(self, "current_section", "tag")
                card.setHidden_(sec != "tag")

    # ── Naming section ────────────────────────────────────────────────────────

    def _build_session_section(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect, NSScrollView,
        )

        cx = float(SIDEBAR_W)
        cw = float(W - SIDEBAR_W)
        ch = float(H - TOP_H)

        section = NSView.alloc().initWithFrame_(NSMakeRect(cx, 0, cw, ch))
        section.setWantsLayer_(True)
        section.setAutoresizingMask_(2 | 16)
        section.setHidden_(True)
        cv.addSubview_(section)
        self._session_section = section

        HEADER_H  = 64.0
        FOLDER_H  = 54.0
        header_y  = ch - HEADER_H

        # ── Header ────────────────────────────────────────────────────────────
        title_lbl = NSTextField.labelWithString_("Naming")
        title_lbl.setFont_(NSFont.boldSystemFontOfSize_(22))
        title_lbl.setTextColor_(NSColor.labelColor())
        title_lbl.sizeToFit()
        tf = title_lbl.frame()
        title_lbl.setFrame_(NSMakeRect(
            32, header_y + (HEADER_H - tf.size.height) / 2,
            tf.size.width, tf.size.height))
        title_lbl.setAutoresizingMask_(8)
        section.addSubview_(title_lbl)

        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, header_y - 1, cw, 1))
        sep.setWantsLayer_(True)
        sep.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        sep.setAutoresizingMask_(2 | 8)
        section.addSubview_(sep)

        # ── Folder row ────────────────────────────────────────────────────────
        FORM_W  = min(560.0, cw - 80.0)
        form_x  = (cw - FORM_W) / 2
        folder_row_y = header_y - FOLDER_H - 12.0

        s = self.app.session if self.app else DEFAULT_SESSION
        self._session_folder = s.get("folder", "")
        folder_name = Path(self._session_folder).name or "No folder selected"
        LABEL_W  = 80.0
        FIELD_H  = 34.0
        CHOOSE_W = 130.0

        row_bg = NSView.alloc().initWithFrame_(
            NSMakeRect(form_x, folder_row_y, FORM_W, FOLDER_H))
        row_bg.setWantsLayer_(True)
        row_bg.layer().setCornerRadius_(10.0)
        row_bg.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.04).CGColor())
        row_bg.layer().setBorderWidth_(0.5)
        row_bg.layer().setBorderColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        section.addSubview_(row_bg)
        self._folder_row = row_bg

        folder_lbl = NSTextField.labelWithString_("Folder")
        folder_lbl.setFont_(NSFont.systemFontOfSize_(13))
        folder_lbl.setTextColor_(NSColor.secondaryLabelColor())
        folder_lbl.setFrame_(NSMakeRect(16, (FOLDER_H - 17) / 2, LABEL_W, 17))
        row_bg.addSubview_(folder_lbl)

        field_x = LABEL_W + 24.0
        path_w  = FORM_W - field_x - CHOOSE_W - 24.0

        path_lbl = NSTextField.labelWithString_(folder_name)
        path_lbl.setFont_(NSFont.systemFontOfSize_(12))
        path_lbl.setTextColor_(NSColor.secondaryLabelColor())
        path_lbl.setFrame_(NSMakeRect(field_x, (FOLDER_H - 17) / 2, path_w, 17))
        path_lbl.setLineBreakMode_(5)
        row_bg.addSubview_(path_lbl)
        self._folder_path_lbl = path_lbl

        choose_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(field_x + path_w + 10, (FOLDER_H - 28) / 2, CHOOSE_W, 28))
        choose_btn.configureTitle_bg_press_action_(
            "Choose Folder…", "#3a3a3c", "#2c2c2e", self._session_choose_folder)
        row_bg.addSubview_(choose_btn)

        # Store form metrics for convention builder to reuse
        self._conv_form_w = FORM_W
        self._conv_form_x = form_x

        # ── Convention builder scroll view ────────────────────────────────────
        conv_sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, 0))
        conv_sv.setHasVerticalScroller_(True)
        conv_sv.setAutohidesScrollers_(True)
        conv_sv.setBorderType_(0)
        conv_sv.setDrawsBackground_(False)
        section.addSubview_(conv_sv)
        self._convention_sv = conv_sv

        self._build_convention_ui(section, cw)
        self._reposition_session_section(cw, ch)

    def _session_choose_folder(self):
        folder = pick_folder_dialog()
        if folder:
            self._session_folder = folder
            name = Path(folder).name or folder
            if hasattr(self, "_folder_path_lbl"):
                self._folder_path_lbl.setStringValue_(name)
            if self.app:
                self.app.session["folder"] = folder
                save_json(CONFIG_FILE, self.app.session)
                self.app._build_menu()
            self.folder = Path(folder)
            self._refresh_files()

    # ── Naming section — layout helpers ──────────────────────────────────────

    def _reposition_session_section(self, cw, ch):
        """Folder row is pinned just below the header; convention_sv fills the rest."""
        from AppKit import NSMakeRect
        HEADER_H = 64.0
        FOLDER_H = 54.0
        GAP      = 12.0
        BOT_PAD  = 12.0

        folder_row_y = ch - HEADER_H - FOLDER_H - GAP
        FORM_W = min(560.0, cw - 80.0)
        form_x = (cw - FORM_W) / 2

        if hasattr(self, "_folder_row"):
            self._folder_row.setFrame_(
                NSMakeRect(form_x, folder_row_y, FORM_W, FOLDER_H))
            # reflow the path label width inside the row
            if hasattr(self, "_folder_path_lbl"):
                LABEL_W  = 80.0
                CHOOSE_W = 130.0
                field_x  = LABEL_W + 24.0
                path_w   = FORM_W - field_x - CHOOSE_W - 24.0
                self._folder_path_lbl.setFrame_(
                    NSMakeRect(field_x, (FOLDER_H - 17) / 2, path_w, 17))

        conv_y = BOT_PAD
        conv_h = max(120.0, folder_row_y - GAP - BOT_PAD)
        if hasattr(self, "_convention_sv"):
            sv = self._convention_sv
            sv.setFrame_(NSMakeRect(0, conv_y, cw, conv_h))
            doc = sv.documentView()
            if doc:
                doc_h = doc.frame().size.height
                # Keep doc width in sync so _rebuild_convention_rows uses correct cw
                if doc.frame().size.width != cw:
                    doc.setFrame_(NSMakeRect(0, 0, cw, doc_h))
                sv.contentView().scrollToPoint_((0, max(0.0, doc_h - conv_h)))
                sv.reflectScrolledClipView_(sv.contentView())

    def _reposition_settings_section(self, cw, ch):
        from AppKit import NSMakeRect
        doc = self._settings_doc
        cur = doc.frame().size
        if cur.width != cw:
            doc.setFrame_(NSMakeRect(0, 0, cw, cur.height))

    def _reposition_help_content_w(self, cw, ch):
        from AppKit import NSMakeRect
        TOC_W      = 200.0
        content_x  = TOC_W + 1.0
        new_w      = max(1.0, cw - content_x)
        container  = self._help_doc_container
        cur        = container.frame().size
        if cur.width != new_w:
            container.setFrame_(NSMakeRect(0, 0, new_w, cur.height))

    def _layout_help_content(self, sv, content_w: float, content_area_h: float):
        """Two-pass (measure → place) render of help content into sv's document view.
        Sets self._help_doc_container and self._help_section_ys."""
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect

        PAD_X      = 36.0
        PAD_TOP    = 28.0
        body_w     = content_w - PAD_X * 2
        LABEL_W    = 148.0
        COL_GAP    = 14.0
        value_w    = body_w - LABEL_W - COL_GAP
        ROW_GAP    = 5.0
        PARA_GAP   = 12.0
        BLOCK_GAP  = 16.0
        SUB_PRE    = 14.0
        SUB_POST   = 7.0
        SEC_GAP    = 36.0
        DIV_H      = 1.0

        t_font   = NSFont.boldSystemFontOfSize_(17.0)
        b_font   = NSFont.systemFontOfSize_(13.0)
        sub_font = NSFont.boldSystemFontOfSize_(10.0)

        def meas(text, font, width):
            f = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, width, 10000))
            f.setStringValue_(text)
            f.setFont_(font)
            f.cell().setWraps_(True)
            sz = f.cell().cellSizeForBounds_(NSMakeRect(0, 0, width, 10000))
            return float(sz.height) + 2.0

        sections = self._help_content_sections()

        def block_h(blk):
            typ = blk[0]
            if typ == "para":
                return meas(blk[1], b_font, body_w) + PARA_GAP
            if typ == "subhead":
                return SUB_PRE + meas(blk[1], sub_font, body_w) + SUB_POST
            if typ == "table":
                h = 0.0
                for k, v in blk[1]:
                    rh = max(meas(k, b_font, LABEL_W), meas(v, b_font, value_w), 18.0)
                    h += rh + ROW_GAP
                return h
            if typ == "bullets":
                h = 0.0
                for item in blk[1]:
                    h += meas("·  " + item, b_font, body_w) + ROW_GAP
                return h
            return 0.0

        # Pass 1 — measure total height
        y_ft = PAD_TOP
        for si, (title, blocks) in enumerate(sections):
            y_ft += meas(title, t_font, body_w) + 4.0 + 10.0
            prev_is_sub = False
            for bi, blk in enumerate(blocks):
                if bi > 0 and blk[0] != "subhead":
                    if not prev_is_sub:
                        y_ft += BLOCK_GAP
                y_ft += block_h(blk)
                prev_is_sub = (blk[0] == "subhead")
            if si < len(sections) - 1:
                y_ft += DIV_H + SEC_GAP * 2

        total_h = max(y_ft + PAD_TOP, float(content_area_h))
        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, content_w, total_h))
        sv.setDocumentView_(container)
        self._help_doc_container = container
        self._help_section_ys    = []

        def place_lbl(text, x, y_from_top, w, h, font, color, wrap=True):
            f = NSTextField.alloc().initWithFrame_(
                NSMakeRect(x, total_h - y_from_top - h, w, h))
            f.setStringValue_(text)
            f.setFont_(font)
            f.setTextColor_(color)
            f.setBezeled_(False)
            f.setDrawsBackground_(False)
            f.setEditable_(False)
            f.setSelectable_(True)
            f.cell().setWraps_(wrap)
            container.addSubview_(f)

        # Pass 2 — place views
        y_ft = PAD_TOP
        for si, (title, blocks) in enumerate(sections):
            self._help_section_ys.append(total_h - y_ft)
            th = meas(title, t_font, body_w) + 4.0
            place_lbl(title, PAD_X, y_ft, body_w, th, t_font, NSColor.labelColor())
            y_ft += th + 10.0
            prev_is_sub = False
            for bi, blk in enumerate(blocks):
                typ = blk[0]
                if bi > 0 and typ != "subhead":
                    if not prev_is_sub:
                        y_ft += BLOCK_GAP
                if typ == "para":
                    h = meas(blk[1], b_font, body_w)
                    place_lbl(blk[1], PAD_X, y_ft, body_w, h,
                               b_font, NSColor.secondaryLabelColor())
                    y_ft += h + PARA_GAP
                elif typ == "subhead":
                    y_ft += SUB_PRE
                    h = meas(blk[1], sub_font, body_w)
                    place_lbl(blk[1], PAD_X, y_ft, body_w, h,
                               sub_font, NSColor.tertiaryLabelColor())
                    y_ft += h + SUB_POST
                elif typ == "table":
                    for k, v in blk[1]:
                        kh = meas(k, b_font, LABEL_W)
                        vh = meas(v, b_font, value_w)
                        rh = max(kh, vh, 18.0)
                        place_lbl(k, PAD_X, y_ft, LABEL_W, rh,
                                   b_font, NSColor.secondaryLabelColor())
                        place_lbl(v, PAD_X + LABEL_W + COL_GAP, y_ft, value_w, rh,
                                   b_font, NSColor.labelColor())
                        y_ft += rh + ROW_GAP
                elif typ == "bullets":
                    for item in blk[1]:
                        h = meas("·  " + item, b_font, body_w)
                        place_lbl("·  " + item, PAD_X, y_ft, body_w, h,
                                   b_font, NSColor.secondaryLabelColor())
                        y_ft += h + ROW_GAP
                prev_is_sub = (typ == "subhead")
            if si < len(sections) - 1:
                y_ft += SEC_GAP
                div = NSView.alloc().initWithFrame_(
                    NSMakeRect(PAD_X, total_h - y_ft, body_w, DIV_H))
                div.setWantsLayer_(True)
                div.layer().setBackgroundColor_(
                    _hex_color_alpha("#ffffff", 0.08).CGColor())
                container.addSubview_(div)
                y_ft += DIV_H + SEC_GAP

        sv.documentView().scrollPoint_((0, total_h))

    def _rebuild_help_scroll(self, cw):
        """Replace the help scroll view's document with content sized for the new cw."""
        if not hasattr(self, "_help_scroll") or not hasattr(self, "_help_section"):
            return
        from AppKit import NSScrollView, NSMakeRect
        section        = self._help_section
        HEADER_H       = 64.0
        TOC_W          = 200.0
        content_x      = TOC_W + 1.0
        ch             = section.frame().size.height
        content_area_h = ch - HEADER_H - 1.0
        content_w      = max(1.0, cw - content_x)

        self._help_scroll.removeFromSuperview()
        sv = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(content_x, 0, content_w, content_area_h))
        sv.setHasVerticalScroller_(True)
        sv.setAutohidesScrollers_(True)
        sv.setBorderType_(0)
        sv.setDrawsBackground_(False)
        sv.setAutoresizingMask_(2 | 16)
        section.addSubview_(sv)
        self._help_scroll          = sv
        self._help_built_content_w = content_w

        self._layout_help_content(sv, content_w, content_area_h)

    # ── Naming Convention Builder ─────────────────────────────────────────────

    def _build_convention_ui(self, section, cw):
        """Initialise convention builder state and populate the doc container."""
        from AppKit import NSView, NSMakeRect

        s = self.app.session if self.app else DEFAULT_SESSION
        sport_key      = s.get("sport", "")
        global_presets = s.get("naming_presets", DEFAULT_NAMING_PRESETS) or list(DEFAULT_NAMING_PRESETS)
        sport_presets  = s.get("sport_presets", {}).get(sport_key, [])
        combined = [dict(p) for p in global_presets] + [dict(p) for p in sport_presets]
        if not combined:
            combined = list(DEFAULT_NAMING_PRESETS)
        active_idx = int(s.get("active_preset", 0))
        if active_idx >= len(combined):
            active_idx = 0

        self._convention_global_count = len(global_presets)
        self._convention_presets      = combined
        self._convention_active_idx   = active_idx
        self._convention_field_data   = [dict(f) for f in combined[active_idx].get("fields", [])]
        self._convention_field_views  = []
        self._convention_tf_refs      = []   # NSTextField per row (None for metadata rows)

        doc = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, 400))
        self._convention_sv.setDocumentView_(doc)
        self._convention_doc = doc

        self._rebuild_convention_rows()

    def _refresh_convention_for_sport(self):
        """Reload global + sport presets from session and rebuild convention rows."""
        if not hasattr(self, "_convention_sv"):
            return
        s = self.app.session if self.app else DEFAULT_SESSION
        sport_key = s.get("sport", "")
        global_presets = s.get("naming_presets", DEFAULT_NAMING_PRESETS) or list(DEFAULT_NAMING_PRESETS)
        sport_presets  = s.get("sport_presets", {}).get(sport_key, [])
        combined = [dict(p) for p in global_presets] + [dict(p) for p in sport_presets]
        if not combined:
            combined = list(DEFAULT_NAMING_PRESETS)
        self._convention_global_count = len(global_presets)
        self._convention_presets      = combined
        active_idx = int(s.get("active_preset", 0))
        if active_idx >= len(combined):
            active_idx = 0
        self._convention_active_idx = active_idx
        self._convention_field_data = [dict(f) for f in combined[active_idx].get("fields", [])]
        self._rebuild_convention_rows()

    def _sync_convention_text_fields(self):
        """Pull current typed values from NSTextFields back into _convention_field_data."""
        for idx, tf in enumerate(self._convention_tf_refs):
            if tf is not None and idx < len(self._convention_field_data):
                self._convention_field_data[idx]["value"] = tf.stringValue()

    def _register_tf_observer(self, tf):
        """Fire _convention_update_preview whenever tf loses focus."""
        from AppKit import NSNotificationCenter
        obs = MainCaller.alloc().init()
        obs._cb = self._convention_update_preview
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            obs, "fire:", "NSControlTextDidEndEditingNotification", tf)
        if not hasattr(self, "_conv_tf_observers"):
            self._conv_tf_observers = []
        self._conv_tf_observers.append(obs)

    def _rebuild_convention_rows(self, scroll_to="top"):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect, NSMenu, NSMenuItem,
            NSNotificationCenter,
        )
        self._sync_convention_text_fields()
        # Clear refs immediately so nothing re-syncs stale values during rebuild
        self._convention_tf_refs = []

        # Save scroll position before tearing down (for preserve mode)
        saved_y = 0.0
        if scroll_to == "preserve":
            saved_y = self._convention_sv.documentVisibleRect().origin.y

        # Remove notification observers from previous build
        if hasattr(self, "_conv_tf_observers"):
            nc = NSNotificationCenter.defaultCenter()
            for obs in self._conv_tf_observers:
                nc.removeObserver_(obs)
        self._conv_tf_observers = []

        doc = self._convention_doc
        for v in list(doc.subviews()):
            v.removeFromSuperview()
        self._convention_field_views = []

        cw     = doc.frame().size.width or 600.0
        FORM_W = self._conv_form_w
        form_x = self._conv_form_x

        n             = len(self._convention_field_data)
        ROW_H         = 44.0
        ROW_GAP       = 8.0
        PER_FIELD     = ROW_H + ROW_GAP
        FIXED_H       = (
            14.0   # top pad
            + 28.0 + 10.0   # sub-header
            + 30.0 + 10.0   # preset bar
            + 44.0 + 12.0   # separator row
            + 30.0 + 10.0   # add-field button
            + 68.0 + 10.0   # preview block
            + 30.0 + 8.0    # save + import buttons
            + 20.0 + 16.0   # status label + bottom pad
        )
        natural_h = FIXED_H + n * PER_FIELD
        sv_vh = self._convention_sv.contentView().frame().size.height
        doc_h = max(natural_h, sv_vh) if sv_vh > 0 else natural_h
        doc.setFrame_(NSMakeRect(0, 0, cw, doc_h))

        # cursor (AppKit: y=0 at bottom, build top-down)
        y = doc_h

        # ── Sub-header ───────────────────────────────────────────────────────
        y -= 14.0
        HDR_H = 28.0
        y -= HDR_H
        hdr = NSTextField.labelWithString_("Naming Convention")
        hdr.setFont_(NSFont.boldSystemFontOfSize_(15))
        hdr.setTextColor_(NSColor.labelColor())
        hdr.setFrame_(NSMakeRect(form_x, y, FORM_W, HDR_H))
        doc.addSubview_(hdr)
        y -= 10.0

        # ── Preset bar ───────────────────────────────────────────────────────
        BAR_H    = 30.0
        y -= BAR_H
        preset   = self._convention_presets[self._convention_active_idx]
        p_name   = preset.get("name", "Default")
        BTN_W    = 60.0
        BTN_GAP  = 6.0
        dd_w     = FORM_W - 3 * (BTN_W + BTN_GAP)

        preset_dd = PillButton.alloc().initWithFrame_(NSMakeRect(form_x, y, dd_w, BAR_H))
        preset_dd.layer().setCornerRadius_(8.0)
        preset_dd.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
        preset_dd.layer().setBorderWidth_(0.5)
        preset_dd.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.18).CGColor())
        dd_lbl = NSTextField.labelWithString_(f"▸  {p_name}")
        dd_lbl.setFont_(NSFont.systemFontOfSize_(13))
        dd_lbl.setTextColor_(NSColor.labelColor())
        dd_lbl.setFrame_(NSMakeRect(10, (BAR_H - 17) / 2, dd_w - 20, 17))
        preset_dd.addSubview_(dd_lbl)
        doc.addSubview_(preset_dd)
        self._convention_preset_lbl = dd_lbl
        preset_dd.setClickHandler_(
            lambda v, e: self._convention_preset_menu(v, e))

        for idx_btn, (btn_title, btn_action, btn_bg) in enumerate([
            ("+ New",  self._convention_new_preset,       "#3a6e3a"),
            ("Dup",    self._convention_duplicate_preset, "#3a3a3c"),
            ("Delete", self._convention_delete_preset,    "#6b1a26"),
        ]):
            bx = form_x + dd_w + BTN_GAP + idx_btn * (BTN_W + BTN_GAP)
            btn = ActionButton.alloc().initWithFrame_(NSMakeRect(bx, y, BTN_W, BAR_H))
            press_bg = "#2c5a2c" if btn_bg == "#3a6e3a" else ("#2c2c2e" if btn_bg == "#3a3a3c" else "#4a1219")
            btn.configureTitle_bg_press_action_(btn_title, btn_bg, press_bg, btn_action)
            doc.addSubview_(btn)
        y -= 10.0

        # ── Separator row ────────────────────────────────────────────────────
        SEP_ROW_H = 44.0
        y -= SEP_ROW_H
        sep_bg = NSView.alloc().initWithFrame_(NSMakeRect(form_x, y, FORM_W, SEP_ROW_H))
        sep_bg.setWantsLayer_(True)
        sep_bg.layer().setCornerRadius_(10.0)
        sep_bg.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.04).CGColor())
        sep_bg.layer().setBorderWidth_(0.5)
        sep_bg.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
        doc.addSubview_(sep_bg)

        sep_lbl = NSTextField.labelWithString_("Separator symbol")
        sep_lbl.setFont_(NSFont.systemFontOfSize_(13))
        sep_lbl.setTextColor_(NSColor.secondaryLabelColor())
        sep_lbl.setFrame_(NSMakeRect(16, (SEP_ROW_H - 17) / 2, 160, 17))
        sep_bg.addSubview_(sep_lbl)

        SEP_FIELD_W = 56.0
        SEP_FIELD_H = 28.0
        sf_bg = NSView.alloc().initWithFrame_(
            NSMakeRect(FORM_W - SEP_FIELD_W - 14,
                       (SEP_ROW_H - SEP_FIELD_H) / 2, SEP_FIELD_W, SEP_FIELD_H))
        sf_bg.setWantsLayer_(True)
        sf_bg.layer().setCornerRadius_(6.0)
        sf_bg.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
        sf_bg.layer().setBorderWidth_(0.5)
        sf_bg.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.18).CGColor())
        sep_bg.addSubview_(sf_bg)

        sep_tf = NSTextField.alloc().initWithFrame_(
            NSMakeRect(6, (SEP_FIELD_H - 18) / 2, SEP_FIELD_W - 12, 18))
        sep_tf.setStringValue_(preset.get("separator", "_"))
        sep_tf.setFont_(NSFont.monospacedSystemFontOfSize_weight_(14, 0))
        sep_tf.setTextColor_(NSColor.labelColor())
        sep_tf.setBezeled_(False)
        sep_tf.setDrawsBackground_(False)
        sep_tf.setEditable_(True)
        sep_tf.setSelectable_(True)
        sf_bg.addSubview_(sep_tf)
        self._convention_sep_tf = sep_tf
        self._register_tf_observer(sep_tf)
        y -= 12.0

        # ── Field rows ───────────────────────────────────────────────────────
        for idx, field in enumerate(self._convention_field_data):
            y -= ROW_H
            row_view, tf_ref = self._build_convention_field_row(doc, idx, form_x, FORM_W, y, ROW_H, field)
            self._convention_field_views.append(row_view)
            self._convention_tf_refs.append(tf_ref)
            if tf_ref is not None:
                self._register_tf_observer(tf_ref)
            y -= ROW_GAP

        # ── Add Field button ─────────────────────────────────────────────────
        ADD_H = 30.0
        y -= ADD_H
        add_btn = ActionButton.alloc().initWithFrame_(NSMakeRect(form_x, y, 120.0, ADD_H))
        add_btn.configureTitle_bg_press_action_(
            "+ Add Field", "#3a3a3c", "#2c2c2e", self._convention_add_field)
        doc.addSubview_(add_btn)
        y -= 10.0

        # ── Preview block ────────────────────────────────────────────────────
        PREV_H = 68.0
        y -= PREV_H
        prev_bg = NSView.alloc().initWithFrame_(NSMakeRect(form_x, y, FORM_W, PREV_H))
        prev_bg.setWantsLayer_(True)
        prev_bg.layer().setCornerRadius_(10.0)
        prev_bg.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.03).CGColor())
        prev_bg.layer().setBorderWidth_(0.5)
        prev_bg.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.06).CGColor())
        doc.addSubview_(prev_bg)

        prev_title = NSTextField.labelWithString_("PREVIEW")
        prev_title.setFont_(NSFont.boldSystemFontOfSize_(10))
        prev_title.setTextColor_(NSColor.tertiaryLabelColor())
        prev_title.setFrame_(NSMakeRect(14, PREV_H - 20, 100, 16))
        prev_bg.addSubview_(prev_title)

        prev_val = NSTextField.labelWithString_("—")
        prev_val.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0))
        prev_val.setTextColor_(_hex_color(COLOR_TAN))
        prev_val.setFrame_(NSMakeRect(14, 10, FORM_W - 28, PREV_H - 36))
        prev_val.setLineBreakMode_(4)  # truncate tail
        prev_bg.addSubview_(prev_val)
        self._convention_preview_lbl = prev_val
        y -= 10.0

        # ── Save Convention + Import Schedule buttons ─────────────────────────
        SAVE_H   = 30.0
        BTN_HALF = (FORM_W - 8) / 2
        y -= SAVE_H
        save_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(form_x, y, BTN_HALF, SAVE_H))
        save_btn.configureTitle_bg_press_action_(
            "Save Convention", "#8c2232", "#6b1a26", self._convention_save)
        doc.addSubview_(save_btn)

        import_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(form_x + BTN_HALF + 8, y, BTN_HALF, SAVE_H))
        import_btn.configureTitle_bg_press_action_(
            "⚡ Import Schedule", "#3a3a3c", "#2c2c2e",
            self._import_schedule_opponents)
        doc.addSubview_(import_btn)
        self._import_schedule_btn = import_btn

        # ── Import status label ───────────────────────────────────────────────
        y -= 24.0
        status_lbl = NSTextField.labelWithString_("")
        status_lbl.setFont_(NSFont.systemFontOfSize_(11))
        status_lbl.setTextColor_(NSColor.secondaryLabelColor())
        status_lbl.setAlignment_(1)
        status_lbl.setFrame_(NSMakeRect(form_x, y, FORM_W, 20))
        doc.addSubview_(status_lbl)
        self._import_schedule_status = status_lbl

        self._convention_update_preview()
        sv = self._convention_sv
        if scroll_to == "top":
            viewport_h = sv.contentView().frame().size.height
            sv.contentView().scrollToPoint_((0, max(0.0, doc_h - viewport_h)))
            sv.reflectScrolledClipView_(sv.contentView())
        elif scroll_to == "bottom":
            sv.contentView().scrollToPoint_((0, 0.0))
            sv.reflectScrolledClipView_(sv.contentView())
        else:  # preserve
            sv.contentView().scrollToPoint_((0, saved_y))
            sv.reflectScrolledClipView_(sv.contentView())

    def _build_convention_field_row(self, doc, idx, form_x, FORM_W, y, ROW_H, field):
        """Build one field row NSView and return (row_view, text_field_or_None)."""
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect

        ftype = field.get("type", "text")

        row = NSView.alloc().initWithFrame_(NSMakeRect(form_x, y, FORM_W, ROW_H))
        row.setWantsLayer_(True)
        row.layer().setCornerRadius_(10.0)
        row.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.04).CGColor())
        row.layer().setBorderWidth_(0.5)
        row.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
        doc.addSubview_(row)

        # Type dropdown button
        TYPE_W = 96.0
        type_btn = PillButton.alloc().initWithFrame_(NSMakeRect(10, (ROW_H - 26) / 2, TYPE_W, 26))
        type_btn.layer().setCornerRadius_(7.0)
        type_btn.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.1).CGColor())
        type_btn.layer().setBorderWidth_(0.5)
        type_btn.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.2).CGColor())
        type_lbl_str = {"text": "Text  ▾", "metadata": "Metadata  ▾", "opponent": "Opponent  ▾", "sport": "Sport  ▾"}.get(ftype, "Text  ▾")
        type_lbl = NSTextField.labelWithString_(type_lbl_str)
        type_lbl.setFont_(NSFont.systemFontOfSize_(12))
        type_lbl.setTextColor_(NSColor.labelColor())
        type_lbl.setFrame_(NSMakeRect(8, (26 - 16) / 2, TYPE_W - 14, 16))
        type_btn.addSubview_(type_lbl)
        row.addSubview_(type_btn)
        type_btn.setClickHandler_(
            lambda v, e, i=idx: self._convention_type_menu(v, e, i))

        # Control buttons (↑ ↓ ×) at the right edge
        CTRL_W  = 24.0
        CTRL_H  = 24.0
        CTRL_GAP = 4.0
        n_ctrls  = 3
        ctrl_x   = FORM_W - 10 - n_ctrls * CTRL_W - (n_ctrls - 1) * CTRL_GAP
        n_fields = len(self._convention_field_data)

        for ci, (sym, action, enabled) in enumerate([
            ("↑", lambda i=idx: self._convention_move_row(i, -1), idx > 0),
            ("↓", lambda i=idx: self._convention_move_row(i,  1), idx < n_fields - 1),
            ("×", lambda i=idx: self._convention_delete_row(i),   True),
        ]):
            bx    = ctrl_x + ci * (CTRL_W + CTRL_GAP)
            cbtn  = PillButton.alloc().initWithFrame_(NSMakeRect(bx, (ROW_H - CTRL_H) / 2, CTRL_W, CTRL_H))
            cbtn.layer().setCornerRadius_(5.0)
            cbtn.layer().setBackgroundColor_(
                _hex_color_alpha("#ffffff", 0.08 if enabled else 0.03).CGColor())
            clbl = NSTextField.labelWithString_(sym)
            clbl.setFont_(NSFont.systemFontOfSize_(12))
            clbl.setTextColor_(
                NSColor.labelColor() if enabled else NSColor.tertiaryLabelColor())
            clbl.setFrame_(NSMakeRect(0, (CTRL_H - 16) / 2, CTRL_W, 16))
            clbl.setAlignment_(1)  # center
            cbtn.addSubview_(clbl)
            row.addSubview_(cbtn)
            if enabled:
                cbtn.setClickHandler_(lambda v, e, a=action: a())

        # Value area — between type button and control buttons
        val_x = 10 + TYPE_W + 8
        val_w = ctrl_x - val_x - 8
        tf_ref = None

        if ftype == "text":
            tf_bg = NSView.alloc().initWithFrame_(NSMakeRect(val_x, (ROW_H - 28) / 2, val_w, 28))
            tf_bg.setWantsLayer_(True)
            tf_bg.layer().setCornerRadius_(6.0)
            tf_bg.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
            tf_bg.layer().setBorderWidth_(0.5)
            tf_bg.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.18).CGColor())
            row.addSubview_(tf_bg)

            tf = NSTextField.alloc().initWithFrame_(NSMakeRect(8, (28 - 18) / 2, val_w - 16, 18))
            tf.setStringValue_(field.get("value", ""))
            tf.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0))
            tf.setTextColor_(NSColor.labelColor())
            tf.setPlaceholderString_("Enter label text…")
            tf.setBezeled_(False)
            tf.setDrawsBackground_(False)
            tf.setEditable_(True)
            tf.setSelectable_(True)
            tf_bg.addSubview_(tf)
            tf_ref = tf

        elif ftype == "metadata":
            meta_fname = field.get("field", "date_created")
            meta_label = dict(METADATA_FIELDS).get(meta_fname, "Date Created")
            META_DD_W  = min(150.0, val_w * 0.45)

            meta_btn = PillButton.alloc().initWithFrame_(
                NSMakeRect(val_x, (ROW_H - 26) / 2, META_DD_W, 26))
            meta_btn.layer().setCornerRadius_(7.0)
            meta_btn.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
            meta_btn.layer().setBorderWidth_(0.5)
            meta_btn.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.18).CGColor())
            meta_lbl = NSTextField.labelWithString_(f"{meta_label}  ▾")
            meta_lbl.setFont_(NSFont.systemFontOfSize_(12))
            meta_lbl.setTextColor_(NSColor.labelColor())
            meta_lbl.setFrame_(NSMakeRect(8, (26 - 16) / 2, META_DD_W - 14, 16))
            meta_btn.addSubview_(meta_lbl)
            row.addSubview_(meta_btn)
            meta_btn.setClickHandler_(
                lambda v, e, i=idx: self._convention_meta_field_menu(v, e, i))

            fmt_x   = val_x + META_DD_W + 6
            fmt_w   = max(90.0, val_w - META_DD_W - 6)
            fmt_key = field.get("format", DATE_FORMATS[0][0] if meta_fname == "date_created" else TIME_FORMATS[0][0])

            fmt_btn = PillButton.alloc().initWithFrame_(
                NSMakeRect(fmt_x, (ROW_H - 26) / 2, fmt_w, 26))
            fmt_btn.layer().setCornerRadius_(7.0)
            fmt_btn.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
            fmt_btn.layer().setBorderWidth_(0.5)
            fmt_btn.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.18).CGColor())
            fmt_lbl = NSTextField.labelWithString_(f"{fmt_key}  ▾")
            fmt_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0))
            fmt_lbl.setTextColor_(NSColor.labelColor())
            fmt_lbl.setFrame_(NSMakeRect(8, (26 - 16) / 2, fmt_w - 14, 16))
            fmt_btn.addSubview_(fmt_lbl)
            row.addSubview_(fmt_btn)
            fmt_btn.setClickHandler_(
                lambda v, e, i=idx: self._convention_meta_format_menu(v, e, i))

        elif ftype == "sport":
            sport_key = self.app.session.get("sport", "MBB") if self.app else "MBB"
            spt_bg = NSView.alloc().initWithFrame_(
                NSMakeRect(val_x, (ROW_H - 28) / 2, val_w, 28))
            spt_bg.setWantsLayer_(True)
            spt_bg.layer().setCornerRadius_(6.0)
            spt_bg.layer().setBackgroundColor_(
                _hex_color_alpha("#1e3a5f", 0.55).CGColor())
            spt_bg.layer().setBorderWidth_(0.5)
            spt_bg.layer().setBorderColor_(
                _hex_color_alpha("#4a8ab5", 0.55).CGColor())
            row.addSubview_(spt_bg)
            spt_lbl = NSTextField.labelWithString_(sport_key)
            spt_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0.3))
            spt_lbl.setTextColor_(_hex_color("#7ab4e0"))
            spt_lbl.setAlignment_(1)
            spt_lbl.setFrame_(NSMakeRect(8, (28 - 18) / 2, val_w - 16, 18))
            spt_bg.addSubview_(spt_lbl)

        elif ftype == "opponent":
            opp_bg = NSView.alloc().initWithFrame_(
                NSMakeRect(val_x, (ROW_H - 28) / 2, val_w, 28))
            opp_bg.setWantsLayer_(True)
            opp_bg.layer().setCornerRadius_(6.0)
            opp_bg.layer().setBackgroundColor_(
                _hex_color_alpha(COLOR_CRIMSON, 0.18).CGColor())
            opp_bg.layer().setBorderWidth_(0.5)
            opp_bg.layer().setBorderColor_(
                _hex_color_alpha(COLOR_CRIMSON, 0.55).CGColor())
            row.addSubview_(opp_bg)
            tf = NSTextField.alloc().initWithFrame_(
                NSMakeRect(8, (28 - 18) / 2, val_w - 16, 18))
            tf.setStringValue_(field.get("value", ""))
            tf.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0))
            tf.setTextColor_(_hex_color(COLOR_TAN))
            tf.setPlaceholderString_("e.g. ND")
            tf.setBezeled_(False)
            tf.setDrawsBackground_(False)
            tf.setEditable_(True)
            tf.setSelectable_(True)
            opp_bg.addSubview_(tf)
            tf_ref = tf

        return row, tf_ref

    # ── Convention — preset management ────────────────────────────────────────

    def _convention_preset_menu(self, pill, event):
        from AppKit import NSMenu, NSMenuItem, NSPoint
        if not hasattr(self, "_convention_preset_mt"):
            self._convention_preset_mt = MenuTarget.alloc().init()

        def on_pick(idx):
            self._sync_convention_text_fields()
            self._convention_active_idx = idx
            preset = self._convention_presets[idx]
            self._convention_field_data = [dict(f) for f in preset.get("fields", [])]
            self._convention_tf_refs = []  # discard old refs so rebuild sync doesn't clobber new values
            if self.app:
                self.app.session["active_preset"] = idx
                save_json(CONFIG_FILE, self.app.session)
            self._rebuild_convention_rows()

        self._convention_preset_mt._callback = on_pick
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        for i, p in enumerate(self._convention_presets):
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                p.get("name", f"Preset {i+1}"), "menuPicked:", "")
            mi.setTarget_(self._convention_preset_mt)
            mi.setRepresentedObject_(i)
            if i == self._convention_active_idx:
                mi.setState_(1)
            menu.addItem_(mi)
        menu.popUpMenuPositioningItem_atLocation_inView_(None, NSPoint(0, 0), pill)

    def _convention_new_preset(self):
        from AppKit import NSAlert, NSTextField as NSTF
        alert = NSAlert.alloc().init()
        alert.setMessageText_("New Preset")
        alert.setInformativeText_("Enter a name for the new naming preset:")
        alert.addButtonWithTitle_("Create")
        alert.addButtonWithTitle_("Cancel")
        tf = NSTF.alloc().initWithFrame_(__import__("AppKit").NSMakeRect(0, 0, 260, 24))
        tf.setPlaceholderString_("e.g. Game Film")
        alert.setAccessoryView_(tf)
        alert.window().setInitialFirstResponder_(tf)
        if alert.runModal() != 1000:
            return
        name = tf.stringValue().strip() or "New Preset"
        new_preset = {"name": name, "separator": "_", "fields": []}
        insert_at  = self._convention_global_count
        self._convention_presets.insert(insert_at, new_preset)
        self._convention_global_count += 1
        new_idx = insert_at
        self._convention_active_idx = new_idx
        self._convention_field_data = []
        self._save_presets_to_config()
        self._rebuild_convention_rows()

    def _convention_duplicate_preset(self):
        import copy
        src = self._convention_presets[self._convention_active_idx]
        dup = copy.deepcopy(src)
        dup["name"] = src.get("name", "Preset") + " Copy"
        self._sync_convention_text_fields()
        src_idx    = self._convention_active_idx
        insert_at  = src_idx + 1
        self._convention_presets.insert(insert_at, dup)
        if src_idx < self._convention_global_count:
            self._convention_global_count += 1
        self._convention_active_idx = insert_at
        self._convention_field_data = [dict(f) for f in dup.get("fields", [])]
        self._save_presets_to_config()
        self._rebuild_convention_rows()

    def _convention_delete_preset(self):
        from AppKit import NSAlert
        if len(self._convention_presets) <= 1:
            a = NSAlert.alloc().init()
            a.setMessageText_("Cannot Delete")
            a.setInformativeText_("You must have at least one naming preset.")
            a.addButtonWithTitle_("OK")
            a.runModal()
            return
        name = self._convention_presets[self._convention_active_idx].get("name", "this preset")
        a = NSAlert.alloc().init()
        a.setMessageText_(f'Delete "{name}"?')
        a.setInformativeText_("This cannot be undone.")
        a.addButtonWithTitle_("Delete")
        a.addButtonWithTitle_("Cancel")
        if a.runModal() != 1000:
            return
        popped_idx = self._convention_active_idx
        self._convention_presets.pop(popped_idx)
        if popped_idx < self._convention_global_count:
            self._convention_global_count = max(1, self._convention_global_count - 1)
        self._convention_active_idx = max(0, popped_idx - 1)
        self._convention_field_data = [dict(f) for f in
                                       self._convention_presets[self._convention_active_idx].get("fields", [])]
        self._save_presets_to_config()
        self._rebuild_convention_rows()

    def _save_presets_to_config(self):
        if not self.app:
            return
        n = self._convention_global_count
        global_presets     = self._convention_presets[:n]
        sport_presets_list = self._convention_presets[n:]
        sport_key = self.app.session.get("sport", "")
        self.app.session["naming_presets"] = global_presets
        sp = self.app.session.get("sport_presets", {})
        if sport_key:
            sp[sport_key] = sport_presets_list
        self.app.session["sport_presets"]  = sp
        self.app.session["active_preset"]  = self._convention_active_idx
        save_json(CONFIG_FILE, self.app.session)

    # ── Convention — field interaction ────────────────────────────────────────

    def _convention_type_menu(self, pill, event, idx):
        from AppKit import NSMenu, NSMenuItem, NSPoint
        if not hasattr(self, "_convention_type_mt"):
            self._convention_type_mt = MenuTarget.alloc().init()

        def on_pick(ftype):
            self._sync_convention_text_fields()
            if ftype == "text":
                new_field = {"type": "text", "value": ""}
            elif ftype == "metadata":
                new_field = {"type": "metadata", "value": "",
                             "field": "date_created", "format": DATE_FORMATS[0][0]}
            elif ftype == "sport":
                new_field = {"type": "sport", "value": ""}
            else:
                new_field = {"type": "opponent", "value": ""}
            self._convention_field_data[idx] = new_field
            self._rebuild_convention_rows(scroll_to="preserve")

        self._convention_type_mt._callback = on_pick
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        current = self._convention_field_data[idx].get("type", "text")
        for label, key in [("Text", "text"), ("Metadata", "metadata"), ("Sport", "sport"), ("Opponent", "opponent")]:
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, "menuPicked:", "")
            mi.setTarget_(self._convention_type_mt)
            mi.setRepresentedObject_(key)
            if key == current:
                mi.setState_(1)
            menu.addItem_(mi)
        menu.popUpMenuPositioningItem_atLocation_inView_(None, NSPoint(0, 0), pill)

    def _convention_meta_field_menu(self, pill, event, idx):
        from AppKit import NSMenu, NSMenuItem, NSPoint
        if not hasattr(self, "_convention_mf_mt"):
            self._convention_mf_mt = MenuTarget.alloc().init()

        def on_pick(fname):
            self._convention_field_data[idx]["field"]  = fname
            default_fmt = (DATE_FORMATS[0][0] if fname == "date_created" else TIME_FORMATS[0][0])
            self._convention_field_data[idx]["format"] = default_fmt
            self._rebuild_convention_rows(scroll_to="preserve")

        self._convention_mf_mt._callback = on_pick
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        current = self._convention_field_data[idx].get("field", "date_created")
        for fname, flabel in METADATA_FIELDS:
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(flabel, "menuPicked:", "")
            mi.setTarget_(self._convention_mf_mt)
            mi.setRepresentedObject_(fname)
            if fname == current:
                mi.setState_(1)
            menu.addItem_(mi)
        menu.popUpMenuPositioningItem_atLocation_inView_(None, NSPoint(0, 0), pill)

    def _convention_meta_format_menu(self, pill, event, idx):
        from AppKit import NSMenu, NSMenuItem, NSPoint
        if not hasattr(self, "_convention_fmt_mt"):
            self._convention_fmt_mt = MenuTarget.alloc().init()

        def on_pick(fmt_key):
            self._convention_field_data[idx]["format"] = fmt_key
            self._rebuild_convention_rows(scroll_to="preserve")

        self._convention_fmt_mt._callback = on_pick
        fname   = self._convention_field_data[idx].get("field", "date_created")
        options = DATE_FORMATS if fname == "date_created" else TIME_FORMATS
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        current = self._convention_field_data[idx].get("format", options[0][0])
        for fmt_key, _ in options:
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(fmt_key, "menuPicked:", "")
            mi.setTarget_(self._convention_fmt_mt)
            mi.setRepresentedObject_(fmt_key)
            if fmt_key == current:
                mi.setState_(1)
            menu.addItem_(mi)
        menu.popUpMenuPositioningItem_atLocation_inView_(None, NSPoint(0, 0), pill)

    def _convention_move_row(self, idx, direction):
        self._sync_convention_text_fields()
        new_idx = idx + direction
        if 0 <= new_idx < len(self._convention_field_data):
            data = self._convention_field_data
            data[idx], data[new_idx] = data[new_idx], data[idx]
            self._rebuild_convention_rows(scroll_to="preserve")

    def _convention_delete_row(self, idx):
        self._sync_convention_text_fields()
        if 0 <= idx < len(self._convention_field_data):
            self._convention_field_data.pop(idx)
            self._rebuild_convention_rows(scroll_to="preserve")

    def _convention_add_field(self):
        self._sync_convention_text_fields()
        self._convention_field_data.append({"type": "text", "value": ""})
        self._rebuild_convention_rows(scroll_to="bottom")

    # ── Convention — save & preview ───────────────────────────────────────────

    def _convention_update_preview(self):
        """Refresh the preview label from current in-memory field data."""
        if not hasattr(self, "_convention_preview_lbl"):
            return
        self._sync_convention_text_fields()
        sep   = ""
        if hasattr(self, "_convention_sep_tf"):
            sep = self._convention_sep_tf.stringValue()
        if not sep:
            sep = "_"
        preset = {
            "separator": sep,
            "fields":    self._convention_field_data,
        }
        session = self.app.session if self.app else None
        stem = resolve_convention(preset, session=session)
        ext  = ".mp4"
        self._convention_preview_lbl.setStringValue_(
            (stem + ext) if stem else "— (no fields defined) —")

    def _convention_save(self):
        from AppKit import NSAlert
        self._sync_convention_text_fields()

        # Validate: highlight empty text rows
        errors = []
        for idx, f in enumerate(self._convention_field_data):
            if f.get("type") == "text" and not f.get("value", "").strip():
                errors.append(idx)

        if errors:
            # Highlight offending rows with a red border
            for idx in errors:
                if idx < len(self._convention_field_views):
                    v = self._convention_field_views[idx]
                    v.layer().setBorderColor_(
                        _hex_color_alpha("#ff3b30", 0.8).CGColor())
                    v.layer().setBorderWidth_(1.5)
            a = NSAlert.alloc().init()
            a.setMessageText_("Empty Text Field")
            a.setInformativeText_(
                f"{len(errors)} field(s) have no text entered. "
                "Please fill them in or delete them before saving.")
            a.addButtonWithTitle_("OK")
            a.runModal()
            return

        sep = self._convention_sep_tf.stringValue() if hasattr(self, "_convention_sep_tf") else "_"
        if not sep:
            sep = "_"

        preset = self._convention_presets[self._convention_active_idx]
        preset["separator"] = sep
        preset["fields"]    = [dict(f) for f in self._convention_field_data]

        self._save_presets_to_config()
        self._convention_update_preview()

        a = NSAlert.alloc().init()
        a.setMessageText_("Convention Saved")
        a.setInformativeText_(
            f"Preset \"{preset['name']}\" saved with {len(preset['fields'])} field(s).\n"
            f"Batch rename will now use this convention.")
        a.addButtonWithTitle_("OK")
        a.runModal()

    # ── Schedule import ───────────────────────────────────────────────────────

    def _import_schedule_opponents(self):
        import threading
        from AppKit import NSAlert

        has_opp_field = any(
            f.get("type") == "opponent" for f in self._convention_field_data)
        if not has_opp_field:
            a = NSAlert.alloc().init()
            a.setMessageText_("No Opponent Field")
            a.setInformativeText_(
                "Add an Opponent field to your preset first using the field "
                "type dropdown, then click Import Schedule.")
            a.addButtonWithTitle_("OK")
            a.runModal()
            return

        sport_key = self.app.session.get("sport", "") if self.app else ""
        base_url  = load_json(SETTINGS_FILE, {}).get("roster_base_url", "").strip()
        if not base_url:
            a = NSAlert.alloc().init()
            a.setMessageText_("No School URL")
            a.setInformativeText_(
                "Set your school's website URL in the Team section first.")
            a.addButtonWithTitle_("OK")
            a.runModal()
            return

        if hasattr(self, "_import_schedule_btn"):
            self._import_schedule_btn.configureTitle_bg_press_action_(
                "Fetching…", "#2c2c2e", "#2c2c2e", lambda: None)
        if hasattr(self, "_import_schedule_status"):
            self._import_schedule_status.setStringValue_("Fetching schedule…")

        caller = MainCaller.alloc().init()

        def _bg():
            opponents = scrape_schedule(sport_key, base_url)
            caller._cb = lambda: self._on_import_schedule_done(opponents)
            caller.performSelectorOnMainThread_withObject_waitUntilDone_(
                "fire:", None, False)

        threading.Thread(target=_bg, daemon=True).start()

    def _on_import_schedule_done(self, opponents):
        from AppKit import NSAlert

        if hasattr(self, "_import_schedule_btn"):
            self._import_schedule_btn.configureTitle_bg_press_action_(
                "⚡ Import Schedule", "#3a3a3c", "#2c2c2e",
                self._import_schedule_opponents)

        if not opponents:
            if hasattr(self, "_import_schedule_status"):
                self._import_schedule_status.setStringValue_(
                    "No opponents found — check sport and school URL")
            return

        self._sync_convention_text_fields()
        sep = self._convention_sep_tf.stringValue() if hasattr(
            self, "_convention_sep_tf") else "_"
        if not sep:
            sep = "_"

        template_fields = [dict(f) for f in self._convention_field_data]
        sport_key = self.app.session.get("sport", "") if self.app else ""
        sp = self.app.session.get("sport_presets", {}) if self.app else {}
        # skip names that exist in global presets (user-created templates)
        existing_names = {p.get("name", "") for p in self._convention_presets[:self._convention_global_count]}
        created = skipped = 0
        new_sport_presets = []  # replace old schedule entirely

        for opp_name in opponents:
            abbr  = abbrev_for_opponent(opp_name)
            pname = f"vs {opp_name.upper()}"
            if pname in existing_names:
                skipped += 1
                continue
            new_fields = []
            for f in template_fields:
                nf = dict(f)
                if nf.get("type") == "opponent":
                    nf["value"] = abbr
                new_fields.append(nf)
            new_sport_presets.append({"name": pname, "separator": sep, "fields": new_fields})
            existing_names.add(pname)
            created += 1

        if self.app:
            sp[sport_key] = new_sport_presets
            self.app.session["sport_presets"] = sp
            save_json(CONFIG_FILE, self.app.session)

        parts = [f"Imported {created} opponent(s)"]
        if skipped:
            parts.append(f"skipped {skipped} (in global presets)")
        status = ", ".join(parts)
        if hasattr(self, "_import_schedule_status"):
            self._import_schedule_status.setStringValue_(status)

        self._refresh_convention_for_sport()

        # Auto-select the sport preset matching the current session opponent so
        # that batch rename immediately uses the correct abbreviation without
        # requiring the user to manually pick from the dropdown.
        if self.app and created > 0:
            session_opp = self.app.session.get("opponent", "").strip().upper()
            for i, p in enumerate(self._convention_presets):
                pname = p.get("name", "").strip().upper()
                if session_opp and pname == f"VS {session_opp}":
                    self._convention_active_idx = i
                    self._convention_field_data = [dict(f) for f in p.get("fields", [])]
                    self.app.session["active_preset"] = i
                    save_json(CONFIG_FILE, self.app.session)
                    self._rebuild_convention_rows()
                    break

    # ── Stats section ─────────────────────────────────────────────────────────

    def _build_stats_section(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import NSView, NSScrollView, NSTextField, NSFont, NSMakeRect
        cx = float(SIDEBAR_W)
        cw = float(W - SIDEBAR_W)
        ch = float(H - TOP_H)

        sec = NSView.alloc().initWithFrame_(NSMakeRect(cx, 0, cw, ch))
        sec.setWantsLayer_(True)
        sec.setAutoresizingMask_(2 | 16)
        sec.setHidden_(True)
        cv.addSubview_(sec)
        self._stats_section = sec

        # Sub-nav tab bar: sport label (left), two ActionButtons (center), reset (right)
        TAB_W   = 110.0
        TAB_H   = 28.0
        TAB_GAP = 4.0
        TAB_Y   = ch - TOP_H + (TOP_H - TAB_H) / 2
        total_w = TAB_W * 2 + TAB_GAP
        TAB_X   = (cw - total_w) / 2

        # Sport label — left-anchored (autoresizingMask 8 = flex right margin)
        sport_key   = self.app.session.get("sport", "MBB") if self.app else "MBB"
        sport_label = SPORTS.get(sport_key, SPORTS["MBB"])["label"].strip()
        sport_lbl = NSTextField.labelWithString_(sport_label)
        sport_lbl.setFont_(NSFont.boldSystemFontOfSize_(12))
        sport_lbl.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.75))
        sport_lbl.setFrame_(NSMakeRect(16, TAB_Y, 200, TAB_H))
        sport_lbl.setAutoresizingMask_(8)
        sec.addSubview_(sport_lbl)
        self._stats_sport_lbl = sport_lbl

        btn_ov = ActionButton.alloc().initWithFrame_(NSMakeRect(TAB_X, TAB_Y, TAB_W, TAB_H))
        btn_ov.configureTitle_bg_press_action_(
            "Overview", COLOR_CRIMSON, "#6b1a26", lambda: self._switch_stats_tab(0))
        btn_ov.setAutoresizingMask_(1 | 4 | 8)
        sec.addSubview_(btn_ov)
        self._stats_btn_ov = btn_ov

        btn_pl = ActionButton.alloc().initWithFrame_(NSMakeRect(TAB_X + TAB_W + TAB_GAP, TAB_Y, TAB_W, TAB_H))
        btn_pl.configureTitle_bg_press_action_(
            "Players", "#3a3a3c", "#2c2c2e", lambda: self._switch_stats_tab(1))
        btn_pl.setAutoresizingMask_(1 | 4 | 8)
        sec.addSubview_(btn_pl)
        self._stats_btn_pl = btn_pl

        # Export CSV + Reset buttons — right-anchored
        RESET_W   = 90.0
        EXPORT_W  = 90.0
        BTN_GAP   = 6.0
        RESET_PAD = 16.0
        btn_export = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - RESET_PAD - EXPORT_W - BTN_GAP - RESET_W, TAB_Y, EXPORT_W, TAB_H))
        btn_export.configureTitle_bg_press_action_(
            "Export CSV", "#3a3a3c", "#2c2c2e", self._export_stats_csv)
        btn_export.setAutoresizingMask_(1 | 8)
        sec.addSubview_(btn_export)
        self._stats_btn_export = btn_export

        btn_reset = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - RESET_PAD - RESET_W, TAB_Y, RESET_W, TAB_H))
        btn_reset.configureTitle_bg_press_action_(
            "Reset Stats", "#6b1a26", "#4a1018", self._reset_stats)
        btn_reset.setAutoresizingMask_(1 | 8)
        sec.addSubview_(btn_reset)
        self._stats_btn_reset = btn_reset

        self._stats_active_tab = 0

        CONTENT_H = ch - TOP_H
        # Overview panel
        ov = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, CONTENT_H))
        ov.setWantsLayer_(True)
        ov.setAutoresizingMask_(2 | 16)
        sec.addSubview_(ov)
        self._stats_overview_panel = ov

        # Players panel (scrollable)
        sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, CONTENT_H))
        sv.setHasVerticalScroller_(True)
        sv.setAutohidesScrollers_(True)
        sv.setBorderType_(0)
        sv.setDrawsBackground_(False)
        sv.setAutoresizingMask_(2 | 16)
        sv.setHidden_(True)
        sec.addSubview_(sv)
        self._stats_players_sv = sv

        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, 0))
        sv.setDocumentView_(container)
        self._stats_players_container = container

        self._stats_expanded_player = None
        self._stats_row_targets = []

    def _switch_stats_tab(self, idx):
        self._stats_active_tab = idx
        # Update button colours to reflect active tab
        if idx == 0:
            self._stats_btn_ov.configureTitle_bg_press_action_(
                "Overview", COLOR_CRIMSON, "#6b1a26", lambda: self._switch_stats_tab(0))
            self._stats_btn_pl.configureTitle_bg_press_action_(
                "Players", "#3a3a3c", "#2c2c2e", lambda: self._switch_stats_tab(1))
        else:
            self._stats_btn_ov.configureTitle_bg_press_action_(
                "Overview", "#3a3a3c", "#2c2c2e", lambda: self._switch_stats_tab(0))
            self._stats_btn_pl.configureTitle_bg_press_action_(
                "Players", COLOR_CRIMSON, "#6b1a26", lambda: self._switch_stats_tab(1))
        self._stats_overview_panel.setHidden_(idx != 0)
        self._stats_players_sv.setHidden_(idx != 1)
        if idx == 0:
            self._refresh_stats_overview()
        else:
            self._refresh_stats_players()

    def _refresh_stats(self):
        if hasattr(self, "_stats_sport_lbl") and self.app:
            sport_key   = self.app.session.get("sport", "MBB")
            sport_label = SPORTS.get(sport_key, SPORTS["MBB"])["label"].strip()
            self._stats_sport_lbl.setStringValue_(sport_label)
        idx = getattr(self, "_stats_active_tab", 0)
        if idx == 0:
            self._refresh_stats_overview()
        else:
            self._refresh_stats_players()

    def _refresh_stats_overview(self):
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect
        panel = self._stats_overview_panel
        for v in list(panel.subviews()):
            v.removeFromSuperview()

        sport_key = self.app.session.get("sport", "MBB") if self.app else "MBB"
        all_data  = load_json(STATS_FILE, [])
        scope     = self._settings.get("stats_scope", "all_time")
        today_str = datetime.now().strftime("%Y-%m-%d")
        sess_ts   = self.app._session_start_ts if self.app and hasattr(self.app, "_session_start_ts") else ""
        all_data  = [e for e in all_data if e.get("sport") == sport_key]
        if scope == "today":
            all_data = [e for e in all_data if e.get("date") == today_str]
        elif scope == "session":
            all_data = [e for e in all_data if e.get("ts", "") >= sess_ts]
        data      = all_data
        stats     = compute_stats(data)
        cw     = panel.frame().size.width or (self.win.frame().size.width - self._SIDEBAR_W)
        ch     = panel.frame().size.height
        PAD    = 32.0

        # Stat tiles
        TILE_H = 88.0
        TILE_W = (cw - PAD * 2 - 24) / 3
        tile_y = ch - PAD - TILE_H
        tiles = [
            (stats["total_clips"],    "Total Clips"),
            (stats["total_sessions"], "Sessions"),
            (len(stats["per_player"]), "Players Logged"),
        ]
        for i, (val, lbl) in enumerate(tiles):
            self._stats_tile(panel, PAD + i * (TILE_W + 12), tile_y, TILE_W, TILE_H, val, lbl)

        # Leaderboard columns
        sections = [
            ("Top Players",  sorted(stats["players"].items(),  key=lambda x: -x[1])),
            ("Top Plays",    sorted(stats["plays"].items(),    key=lambda x: -x[1])),
            ("Top Ratings",  sorted(stats["ratings"].items(),  key=lambda x: -x[1])),
        ]
        total_clips = max(stats["total_clips"], 1)
        ROW_H  = 36.0
        HDR_H  = 28.0
        GAP    = 20.0
        col_w  = (cw - PAD * 2 - GAP * 2) / 3
        col_xs = [PAD + i * (col_w + GAP) for i in range(3)]
        start_y = tile_y - 24

        for col_i, (header, rows) in enumerate(sections):
            cx2 = col_xs[col_i]
            y   = start_y
            hdr = NSTextField.labelWithString_(header.upper())
            hdr.setFont_(NSFont.boldSystemFontOfSize_(11))
            hdr.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.5))
            hdr.setFrame_(NSMakeRect(cx2, y - HDR_H, col_w, 16))
            panel.addSubview_(hdr)
            y -= HDR_H + 4
            sep = NSView.alloc().initWithFrame_(NSMakeRect(cx2, y - 1, col_w, 1))
            sep.setWantsLayer_(True)
            sep.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
            panel.addSubview_(sep)
            y -= 8
            if not rows:
                no_data = NSTextField.labelWithString_("No data yet")
                no_data.setFont_(NSFont.systemFontOfSize_(12))
                no_data.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.4))
                no_data.setFrame_(NSMakeRect(cx2, y - ROW_H, col_w, ROW_H))
                panel.addSubview_(no_data)
            else:
                for rank_i, (name, count) in enumerate(rows[:8]):
                    self._stats_leaderboard_row(panel, cx2, y - ROW_H, col_w,
                                                f"#{rank_i+1}", name, count, total_clips)
                    y -= ROW_H + 2

    def _stats_tile(self, parent, x, y, w, h, value, label):
        from AppKit import NSView, NSTextField, NSFont, NSMakeRect
        tile = NSView.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
        tile.setWantsLayer_(True)
        tile.layer().setCornerRadius_(12.0)
        tile.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.05).CGColor())
        tile.layer().setBorderWidth_(0.5)
        tile.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.10).CGColor())
        val_lbl = NSTextField.labelWithString_(str(value))
        val_lbl.setFont_(NSFont.boldSystemFontOfSize_(28))
        val_lbl.setTextColor_(_hex_color(COLOR_TAN))
        val_lbl.setAlignment_(1)
        val_lbl.setFrame_(NSMakeRect(8, h - 44, w - 16, 36))
        tile.addSubview_(val_lbl)
        lbl_view = NSTextField.labelWithString_(label)
        lbl_view.setFont_(NSFont.systemFontOfSize_(11))
        lbl_view.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.5))
        lbl_view.setAlignment_(1)
        lbl_view.setFrame_(NSMakeRect(8, 8, w - 16, 16))
        tile.addSubview_(lbl_view)
        parent.addSubview_(tile)

    def _stats_leaderboard_row(self, parent, x, y, w, rank_label, name, count, total):
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect
        ROW_H = 36.0
        row = NSView.alloc().initWithFrame_(NSMakeRect(x, y, w, ROW_H))
        rank = NSTextField.labelWithString_(rank_label)
        rank.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0.5))
        rank.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.5))
        rank.setFrame_(NSMakeRect(0, (ROW_H - 16) / 2, 28, 16))
        row.addSubview_(rank)
        name_lbl = NSTextField.labelWithString_(name or "—")
        name_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(13, 0.4))
        name_lbl.setTextColor_(_hex_color(COLOR_TAN))
        name_lbl.setFrame_(NSMakeRect(32, (ROW_H - 17) / 2, 160, 17))
        name_lbl.setLineBreakMode_(4)
        row.addSubview_(name_lbl)
        BAR_X = 200.0
        BAR_W = w - BAR_X - 52
        pct   = (count / total) if total > 0 else 0
        bar_bg = NSView.alloc().initWithFrame_(NSMakeRect(BAR_X, (ROW_H - 6) / 2, BAR_W, 6))
        bar_bg.setWantsLayer_(True)
        bar_bg.layer().setCornerRadius_(3.0)
        bar_bg.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.10).CGColor())
        row.addSubview_(bar_bg)
        fill_w = max(4.0, BAR_W * pct)
        bar_fill = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, fill_w, 6))
        bar_fill.setWantsLayer_(True)
        bar_fill.layer().setCornerRadius_(3.0)
        bar_fill.layer().setBackgroundColor_(_hex_color(COLOR_CRIMSON).CGColor())
        bar_bg.addSubview_(bar_fill)
        count_lbl = NSTextField.labelWithString_(str(count))
        count_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0.4))
        count_lbl.setTextColor_(NSColor.secondaryLabelColor())
        count_lbl.setFrame_(NSMakeRect(w - 48, (ROW_H - 16) / 2, 48, 16))
        count_lbl.setAlignment_(2)
        row.addSubview_(count_lbl)
        parent.addSubview_(row)

    def _refresh_stats_players(self):
        from AppKit import NSView, NSTextField, NSFont, NSColor, NSMakeRect, NSButton
        container = self._stats_players_container
        for v in list(container.subviews()):
            v.removeFromSuperview()
        self._stats_row_targets = []

        sport_key = self.app.session.get("sport", "MBB") if self.app else "MBB"
        all_data  = load_json(STATS_FILE, [])
        scope     = self._settings.get("stats_scope", "all_time")
        today_str = datetime.now().strftime("%Y-%m-%d")
        sess_ts   = self.app._session_start_ts if self.app and hasattr(self.app, "_session_start_ts") else ""
        all_data  = [e for e in all_data if e.get("sport") == sport_key]
        if scope == "today":
            all_data = [e for e in all_data if e.get("date") == today_str]
        elif scope == "session":
            all_data = [e for e in all_data if e.get("ts", "") >= sess_ts]
        data      = all_data
        stats     = compute_stats(data)
        players = sorted(stats["players"].items(), key=lambda x: -x[1])
        total   = max(stats["total_clips"], 1)
        per     = stats["per_player"]

        sv  = self._stats_players_sv
        cw  = sv.frame().size.width or (self.win.frame().size.width - self._SIDEBAR_W)
        PAD = 32.0
        GAP = 8.0
        ROW_H    = 48.0
        DETAIL_H = 120.0

        def row_h(name):
            return ROW_H + (DETAIL_H + GAP if name == self._stats_expanded_player else 0)

        total_h    = PAD + sum(row_h(n) + GAP for n, _ in players) + PAD
        viewport_h = sv.frame().size.height
        container_h = max(total_h, viewport_h)
        container.setFrame_(NSMakeRect(0, 0, cw, container_h))

        y = container_h - PAD
        for name, count in players:
            rh       = row_h(name)
            y       -= rh
            expanded = (name == self._stats_expanded_player)

            full_h  = ROW_H + (DETAIL_H + 8 if expanded else 0)
            wrapper = NSView.alloc().initWithFrame_(NSMakeRect(PAD, y, cw - PAD * 2, full_h))
            wrapper.setWantsLayer_(True)

            row = NSView.alloc().initWithFrame_(NSMakeRect(0, full_h - ROW_H, cw - PAD * 2, ROW_H))
            row.setWantsLayer_(True)
            row.layer().setCornerRadius_(10.0)
            row.layer().setBackgroundColor_(
                _hex_color_alpha(COLOR_CRIMSON, 0.25).CGColor() if expanded
                else _hex_color_alpha("#ffffff", 0.05).CGColor())
            row.layer().setBorderWidth_(0.5)
            row.layer().setBorderColor_(
                _hex_color_alpha(COLOR_CRIMSON, 0.5).CGColor() if expanded
                else _hex_color_alpha("#ffffff", 0.10).CGColor())

            name_lbl = NSTextField.labelWithString_(name)
            name_lbl.setFont_(NSFont.boldSystemFontOfSize_(14))
            name_lbl.setTextColor_(_hex_color(COLOR_TAN))
            name_lbl.setFrame_(NSMakeRect(16, (ROW_H - 18) / 2, 180, 18))
            name_lbl.setLineBreakMode_(4)
            row.addSubview_(name_lbl)

            pw       = cw - PAD * 2
            BAR_X    = 204.0
            BAR_W    = pw - BAR_X - 80
            pct      = count / total
            bar_bg   = NSView.alloc().initWithFrame_(NSMakeRect(BAR_X, (ROW_H - 6) / 2, BAR_W, 6))
            bar_bg.setWantsLayer_(True)
            bar_bg.layer().setCornerRadius_(3.0)
            bar_bg.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.10).CGColor())
            row.addSubview_(bar_bg)
            fill_w   = max(4.0, BAR_W * pct)
            bar_fill = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, fill_w, 6))
            bar_fill.setWantsLayer_(True)
            bar_fill.layer().setCornerRadius_(3.0)
            bar_fill.layer().setBackgroundColor_(_hex_color(COLOR_CRIMSON).CGColor())
            bar_bg.addSubview_(bar_fill)

            chevron   = "▾" if expanded else "▸"
            count_lbl = NSTextField.labelWithString_(f"{count}  {chevron}")
            count_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(13, 0.4))
            count_lbl.setTextColor_(NSColor.secondaryLabelColor())
            count_lbl.setFrame_(NSMakeRect(pw - 72, (ROW_H - 16) / 2, 68, 16))
            count_lbl.setAlignment_(2)
            row.addSubview_(count_lbl)

            t = MenuTarget.alloc().init()
            t._callback = lambda _, n=name: self._toggle_stats_player(n)
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, pw, ROW_H))
            btn.setBordered_(False)
            btn.setTitle_("")
            btn.setTarget_(t)
            btn.setAction_("menuPicked:")
            row.addSubview_(btn)
            self._stats_row_targets.append(t)

            wrapper.addSubview_(row)

            if expanded:
                pdata   = per.get(name, {})
                detail  = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, DETAIL_H))
                detail.setWantsLayer_(True)
                detail.layer().setCornerRadius_(10.0)
                detail.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.03).CGColor())
                detail.layer().setBorderWidth_(0.5)
                detail.layer().setBorderColor_(_hex_color_alpha(COLOR_CRIMSON, 0.3).CGColor())
                p_total  = max(pdata.get("total", 1), 1)
                col_w    = (pw - 48) / 2
                self._stats_detail_col(detail, 16,          8, col_w, DETAIL_H - 16,
                                       "Plays",   pdata.get("plays", {}),   p_total)
                self._stats_detail_col(detail, 24 + col_w,  8, col_w, DETAIL_H - 16,
                                       "Ratings", pdata.get("ratings", {}), p_total)
                wrapper.addSubview_(detail)

            container.addSubview_(wrapper)
            y -= GAP

        sv.contentView().scrollToPoint_((0, max(0.0, container_h - viewport_h)))
        sv.reflectScrolledClipView_(sv.contentView())

        if not players:
            empty = NSTextField.labelWithString_("No clips tagged yet.")
            empty.setFont_(NSFont.systemFontOfSize_(14))
            empty.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.4))
            empty.setAlignment_(1)
            empty.setFrame_(NSMakeRect(0, (container_h - 22) / 2, cw, 22))
            container.addSubview_(empty)

    def _stats_detail_col(self, parent, x, y, w, h, title, data, total):
        from AppKit import NSTextField, NSFont, NSMakeRect
        hdr = NSTextField.labelWithString_(title.upper())
        hdr.setFont_(NSFont.boldSystemFontOfSize_(10))
        hdr.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.5))
        hdr.setFrame_(NSMakeRect(x, y + h - 18, w, 14))
        parent.addSubview_(hdr)
        row_y = y + h - 36
        for item_name, item_count in sorted(data.items(), key=lambda kv: -kv[1])[:5]:
            pct = item_count / total if total > 0 else 0
            row = NSTextField.labelWithString_(
                f"{item_name:<14}  {item_count:>3}  ({pct*100:.0f}%)")
            row.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.0))
            row.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.85))
            row.setFrame_(NSMakeRect(x, row_y, w, 15))
            parent.addSubview_(row)
            row_y -= 18

    def _toggle_stats_player(self, name):
        self._stats_expanded_player = None if self._stats_expanded_player == name else name
        self._refresh_stats_players()

    def _reset_stats(self):
        from AppKit import NSAlert
        sport_key   = self.app.session.get("sport", "MBB") if self.app else "MBB"
        sport_label = SPORTS.get(sport_key, SPORTS["MBB"])["label"].strip()
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"Reset {sport_label} stats?")
        alert.setInformativeText_(
            "This will permanently delete all logged clips for this sport. "
            "Stats for other sports will not be affected. This cannot be undone.")
        alert.addButtonWithTitle_("Reset")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() == 1000:  # NSAlertFirstButtonReturn
            all_data = load_json(STATS_FILE, [])
            save_json(STATS_FILE, [e for e in all_data if e.get("sport") != sport_key])
            self._refresh_stats()

    def _export_stats_csv(self):
        import csv, io
        sport_key   = self.app.session.get("sport", "MBB") if self.app else "MBB"
        folder      = self.app.session.get("folder", "") if self.app else ""
        all_data    = load_json(STATS_FILE, [])
        data        = [e for e in all_data if e.get("sport") == sport_key]
        if not data:
            rumps.alert("No Stats", "No stats recorded for this sport yet.")
            return
        ts_str   = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(os.path.expanduser("~/Desktop"),
                                f"ez_logger_stats_{sport_key}_{ts_str}.csv")
        try:
            fieldnames = ["ts", "date", "sport", "opponent", "phase", "player", "play", "rating"]
            with open(out_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                w.writeheader()
                w.writerows(data)
            rumps.alert("✅ Exported", f"Saved {len(data)} rows to:\n{out_path}")
        except Exception as e:
            rumps.alert("Export Failed", str(e))

    # ── Settings section ──────────────────────────────────────────────────────

    def _build_settings_section(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSScrollView, NSTextField, NSFont, NSColor, NSMakeRect,
        )

        cx = float(SIDEBAR_W)
        cw = float(W - SIDEBAR_W)
        ch = float(H - TOP_H)

        section = NSView.alloc().initWithFrame_(NSMakeRect(cx, 0, cw, ch))
        section.setWantsLayer_(True)
        section.setAutoresizingMask_(2 | 16)
        section.setHidden_(True)
        cv.addSubview_(section)
        self._settings_section = section
        self._settings_btns    = {}
        self._settings_mts     = []  # keep MenuTarget refs alive

        # ── Header ──────────────────────────────────────────────────────────
        HEADER_H = 64.0
        header_y = ch - HEADER_H

        title_lbl = NSTextField.labelWithString_("Settings")
        title_lbl.setFont_(NSFont.boldSystemFontOfSize_(22))
        title_lbl.setTextColor_(NSColor.labelColor())
        title_lbl.sizeToFit()
        tf = title_lbl.frame()
        title_lbl.setFrame_(NSMakeRect(
            32, header_y + (HEADER_H - tf.size.height) / 2,
            tf.size.width, tf.size.height))
        title_lbl.setAutoresizingMask_(8)
        section.addSubview_(title_lbl)

        div = NSView.alloc().initWithFrame_(NSMakeRect(32, header_y - 1, cw - 64, 1))
        div.setWantsLayer_(True)
        div.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
        div.setAutoresizingMask_(2 | 8)
        section.addSubview_(div)

        # ── Scrollable body ─────────────────────────────────────────────────
        SCROLL_H = header_y
        sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, SCROLL_H))
        sv.setHasVerticalScroller_(True)
        sv.setHasHorizontalScroller_(False)
        sv.setAutohidesScrollers_(True)
        sv.setDrawsBackground_(False)
        sv.setAutoresizingMask_(2 | 4 | 8 | 16)
        section.addSubview_(sv)

        EDGE    = 32.0
        ROW_H   = 52.0
        ROW_GAP = 8.0
        HDR_H   = 22.0
        SGAP    = 20.0
        TOP_PAD = 20.0
        BTM_PAD = 28.0
        BTN_H   = 30.0
        TOG_W   = 60.0
        DD_W    = 140.0
        NUM_W   = 110.0

        # Calculate total content height.
        # Each make_* helper subtracts ROW_H + ROW_GAP (including the last row), so budget n gaps per group.
        rows_per_group = [5, 3, 2, 2, 2, 4, 1]  # Log, Rename, Display, Stats, Roster, System, Undo
        total_h = TOP_PAD + BTM_PAD
        for n in rows_per_group:
            total_h += HDR_H + 8 + n * ROW_H + n * ROW_GAP
        total_h += (len(rows_per_group) - 1) * SGAP
        doc_h = max(total_h, SCROLL_H)

        doc = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, doc_h))
        sv.setDocumentView_(doc)
        self._settings_doc = doc

        row_w = cw - EDGE * 2
        _y = [doc_h - TOP_PAD]

        def make_header(title_text):
            y = _y[0] - HDR_H
            lbl = NSTextField.labelWithString_(title_text.upper())
            lbl.setFont_(NSFont.boldSystemFontOfSize_(10))
            lbl.setTextColor_(NSColor.tertiaryLabelColor())
            lbl.setFrame_(NSMakeRect(EDGE, y, row_w, HDR_H))
            lbl.setAutoresizingMask_(2)
            doc.addSubview_(lbl)
            _y[0] = y - 8

        def _row_bg(y):
            bg = NSView.alloc().initWithFrame_(NSMakeRect(EDGE, y, row_w, ROW_H))
            bg.setWantsLayer_(True)
            bg.layer().setCornerRadius_(10.0)
            bg.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.04).CGColor())
            bg.setAutoresizingMask_(2)
            doc.addSubview_(bg)
            return bg

        def _row_labels(bg, title_text, sub_text, ctl_w):
            lw = row_w - 16 - ctl_w - 16 - 12
            t = NSTextField.labelWithString_(title_text)
            t.setFont_(NSFont.systemFontOfSize_(13))
            t.setTextColor_(NSColor.labelColor())
            t.setFrame_(NSMakeRect(16, ROW_H - 28, lw, 18))
            t.setAutoresizingMask_(2)
            bg.addSubview_(t)
            s = NSTextField.labelWithString_(sub_text)
            s.setFont_(NSFont.systemFontOfSize_(11))
            s.setTextColor_(NSColor.secondaryLabelColor())
            s.setFrame_(NSMakeRect(16, 8, lw, 14))
            s.setAutoresizingMask_(2)
            bg.addSubview_(s)

        def make_toggle(key, title_text, sub_text):
            y  = _y[0] - ROW_H
            bg = _row_bg(y)
            _row_labels(bg, title_text, sub_text, TOG_W)
            is_on = bool(self._settings.get(key, DEFAULT_SETTINGS.get(key, False)))
            btn = ActionButton.alloc().initWithFrame_(
                NSMakeRect(row_w - TOG_W - 16, (ROW_H - BTN_H) / 2, TOG_W, BTN_H))
            cb = self._make_toggle_cb(key)
            if is_on:
                btn.configureTitle_bg_press_action_("ON", "#8c2232", "#6b1a26", cb)
            else:
                btn.configureTitle_bg_press_action_("OFF", "#3a3a3c", "#2c2c2e", cb)
            btn.setAutoresizingMask_(1)
            bg.addSubview_(btn)
            self._settings_btns[key] = (btn, cb)
            _y[0] = y - ROW_GAP

        def make_dropdown(key, title_text, sub_text, options, post_cb=None):
            y  = _y[0] - ROW_H
            bg = _row_bg(y)
            _row_labels(bg, title_text, sub_text, DD_W)
            cur_val   = self._settings.get(key, DEFAULT_SETTINGS.get(key, options[0][0]))
            cur_label = next((lbl for v, lbl in options if v == cur_val), options[0][1])

            pill = PillButton.alloc().initWithFrame_(
                NSMakeRect(row_w - DD_W - 16, (ROW_H - BTN_H) / 2, DD_W, BTN_H))
            pill.setWantsLayer_(True)
            pill.layer().setCornerRadius_(8.0)
            pill.layer().setBackgroundColor_(_hex_color("#3a3a3c").CGColor())
            pill_lbl = NSTextField.labelWithString_(f"{cur_label}  ▾")
            pill_lbl.setFont_(NSFont.systemFontOfSize_(12))
            pill_lbl.setTextColor_(NSColor.labelColor())
            pill_lbl.setAlignment_(2)
            pill_lbl.setFrame_(NSMakeRect(4, (BTN_H - 16) / 2, DD_W - 8, 16))
            pill.addSubview_(pill_lbl)

            def make_picker(k, opts, p, pl, pcb):
                def picker(_, event):
                    from AppKit import NSMenu, NSMenuItem, NSPoint
                    cur = self._settings.get(k, DEFAULT_SETTINGS.get(k, opts[0][0]))
                    menu = NSMenu.alloc().init()
                    menu.setAutoenablesItems_(False)
                    _mt = MenuTarget.alloc().init()
                    self._settings_mts.append(_mt)
                    def on_item(rep):
                        v, lbl = rep
                        _save_setting(k, v)
                        self._settings[k] = v
                        pl.setStringValue_(f"{lbl}  ▾")
                        if pcb:
                            pcb(v)
                    _mt._callback = on_item
                    for v, lbl in opts:
                        mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                            lbl, "menuPicked:", "")
                        mi.setTarget_(_mt)
                        mi.setRepresentedObject_((v, lbl))
                        if v == cur:
                            mi.setState_(1)
                        menu.addItem_(mi)
                    menu.popUpMenuPositioningItem_atLocation_inView_(
                        None, NSPoint(0, 0), p)
                return picker

            pill.setClickHandler_(make_picker(key, options, pill, pill_lbl, post_cb))
            pill.setAutoresizingMask_(1)
            bg.addSubview_(pill)
            self._settings_btns[key] = (pill, pill_lbl)
            _y[0] = y - ROW_GAP

        def make_numeric(key, title_text, sub_text, min_val, max_val):
            y  = _y[0] - ROW_H
            bg = _row_bg(y)
            _row_labels(bg, title_text, sub_text, NUM_W)
            cur_val = self._settings.get(key, DEFAULT_SETTINGS.get(key, min_val))
            STEP_W  = 28.0
            VAL_W   = 42.0
            G       = 4.0
            ctl_x   = row_w - NUM_W - 16
            ctl_y   = (ROW_H - BTN_H) / 2

            minus_btn = ActionButton.alloc().initWithFrame_(
                NSMakeRect(ctl_x, ctl_y, STEP_W, BTN_H))
            val_lbl = NSTextField.labelWithString_(str(int(cur_val)))
            val_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(13, 0.3))
            val_lbl.setTextColor_(NSColor.labelColor())
            val_lbl.setAlignment_(2)
            val_lbl.setFrame_(NSMakeRect(ctl_x + STEP_W + G, ctl_y + (BTN_H - 16) / 2, VAL_W, 16))
            plus_btn = ActionButton.alloc().initWithFrame_(
                NSMakeRect(ctl_x + STEP_W + G + VAL_W + G, ctl_y, STEP_W, BTN_H))

            def make_step(k, mn, mx, lbl):
                def on_minus():
                    v = max(mn, self._settings.get(k, mn) - 1)
                    self._settings[k] = v
                    _save_setting(k, v)
                    lbl.setStringValue_(str(v))
                def on_plus():
                    v = min(mx, self._settings.get(k, mn) + 1)
                    self._settings[k] = v
                    _save_setting(k, v)
                    lbl.setStringValue_(str(v))
                return on_minus, on_plus

            on_minus, on_plus = make_step(key, min_val, max_val, val_lbl)
            minus_btn.configureTitle_bg_press_action_("−", "#3a3a3c", "#2c2c2e", on_minus)
            minus_btn.setAutoresizingMask_(1)
            bg.addSubview_(minus_btn)
            val_lbl.setAutoresizingMask_(1)
            bg.addSubview_(val_lbl)
            plus_btn.configureTitle_bg_press_action_("+", "#3a3a3c", "#2c2c2e", on_plus)
            plus_btn.setAutoresizingMask_(1)
            bg.addSubview_(plus_btn)
            self._settings_btns[key] = val_lbl
            _y[0] = y - ROW_GAP

        def section_gap():
            _y[0] -= SGAP

        # ── LOG MODE ────────────────────────────────────────────────────────
        make_header("Log Mode")
        make_toggle("player_search_mode",
                    "Always search for player names",
                    "Type to search the full roster instead of using hotkeys.")
        make_toggle("player_number_search",
                    "Search players by jersey number",
                    "Type digits to find players by # instead of name (requires search mode on).")
        make_toggle("auto_advance_after_tag",
                    "Auto-advance after tag",
                    "Move to the next file automatically after each tag is finalized.")
        make_dropdown("file_sort_order",
                      "File sort order",
                      "Order in which video files appear in the list.",
                      [("name_asc",       "Name A → Z"),
                       ("name_desc",      "Name Z → A"),
                       ("date_created",   "Date Created"),
                       ("date_modified",  "Date Modified")],
                      post_cb=lambda v: self._refresh_files())
        make_numeric("search_mode_threshold",
                     "Auto-search threshold",
                     "Enable search mode automatically when roster has ≥ this many players (0 = off).",
                     0, 100)
        make_toggle("arm_on_file_select",
                    "Arm logging on file select",
                    "Start logging automatically when a file is selected in the list.")

        section_gap()

        # ── RENAME ──────────────────────────────────────────────────────────
        make_header("Rename")
        make_toggle("show_rename_preview",
                    "Show rename preview",
                    "Show a confirmation panel listing all planned renames before executing.")
        make_dropdown("conflict_behavior",
                      "File conflict behavior",
                      "What to do when the destination filename already exists.",
                      [("ask",  "Ask Each Time"),
                       ("skip", "Skip File")])
        make_toggle("preserve_ext_case",
                    "Preserve extension case",
                    "Keep the original extension case (.MP4 stays .MP4). Default lowercases it.")

        section_gap()

        # ── DISPLAY ─────────────────────────────────────────────────────────
        make_header("Display")
        make_toggle("show_jersey_numbers",
                    "Show jersey numbers",
                    "Display jersey numbers alongside player names in the Log section.")
        make_dropdown("pill_density",
                      "Player pill density",
                      "Size of player buttons in the Log section.",
                      [("auto",    "Auto"),
                       ("compact", "Compact"),
                       ("normal",  "Normal"),
                       ("large",   "Large")],
                      post_cb=lambda v: (
                          self._populate_shortcut_pills("players")
                          if hasattr(self, "_sc_scrollviews") else None))

        section_gap()

        # ── STATS ───────────────────────────────────────────────────────────
        make_header("Stats")
        make_toggle("record_stats",
                    "Record stats on tag",
                    "Append clip data to the stats log after every tag is finalized.")
        make_dropdown("stats_scope",
                      "Stats time scope",
                      "Which clips to include when computing stats.",
                      [("all_time", "All Time"),
                       ("today",    "Today"),
                       ("session",  "This Session")],
                      post_cb=lambda v: (
                          self._refresh_stats()
                          if getattr(self, "current_section", "") == "stats" else None))

        section_gap()

        # ── ROSTER ──────────────────────────────────────────────────────────
        make_header("Roster")
        make_toggle("auto_fetch_roster",
                    "Auto-refresh roster on sport switch",
                    "Re-fetch the roster in the background whenever you switch sports.")
        make_numeric("roster_cache_days",
                     "Roster cache max age (days)",
                     "Re-fetch the roster if the cached version is older than this.",
                     1, 30)

        section_gap()

        # ── SYSTEM ──────────────────────────────────────────────────────────
        make_header("System")
        make_toggle("show_in_dock",
                    "Show in Dock",
                    "Show EZ Logger in the Dock. Turn off for menubar-only mode.")
        make_toggle("launch_at_login",
                    "Launch at login",
                    "Start EZ Logger automatically at login (requires built .app).")
        make_toggle("auto_open_on_launch",
                    "Open window at launch",
                    "Automatically open the main window when the app starts.")
        make_toggle("sound_on_rename",
                    "Sound on rename",
                    "Play a brief sound after a file is successfully renamed.")

        section_gap()

        # ── UNDO ────────────────────────────────────────────────────────────
        make_header("Undo")
        make_numeric("undo_stack_size",
                     "Undo history depth",
                     "Maximum number of rename operations that can be undone.",
                     10, 200)

        # Scroll to top
        sv.contentView().scrollToPoint_((0, max(0.0, doc_h - SCROLL_H)))
        sv.reflectScrolledClipView_(sv.contentView())

    def _make_toggle_cb(self, key):
        """Return a stable callback for a settings toggle button (special cases included)."""
        if key == "player_search_mode":
            return self._toggle_player_search_setting
        if key == "player_number_search":
            return self._toggle_player_number_search_setting
        if key == "show_jersey_numbers":
            return self._toggle_show_jersey_numbers
        if key == "show_in_dock":
            return self._toggle_setting_dock
        if key == "launch_at_login":
            return self._toggle_setting_login
        return lambda: self._toggle_setting_bool(key)

    def _toggle_setting_bool(self, key):
        """Flip a boolean setting, persist it, and refresh the toggle button."""
        val = not self._settings.get(key, DEFAULT_SETTINGS.get(key, False))
        self._settings[key] = val
        _save_setting(key, val)
        entry = self._settings_btns.get(key)
        if entry and isinstance(entry, tuple):
            btn, cb = entry
            if val:
                btn.configureTitle_bg_press_action_("ON", "#8c2232", "#6b1a26", cb)
            else:
                btn.configureTitle_bg_press_action_("OFF", "#3a3a3c", "#2c2c2e", cb)

    def _toggle_player_search_setting(self):
        self._apply_search_mode(not self._player_search_mode)

    def _toggle_player_number_search_setting(self):
        val = not self._settings.get("player_number_search", False)
        self._player_number_search = val
        self._settings["player_number_search"] = val
        _save_setting("player_number_search", val)
        entry = self._settings_btns.get("player_number_search") if hasattr(self, "_settings_btns") else None
        if entry and isinstance(entry, tuple):
            btn, cb = entry
            if val:
                btn.configureTitle_bg_press_action_("ON", "#8c2232", "#6b1a26", cb)
            else:
                btn.configureTitle_bg_press_action_("OFF", "#3a3a3c", "#2c2c2e", cb)

    def _toggle_show_jersey_numbers(self):
        self._toggle_setting_bool("show_jersey_numbers")
        if hasattr(self, "_sc_scrollviews"):
            self._populate_shortcut_pills("players")

    def _toggle_setting_dock(self):
        self._toggle_setting_bool("show_in_dock")
        val = self._settings.get("show_in_dock", True)
        try:
            from AppKit import NSApplication
            NSApplication.sharedApplication().setActivationPolicy_(0 if val else 1)
        except Exception:
            pass

    def _toggle_setting_login(self):
        self._toggle_setting_bool("launch_at_login")
        _set_launch_at_login(self._settings.get("launch_at_login", False))

    # ── Help section ──────────────────────────────────────────────────────────

    def _help_content_sections(self):
        return [
            ("Overview", [
                ("para",
                 "EZ Logger is a keyboard-driven tool for tagging sports video files. "
                 "Set up your session once, then use Log Mode to tag each clip — the label "
                 "appends directly to the filename."),
                ("subhead", "LOGGING FLOW"),
                ("para", "Player  →  [custom steps]  →  final step"),
                ("subhead", "NAVIGATION"),
                ("table", [
                    ("Log",      "Tag video files with shortcut keys"),
                    ("Team",     "Manage the player roster and switch sports"),
                    ("Labels",   "Configure shortcut banks for each logging step"),
                    ("Naming",   "Set up filename presets for Batch Rename"),
                    ("Stats",    "View clip counts, leaderboards, and per-player breakdowns"),
                    ("Settings", "App-level preferences"),
                    ("Help",     "This screen"),
                ]),
                ("subhead", "SUPPORTED SPORTS"),
                ("para", "MBB  ·  WBB  ·  MHK  ·  WHK  ·  FB  ·  WLAX  ·  BASE  ·  SB"),
            ]),
            ("Setup Session", [
                ("para",
                 "Configure your session before logging. Click Save Session to apply — "
                 "the top status bar updates immediately."),
                ("subhead", "FIELDS"),
                ("table", [
                    ("Sport",        "Select from the dropdown, or use the Team tab sport pill"),
                    ("Opponent",     "Opposing team code (e.g. MIAMI, DUKE, YALE)"),
                    ("Videographer", "Your initials or operator code (e.g. ZK)"),
                    ("Phase",        "Game phase: PRE · 1H · 2H · OT · POST · PRAC · SCOUT"),
                    ("Folder",       "The folder containing your video files"),
                ]),
            ]),
            ("Log Mode", [
                ("para",
                 "Log Mode tags video files with shortcut labels. The tag appends directly "
                 "to the filename after logging."),
                ("subhead", "STEPS"),
                ("table", [
                    ("1",     "Select a file from the file list"),
                    ("2",     "Press SPACE to QuickLook preview the clip (optional)"),
                    ("3",     "Press ENTER to begin logging"),
                    ("4–N",   "Press shortcut keys at each step, then ENTER to advance"),
                    ("Final", "ENTER on the last step tags the file and marks it ✓"),
                ]),
                ("para",
                 "At each step you can press multiple shortcut keys before advancing — "
                 "labels accumulate. Press ESC at any time to cancel."),
                ("subhead", "CUSTOM INSERT  (⌥ OPTION)"),
                ("para",
                 "At any step, hold Option then type free-form text instead of a shortcut. "
                 "Spaces are preserved as typed. Press ENTER to confirm, Backspace to delete "
                 "the last character, or ⌥ Option again to cancel without confirming."),
                ("subhead", "UNDO  (⌘Z)"),
                ("para",
                 "Reverses the last logged rename. Works from the keyboard in Log Mode "
                 "or from the menubar."),
            ]),
            ("Team & Roster", [
                ("para", "The Team tab manages the player list for the active sport."),
                ("subhead", "SPORT PICKER"),
                ("para",
                 "The pill button at the top shows the active sport "
                 "(e.g. ▸ 🏀 Men's Basketball ▾). Click it to switch sports — "
                 "the roster and session update automatically."),
                ("subhead", "LOADING A ROSTER"),
                ("para",
                 "Click 'Fetch All Rosters ↓' to automatically pull current rosters from "
                 "BC Athletics for all sports. Each athlete becomes a shortcut entry "
                 "with their last name as the label and jersey number shown in the pill."),
                ("subhead", "MANUAL MANAGEMENT"),
                ("bullets", [
                    "Click the pencil icon to edit a shortcut key or label",
                    "Click the trash icon to delete a player",
                    "Click '+ Add Player' to create a new entry",
                ]),
            ]),
            ("Labels", [
                ("para",
                 "The Labels tab configures the shortcut banks for all logging steps after "
                 "Player. Each step has its own set of shortcut keys."),
                ("subhead", "CONFIGURING STEPS"),
                ("para",
                 "The step-order list shows every step in the logging sequence. "
                 "Player is always first and cannot be moved or removed. "
                 "Custom steps appear below it."),
                ("bullets", [
                    "Click '+ Add Step' to add a new logging step",
                    "Click a step's numbered badge to select it and manage its shortcuts",
                    "Edit the step name inline — the Log Mode card updates automatically",
                    "Use ↑ ↓ to reorder steps, × to delete",
                ]),
                ("subhead", "MANAGING SHORTCUTS"),
                ("bullets", [
                    "Click the pencil icon to edit a key or label",
                    "Click the trash icon to delete a shortcut",
                    "Click '+ Add Shortcut' to create a new entry",
                ]),
                ("para",
                 "Shortcut keys are single characters. The same key can be reused across "
                 "different steps — context (which step you're on) determines which label applies."),
            ]),
            ("Naming Conventions", [
                ("para",
                 "The Naming tab configures presets that control how Batch Rename builds "
                 "filenames. The active preset (highlighted) is used when Batch Rename runs."),
                ("subhead", "PRESET STRUCTURE"),
                ("table", [
                    ("Name",      "A label for the preset (e.g. Game, Practice)"),
                    ("Separator", "Character placed between fields (default: _)"),
                    ("Fields",    "Ordered segments that form the filename stem"),
                ]),
                ("subhead", "FIELD TYPES"),
                ("table", [
                    ("Text",     "A fixed string or session value: Sport, Opponent, Videographer, Phase"),
                    ("Metadata", "A date/time value from the video file's creation timestamp (e.g. YYYYMMDD)"),
                    ("Opponent", "Crimson badge — uses the session opponent or a locked schedule value"),
                ]),
                ("subhead", "SCHEDULE IMPORT"),
                ("para",
                 "Click '⚡ Import Schedule' to auto-generate one preset per opponent on BC's "
                 "schedule. The active preset must have an Opponent field. Existing presets "
                 "are not overwritten. Set the base domain in Settings."),
            ]),
            ("Batch Rename", [
                ("para",
                 "Batch Rename standardizes all video filenames in the selected folder using "
                 "the active naming preset. Run it before logging to establish the base filename."),
                ("subhead", "DEFAULT FORMAT"),
                ("para", "SPORT_OPPONENT_YYYYMMDD_HHMMSS_VID_PHASE.ext"),
                ("para", "Example:   MBB_MIAMI_20260117_143022_ZK_2H.mp4"),
                ("para",
                 "Date and time are read from the video file's container metadata via "
                 "AVFoundation, falling back to the file's creation timestamp when metadata "
                 "is unavailable."),
                ("para",
                 "A dry-run preview panel lists every planned rename before executing. "
                 "Confirm to proceed or cancel to abort."),
            ]),
            ("Stats", [
                ("para",
                 "The Stats tab tracks every clip tagged during Log Mode. "
                 "Entries are appended permanently — stats persist across sessions."),
                ("subhead", "OVERVIEW TAB"),
                ("bullets", [
                    "Total clips tagged and total sessions",
                    "Top Player, Top Play, and Top Rating",
                    "Leaderboard columns for players, plays, and ratings",
                ]),
                ("subhead", "PLAYERS TAB"),
                ("para",
                 "Scrollable list of all players with clip counts. "
                 "Click any row to expand a detail card showing per-player "
                 "play and rating breakdowns."),
            ]),
            ("Settings", [
                ("subhead", "ALWAYS SEARCH FOR PLAYER NAMES"),
                ("para",
                 "When enabled, the Player step switches to search mode: type any part of a "
                 "player's name to filter the list — no need to memorize shortcut keys. "
                 "Press ENTER to confirm the highlighted match. "
                 "Toggle at any time; takes effect immediately on the next log."),
                ("subhead", "ROSTER DOMAIN"),
                ("para",
                 "Click '🔗 domain.com' in the Team header to set the base URL for roster "
                 "and schedule scraping (e.g. bceagles.com). Saved to Settings automatically."),
            ]),
            ("Keyboard Reference", [
                ("subhead", "LOG MODE"),
                ("table", [
                    ("ENTER",          "Begin logging · advance step · confirm custom insert"),
                    ("SPACE",          "QuickLook preview of the selected file"),
                    ("ESC",            "Cancel the current log, return to idle"),
                    ("[key]",          "Apply shortcut — stays on current step to allow stacking"),
                    ("⌥ Option",       "Enter custom-insert mode (spaces preserved as typed)"),
                    ("⌥ Option again", "Cancel custom-insert without confirming"),
                    ("Backspace",      "Delete last character in custom-insert mode"),
                    ("TAB",            "Advance to the next file (only when not mid-tag)"),
                    ("⌘Z",            "Undo the last logged file rename"),
                ]),
                ("subhead", "FILE LIST"),
                ("table", [
                    ("↑ / ↓", "Navigate between files"),
                    ("SPACE",  "QuickLook preview"),
                ]),
                ("subhead", "GLOBAL"),
                ("table", [
                    ("⌘Z", "Undo last rename (also from the menubar)"),
                ]),
            ]),
        ]

    def _make_toc_attr(self, text: str, color):
        """Build an NSAttributedString for a TOC sidebar button."""
        from AppKit import (NSAttributedString, NSForegroundColorAttributeName,
                            NSFontAttributeName, NSFont,
                            NSMutableParagraphStyle, NSParagraphStyleAttributeName)
        para = NSMutableParagraphStyle.alloc().init()
        para.setFirstLineHeadIndent_(10.0)
        para.setHeadIndent_(10.0)
        return NSAttributedString.alloc().initWithString_attributes_(
            text, {NSForegroundColorAttributeName: color,
                   NSFontAttributeName: NSFont.systemFontOfSize_(13),
                   NSParagraphStyleAttributeName: para})

    def _build_help_section(self, cv, W, H, SIDEBAR_W, TOP_H):
        from AppKit import (
            NSView, NSTextField, NSFont, NSColor, NSMakeRect, NSScrollView,
            NSButton, NSAttributedString, NSForegroundColorAttributeName,
            NSFontAttributeName,
        )

        cx = float(SIDEBAR_W)
        cw = float(W - SIDEBAR_W)
        ch = float(H - TOP_H)

        section = NSView.alloc().initWithFrame_(NSMakeRect(cx, 0, cw, ch))
        section.setWantsLayer_(True)
        section.setAutoresizingMask_(2 | 16)
        section.setHidden_(True)
        cv.addSubview_(section)
        self._help_section = section

        HEADER_H = 64.0
        header_y  = ch - HEADER_H

        title_lbl = NSTextField.labelWithString_("Help")
        title_lbl.setFont_(NSFont.boldSystemFontOfSize_(22))
        title_lbl.setTextColor_(NSColor.labelColor())
        title_lbl.sizeToFit()
        tf = title_lbl.frame()
        title_lbl.setFrame_(NSMakeRect(
            32, header_y + (HEADER_H - tf.size.height) / 2,
            tf.size.width, tf.size.height))
        title_lbl.setAutoresizingMask_(8)
        section.addSubview_(title_lbl)

        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, header_y - 1, cw, 1))
        sep.setWantsLayer_(True)
        sep.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.08).CGColor())
        sep.setAutoresizingMask_(2 | 8)
        section.addSubview_(sep)

        content_area_h = header_y - 1.0
        TOC_W = 200.0

        # Left TOC panel
        toc_panel = NSView.alloc().initWithFrame_(
            NSMakeRect(0, 0, TOC_W, content_area_h))
        toc_panel.setWantsLayer_(True)
        toc_panel.layer().setBackgroundColor_(
            _hex_color_alpha("#000000", 0.15).CGColor())
        toc_panel.setAutoresizingMask_(16)
        section.addSubview_(toc_panel)

        toc_div = NSView.alloc().initWithFrame_(
            NSMakeRect(TOC_W, 0, 1, content_area_h))
        toc_div.setWantsLayer_(True)
        toc_div.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.06).CGColor())
        toc_div.setAutoresizingMask_(16)
        section.addSubview_(toc_div)

        toc_hdr = NSTextField.labelWithString_("CONTENTS")
        toc_hdr.setFont_(NSFont.boldSystemFontOfSize_(10))
        toc_hdr.setTextColor_(NSColor.tertiaryLabelColor())
        toc_hdr.setFrame_(NSMakeRect(16, content_area_h - 36, TOC_W - 32, 14))
        toc_hdr.setAutoresizingMask_(8)
        toc_panel.addSubview_(toc_hdr)

        sections = self._help_content_sections()

        # TOC items
        self._help_toc_btns = []
        if not hasattr(self, "_toc_targets"):
            self._toc_targets = []
        toc_y = content_area_h - 74.0
        for idx, (title, _) in enumerate(sections):
            btn = NSButton.alloc().initWithFrame_(
                NSMakeRect(8, toc_y, TOC_W - 16, 30))
            btn.setBordered_(False)
            btn.setAttributedTitle_(self._make_toc_attr(title, NSColor.secondaryLabelColor()))
            btn.setAlignment_(0)
            btn.setWantsLayer_(True)
            btn.layer().setCornerRadius_(8.0)
            btn.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
            t = MenuTarget.alloc().init()
            t._callback = lambda _, i=idx: self._help_scroll_to(i)
            btn.setTarget_(t)
            btn.setAction_("menuPicked:")
            self._toc_targets.append(t)
            toc_panel.addSubview_(btn)
            self._help_toc_btns.append((btn, title))
            toc_y -= 36.0

        b0, t0 = self._help_toc_btns[0]
        b0.layer().setBackgroundColor_(_hex_color_alpha("#8c2232", 0.25).CGColor())
        b0.setAttributedTitle_(self._make_toc_attr(t0, _hex_color("#dbcca6")))

        # Right scrollable content
        content_x = TOC_W + 1.0
        content_w  = cw - content_x

        sv = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(content_x, 0, content_w, content_area_h))
        sv.setHasVerticalScroller_(True)
        sv.setAutohidesScrollers_(True)
        sv.setBorderType_(0)
        sv.setDrawsBackground_(False)
        sv.setAutoresizingMask_(2 | 16)
        section.addSubview_(sv)
        self._help_scroll = sv
        self._help_built_content_w = content_w

        self._layout_help_content(sv, content_w, content_area_h)

    def _help_scroll_to(self, idx):
        if not hasattr(self, "_help_section_ys") or idx >= len(self._help_section_ys):
            return

        from AppKit import NSColor
        for i, (btn, title) in enumerate(self._help_toc_btns):
            if i == idx:
                btn.layer().setBackgroundColor_(
                    _hex_color_alpha("#8c2232", 0.25).CGColor())
                btn.setAttributedTitle_(self._make_toc_attr(title, _hex_color("#dbcca6")))
            else:
                btn.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
                btn.setAttributedTitle_(self._make_toc_attr(title, NSColor.secondaryLabelColor()))

        section_top = self._help_section_ys[idx]
        viewport_h  = float(self._help_scroll.contentView().bounds().size.height)
        scroll_y    = max(0.0, section_top - viewport_h + 24.0)
        self._help_scroll.contentView().scrollToPoint_((0, scroll_y))
        self._help_scroll.reflectScrolledClipView_(self._help_scroll.contentView())

    def show(self):
        from AppKit import NSApplication
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.win.makeKeyAndOrderFront_(None)


# ── Menubar App ───────────────────────────────────────────────────────────────

class BasketballRenamerApp(rumps.App):
    def __init__(self):
        super().__init__("🪵", quit_button=None)
        self.session          = load_json(CONFIG_FILE, DEFAULT_SESSION)
        raw                   = load_json(SHORTCUTS_FILE, {})
        self._shortcuts_data  = self._migrate_shortcuts(raw)
        sport                 = self.session.get("sport", "MBB")
        self.shortcuts        = dict(self._shortcuts_data.get(sport, DEFAULT_SHORTCUTS))
        self._shortcuts_data[sport] = self.shortcuts
        self._session_start_ts = datetime.now().isoformat()
        self._build_menu()
        # Apply dock visibility preference at startup
        _s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        if not _s.get("show_in_dock", True):
            try:
                from AppKit import NSApplication
                NSApplication.sharedApplication().setActivationPolicy_(1)
            except Exception:
                pass
        rumps.Timer(self._auto_open, 0.1).start()

    def _migrate_shortcuts(self, data):
        """Migrate old flat {bank: [...]} format to nested {sport_key: {bank: [...]}}."""
        if isinstance(data.get("players"), list):
            sport = self.session.get("sport", "MBB")
            migrated = {sport: data}
            save_json(SHORTCUTS_FILE, migrated)
            return migrated
        return data if data else {}

    def _save_shortcuts(self):
        """Write self.shortcuts into the active sport's slot and persist."""
        sport = self.session.get("sport", "MBB")
        self._shortcuts_data[sport] = self.shortcuts
        save_json(SHORTCUTS_FILE, self._shortcuts_data)

    def _auto_open(self, timer):
        timer.stop()
        s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        if s.get("auto_open_on_launch", True):
            self.open_tag_mode_v2(None)

    def _build_menu(self):
        self.menu.clear()
        s = self.session
        sport_label = SPORTS.get(s.get("sport",""), {}).get("label", s.get("sport",""))
        self.menu.add(rumps.MenuItem(
            f"  {sport_label}  |  vs {s['opponent']}  |  {s['videographer']}  |  {s['phase']}  "
            f"|  {Path(s['folder']).name or 'No folder'}"))
        self.menu.add(rumps.separator)

        undo_item = rumps.MenuItem("  ↩  Undo Rename", callback=self.undo_last, key="z")
        undo_item._menuitem.setEnabled_(False)
        self._undo_item = undo_item
        self.menu.add(undo_item)
        self._refresh_undo_item()
        self.menu.add(rumps.separator)

        self.menu.add(rumps.MenuItem("Open Window", callback=self.open_tag_mode_v2))
        self.menu.add(rumps.separator)

        # ── DEV ──────────────────────────────────────────────────────────────
        self.menu.add(rumps.MenuItem("🔄  Load Roster from BC Website", callback=self.load_roster))
        self.menu.add(rumps.MenuItem("⚙️  Setup Session",               callback=self.setup_session))
        self.menu.add(rumps.separator)

        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    # ── Session setup ─────────────────────────────────────────────────────────

    def setup_session(self, _):
        s = dict(self.session)
        fields = [
            ("sport",        "Sport Code",           f"Options: {', '.join(SPORT_OPTIONS)}"),
            ("opponent",     "Opponent",              "e.g. MIAMI"),
            ("videographer", "Videographer Initials", "e.g. ZK"),
            ("phase",        "Game Phase",            f"Options: {', '.join(PHASE_OPTIONS)}"),
        ]
        for key, title, hint in fields:
            val = ask(title, hint, s[key])
            if val is None: return
            s[key] = _asc(val).upper()

        if rumps.alert("Select Footage Folder",
                       f"Current: {s['folder'] or 'None'}\n\nChoose a new folder?",
                       ok="Choose", cancel="Keep") == 1:
            folder = pick_folder_dialog()
            if folder: s["folder"] = folder

        self.session = s
        save_json(CONFIG_FILE, s)
        self._build_menu()
        rumps.alert("✅ Session Saved",
                    f"{s['sport']} vs {s['opponent']}  |  {s['videographer']}  |  {s['phase']}\n"
                    f"Folder: {s['folder'] or 'Not set'}")

    def switch_sport(self, sport_key):
        old_sport = self.session.get("sport", "MBB")
        self._shortcuts_data[old_sport] = dict(self.shortcuts)

        self.session["sport"] = sport_key
        save_json(CONFIG_FILE, self.session)
        self._build_menu()

        # Load this sport's shortcuts (all banks), falling back to defaults
        new_sc = dict(self._shortcuts_data.get(sport_key, DEFAULT_SHORTCUTS))

        # Overlay the cached roster for the new sport's players bank
        cache = load_json(ROSTERS_FILE, {})
        if sport_key in cache and cache[sport_key]:
            new_sc["players"] = cache[sport_key]

        # Swap in-place so the window's reference stays valid
        self.shortcuts.clear()
        self.shortcuts.update(new_sc)
        self._shortcuts_data[sport_key] = self.shortcuts
        self._save_shortcuts()

        self._refresh_tag_window_shortcuts()
        _s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        if _s.get("auto_fetch_roster", False) or not (sport_key in cache and cache[sport_key]):
            _cd = _s.get("roster_cache_days", 7)
            threading.Thread(target=self._load_roster_bg, args=(sport_key, True, _cd), daemon=True).start()

        if hasattr(self, "_tag_window_v2") and self._tag_window_v2:
            tw = self._tag_window_v2
            if getattr(tw, "current_section", None) == "session":
                tw._refresh_convention_for_sport()
            if getattr(tw, "current_section", None) == "stats":
                tw._refresh_stats()

    def load_roster(self, _):
        """Menubar dev shortcut — fetch all rosters using the saved base URL."""
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        base_url = settings.get("roster_base_url", "").strip()
        if not base_url:
            # Fall back to single-sport scrape for the active sport
            sport_key = self.session.get("sport", "MBB")
            _cd = settings.get("roster_cache_days", 7)
            rumps.alert("Loading Roster…",
                        f"Fetching roster for {SPORTS[sport_key]['label']}.\nThis takes a few seconds.")
            threading.Thread(target=self._load_roster_bg, args=(sport_key, False, _cd), daemon=True).start()
        else:
            threading.Thread(target=self._scrape_all_bg, args=(base_url, False), daemon=True).start()

    def load_all_rosters(self, base_url):
        """Called from the Team section UI with a specific base URL."""
        threading.Thread(target=self._scrape_all_bg, args=(base_url, True), daemon=True).start()

    def _scrape_all_bg(self, base_url, ui_mode):
        """Background worker: scrape all sports, save cache, refresh current sport."""
        results = scrape_all_rosters(base_url)
        if not results:
            if not ui_mode:
                rumps.alert("❌ Roster Fetch Failed",
                            "No rosters found at that URL.\n"
                            "Check the URL and your internet connection.")
            self._notify_tag_window_scrape_done(False, {})
            return
        cache = {code: roster_to_shortcuts(names) for code, names in results.items()}
        save_json(ROSTERS_FILE, cache)
        now_iso = datetime.now().isoformat()
        meta = load_json(ROSTERS_META_FILE, {})
        meta.update({code: now_iso for code in cache})
        save_json(ROSTERS_META_FILE, meta)
        sport_key = self.session.get("sport", "MBB")
        if sport_key in cache:
            self.shortcuts["players"] = cache[sport_key]
            self._save_shortcuts()
        self._refresh_tag_window_players()
        self._notify_tag_window_scrape_done(True, results)

    def _notify_tag_window_scrape_done(self, success, results):
        """Bounce scrape-complete notification to the Team section UI."""
        win = getattr(self, "_tag_window_v2", None)
        if win is None or not MainCaller:
            return
        def on_main():
            if hasattr(win, "_on_fetch_all_done"):
                win._on_fetch_all_done(success, results)
        caller = MainCaller.alloc().init()
        caller._cb = on_main
        caller.performSelectorOnMainThread_withObject_waitUntilDone_(
            b"fire:", None, False)

    def _load_roster_bg(self, sport_key, silent, cache_days: int = 7):
        names = fetch_roster(sport_key, cache_days=cache_days)
        if names:
            shortcuts = roster_to_shortcuts(names)
            self.shortcuts["players"] = shortcuts
            self._save_shortcuts()
            meta = load_json(ROSTERS_META_FILE, {})
            meta[sport_key] = datetime.now().isoformat()
            save_json(ROSTERS_META_FILE, meta)
            if not silent:
                rumps.alert("✅ Roster Loaded",
                            f"{SPORTS[sport_key]['label']}\n\n"
                            f"{len(names)} players loaded:\n" +
                            "\n".join(f"[{sc['key']}]  {sc['label']}" for sc in shortcuts[:15]) +
                            ("\n…" if len(shortcuts) > 15 else ""))
            self._refresh_tag_window_players()
        else:
            if not silent:
                rumps.alert("❌ Roster Load Failed",
                            "Could not fetch roster from BC Athletics website.\n"
                            "Check your internet connection and try again.\n"
                            "You can still manage players manually via Manage Players.")

    def _refresh_tag_window_players(self):
        win = getattr(self, "_tag_window_v2", None)
        if win is None:
            return
        if not MainCaller:
            return
        sport_key = self.session.get("sport", "MBB")
        def refresh():
            if hasattr(win, "_refresh_players_grid"):
                win._refresh_players_grid()
            if hasattr(win, "_populate_shortcut_pills"):
                win._populate_shortcut_pills("players")
            if hasattr(win, "_update_sport_pill"):
                win._update_sport_pill(sport_key)
            # Auto-enable search mode if roster exceeds configured threshold
            threshold = win._settings.get("search_mode_threshold", 0)
            if threshold > 0:
                roster_size = len(self.shortcuts.get("players", []))
                if roster_size >= threshold and not win._player_search_mode:
                    win._apply_search_mode(True)
            if hasattr(win, "_update_session_status_btn"):
                win._update_session_status_btn()
        caller = MainCaller.alloc().init()
        caller._cb = refresh
        caller.performSelectorOnMainThread_withObject_waitUntilDone_(
            b"fire:", None, False)

    def _refresh_tag_window_shortcuts(self):
        """Refresh all shortcut UI after a sport switch (players + all label banks)."""
        win = getattr(self, "_tag_window_v2", None)
        if win is None:
            return
        if not MainCaller:
            return
        sport_key = self.session.get("sport", "MBB")
        def refresh():
            if hasattr(win, "_refresh_players_grid"):
                win._refresh_players_grid()
            if hasattr(win, "_update_sport_pill"):
                win._update_sport_pill(sport_key)
            if hasattr(win, "_refresh_labels_grid"):
                win._refresh_labels_grid()
            if hasattr(win, "_rebuild_sc_cards"):
                win._rebuild_sc_cards()
                # Hide all sc_cards if we switched sport while not in the log section
                if win.current_section != "tag" and hasattr(win, "_sc_cards"):
                    for card in win._sc_cards.values():
                        card.setHidden_(True)
        caller = MainCaller.alloc().init()
        caller._cb = refresh
        caller.performSelectorOnMainThread_withObject_waitUntilDone_(
            b"fire:", None, False)

    # ── Batch rename ──────────────────────────────────────────────────────────

    def batch_rename(self, _):
        folder = self.session.get("folder", "")
        ok, err = SafeRenamer.validate_folder(folder)
        if not ok:
            rumps.alert("Cannot Rename", err)
            return

        folder_path = Path(folder)
        files = sorted(
            [p for p in folder_path.iterdir()
             if SafeRenamer.validate_file(p, folder_path)[0]],
            key=lambda p: p.name
        )
        if not files:
            rumps.alert("No Files", f"No video files found in:\n{folder}")
            return

        s            = self.session
        sport_key    = s.get("sport", "")
        global_p     = s.get("naming_presets", DEFAULT_NAMING_PRESETS) or list(DEFAULT_NAMING_PRESETS)
        sport_p      = s.get("sport_presets", {}).get(sport_key, [])
        presets      = global_p + sport_p
        act_idx      = int(s.get("active_preset", 0))
        if act_idx >= len(presets):
            act_idx = 0
        preset = presets[act_idx] if presets else None

        if not preset or not preset.get("fields"):
            rumps.alert("No Naming Convention",
                        "Set up a naming convention in the Naming section before running Batch Rename.")
            return

        # Build the dry-run rename plan
        _s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        plan          = []   # [(src_path, new_name, was_deduped)]
        planned_names = set()  # track names already claimed in this batch
        for f in files:
            stem = resolve_convention(preset, f, session=s)
            if not stem:
                continue
            _ext = f.suffix if _s.get("preserve_ext_case", False) else f.suffix.lower()
            base_name = f"{stem}{_ext}"
            candidate = base_name
            counter   = 2
            # Check both existing disk names AND names already claimed in this batch
            while (((f.parent / candidate).exists() and (f.parent / candidate) != f)
                   or candidate in planned_names):
                stem_part, ext = os.path.splitext(base_name)
                candidate = f"{stem_part}_{counter}{ext}"
                counter  += 1
            was_deduped = (candidate != base_name)
            plan.append((f, candidate, was_deduped))
            planned_names.add(candidate)

        if not plan:
            rumps.alert("No Files to Rename",
                        "No files matched the naming convention. "
                        "Check your convention fields are not empty.")
            return

        # ── Duplicate-destination guard ─────────────────────────────────────
        # If ALL files resolve to variations of the same base name it usually
        # means the convention has no unique field (no date/time/metadata).
        # Count how many distinct base names (ignoring the _2 _3 suffix we
        # added above) come out of the plan.
        import collections as _col
        base_stems = _col.Counter(
            os.path.splitext(n)[0].rstrip("_0123456789").rstrip("_")
            for _, n, _d in plan
        )
        most_common_base, most_common_count = base_stems.most_common(1)[0]
        if most_common_count > 1 and most_common_count >= len(plan) * 0.8:
            # 80%+ of files share the same base stem — very likely a missing unique field
            from AppKit import NSAlert
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Convention Produces Duplicate Names")
            alert.setInformativeText_(
                f"{most_common_count} of {len(plan)} files would share the base name "
                f"“{most_common_base}” — only one file per unique name can "
                f"survive a rename.\n\n"
                "Add a Metadata field (date or time) to your naming convention to "
                "give each file a unique name before running Batch Rename.")
            alert.addButtonWithTitle_("Open Naming Tab")
            alert.addButtonWithTitle_("Cancel")
            if alert.runModal() == 1000:
                if self._tag_window_v2:
                    self._tag_window_v2.show()
                    self._tag_window_v2._on_nav_select("session")
            return

        # Show dry-run confirmation window (blocks until user chooses)
        if _s.get("show_rename_preview", True):
            if not self._show_batch_rename_preview(plan, folder):
                return

        snapshot = {
            "type":      "batch",
            "folder":    folder,
            "timestamp": datetime.now().isoformat(),
            "renames":   [],
        }
        renamed, failed, errors = 0, 0, []
        for src, new_name, _deduped in plan:
            dst = src.parent / new_name
            ok, err = SafeRenamer.safe_rename(src, dst, folder_path, self.session)
            if ok:
                snapshot["renames"].append({"old": src.name, "new": new_name})
                renamed += 1
            else:
                failed += 1
                errors.append(f"  {src.name}: {err}")

        if snapshot["renames"]:
            _max_stack = load_json(SETTINGS_FILE, DEFAULT_SETTINGS).get("undo_stack_size", 50)
            self._push_undo(snapshot, max_stack=_max_stack)

        if renamed and not failed:
            rumps.alert("Done", f"Renamed {renamed} file(s).")
        elif renamed and failed:
            rumps.alert("Done with Errors",
                        f"{renamed} file(s) renamed successfully.\n"
                        f"{failed} file(s) failed:\n" + "\n".join(errors))
        else:
            rumps.alert("Rename Failed",
                        f"No files were renamed.\n{failed} file(s) failed:\n"
                        + "\n".join(errors))
        self._refresh_tag_window_files()

    def _show_batch_rename_preview(self, plan, folder) -> bool:
        """Show a native confirmation panel listing the planned renames.
        Returns True if the user clicks Confirm, False for Cancel."""
        from AppKit import (
            NSApplication, NSPanel, NSView, NSTextField, NSScrollView,
            NSFont, NSColor, NSMakeRect, NSMakeSize, NSButton,
            NSTitledWindowMask, NSClosableWindowMask, NSResizableWindowMask,
            NSBackingStoreBuffered, NSWindowStyleMaskTitled,
            NSWindowStyleMaskClosable, NSWindowStyleMaskResizable,
        )

        PREVIEW_LIMIT = 20
        shown   = plan[:PREVIEW_LIMIT]
        extra   = len(plan) - len(shown)

        W, H = 640.0, 480.0

        # Activate the app so the panel gets focus
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

        style = (NSWindowStyleMaskTitled |
                 NSWindowStyleMaskClosable |
                 NSWindowStyleMaskResizable)
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, H), style, NSBackingStoreBuffered, False)
        panel.setTitle_("Confirm Batch Rename")
        panel.center()
        panel.setReleasedWhenClosed_(False)

        cv = panel.contentView()

        # ── Header ────────────────────────────────────────────────────────────
        hdr = NSTextField.labelWithString_(
            f"Rename {len(plan)} file(s) in:  {Path(folder).name}/")
        hdr.setFont_(NSFont.boldSystemFontOfSize_(13))
        hdr.setTextColor_(NSColor.labelColor())
        hdr.setFrame_(NSMakeRect(20, H - 44, W - 40, 20))
        hdr.setAutoresizingMask_(2 | 8)
        cv.addSubview_(hdr)

        # ── Column headers ────────────────────────────────────────────────────
        COL_Y = H - 68
        for text, x, w in [("Before", 20, W / 2 - 28), ("After", W / 2 + 8, W / 2 - 28)]:
            lbl = NSTextField.labelWithString_(text.upper())
            lbl.setFont_(NSFont.boldSystemFontOfSize_(10))
            lbl.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.6))
            lbl.setFrame_(NSMakeRect(x, COL_Y, w, 14))
            lbl.setAutoresizingMask_(2 | 8)
            cv.addSubview_(lbl)

        sep_top = NSView.alloc().initWithFrame_(NSMakeRect(20, COL_Y - 4, W - 40, 1))
        sep_top.setWantsLayer_(True)
        sep_top.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.12).CGColor())
        sep_top.setAutoresizingMask_(2 | 8)
        cv.addSubview_(sep_top)

        # ── Scrollable file list ───────────────────────────────────────────────
        BTN_AREA_H = 52.0
        list_h     = COL_Y - 4 - BTN_AREA_H - 8
        sv = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(20, BTN_AREA_H + 8, W - 40, list_h))
        sv.setHasVerticalScroller_(True)
        sv.setAutohidesScrollers_(True)
        sv.setBorderType_(0)
        sv.setDrawsBackground_(False)
        sv.setAutoresizingMask_(2 | 16)
        cv.addSubview_(sv)

        ROW_H   = 22.0
        n_rows  = len(shown) + (1 if extra else 0)
        doc_h   = max(n_rows * ROW_H + 16, list_h)
        doc = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, W - 40, doc_h))
        sv.setDocumentView_(doc)

        col_w = (W - 40 - 8) / 2 - 4
        y = doc_h - ROW_H
        COLOR_AMBER = "#e6a817"
        for src, new_name, was_deduped in shown:
            dst_path = src.parent / new_name
            disk_conflict  = dst_path.exists() and dst_path.resolve() != src.resolve()
            warn = disk_conflict or was_deduped

            old_lbl = NSTextField.labelWithString_(src.name)
            old_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.3))
            old_lbl.setTextColor_(NSColor.secondaryLabelColor())
            old_lbl.setFrame_(NSMakeRect(0, y, col_w, ROW_H - 2))
            old_lbl.setLineBreakMode_(4)
            doc.addSubview_(old_lbl)

            arr = NSTextField.labelWithString_("→")
            arr.setFont_(NSFont.systemFontOfSize_(11))
            arr.setTextColor_(_hex_color_alpha(COLOR_TAN, 0.5))
            arr.setAlignment_(1)
            arr.setFrame_(NSMakeRect(col_w + 2, y, 8, ROW_H - 2))
            doc.addSubview_(arr)

            if disk_conflict:
                new_label_text = f"⚠  {new_name}  (already exists on disk)"
            elif was_deduped:
                new_label_text = f"⚠  {new_name}  (suffix added — convention not unique)"
            else:
                new_label_text = new_name
            new_lbl = NSTextField.labelWithString_(new_label_text)
            new_lbl.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.4))
            new_lbl.setTextColor_(_hex_color(COLOR_AMBER if warn else COLOR_TAN))
            new_lbl.setFrame_(NSMakeRect(col_w + 12, y, col_w, ROW_H - 2))
            new_lbl.setLineBreakMode_(4)
            doc.addSubview_(new_lbl)

            y -= ROW_H

        if extra:
            more = NSTextField.labelWithString_(
                f"  …and {extra} more file{'s' if extra != 1 else ''}")
            more.setFont_(NSFont.systemFontOfSize_(11))
            more.setTextColor_(NSColor.tertiaryLabelColor())
            more.setFrame_(NSMakeRect(0, y, W - 40, ROW_H - 2))
            doc.addSubview_(more)

        # ── Buttons ────────────────────────────────────────────────────────────
        sep_bot = NSView.alloc().initWithFrame_(NSMakeRect(0, BTN_AREA_H, W, 1))
        sep_bot.setWantsLayer_(True)
        sep_bot.layer().setBackgroundColor_(
            _hex_color_alpha("#ffffff", 0.10).CGColor())
        sep_bot.setAutoresizingMask_(2)
        cv.addSubview_(sep_bot)

        result_box = [False]   # mutable box so closures can write to it

        if not ActionButton:
            # Fallback before ObjC classes initialised (shouldn't happen at runtime)
            panel.close()
            return True

        confirm_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(W - 20 - 130, (BTN_AREA_H - 32) / 2, 130, 32))
        confirm_btn.configureTitle_bg_press_action_(
            f"Rename {len(plan)} Files", COLOR_CRIMSON, COLOR_CRIMSON_D,
            lambda: (result_box.__setitem__(0, True),
                     NSApplication.sharedApplication().stopModal()))
        confirm_btn.setAutoresizingMask_(1)
        cv.addSubview_(confirm_btn)

        cancel_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(W - 20 - 130 - 10 - 90, (BTN_AREA_H - 32) / 2, 90, 32))
        cancel_btn.configureTitle_bg_press_action_(
            "Cancel", "#3a3a3c", "#2c2c2e",
            lambda: NSApplication.sharedApplication().stopModal())
        cancel_btn.setAutoresizingMask_(1)
        cv.addSubview_(cancel_btn)

        # Stop the modal if the user closes via the red X button
        preview_delegate = WindowDelegate.alloc().init()
        preview_delegate._close_cb = lambda: NSApplication.sharedApplication().stopModal()
        panel.setDelegate_(preview_delegate)

        NSApplication.sharedApplication().runModalForWindow_(panel)
        panel.setDelegate_(None)
        panel.orderOut_(None)
        return result_box[0]

    def _push_undo(self, op, max_stack: int = 50):
        stack = load_json(UNDO_FILE, [])
        if not isinstance(stack, list):
            stack = []
        stack.append(op)
        if len(stack) > max_stack:
            stack = stack[-max_stack:]
        save_json(UNDO_FILE, stack)
        self._refresh_undo_item()

    def undo_last(self, _):
        stack = load_json(UNDO_FILE, [])
        if not isinstance(stack, list) or not stack:
            rumps.alert("Nothing to Undo", "No rename operations to undo.")
            return

        op      = stack[-1]
        folder  = op.get("folder", "")
        renames = op.get("renames", [])
        op_type = op.get("type", "rename")

        reversible = [r for r in renames
                      if os.path.exists(os.path.join(folder, r["new"]))]
        if not reversible:
            stack.pop()
            save_json(UNDO_FILE, stack)
            self._refresh_undo_item()
            rumps.alert("Nothing to Undo",
                        "The file(s) for this operation are no longer present.")
            return

        if op_type == "batch":
            title = "Undo Batch Rename"
            msg   = f"Restore {len(reversible)} file(s) to their original names in:\n{folder}\n\nContinue?"
        else:
            r     = reversible[0]
            title = "Undo Tag Rename"
            msg   = f"Restore:\n  {r['new']}\n→ {r['old']}\n\nContinue?"

        if not rumps.alert(title=title, message=msg, ok="Undo", cancel="Cancel"):
            return

        folder_path = Path(folder)
        restored, failed, skipped, errors = 0, 0, 0, []
        for r in reversible:
            src = folder_path / r["new"]
            dst = folder_path / r["old"]
            if not src.exists():
                skipped += 1
                errors.append(f"  {r['new']}: no longer exists")
                continue
            ok, err = SafeRenamer.safe_rename(src, dst, folder_path, self.session)
            if ok:
                restored += 1
            else:
                failed += 1
                errors.append(f"  {r['new']}: {err}")

        stack.pop()
        save_json(UNDO_FILE, stack)
        self._refresh_undo_item()
        parts = [f"Restored {restored} file(s)."]
        if skipped:
            parts.append(f"{skipped} file(s) no longer present — skipped.")
        if failed:
            parts.append(f"{failed} file(s) could not be restored:\n" + "\n".join(errors))
        rumps.alert("Done", "\n".join(parts))
        self._refresh_tag_window_files()

    def _refresh_tag_window_files(self):
        for attr in ("_tag_window_v2", "_tag_window"):
            win = getattr(self, attr, None)
            if win is None:
                continue
            if not hasattr(win, "_refresh_files"):
                continue
            win._refresh_files()
            if hasattr(win, "_selected_file_idx") and hasattr(win, "_files"):
                idx = max(0, min(win._selected_file_idx, len(win._files) - 1))
                if win._files:
                    win._on_file_selected(idx)

    def _refresh_undo_item(self):
        if not hasattr(self, "_undo_item"):
            return
        stack = load_json(UNDO_FILE, []) if os.path.exists(UNDO_FILE) else []
        if not isinstance(stack, list):
            stack = []

        # Find the top operation that still has at least one reversible file
        top = None
        for op in reversed(stack):
            folder = op.get("folder", "")
            if any(os.path.exists(os.path.join(folder, r["new"]))
                   for r in op.get("renames", [])):
                top = op
                break

        if top is None:
            self._undo_item._menuitem.setEnabled_(False)
            self._undo_item.title = "    ↩  Undo Rename"
        elif top.get("type") == "batch":
            self._undo_item._menuitem.setEnabled_(True)
            self._undo_item.title = "    ↩  Undo Batch Rename"
        else:
            label = top["renames"][0]["new"] if top.get("renames") else "Last Rename"
            self._undo_item._menuitem.setEnabled_(True)
            self._undo_item.title = f"    ↩  Undo: {label}"

    # ── Tag mode ──────────────────────────────────────────────────────────────

    def open_tag_mode_v2(self, _):
        folder = self.session.get("folder", "")
        self._tag_window_v2 = TagWindowV2(folder, self.shortcuts, app=self)
        self._tag_window_v2.show()

    def open_stats(self, _=None):
        win = getattr(self, "_tag_window_v2", None)
        if win is None:
            folder = self.session.get("folder", "")
            win = TagWindowV2(folder, self.shortcuts, app=self)
            self._tag_window_v2 = win
        win.show()
        win._on_nav_select("stats")

    # ── Shortcut bank management ──────────────────────────────────────────────

    def manage_bank(self, bank: str):
        bank_names = {"players": "Players", "plays": "Plays", "ratings": "Ratings"}
        name = bank_names[bank]
        items = self.shortcuts.get(bank, [])

        while True:
            listing = "\n".join(
                f"{i+1}. [{sc['key']}]  {sc['label']}"
                for i, sc in enumerate(items)
            ) or "(none)"

            w = rumps.Window(
                title=f"Manage {name}",
                message=(f"Current {name}:\n\n{listing}\n\n"
                         "Enter number to EDIT,  d<number> to DELETE,  or 'add' to add new:"),
                default_text="", ok="Go", cancel="Done", dimensions=(340, 24)
            )
            r = w.run()
            if not r.clicked or not r.text.strip():
                break

            text = r.text.strip().lower()

            if text == "add":
                self._add_shortcut(bank, items)
                continue

            delete = text.startswith("d")
            num_str = text.lstrip("d").strip()
            try:
                idx = int(num_str) - 1
                assert 0 <= idx < len(items)
            except Exception:
                rumps.alert("Invalid", "Enter a valid number, d<number>, or 'add'.")
                continue

            if delete:
                sc = items[idx]
                if rumps.alert("Delete?", f"Delete [{sc['key']}] {sc['label']}?",
                               ok="Delete", cancel="Cancel") == 1:
                    items.pop(idx)
                    self.shortcuts[bank] = items
                    self._save_shortcuts()
            else:
                self._edit_shortcut(bank, items, idx)

    def _edit_shortcut(self, bank, items, idx):
        sc = dict(items[idx])
        key = ask("Hotkey", "Single key (e.g. 1, 2, q, w):", sc["key"])
        if key is None: return
        label = ask("Label", "Label for this shortcut (e.g. HAND, LAYUP, GOOD):", sc["label"])
        if label is None: return
        sc["key"] = key[:1]
        sc["label"] = label.upper()
        items[idx] = sc
        self.shortcuts[bank] = items
        self._save_shortcuts()
        rumps.alert("✅ Saved", f"[{sc['key']}]  {sc['label']}")

    def _add_shortcut(self, bank, items):
        key = ask("Hotkey", "Single key for this shortcut (e.g. 1, 2, q, w):")
        if not key: return
        label = ask("Label", "Label (e.g. HAND, LAYUP, GOOD, MISS):")
        if not label: return
        sc = {"key": key[:1], "label": label.upper()}
        items.append(sc)
        self.shortcuts[bank] = items
        self._save_shortcuts()
        rumps.alert("✅ Added", f"[{sc['key']}]  {sc['label']}")

    # ── Help ──────────────────────────────────────────────────────────────────

    def show_help(self, _):
        win = getattr(self, "_tag_window_v2", None)
        if win and hasattr(win, "_on_nav_select"):
            win.show()
            win._on_nav_select("help")
        else:
            self.open_tag_mode_v2(None)


if __name__ == "__main__":
    BasketballRenamerApp().run()
