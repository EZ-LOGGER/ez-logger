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
import sys
import traceback
import struct
import smtplib
import platform
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime

APP_VERSION = "1.0.6"

CRASH_LOG_DIR  = os.path.expanduser("~/.ezlogger/crashes")
CRASH_EMAIL_TO = "zachjkeding@gmail.com"
CRASH_EMAIL_FROM = "zachjkeding@gmail.com"

def _get_crash_email_password():
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", CRASH_EMAIL_FROM,
             "-s", "ez-logger-crash-reporter", "-w"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None

def _send_crash_email(subject, body):
    try:
        password = _get_crash_email_password()
        if not password:
            return
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"]    = CRASH_EMAIL_FROM
        msg["To"]      = CRASH_EMAIL_TO
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(CRASH_EMAIL_FROM, password)
            smtp.send_message(msg)
    except Exception:
        pass  # never let crash reporting crash the app

def _crash_handler(exc_type, exc_value, exc_tb):
    os.makedirs(CRASH_LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    body = (
        f"EZ Logger v{APP_VERSION} crash report\n"
        f"Time:    {datetime.now().isoformat()}\n"
        f"macOS:   {platform.mac_ver()[0]}\n"
        f"Python:  {sys.version.split()[0]}\n\n"
        f"{tb_str}"
    )
    log_path = os.path.join(CRASH_LOG_DIR, f"crash_{timestamp}.txt")
    try:
        with open(log_path, "w") as f:
            f.write(body)
    except Exception:
        pass
    _send_crash_email(f"EZ Logger v{APP_VERSION} crash — {timestamp}", body)
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _crash_handler

# ── Update checker ────────────────────────────────────────────────────────────
UPDATE_CHECK_URL = "https://api.github.com/repos/EZ-LOGGER/ez-logger/releases/latest"

_sparkle_controller = None   # SPUStandardUpdaterController, set by _init_sparkle()

def _init_sparkle():
    """Load Sparkle.framework and start the auto-updater (main thread only)."""
    global _sparkle_controller
    try:
        import objc
        from Foundation import NSBundle
        # In a built app the framework is in Contents/Frameworks/; in dev it's in Sparkle/
        main_bundle = NSBundle.mainBundle()
        candidates = [
            main_bundle.bundlePath() + "/Contents/Frameworks/Sparkle.framework",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "Sparkle", "Sparkle.framework"),
        ]
        fw_path = next((p for p in candidates if os.path.exists(p)), None)
        if fw_path is None:
            return
        bundle = NSBundle.bundleWithPath_(fw_path)
        if not bundle.load():
            return
        SPUStandardUpdaterController = objc.lookUpClass("SPUStandardUpdaterController")
        _sparkle_controller = (
            SPUStandardUpdaterController.alloc()
            .initWithStartingUpdater_updaterDelegate_userDriverDelegate_(True, None, None)
        )
    except Exception:
        pass

def _check_for_updates_bg(on_update_available):
    """Fetch latest GitHub release version in background. Calls on_update_available(version, url) if newer."""
    try:
        req = urllib.request.Request(UPDATE_CHECK_URL, headers={"User-Agent": f"EZLogger/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        tag = data.get("tag_name", "").lstrip("v")
        html_url = data.get("html_url", "")
        if not tag:
            return
        def _parse(v):
            try:
                return tuple(int(x) for x in v.split("."))
            except Exception:
                return (0,)
        if _parse(tag) > _parse(APP_VERSION):
            on_update_available(tag, html_url)
    except Exception:
        pass

# ── Paths ─────────────────────────────────────────────────────────────────────
CONFIG_FILE    = os.path.expanduser("~/.bball_renamer_v3_config.json")
SHORTCUTS_FILE = os.path.expanduser("~/.bball_renamer_v3_shortcuts.json")
SETTINGS_FILE  = os.path.expanduser("~/.bball_renamer_v3_settings.json")
UNDO_FILE      = os.path.expanduser("~/.bball_renamer_undo.json")
ROSTERS_FILE   = os.path.expanduser("~/.bball_renamer_v3_rosters.json")
STATS_FILE     = os.path.expanduser("~/.bball_renamer_v3_stats.json")
RENAME_LOG_FILE  = os.path.expanduser("~/.ezlogger/rename_log.json")
TAG_RECORDS_FILE = os.path.expanduser("~/.ezlogger/tag_records.json")
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
    "file_list_density":       "normal",   # row height of the clip lists: compact / normal / comfortable
    "file_list_width":         260,
    "file_list_columns":       {"visible": [], "widths": {}},   # info columns in the Log Mode file list
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
    # Onboarding
    "seen_tutorial":           False,
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
    "mens-soccer":       "MSOC",
    "womens-soccer":     "WSOC",
    "womens-volleyball": "WVB",
    "mens-lacrosse":     "MLAX",
    "field-hockey":      "FH",
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
    "MBB":   {"label": "🏀  Men's Basketball",    "code": "MBB",   "emoji": "🏀"},
    "WBB":   {"label": "🏀  Women's Basketball",  "code": "WBB",   "emoji": "🏀"},
    "MHK":   {"label": "🏒  Men's Ice Hockey",    "code": "MHK",   "emoji": "🏒"},
    "WHK":   {"label": "🏒  Women's Ice Hockey",  "code": "WHK",   "emoji": "🏒"},
    "FB":    {"label": "🏈  Football",             "code": "FB",    "emoji": "🏈"},
    "WLAX":  {"label": "🥍  Women's Lacrosse",    "code": "WLAX",  "emoji": "🥍"},
    "BASE":  {"label": "⚾  Baseball",             "code": "BASE",  "emoji": "⚾"},
    "SB":    {"label": "🥎  Softball",             "code": "SB",    "emoji": "🥎"},
    "MSOC":  {"label": "⚽  Men's Soccer",         "code": "MSOC",  "emoji": "⚽"},
    "WSOC":  {"label": "⚽  Women's Soccer",       "code": "WSOC",  "emoji": "⚽"},
    "WVB":   {"label": "🏐  Women's Volleyball",  "code": "WVB",   "emoji": "🏐"},
    "MLAX":  {"label": "🥍  Men's Lacrosse",      "code": "MLAX",  "emoji": "🥍"},
    "FH":    {"label": "🏑  Field Hockey",         "code": "FH",    "emoji": "🏑"},
}
SPORT_OPTIONS = list(SPORTS.keys())

# Sports the user added. Loaded from the config at launch (session["custom_sports"])
# and kept in step by set_custom_sports, so lookups never need the session.
_custom_sports = []
DEFAULT_SPORT_EMOJI = "🏅"


def set_custom_sports(entries):
    """Replace the user's own sports: [{"code", "name", "emoji", "slug"}]."""
    global _custom_sports
    clean = []
    for e in entries or []:
        code = str(e.get("code", "")).strip().upper()
        if code and code not in SPORTS and all(c["code"] != code for c in clean):
            clean.append({"code": code,
                          "name": str(e.get("name", "")).strip() or code,
                          "emoji": str(e.get("emoji", "")).strip() or DEFAULT_SPORT_EMOJI,
                          "slug": str(e.get("slug", "")).strip().strip("/")})
    _custom_sports = clean
    return clean


def all_sports():
    """Every sport, built-in first then the user's own: {code: info}. Each info has
    label, code, emoji, name, slug and custom."""
    out = {}
    slug_for = {c: sl for sl, c in SLUG_TO_CODE.items()}
    for code, info in SPORTS.items():
        out[code] = dict(info, name=info["label"].split("  ", 1)[-1].strip(),
                         slug=slug_for.get(code, ""), custom=False)
    for c in _custom_sports:
        out[c["code"]] = {"label": f"{c['emoji']}  {c['name']}", "code": c["code"],
                          "emoji": c["emoji"], "name": c["name"], "slug": c["slug"],
                          "custom": True}
    return out


def sport_info(code):
    """One sport's info. An unknown code shows as itself, never as another sport."""
    info = all_sports().get(code)
    if info:
        return info
    code = code or "?"
    return {"label": f"{DEFAULT_SPORT_EMOJI}  {code}", "code": code,
            "emoji": DEFAULT_SPORT_EMOJI, "name": code, "slug": "", "custom": False}


def sport_slug(code):
    """The sport's name in school-site URLs (/sports/<slug>/roster), or ''."""
    return sport_info(code)["slug"]


def suggest_sport_code(name, taken):
    """A code for a new sport from its name: letters and digits, up to 6, unique."""
    words = re.findall(r"[A-Za-z0-9]+", name.replace("'", ""))
    if not words:
        base = "SPORT"
    elif len(words) == 1:
        base = words[0][:4]
    else:
        lead = words[0][0] if words[0].lower() in ("mens", "men", "womens", "women") else ""
        rest = words[1:] if lead else words
        base = lead + "".join(w[:3] for w in rest)
    base = base.upper()[:6]
    code, n = base, 2
    while code in taken:
        suffix = str(n)
        code = base[:6 - len(suffix)] + suffix
        n += 1
    return code


def validate_sport_code(code, taken):
    """Return '' if code can be a new sport's code, else the reason it can't."""
    if not code:
        return "Enter a code."
    if not re.fullmatch(r"[A-Z0-9]{1,6}", code):
        return "Use 1 to 6 capital letters or digits, with no spaces."
    if code in taken:
        return f"{code} is already used by another sport."
    return ""

DEFAULT_SESSION = {
    "sport": "MBB", "opponent": "OPP",
    "videographer": "VID", "phase": "PRE", "folder": "",
    "naming_presets": DEFAULT_NAMING_PRESETS,
    "active_preset": 0,
    "sport_presets": {},
    "custom_steps": [
        {"id": "plays",   "label": "Play"},
        {"id": "ratings", "label": "Rating"},
    ],
}

# Starter Play and Rating labels, assigned hotkeys in order from TEMPLATE_KEYS.
_BASKETBALL_PLAYS = ["LAYUP", "THREE", "DUNK", "JUMPER", "FLOATER", "POST UP",
                     "DRIVE", "FREE THROW", "ASSIST", "REBOUND", "STEAL", "BLOCK"]
_SOCCER_PLAYS = ["GOAL", "ASSIST", "SHOT", "SAVE", "CROSS", "CORNER",
                 "FREE KICK", "PK", "TACKLE", "HEADER", "THROUGH BALL", "CLEARANCE"]
_HOCKEY_PLAYS = ["GOAL", "ASSIST", "SHOT", "SAVE", "HIT", "FACEOFF",
                 "BREAKAWAY", "ONE TIMER", "POWER PLAY", "PENALTY", "BLOCK", "TAKEAWAY"]
SPORT_PLAY_TEMPLATES = {
    "MBB":  _BASKETBALL_PLAYS,
    "WBB":  _BASKETBALL_PLAYS,
    "MHK":  _HOCKEY_PLAYS,
    "WHK":  _HOCKEY_PLAYS,
    "FB":   ["RUN", "PASS", "CATCH", "TOUCHDOWN", "SACK", "TACKLE",
             "INT", "FUMBLE", "KICKOFF", "PUNT", "FIELD GOAL", "BLOCK"],
    "WLAX": ["GOAL", "ASSIST", "SHOT", "SAVE", "DODGE", "DRAW",
             "GROUND BALL", "FREE POS", "CLEAR", "CHECK", "INTERCEPT", "CAUSED TO"],
    "BASE": ["PITCH", "STRIKEOUT", "SINGLE", "DOUBLE", "TRIPLE", "HOME RUN",
             "WALK", "BUNT", "STOLEN BASE", "DOUBLE PLAY", "CATCH", "THROW OUT"],
    "SB":   ["PITCH", "STRIKEOUT", "SINGLE", "DOUBLE", "TRIPLE", "HOME RUN",
             "BUNT", "SLAP", "STOLEN BASE", "DOUBLE PLAY", "CATCH", "THROW OUT"],
    "MSOC": _SOCCER_PLAYS,
    "WSOC": _SOCCER_PLAYS,
    "WVB":  ["KILL", "ATTACK", "SERVE", "ACE", "DIG", "BLOCK",
             "SET", "PASS", "RECEPTION", "TIP", "FREE BALL", "TRANSITION"],
    "MLAX": ["GOAL", "ASSIST", "SHOT", "SAVE", "DODGE", "FACEOFF",
             "GROUND BALL", "CLEAR", "RIDE", "CHECK", "EMO", "CAUSED TO"],
    "FH":   ["GOAL", "ASSIST", "SHOT", "SAVE", "PENALTY CORNER", "STROKE",
             "TACKLE", "INTERCEPT", "DRIBBLE", "AERIAL", "FREE HIT", "CIRCLE ENTRY"],
}
_BASKETBALL_RATINGS = ["GOOD", "MISS", "FOUL", "TO"]
_HOCKEY_RATINGS     = ["GOOD", "MISS", "SAVED", "BLOCKED", "TO"]
_DIAMOND_RATINGS    = ["GOOD", "SAFE", "OUT", "FOUL BALL", "ERROR"]
SPORT_RATING_TEMPLATES = {
    "MBB":  _BASKETBALL_RATINGS,
    "WBB":  _BASKETBALL_RATINGS,
    "MHK":  _HOCKEY_RATINGS,
    "WHK":  _HOCKEY_RATINGS,
    "FB":   ["GOOD", "NO GAIN", "LOSS", "FLAG", "TO"],
    "WLAX": ["GOOD", "MISS", "SAVED", "FOUL", "TO"],
    "BASE": _DIAMOND_RATINGS,
    "SB":   _DIAMOND_RATINGS,
    "MSOC": ["GOOD", "MISS", "SAVED", "BLOCKED", "FOUL", "TO"],
    "WSOC": ["GOOD", "MISS", "SAVED", "BLOCKED", "FOUL", "TO"],
    "WVB":  ["GOOD", "ERROR", "BLOCKED", "DUG", "OUT"],
    "MLAX": ["GOOD", "MISS", "SAVED", "FOUL", "TO"],
    "FH":   ["GOOD", "MISS", "SAVED", "FOUL", "TO"],
}
# No "0": the shortcut editors sort digit keys numerically, which would move it to the front.
TEMPLATE_KEYS = "123456789qwe"

def default_shortcuts(sport_key: str) -> dict:
    """Starter shortcuts for a sport with nothing saved. Returns fresh lists on every call,
    because callers keep the result and edit it in place."""
    def bank(labels):
        return [{"key": k, "label": label} for k, label in zip(TEMPLATE_KEYS, labels)]
    return {
        "players": [],
        "plays":   bank(SPORT_PLAY_TEMPLATES.get(sport_key, [])),
        "ratings": bank(SPORT_RATING_TEMPLATES.get(sport_key, ["GOOD", "MISS"])),
    }

PLAYER_STEP = {"id": "players", "label": "Player"}


def sport_steps(session, sport):
    """The logging steps for one sport, in order, as [{"id", "label"}]. Player is
    included wherever it sits, or missing when the sport has it turned off.
    A sport with no steps of its own yet uses the older shared list, which is
    no longer changed, so it looks exactly as it did before steps were per sport."""
    per = (session or {}).get("sport_steps") or {}
    steps = per.get(sport)
    if isinstance(steps, list) and steps:
        return steps
    legacy = (session or {}).get("custom_steps") or DEFAULT_SESSION["custom_steps"]
    return [dict(PLAYER_STEP)] + [dict(s) for s in legacy]


def own_sport_steps(session, sport):
    """The sport's step list, stored on the session so changes apply to that sport only.
    Call this before adding, removing, renaming or reordering steps."""
    per = session.setdefault("sport_steps", {})
    if not (isinstance(per.get(sport), list) and per[sport]):
        per[sport] = [dict(s) for s in sport_steps(session, sport)]
    return per[sport]


BLANK_SPORT_STEPS = [{"id": "players", "label": "Player"},
                     {"id": "plays",   "label": "Play"},
                     {"id": "ratings", "label": "Rating"}]


def create_custom_sport(session, shortcuts_data, entry, copy_from=None):
    """Add a user sport to the session: its registry entry, its own steps and empty
    or copied label banks. copy_from is another sport's code, or None for blank
    Player, Play and Rating steps. The roster is never copied. Returns the code."""
    import copy
    code = entry["code"]
    session.setdefault("custom_sports", []).append(
        {"code": code, "name": entry["name"],
         "emoji": entry.get("emoji") or DEFAULT_SPORT_EMOJI,
         "slug": entry.get("slug", "")})
    set_custom_sports(session["custom_sports"])
    if copy_from:
        steps = copy.deepcopy(sport_steps(session, copy_from))
        src = shortcuts_data.get(copy_from) or default_shortcuts(copy_from)
    else:
        steps = copy.deepcopy(BLANK_SPORT_STEPS)
        src = {}
    session.setdefault("sport_steps", {})[code] = steps
    banks = {"players": []}
    for st in steps:
        if st["id"] != "players":
            banks[st["id"]] = copy.deepcopy(src.get(st["id"], []))
    shortcuts_data[code] = banks
    return code


def remove_custom_sport(session, shortcuts_data, rosters, rosters_meta, key_presets, code):
    """Forget a user sport: its registry entry, steps, labels, naming presets, roster
    cache and hotkey layouts. Stats and video files are not touched. Built-in sports
    are refused. Returns True when the sport was removed."""
    if code in SPORTS:
        return False
    before = session.get("custom_sports", [])
    session["custom_sports"] = [c for c in before if c.get("code") != code]
    set_custom_sports(session["custom_sports"])
    for store in (session.get("sport_steps"), session.get("sport_presets"),
                  shortcuts_data, rosters, rosters_meta, key_presets):
        if isinstance(store, dict):
            store.pop(code, None)
    return len(session["custom_sports"]) != len(before)


def update_custom_sport(session, code, name=None, emoji=None, slug=None):
    """Change a user sport's name, emoji or school-site slug. The code never changes."""
    for c in session.get("custom_sports", []):
        if c.get("code") == code:
            if name is not None and name.strip():
                c["name"] = name.strip()
            if emoji is not None:
                c["emoji"] = emoji.strip() or DEFAULT_SPORT_EMOJI
            if slug is not None:
                c["slug"] = slug.strip().strip("/")
            set_custom_sports(session["custom_sports"])
            return True
    return False


def stat_segments(parts, part_steps, custom_indices, boundaries, step_order):
    """Split one logged clip into per-player segments for stats: [(parts, part_steps)].
    Typed custom text is left out. When Player isn't the first step, the labels picked
    before it describe the whole clip, so every chained player shares them unless
    that player's segment has its own label on the step."""
    part_steps = list(part_steps) + [None] * (len(parts) - len(part_steps))
    starts = [0] + sorted(boundaries)
    ends = sorted(boundaries) + [len(parts)]
    segs = []
    for a, b in zip(starts, ends):
        keep = [i for i in range(a, b) if i not in custom_indices]
        segs.append(([parts[i] for i in keep], [part_steps[i] for i in keep]))
    if len(segs) > 1 and "players" in step_order:
        before = set(step_order[:step_order.index("players")])
        shared = [(p, st) for p, st in zip(*segs[0]) if st in before]
        for k in range(1, len(segs)):
            sp, ss = segs[k]
            add = [(p, st) for p, st in shared if st not in ss]
            segs[k] = ([p for p, _ in add] + sp, [st for _, st in add] + ss)
    return segs


def stat_rows_for_segment(parts, part_steps, step_order, step_labels=None):
    """Turn one logged player-sequence into stats rows, using the step each label
    was picked on rather than its position. parts and part_steps are parallel lists
    with typed custom text already removed. Each player gets a row; the sport's
    last non-player step is the rating; the other steps together are the play.
    Returns [(player, play, rating, {step label: value})]."""
    if not parts:
        return []
    others = [s for s in step_order if s != "players"]
    rating_step = others[-1] if others else None
    by_step = {}
    for p, s in zip(parts, part_steps):
        by_step.setdefault(s, []).append(p)
    players = by_step.get("players") or [""]
    rating  = "_".join(by_step.get(rating_step, []))
    play    = "_".join(p for s in others if s != rating_step for p in by_step.get(s, []))
    labels  = step_labels or {}
    detail  = {labels.get(s, s): "_".join(v) for s, v in by_step.items() if s != "players"}
    return [(player, play, rating, detail) for player in players]


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

# ── Clip info columns (Log Mode file list) ────────────────────────────────────

# (id, header title, default width, right-aligned). "name" is always shown first.
FILE_INFO_COLUMNS = [
    ("duration",   "Duration",   62, True),
    ("timecode",   "Timecode",   90, False),
    ("fps",        "FPS",        52, True),
    ("resolution", "Resolution", 86, False),
    ("codec",      "Codec",      84, False),
    ("audio",      "Audio",      84, False),
    ("size",       "Size",       64, True),
    ("recorded",   "Recorded",  118, False),
]
FILE_INFO_IDS        = [c[0] for c in FILE_INFO_COLUMNS]
FILE_INFO_MIN_W      = 36
FILE_INFO_MAX_W      = 400

CODEC_NAMES = {
    "avc1": "H.264", "avc3": "H.264",
    "hvc1": "HEVC",  "hev1": "HEVC",
    "apch": "ProRes HQ", "apcn": "ProRes 422", "apcs": "ProRes LT",
    "apco": "ProRes Proxy", "ap4h": "ProRes 4444", "ap4x": "ProRes 4444 XQ",
    "aprn": "ProRes RAW", "aprh": "ProRes RAW HQ",
    "av01": "AV1", "vp09": "VP9", "mp4v": "MPEG-4",
    "mx5p": "MPEG-2", "xdvc": "XDCAM", "xd5c": "XDCAM HD422",
    "dvh1": "Dolby Vision", "jpeg": "Motion JPEG", "mjpa": "Motion JPEG",
}
AUDIO_CODEC_NAMES = {"aac ": "AAC", "lpcm": "PCM", "sowt": "PCM", "twos": "PCM",
                     "in24": "PCM", "in32": "PCM", "ac-3": "AC-3", "ec-3": "E-AC-3",
                     "alac": "ALAC", ".mp3": "MP3", "opus": "Opus"}

# Frame rates cameras actually use; a measured rate within 0.02 snaps to one of these
_COMMON_FPS = [(23.976, "23.976"), (24.0, "24"), (25.0, "25"), (29.97, "29.97"),
               (30.0, "30"), (47.952, "47.952"), (48.0, "48"), (50.0, "50"),
               (59.94, "59.94"), (60.0, "60"), (100.0, "100"), (119.88, "119.88"),
               (120.0, "120"), (239.76, "239.76"), (240.0, "240")]


def format_fps(fps):
    """23.976…, 29.97…, 60.0 → '23.976', '29.97', '60'. None or 0 → ''."""
    try:
        fps = float(fps)
    except (TypeError, ValueError):
        return ""
    if fps <= 0:
        return ""
    for val, label in _COMMON_FPS:
        if abs(fps - val) < 0.02:
            return label
    return f"{fps:.2f}".rstrip("0").rstrip(".")


def format_duration(seconds):
    """62.4 → '1:02', 3725 → '1:02:05'. Rounds down to whole seconds."""
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    if s < 0:
        return ""
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def format_bytes(n):
    """Finder-style decimal sizes: 1 200 000 000 → '1.2 GB'."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    if n < 0:
        return ""
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            if unit == "bytes":
                return f"{int(n)} bytes"
            return f"{n:.1f} {unit}" if n < 100 else f"{n:.0f} {unit}"
        n /= 1000.0
    return ""


def frames_to_timecode(frame, quanta, drop_frame=False):
    """Frame count since 00:00:00:00 → 'HH:MM:SS:FF' (';' before frames when drop-frame).
    quanta is the whole-number timecode rate (30 for 29.97, 60 for 59.94)."""
    try:
        frame, quanta = int(frame), int(quanta)
    except (TypeError, ValueError):
        return ""
    if quanta <= 0 or frame < 0:
        return ""
    drop = bool(drop_frame) and quanta % 30 == 0
    if drop:
        # SMPTE drop-frame: skip the first 2 (or 4 at 60) frame numbers of every
        # minute except each tenth minute
        d          = quanta // 15                 # 2 at 30, 4 at 60
        per_10min  = quanta * 600 - d * 9
        per_min    = quanta * 60 - d
        tens, rem  = divmod(frame, per_10min)
        if rem > d:
            frame += d * 9 * tens + d * ((rem - d) // per_min)
        else:
            frame += d * 9 * tens
    ff = frame % quanta
    ss = (frame // quanta) % 60
    mm = (frame // (quanta * 60)) % 60
    hh = (frame // (quanta * 3600)) % 24
    return f"{hh:02d}:{mm:02d}:{ss:02d}{';' if drop else ':'}{ff:02d}"


def file_info_value(info, col_id):
    """Display text for one info column. None info means still loading."""
    if info is None:
        return "…"
    if col_id == "duration":
        return format_duration(info.get("duration")) or "—"
    if col_id == "timecode":
        if info.get("tc_frame") is None:
            return "—"
        return frames_to_timecode(info["tc_frame"], info.get("tc_quanta"),
                                  info.get("tc_drop")) or "—"
    if col_id == "fps":
        return format_fps(info.get("fps")) or "—"
    if col_id == "resolution":
        w, h = info.get("width"), info.get("height")
        return f"{int(w)}×{int(h)}" if w and h else "—"
    if col_id == "codec":
        code = info.get("codec") or ""
        name = CODEC_NAMES.get(code, code.strip().upper())
        if not name:
            return "—"
        return f"{name} HDR" if info.get("hdr") else name
    if col_id == "audio":
        ch, rate = info.get("audio_channels"), info.get("audio_rate")
        if not ch:
            return "None" if info.get("has_audio") is False else "—"
        rate_s = f" · {rate / 1000:g} kHz" if rate else ""
        return f"{int(ch)} ch{rate_s}"
    if col_id == "size":
        return format_bytes(info.get("size")) or "—"
    if col_id == "recorded":
        dt = info.get("recorded")
        if not dt:
            return "—"
        try:
            return f"{dt.strftime('%b')} {dt.day}, {dt.year}  {dt.strftime('%H:%M')}"
        except Exception:
            return "—"
    return ""


def normalize_column_prefs(prefs):
    """Clean a saved file_list_columns setting: known ids only, in canonical order,
    widths clamped. Bad or missing data gives no info columns."""
    prefs   = prefs if isinstance(prefs, dict) else {}
    visible = prefs.get("visible")
    visible = set(visible) if isinstance(visible, (list, tuple)) else set()
    widths  = prefs.get("widths")
    widths  = widths if isinstance(widths, dict) else {}
    clean_w = {}
    for cid in FILE_INFO_IDS:
        w = widths.get(cid)
        if isinstance(w, (int, float)) and not isinstance(w, bool):
            clean_w[cid] = int(max(FILE_INFO_MIN_W, min(FILE_INFO_MAX_W, w)))
    return {"visible": [c for c in FILE_INFO_IDS if c in visible], "widths": clean_w}


def toggle_info_column(prefs, col_id):
    """Return new prefs with col_id shown if it was hidden, hidden if it was shown."""
    prefs = normalize_column_prefs(prefs)
    if col_id not in FILE_INFO_IDS:
        return prefs
    vis = set(prefs["visible"])
    vis.symmetric_difference_update({col_id})
    prefs["visible"] = [c for c in FILE_INFO_IDS if c in vis]
    return prefs


FILE_LIST_DENSITIES = {
    # setting value: (row height, name font size, info font size)
    "compact":     (20.0, 12.0, 11.0),
    "normal":      (26.0, 13.0, 11.5),
    "comfortable": (34.0, 14.0, 12.5),
}

SORT_LABELS = {"name_asc": "Name A → Z", "name_desc": "Name Z → A",
               "date_created": "Date Created", "date_modified": "Date Modified"}


def parse_sort_order(sort):
    """'name_asc' → ('name', True); 'duration_desc' → ('duration', False).
    The older 'date_created' / 'date_modified' values come back as themselves, ascending.
    Anything unknown falls back to ('name', True)."""
    if sort in ("date_created", "date_modified"):
        return sort, True
    if isinstance(sort, str) and "_" in sort:
        col, _, direction = sort.rpartition("_")
        if direction in ("asc", "desc") and (col == "name" or col in FILE_INFO_IDS):
            return col, direction == "asc"
    return "name", True


def next_sort_order(current, clicked_col):
    """Header click: the same column flips direction, a new column starts ascending."""
    col, asc = parse_sort_order(current)
    if col == clicked_col:
        return f"{clicked_col}_{'desc' if asc else 'asc'}"
    return f"{clicked_col}_asc"


def sort_order_label(sort):
    if sort in SORT_LABELS:
        return SORT_LABELS[sort]
    col, asc = parse_sort_order(sort)
    title = next((t for cid, t, _w, _r in FILE_INFO_COLUMNS if cid == col), "Name")
    return f"{title} {'↑' if asc else '↓'}"


def _info_sort_value(col, info, st):
    """Comparable value for one info column, or None when unknown."""
    if col == "size":
        return st.st_size if st is not None else None
    if not info:
        return None
    if col == "duration":
        return info.get("duration")
    if col == "timecode":
        f, q = info.get("tc_frame"), info.get("tc_quanta")
        return f / float(q) if f is not None and q else None
    if col == "fps":
        return info.get("fps")
    if col == "resolution":
        w, h = info.get("width"), info.get("height")
        return w * h if w and h else None
    if col == "codec":
        return file_info_value(info, "codec").lower() if info.get("codec") else None
    if col == "audio":
        return info.get("audio_channels") or (0 if info.get("has_audio") is False else None)
    if col == "recorded":
        dt = info.get("recorded")
        return dt.timestamp() if dt else None
    return None


def sort_file_entries(entries, sort, info_for=lambda path, st: None):
    """Sort [(Path, stat)] for the file list. info_for(path, st) returns cached clip
    info or None. Clips whose value is unknown go last in either direction;
    ties fall back to the name."""
    col, asc = parse_sort_order(sort)
    if sort == "date_created":
        return sorted(entries, key=lambda e: (getattr(e[1], "st_birthtime", e[1].st_mtime), e[0].name))
    if sort == "date_modified":
        return sorted(entries, key=lambda e: (e[1].st_mtime, e[0].name))
    if col == "name":
        return sorted(entries, key=lambda e: e[0].name, reverse=not asc)
    known, unknown = [], []
    for e in entries:
        v = _info_sort_value(col, info_for(e[0], e[1]), e[1])
        (unknown if v is None else known).append((v, e))
    known.sort(key=lambda ve: ve[1][0].name)                 # stable tie-break by name
    known.sort(key=lambda ve: ve[0], reverse=not asc)
    unknown.sort(key=lambda ve: ve[1][0].name)
    return [e for _v, e in known] + [e for _v, e in unknown]


FILE_LIST_MIN_W   = 160    # narrowest the Log Mode file list gets
FILE_LIST_NAME_MIN = 170   # keep at least this much for clip names before dropping info columns
CARDS_MIN_TOTAL   = 440    # Log Mode cards' minimum width (400) plus their side margins


def fit_file_list(preferred_w, max_w, columns, spacing=3.0,
                  min_w=FILE_LIST_MIN_W, name_min=FILE_LIST_NAME_MIN, chrome=24.0):
    """Fit the Log Mode file list into the room the window leaves beside the cards.
    columns is [(col_id, width)] of the info columns the user turned on, left to right.
    Returns (panel width, [col_ids to show]). While the preferred width fits, nothing
    changes. Otherwise the panel narrows to max_w (never below min_w), and info
    columns drop from the right until the clip names keep name_min."""
    ids = [c for c, _w in columns]
    if preferred_w <= max_w:
        return preferred_w, ids
    width = max(min_w, max_w)
    shown = list(columns)
    while shown and name_min + chrome + sum(w + spacing for _c, w in shown) > width:
        shown.pop()
    return width, [c for c, _w in shown]


def step_circle_scale(left_w, card_h, n_steps):
    """Scale for the Log Mode step circles (1.0 = 32 px circles, the original size).
    Limited by the height between the preview line and the hint, and by the width
    the row of circles needs, so circles and labels grow and shrink together."""
    band    = max(0.0, card_h - 100.0)          # between hint (32) and preview text (card_h-68)
    s_v     = band / 120.0                      # 1.0 at the default 220 px card
    n       = max(1, int(n_steps))
    # circles + gaps + the label overhang (up to 30 px) past the first and last circle
    s_h     = max(0.0, left_w - 40.0) / (n * 32.0 + (n - 1) * 60.0 + 60.0)
    return round(max(0.85, min(1.75, s_v, s_h)), 3)


def media_info_key(path):
    """Cache key that survives a rename (same inode) but not a re-export (new mtime/size)."""
    try:
        st = Path(path).stat()
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def _fourcc(n):
    try:
        return struct.pack(">I", int(n) & 0xFFFFFFFF).decode("latin-1")
    except Exception:
        return ""


def _read_start_timecode(asset, track):
    """Return (frame, quanta, drop_frame) from a tmcd track, or None."""
    import AVFoundation, CoreMedia
    fds = track.formatDescriptions()
    if not fds:
        return None
    fd     = fds[0]
    quanta = int(CoreMedia.CMTimeCodeFormatDescriptionGetFrameQuanta(fd) or 0)
    flags  = int(CoreMedia.CMTimeCodeFormatDescriptionGetTimeCodeFlags(fd) or 0)
    if quanta <= 0:
        return None
    reader, _err = AVFoundation.AVAssetReader.assetReaderWithAsset_error_(asset, None)
    if reader is None:
        return None
    out = AVFoundation.AVAssetReaderTrackOutput.assetReaderTrackOutputWithTrack_outputSettings_(
        track, None)
    if not reader.canAddOutput_(out):
        return None
    reader.addOutput_(out)
    if not reader.startReading():
        return None
    try:
        for _ in range(8):   # the reader can hand back empty buffers before the sample
            sb = out.copyNextSampleBuffer()
            if sb is None:
                return None
            bb = CoreMedia.CMSampleBufferGetDataBuffer(sb)
            if bb is None or CoreMedia.CMBlockBufferGetDataLength(bb) < 4:
                continue
            buf = bytearray(4)
            err, data = CoreMedia.CMBlockBufferCopyDataBytes(bb, 0, 4, buf)
            if err != 0:
                return None
            frame = struct.unpack(">i", bytes(data)[:4])[0]   # 'tmcd' samples are big-endian
            return frame, quanta, bool(flags & 1)            # kCMTimeCodeFlag_DropFrame
        return None
    finally:
        reader.cancelReading()


def clip_media_info(path):
    """Read duration, timecode, frame rate, size, codec, audio and recorded time.
    Runs off the main thread; touches no AppKit. Any field it can't read is None,
    and it never raises."""
    path = Path(path)
    info = {"duration": None, "fps": None, "width": None, "height": None,
            "codec": None, "hdr": False, "tc_frame": None, "tc_quanta": None,
            "tc_drop": False, "has_audio": None, "audio_channels": None,
            "audio_rate": None, "size": None, "recorded": None}
    try:
        info["size"] = path.stat().st_size
    except OSError:
        pass
    asset = None
    try:
        import AVFoundation, CoreMedia
        from Foundation import NSURL
        asset = AVFoundation.AVURLAsset.URLAssetWithURL_options_(
            NSURL.fileURLWithPath_(str(path)), None)
        d = asset.duration()
        if d.timescale and d.value >= 0 and not (d.flags & 0x10):   # not indefinite
            info["duration"] = d.value / float(d.timescale)
        tracks = list(asset.tracks() or [])
        info["has_audio"] = any(t.mediaType() == "soun" for t in tracks)
        for t in tracks:
            kind = t.mediaType()
            fds  = t.formatDescriptions() or []
            fd   = fds[0] if fds else None
            if kind == "vide" and info["width"] is None:
                try:
                    info["fps"] = float(t.nominalFrameRate()) or None
                    sz, tf = t.naturalSize(), t.preferredTransform()
                    w = abs(sz.width * tf.a + sz.height * tf.c)
                    h = abs(sz.width * tf.b + sz.height * tf.d)
                    info["width"], info["height"] = (round(w), round(h)) if w and h else (None, None)
                except Exception:
                    pass
                if fd is not None:
                    try:
                        info["codec"] = _fourcc(CoreMedia.CMFormatDescriptionGetMediaSubType(fd))
                        ext = CoreMedia.CMFormatDescriptionGetExtensions(fd) or {}
                        tfn = str(ext.get("CVImageBufferTransferFunction") or "")
                        info["hdr"] = ("2084" in tfn or "HLG" in tfn or "2100" in tfn)
                    except Exception:
                        pass
            elif kind == "soun" and info["audio_channels"] is None and fd is not None:
                try:
                    asbd = CoreMedia.CMAudioFormatDescriptionGetStreamBasicDescription(fd)
                    if asbd is not None:
                        info["audio_channels"] = int(asbd.mChannelsPerFrame) or None
                        info["audio_rate"]     = float(asbd.mSampleRate) or None
                except Exception:
                    pass
            elif kind == "tmcd" and info["tc_frame"] is None:
                try:
                    tc = _read_start_timecode(asset, t)
                    if tc:
                        info["tc_frame"], info["tc_quanta"], info["tc_drop"] = tc
                except Exception:
                    pass
        try:
            items = AVFoundation.AVMetadataItem.metadataItemsFromArray_withKey_keySpace_(
                asset.commonMetadata(),
                AVFoundation.AVMetadataCommonKeyCreationDate,
                AVFoundation.AVMetadataKeySpaceCommon)
            if items and len(items) > 0:
                val = str(items[0].stringValue() or "").strip()
                if len(val) >= 19:
                    info["recorded"] = datetime.strptime(
                        val[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    except Exception:
        pass
    if info["recorded"] is None:
        try:
            st = path.stat()
            info["recorded"] = datetime.fromtimestamp(
                getattr(st, "st_birthtime", None) or st.st_mtime)
        except Exception:
            pass
    return info

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
    def safe_trash(src: Path, folder_root: Path,
                   session: dict = None) -> tuple[bool, str]:
        """Move a clip to the Trash after the same checks as a rename.
        Returns (True, trash_path) or (False, reason). Never deletes permanently."""
        ok, reason = SafeRenamer.validate_file(src, folder_root)
        if not ok:
            SafeRenamer._log(src, Path("TRASH"), session, success=False,
                             error=reason, action="trash")
            return False, reason
        ok, trash_path, err = _trash_file(src)
        SafeRenamer._log(src, Path(trash_path or "TRASH"), session, success=ok,
                         error=err, action="trash")
        return (True, trash_path) if ok else (False, err)

    @staticmethod
    def safe_restore(trash_path: Path, dst: Path, folder_root: Path,
                     session: dict = None) -> tuple[bool, str]:
        """Put a trashed clip back at dst. Only moves files out of a Trash folder,
        only to the top level of the session folder, and never overwrites."""
        def fail(msg):
            SafeRenamer._log(trash_path, dst, session, success=False,
                             error=msg, action="restore")
            return False, msg

        if not _is_in_trash(trash_path):
            return fail("source is not in the Trash")
        if not os.path.isfile(str(trash_path)) or os.path.islink(str(trash_path)):
            return fail("no longer in the Trash")
        real_folder = os.path.realpath(str(folder_root))
        if not os.path.isdir(real_folder):
            return fail("session folder no longer exists")
        if os.path.realpath(str(Path(dst).parent)) != real_folder:
            return fail("destination is outside session folder boundary")
        if Path(dst).suffix.lower() not in SafeRenamer.ALLOWED_EXTENSIONS:
            return fail("not a supported video extension")
        if os.path.lexists(str(dst)):
            return fail(f"a file named {Path(dst).name} is already in the folder")
        try:
            Path(trash_path).rename(dst)
        except Exception as e:
            return fail(str(e))
        SafeRenamer._log(trash_path, dst, session, success=True, action="restore")
        return True, ""

    @staticmethod
    def check_destination(src: Path, dst: Path) -> str:
        """Return a warning string if dst already exists and is not src, else ''."""
        if src.resolve() == dst.resolve():
            return ""
        if dst.exists():
            return f"{dst.name} already exists in this folder"
        return ""

    @staticmethod
    def _log(src: Path, dst: Path, session: dict, success: bool, error: str = "",
             action: str = "rename"):
        """Append one JSON-lines entry to RENAME_LOG_FILE (pure append, O(1))."""
        s = session or {}
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action":    action,
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
    slug = sport_slug(sport_key)
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
        code_for = {i["slug"]: c for c, i in all_sports().items() if i["slug"]}
        for slug in dict.fromkeys(slugs):  # dedupe, preserve order
            code = code_for.get(slug)
            if code and code not in found:
                found[code] = f"{base}/sports/{slug}/roster"
    except Exception:
        pass
    # Fill in known sports not surfaced by discovery
    for code, info in all_sports().items():
        slug = info["slug"]
        if slug and code not in found:
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
    # Cache miss — scrape the user's school website; nothing to fetch until one is set
    base_url = load_json(SETTINGS_FILE, DEFAULT_SETTINGS).get("roster_base_url", "").strip()
    slug = sport_slug(sport_key)
    if not base_url or not slug:
        return []
    return fetch_roster_from_url(f"{base_url.rstrip('/')}/sports/{slug}/roster")

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

def tag_base_stem(stem, record):
    """Return the name to build labels onto, dropping labels from an earlier tag.
    Uses the base saved when the clip was tagged; a clip with no saved base keeps its name."""
    base = (record or {}).get("base")
    if base and (stem == base or stem.startswith(f"{base}_")):
        return base
    return stem.rstrip("_")


def save_tag_records(records):
    """Save the tagged-clip records. The rename already happened, so a failure here must not raise."""
    try:
        os.makedirs(os.path.dirname(TAG_RECORDS_FILE), exist_ok=True)
        save_json(TAG_RECORDS_FILE, records)
    except Exception:
        pass


def batch_base_stem(name, was_deduped):
    """Return a planned name's stem without the _2, _3 suffix batch rename may have added."""
    stem = os.path.splitext(name)[0]
    if was_deduped:
        stem = re.sub(r"_\d+$", "", stem)
    return stem.rstrip("_")


def select_batch_files(files, only_names=None):
    """Limit a batch rename to the selected clip names; no selection means every file."""
    if not only_names:
        return list(files)
    return [f for f in files if f.name in only_names]


def match_renames(old_inodes, new_inodes):
    """Find clips renamed outside the app. Takes {name: inode} before and after a
    scan; returns {old_name: new_name} for files whose inode moved to a new name."""
    gone  = {ino: n for n, ino in old_inodes.items() if n not in new_inodes}
    added = {ino: n for n, ino in new_inodes.items() if n not in old_inodes}
    return {gone[ino]: added[ino] for ino in gone if ino in added}


def move_records_for_renames(records, renames):
    """Carry tag records (base, colors, reject) over to clips renamed outside the
    app. Never replaces a record already stored under the new name. Returns True
    when anything moved."""
    moved = False
    for old, new in renames.items():
        if old in records and new not in records:
            records[new] = records.pop(old)
            moved = True
    return moved


def pick_selection(names, prev_name, renames, prev_idx):
    """Row to select after the list reloads: the same clip, followed through a
    rename, else the row where it was (clamped). -1 for an empty list."""
    if not names or (prev_name is None and prev_idx < 0):
        return -1   # nothing was selected, so don't pick a clip on the user's behalf
    for candidate in (prev_name, renames.get(prev_name)):
        if candidate and candidate in names:
            return names.index(candidate)
    return max(0, min(prev_idx, len(names) - 1))


def rejected_names(records, names):
    """Return the clip names in `names` that are marked as rejects."""
    return {n for n in names if (records.get(n) or {}).get("reject")}


def set_reject(records, name, on):
    """Mark or unmark a clip as a reject in the tag records, in place."""
    rec = dict(records.get(name) or {})
    if on:
        rec["reject"] = True
    else:
        rec.pop("reject", None)
    if rec:
        records[name] = rec
    else:
        records.pop(name, None)


def trash_targets(files, selected, rejected):
    """Clips the Naming tab's trash button acts on: the selection, else the rejects."""
    pick = selected if selected else rejected
    return [f for f in files if f.name in pick]


def undo_op_available(op):
    """True when at least one file in an undo entry can still be put back."""
    if op.get("type") == "trash":
        return any(i.get("trash_path") and os.path.exists(i["trash_path"])
                   for i in op.get("items", []))
    folder = op.get("folder", "")
    return any(os.path.exists(os.path.join(folder, r["new"]))
               for r in op.get("renames", []))


def _trash_file(path):
    """Move one file to the Trash with Finder's API. Returns (ok, trash_path, error).
    Never deletes: a volume with no Trash fails here instead."""
    try:
        from Foundation import NSFileManager, NSURL
        url = NSURL.fileURLWithPath_(str(path))
        ok, result_url, err = (NSFileManager.defaultManager()
                               .trashItemAtURL_resultingItemURL_error_(url, None, None))
        if ok:
            return True, (str(result_url.path()) if result_url is not None else ""), ""
        msg = str(err.localizedDescription()) if err is not None else ""
        return False, "", msg or "this drive has no Trash"
    except Exception as e:
        return False, "", str(e)


def _is_in_trash(path):
    parts = Path(os.path.realpath(str(path))).parts
    return ".Trash" in parts or ".Trashes" in parts


# ── Finder color labels ───────────────────────────────────────────────────────
FINDER_COLOR_HEX = {
    "Red": "#ff5f57", "Orange": "#ff9f0a", "Yellow": "#ffd60a", "Green": "#32d74b",
    "Blue": "#0a84ff", "Purple": "#bf5af2", "Gray": "#98989d",
}
FINDER_COLORS = list(FINDER_COLOR_HEX)


def finder_colors_for_tags(tag_parts, custom_indices, shortcuts, steps):
    """Return the Finder colors for a clip's labels, in the order they were applied.
    Player names and custom text never set a color; a branch child without its
    own color uses its parent's."""
    by_label = {}
    for bank in steps:
        if bank == "players":
            continue
        for sc in shortcuts.get(bank, []):
            color = sc.get("finder_color")
            if color:
                by_label[sc["label"].replace(" ", "_")] = color
            for child in sc.get("children", []):
                child_color = child.get("finder_color") or color
                if child_color:
                    by_label[child["label"].replace(" ", "_")] = child_color
    colors = []
    for i, part in enumerate(tag_parts):
        color = by_label.get(part)
        if color and i not in custom_indices and color not in colors:
            colors.append(color)
    return colors


def merged_finder_tags(existing, new_colors, previous_colors):
    """Work out a clip's Finder tags. Tags that are not colors are always kept.
    With no new colors, only colors the app applied earlier are removed, so a
    color the user set by hand in Finder stays."""
    if new_colors:
        return [t for t in existing if t not in FINDER_COLORS] + list(new_colors)
    return [t for t in existing if t not in previous_colors]


def get_finder_tags(path):
    try:
        from Foundation import NSURL, NSURLTagNamesKey
        url = NSURL.fileURLWithPath_(str(path))
        ok, tags, _err = url.getResourceValue_forKey_error_(None, NSURLTagNamesKey, None)
        return [str(t) for t in tags] if ok and tags else []
    except Exception:
        return []


def set_finder_tags(path, tags):
    try:
        from Foundation import NSURL, NSURLTagNamesKey
        url = NSURL.fileURLWithPath_(str(path))
        ok, _err = url.setResourceValue_forKey_error_(list(tags), NSURLTagNamesKey, None)
        return bool(ok)
    except Exception:
        return False


def trash_confirm_text(names, shown=5):
    """Title and body for the Move to Trash confirmation."""
    n = len(names)
    title = f"Move {n} clip{'' if n == 1 else 's'} to the Trash?"
    listed = "\n".join(names[:shown])
    if n > shown:
        listed += f"\n+{n - shown} more"
    body = (f"{listed}\n\nYou can put them back with Undo (⌘Z) "
            "or from the Trash in Finder.")
    return title, body


def _confirm_trash_alert(names):
    """Ask before trashing. Return is Cancel, so a stray keypress can't trash clips."""
    from AppKit import NSAlert, NSApp
    title, body = trash_confirm_text(names)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setInformativeText_(body)
    trash_btn  = alert.addButtonWithTitle_("Move to Trash")
    cancel_btn = alert.addButtonWithTitle_("Cancel")
    try:
        trash_btn.setHasDestructiveAction_(True)
    except Exception:
        pass
    trash_btn.setKeyEquivalent_("")
    cancel_btn.setKeyEquivalent_("\r")
    NSApp.activateIgnoringOtherApps_(True)
    return alert.runModal() == 1000   # NSAlertFirstButtonReturn


_folder_watch = None   # (FSEventStream, callback) for the session folder; one at a time


def _watch_folder(folder, on_change):
    """Call on_change on the main thread shortly after anything changes in folder,
    including the folder itself moving. Replaces any earlier watch. Returns False
    when FSEvents is unavailable; the window-focus refresh still covers that case."""
    global _folder_watch
    _stop_folder_watch()
    if not folder or not os.path.isdir(str(folder)):
        return False
    try:
        import FSEvents
        from CoreFoundation import CFRunLoopGetMain, kCFRunLoopDefaultMode

        def callback(stream, info, n, paths, flags, ids):
            try:
                on_change()
            except Exception:
                pass   # a refresh problem must never reach the crash reporter

        stream = FSEvents.FSEventStreamCreate(
            None, callback, None, [os.path.realpath(str(folder))],
            FSEvents.kFSEventStreamEventIdSinceNow, 0.3,
            FSEvents.kFSEventStreamCreateFlagWatchRoot)
        if stream is None:
            return False
        FSEvents.FSEventStreamScheduleWithRunLoop(
            stream, CFRunLoopGetMain(), kCFRunLoopDefaultMode)
        if not FSEvents.FSEventStreamStart(stream):
            FSEvents.FSEventStreamInvalidate(stream)
            return False
        _folder_watch = (stream, callback)   # keep the callback alive with the stream
        return True
    except Exception:
        _folder_watch = None
        return False


def _stop_folder_watch():
    global _folder_watch
    if _folder_watch is None:
        return
    stream, _cb = _folder_watch
    _folder_watch = None
    try:
        import FSEvents
        FSEvents.FSEventStreamStop(stream)
        FSEvents.FSEventStreamInvalidate(stream)
    except Exception:
        pass


_cmd_z_target  = None   # the open TagWindowV2; ⌘Z in its window runs the app's Undo
_cmd_z_monitor = None   # installed once, so reopening the window never stacks monitors


def _install_cmd_z_monitor(tag_window):
    """Make ⌘Z undo the last rename or trash from any tab, not just the Log Mode list.
    Text fields keep ⌘Z for undoing typing."""
    global _cmd_z_target, _cmd_z_monitor
    _cmd_z_target = tag_window
    if _cmd_z_monitor is not None:
        return
    from AppKit import NSEvent, NSText

    def handler(event):
        try:
            target = _cmd_z_target
            flags  = event.modifierFlags()
            if (target is None or event.window() is None
                    or event.window() != target.win
                    or not (flags & 0x100000)              # ⌘
                    or (flags & (0x20000 | 0x80000 | 0x40000))   # ⇧ ⌥ ⌃
                    or (event.charactersIgnoringModifiers() or "").lower() != "z"):
                return event
            if isinstance(target.win.firstResponder(), NSText):
                return event                               # editing text: its own undo
            target.handle_cmd_z()
            return None
        except Exception:
            return event

    _cmd_z_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
        1 << 10, handler)   # NSEventMaskKeyDown


def _style_reject_cell(owner, cell, row, text=None):
    """Strike through and dim a clip marked as a reject in a file list.
    text is the cell's string when it isn't the clip name (an info column)."""
    if not owner or not (0 <= row < len(owner._files)):
        return
    name = owner._files[row].name
    if name not in getattr(owner, "_rejected", ()):
        return
    if text is not None:
        name = text
    from AppKit import (NSAttributedString, NSMutableParagraphStyle, NSColor,
                        NSStrikethroughStyleAttributeName, NSFontAttributeName,
                        NSForegroundColorAttributeName, NSParagraphStyleAttributeName)
    para = NSMutableParagraphStyle.alloc().init()
    para.setLineBreakMode_(3)
    para.setAlignment_(cell.alignment())   # info columns can be right-aligned
    attrs = {
        NSStrikethroughStyleAttributeName: 1,
        NSForegroundColorAttributeName:    NSColor.tertiaryLabelColor(),
        NSParagraphStyleAttributeName:     para,
    }
    if cell.font() is not None:
        attrs[NSFontAttributeName] = cell.font()
    cell.setAttributedStringValue_(
        NSAttributedString.alloc().initWithString_attributes_(name, attrs))


def log_stat(session, player, play, rating, steps=None):
    """Append one tagged-clip event to STATS_FILE. steps is {step label: value}."""
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
    if steps:
        entry["steps"] = dict(steps)
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
EmojiField    = None
FileListDelegate     = None
NamingClipsDelegate  = None
NamingClipsTable     = None
TutorialOverlay      = None
QLDataSource         = None
SearchResultsDelegate = None
SearchResultsTable = None
HoverButton = None
add_hover_highlight = None
clear_hover_highlight = None
hover_press_down = None
hover_press_up = None
hover_dip = None
WindowDelegate       = None
FilePanelResizer     = None
VCenterTextCell      = None
NowCardResizer       = None
CardHeightResizer    = None

def make_objc_classes():
    global _classes_made, KeyTableView, NavItemView, ActionButton, PillButton, MenuTarget, MainCaller, FileListDelegate, NamingClipsDelegate, NamingClipsTable, QLDataSource, SearchResultsDelegate, SearchResultsTable, HoverButton, add_hover_highlight, clear_hover_highlight, hover_press_down, hover_press_up, hover_dip, WindowDelegate, FilePanelResizer, NowCardResizer, CardHeightResizer, TutorialOverlay, EmojiField, VCenterTextCell
    if _classes_made:
        return
    _classes_made = True

    import objc
    from AppKit import (
        NSObject, NSTableView, NSView, NSTextField, NSFont, NSColor,
        NSImage, NSImageView, NSMakeRect, NSButton,
    )

    _HOVER_KEY = "ez_logger_hover_tracker"

    def _depth_colors(pressed):
        """Gradient for a lit, raised button, or a shaded, pushed-in one."""
        from Quartz import CGColorCreateGenericRGB as rgb
        if pressed:
            return [rgb(0, 0, 0, 0.32), rgb(0, 0, 0, 0.04)]
        return [rgb(1, 1, 1, 0.26), rgb(1, 1, 1, 0.05)]

    def _scale_about_center(view, scale):
        """The backing layer scales from its anchor, so shift to keep the center fixed."""
        from Quartz import CATransform3DMakeTranslation, CATransform3DScale
        layer  = view.layer()
        size   = layer.bounds().size
        anchor = layer.anchorPoint()
        dx = size.width  * (0.5 - anchor.x) * (1 - scale)
        dy = size.height * (0.5 - anchor.y) * (1 - scale)
        return CATransform3DScale(CATransform3DMakeTranslation(dx, dy, 0), scale, scale, 1)

    def _motion_allowed():
        from AppKit import NSWorkspace
        return not NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion()

    class _HoverTracker(NSObject):
        """Gives a clickable view physical depth: it lifts on hover and pushes in on
        click. Only reacts in the key window, so nothing behind a dialog lights up.
        Press motion is animation only, so AppKit's layout never sees a changed frame."""
        _view_ref = None
        _overlay  = None
        _hovering = False
        _pressed  = False

        def mouseEntered_(self, _event):
            self.setOn_(True)

        def mouseExited_(self, _event):
            self.setOn_(False)

        def setOn_(self, on):
            self._hovering = bool(on)
            if not on:
                self._pressed = False
            self.refresh()

        def ensureOverlay(self):
            from Quartz import CAGradientLayer, CGColorCreateGenericRGB
            view = self._view_ref() if self._view_ref else None
            if view is None or view.layer() is None:
                return None
            if self._overlay is None:
                overlay = CAGradientLayer.layer()
                overlay.setFrame_(view.layer().bounds())
                overlay.setCornerRadius_(view.layer().cornerRadius() or 6.0)
                overlay.setBorderWidth_(0.75)
                overlay.setBorderColor_(CGColorCreateGenericRGB(1, 1, 1, 0.22))
                overlay.setOpacity_(0.0)
                overlay.setAutoresizingMask_(2 | 16)  # follows width and height
                view.layer().addSublayer_(overlay)
                self._overlay = overlay
            return self._overlay

        def refresh(self):
            from Quartz import CATransaction
            overlay = self.ensureOverlay()
            if overlay is None:
                return
            layer = self._view_ref().layer()
            CATransaction.begin()
            CATransaction.setAnimationDuration_(0.12)
            overlay.setColors_(_depth_colors(self._pressed))
            overlay.setOpacity_(1.0 if (self._hovering or self._pressed) else 0.0)
            CATransaction.commit()
            raised = self._hovering and not self._pressed
            layer.setMasksToBounds_(False)
            layer.setShadowOpacity_(0.45 if raised else 0.0)
            layer.setShadowRadius_(5.0)
            layer.setShadowOffset_((0, -2))

    def _tracker(view):
        return objc.getAssociatedObject(view, _HOVER_KEY)

    def add_hover_highlight(view):
        """Make `view` lift on hover. Safe to call more than once."""
        from AppKit import NSTrackingArea
        from Foundation import NSZeroRect
        if _tracker(view) is not None:
            return
        view.setWantsLayer_(True)
        tracker = _HoverTracker.alloc().init()
        tracker._view_ref = objc.WeakRef(view)
        objc.setAssociatedObject(view, _HOVER_KEY, tracker)  # lives as long as the view
        options = 0x01 | 0x20 | 0x200  # entered/exited, key window only, visible rect
        view.addTrackingArea_(NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            NSZeroRect, options, tracker, None))

    def clear_hover_highlight(view):
        tracker = _tracker(view)
        if tracker is not None:
            tracker.setOn_(False)

    def hover_press_down(view):
        """Push in and hold, for controls that act when the mouse is released."""
        from AppKit import NSValue
        from Quartz import CABasicAnimation
        tracker = _tracker(view)
        if tracker is None:
            return
        tracker._pressed = True
        tracker.refresh()
        if _motion_allowed():
            anim = CABasicAnimation.animationWithKeyPath_("transform")
            anim.setToValue_(NSValue.valueWithCATransform3D_(_scale_about_center(view, 0.95)))
            anim.setDuration_(0.07)
            anim.setFillMode_("forwards")
            anim.setRemovedOnCompletion_(False)
            view.layer().addAnimation_forKey_(anim, "ez_press")

    def hover_press_up(view):
        """Spring back from hover_press_down."""
        from AppKit import NSValue
        from Quartz import CASpringAnimation, CATransform3DIdentity
        tracker = _tracker(view)
        if tracker is None:
            return
        tracker._pressed = False
        tracker.refresh()
        if _motion_allowed():
            spring = CASpringAnimation.animationWithKeyPath_("transform")
            spring.setFromValue_(NSValue.valueWithCATransform3D_(_scale_about_center(view, 0.95)))
            spring.setToValue_(NSValue.valueWithCATransform3D_(CATransform3DIdentity))
            spring.setStiffness_(420.0)
            spring.setDamping_(24.0)
            spring.setDuration_(spring.settlingDuration())
            view.layer().addAnimation_forKey_(spring, "ez_press")  # replaces the hold

    def hover_dip(view):
        """One complete push-in and bounce, for controls that act on mouse down. It can't
        wait for mouse up: the action may open a dialog that swallows the release."""
        from AppKit import NSValue
        from Quartz import CAKeyframeAnimation
        tracker = _tracker(view)
        if tracker is None:
            return
        overlay = tracker.ensureOverlay()
        if overlay is None:
            return
        times = [0.0, 0.3, 0.7, 1.0]
        lit, shaded = _depth_colors(False), _depth_colors(True)
        tint = CAKeyframeAnimation.animationWithKeyPath_("colors")
        tint.setValues_([lit, shaded, lit, lit])
        tint.setKeyTimes_(times)
        tint.setDuration_(0.24)
        overlay.addAnimation_forKey_(tint, "ez_dip")
        if _motion_allowed():
            dip = CAKeyframeAnimation.animationWithKeyPath_("transform")
            dip.setValues_([NSValue.valueWithCATransform3D_(_scale_about_center(view, k))
                            for k in (1.0, 0.94, 1.015, 1.0)])
            dip.setKeyTimes_(times)
            dip.setDuration_(0.24)
            view.layer().addAnimation_forKey_(dip, "ez_dip")

    class _KeyTableView(NSTableView):
        owner = None

        def keyDown_(self, event):
            chars = event.characters() or ""
            # ⌘Z → undo (NSCommandKeyMask = 0x100000)
            if (chars == "z" and (event.modifierFlags() & 0x100000)
                    and not (event.modifierFlags() & 0x20000)):   # plain ⌘Z, not ⇧⌘Z
                if self.owner and hasattr(self.owner, "handle_cmd_z"):
                    self.owner.handle_cmd_z()
                return
            # ⌘⌫ → move the current clip to the Trash
            if chars == "\x7f" and (event.modifierFlags() & 0x100000):
                if self.owner and hasattr(self.owner, "_trash_current_clip"):
                    self.owner._trash_current_clip()
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
            add_hover_highlight(self)
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
            hover_dip(self)
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
            add_hover_highlight(self)
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
            hover_press_down(self)

        def mouseUp_(self, event):
            was_pressed = self._pressed
            self._pressed = False
            self.layer().setBackgroundColor_(_hex_color(self._bg).CGColor())
            hover_press_up(self)
            if was_pressed and self._action is not None:
                self._action()

        def viewDidHide(self):
            clear_hover_highlight(self)  # hidden views never get a mouse-exit

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
            if handler is not None:  # pills without a handler are not clickable
                add_hover_highlight(self)

        def hitTest_(self, point):
            result = objc.super(_PillButton, self).hitTest_(point)
            if result is not None:
                return self
            return None

        def viewDidHide(self):
            clear_hover_highlight(self)  # hidden views never get a mouse-exit

        def mouseDown_(self, event):
            if self._handler is not None:
                hover_dip(self)
                self._handler(self, event)

    PillButton = _PillButton

    class _MenuTarget(NSObject):
        def menuPicked_(self, sender):
            cb = getattr(self, "_callback", None)
            if cb is not None:
                cb(sender.representedObject())

    MenuTarget = _MenuTarget

    class _HoverButton(NSButton):
        def mouseDown_(self, event):
            hover_dip(self)
            objc.super(_HoverButton, self).mouseDown_(event)

    HoverButton = _HoverButton

    class _MainCaller(NSObject):
        def fire_(self, _):
            cb = getattr(self, "_cb", None)
            if callable(cb):
                cb()

    MainCaller = _MainCaller

    class _EmojiField(NSTextField):
        """Text field that opens the system emoji picker when clicked or tabbed into.
        Its text is selected first, so the picked emoji replaces the old one."""
        def becomeFirstResponder(self):
            ok = objc.super(_EmojiField, self).becomeFirstResponder()
            if ok:
                # After the field editor is in place; modal mode so it fires inside an alert
                self.performSelector_withObject_afterDelay_inModes_(
                    "openEmojiPicker:", None, 0.0,
                    ["NSDefaultRunLoopMode", "NSModalPanelRunLoopMode"])
            return ok

        def openEmojiPicker_(self, _):
            ed = self.currentEditor()
            if ed is not None:
                ed.selectAll_(None)
            from AppKit import NSApp
            NSApp.orderFrontCharacterPalette_(None)

        def textDidChange_(self, note):
            objc.super(_EmojiField, self).textDidChange_(note)
            # Keep one emoji: the newest pick
            val = self.stringValue()
            if val.length() > 1:
                r = val.rangeOfComposedCharacterSequenceAtIndex_(val.length() - 1)
                last = val.substringWithRange_(r)
                if last != val:
                    self.setStringValue_(last)

    EmojiField = _EmojiField

    from AppKit import NSTextFieldCell

    class _VCenterTextCell(NSTextFieldCell):
        """Table text cell that draws its text centred in the row, whatever the row height."""
        def drawInteriorWithFrame_inView_(self, frame, view):
            h = self.cellSizeForBounds_(frame).height
            if 0 < h < frame.size.height:
                frame = NSMakeRect(frame.origin.x,
                                   frame.origin.y + (frame.size.height - h) / 2.0,
                                   frame.size.width, h)
            objc.super(_VCenterTextCell, self).drawInteriorWithFrame_inView_(frame, view)

    VCenterTextCell = _VCenterTextCell

    class _FileListDelegate(NSObject):
        owner = None

        def numberOfRowsInTableView_(self, tv):
            return len(self.owner._files) if self.owner else 0

        def tableView_objectValueForTableColumn_row_(self, tv, col, row):
            if self.owner and row < len(self.owner._files):
                cid = col.identifier() if col is not None else "name"
                if cid == "name":
                    return self.owner._files[row].name
                return self.owner._file_info_text(row, cid)
            return ""

        def tableView_willDisplayCell_forTableColumn_row_(self, tv, cell, col, row):
            cid = col.identifier() if col is not None else "name"
            if cid == "name":
                cell.setLineBreakMode_(3)  # NSLineBreakByTruncatingHead — shows end of filename where labels are
                _style_reject_cell(self.owner, cell, row)
            else:
                cell.setLineBreakMode_(4)  # truncate tail
                _style_reject_cell(self.owner, cell, row,
                                   text=self.owner._file_info_text(row, cid) if self.owner else "")

        def tableView_didClickTableColumn_(self, tv, col):
            if self.owner and col is not None:
                self.owner._on_file_header_clicked(col.identifier())

        def tableViewColumnDidResize_(self, notif):
            col = notif.userInfo().get("NSTableColumn") if notif.userInfo() else None
            if self.owner and col is not None and col.identifier() != "name":
                self.owner._on_info_column_resized(col.identifier(), col.width())

        def tableViewSelectionDidChange_(self, notif):
            if not self.owner:
                return
            row = notif.object().selectedRow()
            if row >= 0:
                self.owner._on_file_selected(row)

    FileListDelegate = _FileListDelegate

    class _NamingClipsDelegate(NSObject):
        owner       = None
        _suppressed = False

        def numberOfRowsInTableView_(self, tv):
            return len(self.owner._files) if self.owner else 0

        def tableView_objectValueForTableColumn_row_(self, tv, col, row):
            if self.owner and row < len(self.owner._files):
                return self.owner._files[row].name
            return ""

        def tableView_willDisplayCell_forTableColumn_row_(self, tv, cell, col, row):
            cell.setLineBreakMode_(3)  # truncate the head so the end of the name stays visible
            _style_reject_cell(self.owner, cell, row)

        def tableViewSelectionDidChange_(self, notif):
            if self.owner and not self._suppressed:
                self.owner._on_naming_selection_changed()

    NamingClipsDelegate = _NamingClipsDelegate

    class _NamingClipsTable(NSTableView):
        owner = None

        def acceptsFirstResponder(self):
            return True

        def mouseDown_(self, event):
            point = self.convertPoint_fromView_(event.locationInWindow(), None)
            row   = self.rowAtPoint_(point)
            objc.super(_NamingClipsTable, self).mouseDown_(event)
            if self.owner and 0 <= row < len(self.owner._files):
                self.owner._on_naming_row_clicked(row)

        def keyDown_(self, event):
            chars    = event.characters() or ""
            key_code = event.keyCode()
            if chars == " ":
                if self.owner:
                    self.owner._naming_quicklook()
                return
            if chars == "\x1b":   # ESC
                close_quicklook()
                return
            # ⌘⌫ → trash the selected clips (selection only, never the rejects)
            if chars == "\x7f" and (event.modifierFlags() & 0x100000):
                if self.owner and self.owner._naming_selected:
                    self.owner._naming_trash()
                return
            is_arrow = key_code in (125, 126)   # down=125, up=126
            objc.super(_NamingClipsTable, self).keyDown_(event)
            if is_arrow and self.owner:
                row = self.selectedRow()
                if 0 <= row < len(self.owner._files):
                    self.owner._on_naming_row_clicked(row)

    NamingClipsTable = _NamingClipsTable

    class _SearchResultsDelegate(NSObject):
        owner = None

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

    SearchResultsDelegate = _SearchResultsDelegate

    class _SearchResultsTable(NSTableView):
        owner = None

        def mouseDown_(self, event):
            # Picks on the click itself, not on a selection change: the top match
            # is already highlighted, so clicking it would not change the selection.
            point = self.convertPoint_fromView_(event.locationInWindow(), None)
            row   = self.rowAtPoint_(point)
            owner = self.owner
            if owner and 0 <= row < len(owner._search_matches):
                owner._search_idx = row
                owner._confirm_search_selection()

    SearchResultsTable = _SearchResultsTable

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

        def windowDidBecomeKey_(self, notif):
            # Back from Finder: catch changes FSEvents can miss (network drives)
            if self.owner and hasattr(self.owner, "_on_folder_changed"):
                self.owner._on_folder_changed()

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
            # Start from the width on screen, which is narrower than the saved one
            # while the window is too small for it
            panel = getattr(self.owner, "_file_list_panel", None)
            self._drag_start_w = float(panel.frame().size.width if panel is not None
                                       else self.owner._file_list_w)

        def mouseDragged_(self, event):
            if self.owner is None:
                return
            dx  = event.locationInWindow().x - self._drag_start_x
            W   = self.owner.win.frame().size.width
            max_w = max(FILE_LIST_MIN_W, self.owner._file_list_max_w(W))   # cards keep their room
            new_w = max(FILE_LIST_MIN_W, min(max_w, self._drag_start_w + dx))
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

    # ── Tutorial overlay ──────────────────────────────────────────────────────
    class _TutorialOverlay(NSView):
        """Full-window dim + spotlight cutout + step card for first-run tutorial."""

        def initWithFrame_(self, frame):
            self = objc.super(_TutorialOverlay, self).initWithFrame_(frame)
            if self is None:
                return None
            self._spotlight_rect = None   # NSRect of the highlighted region (window coords)
            self._card = None             # the step card NSView
            self.setWantsLayer_(True)
            self.layer().setZPosition_(9999)
            return self

        def acceptsFirstMouse_(self, event):
            return True

        def mouseDown_(self, event):
            # Clicks outside the spotlight are eaten (no pass-through)
            pass

        # ----- drawing -----
        def drawRect_(self, dirty):
            from AppKit import NSColor, NSBezierPath, NSRectFill, NSGraphicsContext
            import Quartz
            ctx = NSGraphicsContext.currentContext().CGContext()
            bounds = self.bounds()
            # Dark scrim
            Quartz.CGContextSetRGBFillColor(ctx, 0, 0, 0, 0.62)
            Quartz.CGContextFillRect(ctx, bounds)
            # Spotlight cutout — clear the highlighted rect
            sr = self._spotlight_rect
            if sr is not None:
                Quartz.CGContextSetBlendMode(ctx, Quartz.kCGBlendModeClear)
                r = 10.0
                Quartz.CGContextBeginPath(ctx)
                Quartz.CGContextMoveToPoint(ctx, sr.origin.x + r, sr.origin.y)
                Quartz.CGContextAddArcToPoint(ctx, sr.origin.x + sr.size.width, sr.origin.y, sr.origin.x + sr.size.width, sr.origin.y + sr.size.height, r)
                Quartz.CGContextAddArcToPoint(ctx, sr.origin.x + sr.size.width, sr.origin.y + sr.size.height, sr.origin.x, sr.origin.y + sr.size.height, r)
                Quartz.CGContextAddArcToPoint(ctx, sr.origin.x, sr.origin.y + sr.size.height, sr.origin.x, sr.origin.y, r)
                Quartz.CGContextAddArcToPoint(ctx, sr.origin.x, sr.origin.y, sr.origin.x + sr.size.width, sr.origin.y, r)
                Quartz.CGContextClosePath(ctx)
                Quartz.CGContextFillPath(ctx)
                Quartz.CGContextSetBlendMode(ctx, Quartz.kCGBlendModeNormal)

        def setSpotlightRect_cardTitle_body_step_total_onNext_onSkip_(
                self, rect, title, body, step, total, next_cb, skip_cb):
            from AppKit import (NSView, NSTextField, NSFont, NSColor,
                                NSMakeRect, NSMakeSize, NSTextAlignment)
            self._spotlight_rect = rect
            self.setNeedsDisplay_(True)

            # Remove old card
            if self._card is not None:
                self._card.removeFromSuperview()

            CARD_W  = 340.0
            CARD_H  = 190.0
            PAD     = 20.0
            bounds  = self.bounds()

            # Position card below spotlight (or above if near bottom)
            if rect is not None:
                cx = rect.origin.x + rect.size.width / 2 - CARD_W / 2
                # Try below
                card_y = rect.origin.y - CARD_H - 16
                if card_y < 20:
                    card_y = rect.origin.y + rect.size.height + 16
            else:
                cx = (bounds.size.width - CARD_W) / 2
                card_y = (bounds.size.height - CARD_H) / 2

            cx = max(16, min(cx, bounds.size.width - CARD_W - 16))
            card_y = max(16, min(card_y, bounds.size.height - CARD_H - 16))

            card = NSView.alloc().initWithFrame_(NSMakeRect(cx, card_y, CARD_W, CARD_H))
            card.setWantsLayer_(True)
            card.layer().setBackgroundColor_(_hex_color("#1c1c1e").CGColor())
            card.layer().setCornerRadius_(14.0)
            card.layer().setBorderWidth_(0.5)
            card.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.15).CGColor())

            # Step dots
            DOT_R = 4.0
            dot_spacing = 12.0
            dots_total_w = total * DOT_R * 2 + (total - 1) * (dot_spacing - DOT_R * 2)
            dot_x = (CARD_W - dots_total_w) / 2
            dot_y = CARD_H - PAD - DOT_R * 2
            for i in range(total):
                dot = NSView.alloc().initWithFrame_(NSMakeRect(dot_x, dot_y, DOT_R * 2, DOT_R * 2))
                dot.setWantsLayer_(True)
                dot.layer().setCornerRadius_(DOT_R)
                if i == step - 1:
                    dot.layer().setBackgroundColor_(_hex_color(COLOR_CRIMSON).CGColor())
                else:
                    dot.layer().setBackgroundColor_(_hex_color_alpha("#ffffff", 0.25).CGColor())
                card.addSubview_(dot)
                dot_x += dot_spacing

            # Title
            title_lbl = NSTextField.labelWithString_(title)
            title_lbl.setFont_(NSFont.boldSystemFontOfSize_(15))
            title_lbl.setTextColor_(NSColor.labelColor())
            title_lbl.setFrame_(NSMakeRect(PAD, dot_y - 8 - 20, CARD_W - PAD * 2, 20))
            card.addSubview_(title_lbl)

            # Body
            body_lbl = NSTextField.wrappingLabelWithString_(body)
            body_lbl.setFont_(NSFont.systemFontOfSize_(13))
            body_lbl.setTextColor_(NSColor.secondaryLabelColor())
            body_lbl.setFrame_(NSMakeRect(PAD, dot_y - 8 - 20 - 52, CARD_W - PAD * 2, 52))
            card.addSubview_(body_lbl)

            # Buttons
            BTN_H  = 32.0
            BTN_W  = 110.0
            SKIP_W = 60.0
            btn_y  = PAD

            next_btn = ActionButton.alloc().initWithFrame_(
                NSMakeRect(CARD_W - PAD - BTN_W, btn_y, BTN_W, BTN_H))
            next_lbl = "Finish" if step == total else "Next  →"
            next_btn.configureTitle_bg_press_action_(
                next_lbl, COLOR_CRIMSON, "#6b1a26", next_cb)
            card.addSubview_(next_btn)

            skip_btn = ActionButton.alloc().initWithFrame_(
                NSMakeRect(CARD_W - PAD - BTN_W - 10 - SKIP_W, btn_y, SKIP_W, BTN_H))
            skip_btn.configureTitle_bg_press_action_(
                "Skip", "#2c2c2e", "#232325", skip_cb)
            card.addSubview_(skip_btn)

            self.addSubview_(card)
            self._card = card

    TutorialOverlay = _TutorialOverlay

# ── Tag Window v2 (Adobe-CC inspired redesign) ───────────────────────────────

class TagWindowV2:
    NAV_ITEMS = [
        ("session",  "pencil",                    "Naming"),
        ("tag",      "bolt.fill",                "Log Mode"),
        ("players",  "person.2.fill",            "Team"),
        (None, None, None),
        ("labels",   "list.bullet",              "Labels"),
        ("stats",    "chart.bar.fill",           "Stats"),
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
        self.current_section = "session"
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
        self._tag_part_steps         = []    # step id each _tag_parts entry was picked on
        self._sport_setup            = None  # {"code", "prev"} while Add Sport is on step 2
        self._chain_btns             = {}    # {bank: PillButton} for "+ Player (+)" buttons
        # Search-mode state
        self._search_enabled     = False   # toggled by top-bar switch
        self._naming_selected    = set()   # clip names chosen in the Naming tab for Batch Rename
        self._search_mode        = False
        self._search_text        = ""
        self._search_matches     = []
        self._search_idx         = 0
        self._rebuild_steps()
        self._build_window()

    def _current_sport(self):
        return self.app.session.get("sport", "MBB") if self.app else "MBB"

    def _sport_step_list(self):
        """This sport's steps as [{"id", "label"}], Player included where it sits."""
        config = self.app.session if self.app else DEFAULT_SESSION
        return sport_steps(config, self._current_sport())

    def _own_step_list(self):
        """This sport's steps, stored so edits apply to this sport only."""
        if not self.app:
            return self._sport_step_list()
        return own_sport_steps(self.app.session, self._current_sport())

    def _non_player_steps(self):
        return [s for s in self._sport_step_list() if s["id"] != "players"]

    def _rebuild_steps(self):
        steps = self._sport_step_list()
        self._steps = [s["id"] for s in steps]
        self._step_labels_map = {"players": "Player"}
        for st in steps:
            if st["id"] != "players":
                self._step_labels_map[st["id"]] = st["label"]

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
        n = len(self._steps)
        # One scale for circle, number, label and spacing, so they keep their proportions
        sc        = step_circle_scale(LEFT_W, card_h, n)
        circle_d  = round(32 * sc)
        lbl_drop  = 18 * sc            # label sits this far below the circle's bottom
        lbl_h     = round(14 * sc)
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

        gap = min(70 * sc, max(20 * sc, (LEFT_W - 40 - circle_d * n) / max(1, n - 1)))
        gap = int(gap)
        # Labels are wider than circles; tighten the gap until the first and last
        # labels stay inside the left column (not over the divider)
        def _row_span(g):
            overhang = max(0.0, min(60 * sc, g - 10 * sc)) / 2
            return circle_d * n + g * (n - 1) + 2 * overhang
        while gap > int(20 * sc) and _row_span(gap) > LEFT_W - 24:
            gap -= 1
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
            c.layer().setBorderWidth_(max(1.0, 1.5 * sc))
            c.setClickHandler_(
                lambda v, e, idx=i: self._set_step_state(active=idx))
            card.addSubview_(c)

            num_lbl = NSTextField.labelWithString_(str(i + 1))
            num_lbl.setFont_(NSFont.boldSystemFontOfSize_(13 * sc))
            num_lbl.sizeToFit()
            nf = num_lbl.frame()
            num_lbl.setFrame_(NSMakeRect(
                (circle_d - nf.size.width) / 2,
                (circle_d - nf.size.height) / 2,
                nf.size.width, nf.size.height))
            c.addSubview_(num_lbl)

            # Truncate label to fit — wider gap → more room (character width grows with scale)
            max_chars = max(4, int(gap // (7 * sc)))
            display   = label[:max_chars] if len(label) > max_chars else label
            step_lbl  = NSTextField.labelWithString_(display)
            step_lbl.setFont_(NSFont.systemFontOfSize_(10 * sc))
            step_lbl.setAlignment_(2)
            lbl_w = circle_d + min(60 * sc, gap - 10 * sc)
            step_lbl.setFrame_(NSMakeRect(
                x - (lbl_w - circle_d) / 2, circles_y - lbl_drop, lbl_w, lbl_h))
            card.addSubview_(step_lbl)

            self._now_step_circles.append((c, num_lbl))
            self._now_step_labels.append(step_lbl)

        # New circles start unstyled; give them the current step's colors again
        self._paint_step_circles(*getattr(self, "_step_state", (-1, ())))
        self._raise_search_panel()

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
        self.win.setTitle_(f"EZ Logger {APP_VERSION}")
        self.win.setReleasedWhenClosed_(False)
        _install_cmd_z_monitor(self)
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

        self.nav_items["session"].setSelected_(True)

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

        # Now Tagging card (Tag Mode section)
        self._build_now_tagging_card(cv, W, H, SIDEBAR_W, TOP_H)

        # Three shortcut cards below
        self._build_shortcut_cards(cv, W, H, SIDEBAR_W, TOP_H)

        # File list panel (tag section, left of cards)
        self._build_file_list(cv, W, H, SIDEBAR_W, TOP_H)
        self._start_folder_watch()   # Finder changes show up without a manual refresh

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

        # Sidebar show/hide. In Log Mode it also hides when the file list couldn't
        # keep its minimum width beside the cards.
        tag_need = (self.SIDEBAR_W + 20 + FILE_LIST_MIN_W + CARDS_MIN_TOTAL
                    if self.current_section == "tag" and self._file_list_visible else 0)
        if self._sidebar_visible and (W < self.SIDEBAR_HIDE_W or W < tag_need):
            self._sidebar_visible = False
            self._sidebar.setHidden_(True)
            if hasattr(self, "_sidebar_toggle_btn"):
                self._sidebar_toggle_btn.setHidden_(False)
        elif (not self._sidebar_visible and W >= self.SIDEBAR_SHOW_W
                and W >= tag_need + 40):
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

        # File-list panel — the user's width when it fits beside the cards; otherwise
        # info columns drop first, then the panel narrows (_fit_file_list)
        fl_eff_w = self._fit_file_list(W)
        if hasattr(self, "_file_list_panel"):
            f = self._file_list_panel.frame()
            self._file_list_panel.setFrame_(
                NSMakeRect(cx + 12, f.origin.y, fl_eff_w, f.size.height))

        # Drag handle — sits on the right edge of the file-list panel
        if hasattr(self, "_fl_resize_handle"):
            f = self._fl_resize_handle.frame()
            handle_x = cx + 12 + fl_eff_w - 3
            self._fl_resize_handle.setFrame_(
                NSMakeRect(handle_x, f.origin.y, f.size.width, f.size.height))

        # Re-center now-tagging card and shortcut cards
        fl_w = fl_eff_w if self._file_list_visible else 0
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

    def _file_list_max_w(self, W):
        """Widest the file list can be with the Log Mode cards still at full minimum width."""
        cx = self.SIDEBAR_W if self._sidebar_visible else 0
        return W - cx - 20 - CARDS_MIN_TOTAL

    def _fit_file_list(self, W):
        """Return the file list's width for this window width, dropping info columns
        that no longer fit. Their on/off choice and widths in Settings stay as they are,
        so they come back when the window widens again."""
        prefs = self._column_prefs() if hasattr(self, "_settings") else {"visible": [], "widths": {}}
        defaults = {cid: w for cid, _t, w, _r in FILE_INFO_COLUMNS}
        cols = [(c, prefs["widths"].get(c, defaults[c])) for c in prefs["visible"]]
        spacing = 3.0
        if hasattr(self, "_file_list_table"):
            spacing = self._file_list_table.intercellSpacing().width
        width, shown = fit_file_list(self._file_list_w, self._file_list_max_w(W), cols, spacing)
        self._fit_shown_cols = shown
        if (hasattr(self, "_file_list_table")
                and shown != getattr(self, "_applied_shown_cols", None)):
            self._apply_info_columns()
        return width

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

        if is_tag and hasattr(self, "_file_list_table"):
            # Logging keys only reach the app while the Log file list has focus
            self.win.makeFirstResponder_(self._file_list_table)
        if is_session:
            self._refresh_files()
            if hasattr(self, "_naming_clips_table"):
                self.win.makeFirstResponder_(self._naming_clips_table)
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
        self.app.batch_rename(None, only_names=set(self._naming_selected) or None)

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
        sr_scroll.setBackgroundColor_(_hex_color("#1e1e20"))
        sr_scroll.setDrawsBackground_(True)
        sr_scroll.setHidden_(True)

        sr_table = SearchResultsTable.alloc().initWithFrame_(
            NSMakeRect(0, 0, SR_W, SR_H))
        sr_table.owner = self
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
        sr_table.setRefusesFirstResponder_(True)  # keys must keep reaching the file list

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
        if abs(old_w - left_w) > 3 or abs(old_h - card_h) > 3:
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
        self._sc_current_bank = self._steps[0]

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
            card.setAlphaValue_(1.0 if bank == self._steps[0] else 0.0)
            card.setHidden_(bank != self._steps[0])  # transparent views still take clicks
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
        self._set_active_shortcut_card(self._steps[0])

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
        # The window may have been laid out since the first build. Pills are sized from
        # _effective_card_w, so the card must match it or the right-hand pills get cut off.
        if hasattr(self, "_effective_card_w") and hasattr(self, "_now_card"):
            TOTAL_W = self._effective_card_w
            cx      = self._now_card.frame().origin.x

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
            card.setAlphaValue_(1.0 if bank == self._steps[0] else 0.0)
            card.setHidden_(bank != self._steps[0])  # transparent views still take clicks
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

        self._sc_current_bank = self._steps[0]
        self._set_active_shortcut_card(self._steps[0])

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
            self._tag_part_steps         = []
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
                    if len(self._tag_part_steps) > len(self._tag_parts):
                        self._tag_part_steps.pop()
                    self._custom_indices         = {i for i in self._custom_indices
                                                    if i < popped_idx}
                    self._chain_boundary_indices = {i for i in self._chain_boundary_indices
                                                    if i < popped_idx}
                    self._now_tag_preview.setStringValue_(
                        "_".join(self._tag_parts) or "…")
                    self._set_v2_hint(
                        "⌫  Removed last label  ·  press a key or ENTER to advance")
            return

        # X → mark or unmark the current clip as a reject (only between logs)
        if key in ("x", "X") and self.step is None and not self._custom_mode:
            self._toggle_reject_current()
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
                if (self.step == "players" and len(key) == 1
                        and (key.isalpha() or digit_search)
                        and self._search_enabled and not in_branch):
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
        self._tag_part_steps.append(bank)
        self._now_tag_preview.setStringValue_("_".join(self._tag_parts) or "—")
        step_lbl = self._step_labels_map.get(bank, bank.title())
        self._set_v2_hint(
            f"⚡ {step_lbl}  —  ✔ {label}  ·  press another key or ENTER to advance"
        )

    def _on_shortcut_pill_click(self, bank, sc):
        """Clicking a Log-section pill does the same thing as pressing its key."""
        if self._custom_mode:
            return
        if self.step is None:
            if bank != self._steps[0] or self._selected_file_idx < 0 or not self._files:
                return
            self._reset_tag_state()
            self._start_player_step()
        if self.step != bank:
            return
        if self._search_mode:
            self._exit_search_mode()
        self._handle_shortcut_key_v2(sc)

    def handle_cmd_z(self):
        if self.app:
            self.app.undo_last(None)

    # ── Rejects and Move to Trash ─────────────────────────────────────────────

    def _select_file_row(self, idx):
        from AppKit import NSIndexSet
        self._file_list_table.selectRowIndexes_byExtendingSelection_(
            NSIndexSet.indexSetWithIndex_(idx), False)
        self._file_list_table.scrollRowToVisible_(idx)
        self._on_file_selected(idx)

    def _toggle_reject_current(self):
        idx = self._selected_file_idx
        if not (0 <= idx < len(self._files)):
            return
        name = self._files[idx].name
        on = name not in self._rejected
        records = load_json(TAG_RECORDS_FILE, {})
        set_reject(records, name, on)
        save_tag_records(records)
        if on:
            self._rejected.add(name)
        else:
            self._rejected.discard(name)
        self._file_list_table.reloadData()
        self._refresh_naming_clips()
        if on:
            # Move on first: selecting a clip resets the hint
            if idx + 1 < len(self._files):
                self._select_file_row(idx + 1)
            self._set_v2_hint(
                f"✕  Marked as reject ({len(self._rejected)})  ·  X to unmark  ·  "
                "trash rejects from the Naming tab")
        else:
            self._set_v2_hint("Reject removed  ·  ENTER to log this clip")

    def _trash_current_clip(self):
        if self.step is not None:
            self._set_v2_hint("Finish this log or press ESC before moving the clip to the Trash")
            return
        idx = self._selected_file_idx
        if not self.app or not (0 <= idx < len(self._files)):
            return
        if self.app.trash_clips([self._files[idx]], self.folder):
            self._set_v2_hint("🗑  Moved to the Trash  ·  ⌘Z to put it back")

    def _naming_trash(self):
        targets = trash_targets(self._files, self._naming_selected, self._rejected)
        if self.app and targets:
            self.app.trash_clips(targets, self.folder)

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
        self._tag_part_steps         = []
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
        if "players" not in self._steps:
            self._set_v2_hint("This sport has no Player step, so + has nothing to add")
            return
        # Mark chain boundary at the current end of tag parts
        self._chain_boundary_indices.add(len(self._tag_parts))
        # Jump to the Player step, wherever it sits, keeping the accumulated preview
        p_idx = self._steps.index("players")
        self.step = "players"
        self._set_step_state(active=p_idx, completed=tuple(range(p_idx)))
        if self._players_bypass_hotkeys and not self._search_enabled:
            self._toggle_search_mode()
        title, hint = self._step_label("players")
        search_note = "  ·  ⌨ type to search" if self._search_enabled else ""
        self._set_v2_hint(f"⚡ + Chain  —  {title}: {hint}{search_note}")
        # Keep preview showing accumulated labels so the user knows they're still there
        acc = "_".join(self._tag_parts)
        self._now_tag_preview.setStringValue_(f"{acc}_…" if acc else "…")

    def _start_player_step(self):
        """Begin a log at the sport's first step (Player unless the sport moved it)."""
        first = self._steps[0]
        if first != "players":
            self.step = first
            self._set_step_state(active=0)
            title, hint = self._step_label(first)
            self._set_v2_hint(f"⚡ {title}  —  {hint}")
            self._now_tag_preview.setStringValue_("…")
            return
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
        self._tag_part_steps.append(self._step_before_custom)
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

    def _raise_search_panel(self):
        """Keep the dropdown above the step circles, which get rebuilt after it."""
        from AppKit import NSWindowAbove
        panel = getattr(self, "_search_results_scroll", None)
        if panel is not None and panel.superview() is not None:
            panel.superview().addSubview_positioned_relativeTo_(panel, NSWindowAbove, None)

    def _show_search_panel(self):
        if hasattr(self, "_search_results_scroll"):
            self._raise_search_panel()
            self._search_results_scroll.setHidden_(False)

    def _hide_search_panel(self):
        if hasattr(self, "_search_results_scroll"):
            self._search_results_scroll.setHidden_(True)

    def _refresh_search_panel(self):
        if not hasattr(self, "_search_results_table"):
            return
        from AppKit import NSIndexSet
        tv = self._search_results_table
        tv.reloadData()
        if self._search_matches:
            idx_set = NSIndexSet.indexSetWithIndex_(self._search_idx)
            tv.selectRowIndexes_byExtendingSelection_(idx_set, False)
            tv.scrollRowToVisible_(self._search_idx)
        else:
            tv.deselectAll_(None)

    def _confirm_search_selection(self):
        if not self._search_matches:
            return
        sc    = self._search_matches[self._search_idx]
        bank  = self.step
        label = sc["label"]
        self._exit_search_mode()
        self._tag_parts.append(label.replace(" ", "_"))
        self._tag_part_steps.append(bank)
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
        self._set_v2_hint(f"⚡ {title}  —  {hint}")
        self._now_tag_preview.setStringValue_("_".join(self._tag_parts) or "—")
        self._set_step_state(active=next_idx, completed=tuple(range(next_idx)))

    def _finalize_v2(self):
        from AppKit import NSIndexSet
        if self._selected_file_idx < 0 or not self._files:
            return
        f = self._files[self._selected_file_idx]
        close_quicklook()

        tag_str  = "_".join(self._tag_parts)
        records  = load_json(TAG_RECORDS_FILE, {})
        record   = records.get(f.name)
        base     = tag_base_stem(f.stem, record)
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

        # Finder colors follow this clip's labels; a problem here never undoes the rename
        colors = finder_colors_for_tags(
            self._tag_parts, self._custom_indices, self.shortcuts, self._steps)
        previous_colors = (record or {}).get("colors", [])
        tags_before = get_finder_tags(new_path)
        tags_after  = merged_finder_tags(tags_before, colors, previous_colors)
        color_failed = (tags_after != tags_before
                        and not set_finder_tags(new_path, tags_after))

        records.pop(old_name, None)
        if tag_str:
            records[new_name] = {"base": base, "colors": [] if color_failed else colors}
        save_tag_records(records)

        if self.app:
            undo_entry = {"old": old_name, "new": new_name}
            if record:
                undo_entry["record_before"] = record
            if tags_after != tags_before and not color_failed:
                undo_entry["tags_before"] = tags_before
            self.app._push_undo({
                "type": "tag",
                "folder": str(f.parent),
                "timestamp": datetime.now().isoformat(),
                "renames": [undo_entry],
            }, max_stack=self._settings.get("undo_stack_size", 50))
            # Log stat — split at chain boundaries, hotkey parts only per segment
            for seg_parts, seg_steps in stat_segments(
                    self._tag_parts, self._tag_part_steps, self._custom_indices,
                    self._chain_boundary_indices, self._steps):
                rows = stat_rows_for_segment(
                    seg_parts, seg_steps, self._steps, self._step_labels_map)
                if not self._settings.get("record_stats", True):
                    continue
                for player, play, rating, detail in rows:
                    log_stat(self.app.session, player, play, rating, detail)

        color_note = "  (Finder color could not be set)" if color_failed else ""
        self._now_tag_preview.setStringValue_(f"✓  {new_name}{color_note}")
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
            NSView, NSScrollView, NSTableColumn, NSImageView, NSImage,
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
        hdr.setAutoresizingMask_(1 | 4 | 8)  # stays centred as the panel widens, pinned to top
        panel.addSubview_(hdr)

        # Scroll + table
        scroll_y = 8
        scroll_h = panel_h - 44
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, scroll_y, FILE_LIST_W, scroll_h))
        scroll.setHasVerticalScroller_(True)
        scroll.setHasHorizontalScroller_(True)   # info columns can outgrow the panel
        scroll.setAutohidesScrollers_(True)
        scroll.setDrawsBackground_(False)
        scroll.setAutoresizingMask_(2 | 16)  # widthSizable + heightSizable
        panel.addSubview_(scroll)
        self._file_list_scroll = scroll

        table = KeyTableView.alloc().initWithFrame_(
            NSMakeRect(0, 0, FILE_LIST_W, scroll_h))
        table.owner = self
        table.setBackgroundColor_(_hex_color("#252528"))
        table.setRowHeight_(26)
        table.setGridStyleMask_(0)
        table.setUsesAlternatingRowBackgroundColors_(False)
        table.setSelectionHighlightStyle_(1)  # NSTableViewSelectionHighlightStyleRegular
        table.setAllowsColumnReordering_(False)
        table.setAllowsColumnResizing_(True)
        # The name column takes up (or gives back) any width the info columns don't use
        table.setColumnAutoresizingStyle_(5)   # NSTableViewFirstColumnOnlyAutoresizingStyle
        self._file_list_header = table.headerView()   # kept so it can be shown again
        table.setHeaderView_(None)

        col = NSTableColumn.alloc().initWithIdentifier_("name")
        col.setWidth_(FILE_LIST_W - 20)
        col.setMinWidth_(90)
        col.setMaxWidth_(100000)
        col.setEditable_(False)
        col.setResizingMask_(1 | 2)   # autoresizing + user resizing
        col.headerCell().setStringValue_("Name")
        col.setDataCell_(VCenterTextCell.alloc().initTextCell_(""))
        table.addTableColumn_(col)

        scroll.setDocumentView_(table)

        # Columns button — right end of the header strip; opens the show/hide menu
        cb_sz = 22
        col_btn = PillButton.alloc().initWithFrame_(NSMakeRect(
            FILE_LIST_W - cb_sz - 8,
            panel_h - HEADER_STRIP_H + (HEADER_STRIP_H - cb_sz) / 2, cb_sz, cb_sz))
        col_btn.layer().setCornerRadius_(6.0)
        col_btn.setAutoresizingMask_(1 | 8)   # right-anchored, pinned to top
        col_btn.setToolTip_("Show or hide clip info columns")
        cb_icon = NSImageView.alloc().initWithFrame_(NSMakeRect(3, 3, cb_sz - 6, cb_sz - 6))
        cb_img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "tablecells", "Columns")
        if cb_img:
            cb_icon.setImage_(cb_img)
        cb_icon.setContentTintColor_(NSColor.secondaryLabelColor())
        col_btn.addSubview_(cb_icon)
        col_btn.setClickHandler_(lambda v, e: self._show_columns_menu(v))
        panel.addSubview_(col_btn)
        self._file_columns_btn = col_btn

        self._media_info      = {}     # media_info_key → clip_media_info dict
        self._media_info_gen  = 0      # bumped to stop a stale background pass
        self._media_info_busy = False
        self._media_info_lock = threading.Lock()
        self._col_menu_targets = []

        self._files            = []
        self._file_inodes      = {}      # {name: inode} from the last scan, to spot Finder renames
        self._folder_missing   = False
        self._quiet_select     = False
        self._rejected         = set()   # clip names marked as rejects (X in Log Mode)
        self._selected_file_idx = -1
        self._file_list_delegate = FileListDelegate.alloc().init()
        self._file_list_delegate.owner = self
        table.setDataSource_(self._file_list_delegate)
        table.setDelegate_(self._file_list_delegate)
        self._file_list_table = table
        self._apply_info_columns()

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

    # ── Clip info columns ─────────────────────────────────────────────────────

    def _column_prefs(self):
        return normalize_column_prefs(self._settings.get("file_list_columns"))

    def _apply_info_columns(self):
        """Rebuild the file list's info columns from the saved prefs. The header row
        only shows while at least one info column is on."""
        if not hasattr(self, "_file_list_table"):
            return
        from AppKit import NSTableColumn, NSFont, NSColor
        table = self._file_list_table
        prefs = self._column_prefs()
        fitted = getattr(self, "_fit_shown_cols", None)
        shown  = [c for c in prefs["visible"] if fitted is None or c in fitted]
        self._applied_shown_cols = shown
        self._applying_columns = True
        try:
            for c in list(table.tableColumns()):
                if c.identifier() != "name":
                    table.removeTableColumn_(c)
            titles = {cid: (title, w, right) for cid, title, w, right in FILE_INFO_COLUMNS}
            for cid in shown:
                title, default_w, right = titles[cid]
                col = NSTableColumn.alloc().initWithIdentifier_(cid)
                col.setEditable_(False)
                col.setMinWidth_(FILE_INFO_MIN_W)
                col.setMaxWidth_(FILE_INFO_MAX_W)
                col.setResizingMask_(2)   # user resizing only; the name column absorbs the rest
                col.setWidth_(prefs["widths"].get(cid, default_w))
                col.headerCell().setStringValue_(title)
                cell = VCenterTextCell.alloc().initTextCell_("")
                col.setDataCell_(cell)
                cell.setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(self._density()[2], 0.0))
                cell.setTextColor_(NSColor.secondaryLabelColor())
                if right:
                    cell.setAlignment_(1)              # NSTextAlignmentRight
                    col.headerCell().setAlignment_(1)
                table.addTableColumn_(col)
            want_header = bool(shown)
            if want_header and table.headerView() is None:
                table.setHeaderView_(self._file_list_header)
                self._file_list_header.setMenu_(self._build_columns_menu())
            elif not want_header and table.headerView() is not None:
                table.setHeaderView_(None)
            if want_header:
                self._file_list_header.setMenu_(self._build_columns_menu())
            if hasattr(self, "_file_list_scroll"):
                self._file_list_scroll.tile()
            table.sizeToFit()
            self._apply_file_list_density(reload=False)
            self._update_sort_indicators()
            table.reloadData()
        finally:
            self._applying_columns = False
        self._queue_media_info()

    # ── Sorting and row density ───────────────────────────────────────────────

    def _density(self):
        return FILE_LIST_DENSITIES.get(self._settings.get("file_list_density", "normal"),
                                       FILE_LIST_DENSITIES["normal"])

    def _apply_file_list_density(self, reload=True):
        """Row height and fonts for both clip lists (Log Mode and the Naming tab)."""
        from AppKit import NSFont
        row_h, name_pt, info_pt = self._density()
        for attr in ("_file_list_table", "_naming_clips_table"):
            table = getattr(self, attr, None)
            if table is None:
                continue
            table.setRowHeight_(row_h)
            for c in table.tableColumns():
                cell = c.dataCell()
                if c.identifier() == "name":
                    cell.setFont_(NSFont.systemFontOfSize_(name_pt))
                else:
                    cell.setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(info_pt, 0.0))
            if reload:
                table.reloadData()

    def _update_sort_indicators(self):
        """Arrow on the sorted column's header; none for the date sorts from Settings."""
        if not hasattr(self, "_file_list_table"):
            return
        from AppKit import NSImage
        table = self._file_list_table
        sort  = self._settings.get("file_sort_order", "name_asc")
        col_id, asc = parse_sort_order(sort)
        if sort in ("date_created", "date_modified"):
            col_id = None
        sorted_col = None
        for c in table.tableColumns():
            if c.identifier() == col_id:
                sorted_col = c
                img = NSImage.imageNamed_(
                    "NSAscendingSortIndicator" if asc else "NSDescendingSortIndicator")
                table.setIndicatorImage_inTableColumn_(img, c)
            else:
                table.setIndicatorImage_inTableColumn_(None, c)
        table.setHighlightedTableColumn_(sorted_col)

    def _set_sort_order(self, sort):
        self._settings["file_sort_order"] = sort
        _save_setting("file_sort_order", sort)
        btn = getattr(self, "_settings_btns", {}).get("file_sort_order")
        if isinstance(btn, tuple) and len(btn) == 2 and hasattr(btn[1], "setStringValue_"):
            btn[1].setStringValue_(f"{sort_order_label(sort)}  ▾")
        self._update_sort_indicators()
        self._refresh_files()
        if 0 <= self._selected_file_idx and hasattr(self, "_file_list_table"):
            self._file_list_table.scrollRowToVisible_(self._selected_file_idx)

    def _on_file_header_clicked(self, col_id):
        self._set_sort_order(
            next_sort_order(self._settings.get("file_sort_order", "name_asc"), col_id))

    def _on_media_pass_done(self):
        """Clip info finished loading; re-sort if the list is sorted by an info column."""
        col_id, _asc = parse_sort_order(self._settings.get("file_sort_order", "name_asc"))
        if col_id in FILE_INFO_IDS and col_id != "size":
            self._refresh_files()

    def _build_columns_menu(self):
        from AppKit import NSMenu, NSMenuItem
        menu = NSMenu.alloc().initWithTitle_("Columns")
        menu.setAutoenablesItems_(False)
        tgt = MenuTarget.alloc().init()
        tgt._callback = self._toggle_info_column
        self._col_menu_targets = [tgt]      # ObjC doesn't retain menu targets
        hdr = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Show Columns", None, "")
        hdr.setEnabled_(False)
        menu.addItem_(hdr)
        visible = set(self._column_prefs()["visible"])
        for cid, title, _w, _r in FILE_INFO_COLUMNS:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "menuPicked:", "")
            item.setTarget_(tgt)
            item.setRepresentedObject_(cid)
            item.setState_(1 if cid in visible else 0)
            menu.addItem_(item)
        menu.addItem_(NSMenuItem.separatorItem())
        reset = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Reset Column Widths", "menuPicked:", "")
        reset.setTarget_(tgt)
        reset.setRepresentedObject_("__reset_widths__")
        reset.setEnabled_(bool(self._column_prefs()["widths"]))
        menu.addItem_(reset)
        return menu

    def _show_columns_menu(self, anchor_view):
        menu = self._build_columns_menu()
        h = anchor_view.frame().size.height
        menu.popUpMenuPositioningItem_atLocation_inView_(None, (0, h + 4), anchor_view)

    def _toggle_info_column(self, col_id):
        if col_id == "__reset_widths__":
            prefs = self._column_prefs()
            prefs["widths"] = {}
        else:
            prefs = toggle_info_column(self._column_prefs(), col_id)
        turned_on = col_id in prefs["visible"]
        self._settings["file_list_columns"] = prefs
        _save_setting("file_list_columns", prefs)
        self._apply_info_columns()
        sorted_col, _asc = parse_sort_order(self._settings.get("file_sort_order", "name_asc"))
        if sorted_col in FILE_INFO_IDS and sorted_col not in prefs["visible"]:
            self._set_sort_order("name_asc")   # the sorted column was hidden
        if turned_on:
            self._widen_file_list_for_columns()

    def _widen_file_list_for_columns(self):
        """Grow the file list panel so the info columns fit beside a readable name,
        as far as the window allows. It never shrinks the panel."""
        if not (hasattr(self, "_file_list_table") and hasattr(self, "win")):
            return
        table   = self._file_list_table
        spacing = table.intercellSpacing().width
        cols    = list(table.tableColumns())
        need = 170 + 24 + sum(c.width() + spacing for c in cols if c.identifier() != "name")
        W = self.win.frame().size.width
        max_w = max(FILE_LIST_MIN_W, self._file_list_max_w(W))   # same limit as dragging the edge
        new_w = int(min(max_w, need))
        if new_w <= self._file_list_w:
            return
        self._file_list_w = new_w
        self._settings["file_list_width"] = new_w
        _save_setting("file_list_width", new_w)
        H = self.win.contentView().frame().size.height
        self._reposition_layout(W, H)
        if hasattr(self, "_sc_scrollviews"):
            self._populate_shortcut_pills(getattr(self, "_sc_current_bank", "players"))

    def _on_info_column_resized(self, col_id, width):
        """Remember a dragged column width; saved shortly after the drag settles."""
        if getattr(self, "_applying_columns", False):
            return
        prefs = self._column_prefs()
        prefs["widths"][col_id] = int(max(FILE_INFO_MIN_W, min(FILE_INFO_MAX_W, width)))
        self._settings["file_list_columns"] = prefs
        if getattr(self, "_col_save_caller", None) is None:
            self._col_save_caller = MainCaller.alloc().init()
            self._col_save_caller._cb = lambda: _save_setting(
                "file_list_columns", self._column_prefs())
        from Foundation import NSObject
        NSObject.cancelPreviousPerformRequestsWithTarget_(self._col_save_caller)
        self._col_save_caller.performSelector_withObject_afterDelay_("fire:", None, 0.4)

    def _file_info_text(self, row, col_id):
        if not (0 <= row < len(self._files)):
            return ""
        key = media_info_key(self._files[row])
        return file_info_value(self._media_info.get(key) if key else {}, col_id)

    def _queue_media_info(self):
        """Read clip info for files not yet cached, one at a time in the background,
        only while an info column is showing."""
        if not self._column_prefs()["visible"] or not self._files:
            return
        with self._media_info_lock:
            self._media_info_gen += 1
            if self._media_info_busy:
                return    # the running pass rescans the list when it sees the new gen
            self._media_info_busy = True
        threading.Thread(target=self._media_info_worker, daemon=True).start()

    def _media_info_worker(self):
        """Background: fill self._media_info, then ask the main thread to redraw the row.
        Dict writes are atomic, so the main thread can read the cache at any time."""
        did_work = False
        try:
            while True:
                gen = self._media_info_gen
                pending = [(f, k) for f in list(self._files)
                           for k in (media_info_key(f),)
                           if k is not None and k not in self._media_info]
                with self._media_info_lock:
                    if not pending and gen == self._media_info_gen:
                        self._media_info_busy = False
                        if did_work:   # only then, or the re-sort would start another pass forever
                            caller = MainCaller.alloc().init()
                            caller._cb = self._on_media_pass_done
                            caller.performSelectorOnMainThread_withObject_waitUntilDone_(
                                "fire:", None, False)
                        return
                did_work = True
                for f, key in pending:
                    if gen != self._media_info_gen:
                        break     # the list changed; rescan it
                    self._media_info[key] = clip_media_info(f)
                    caller = MainCaller.alloc().init()
                    caller._cb = lambda n=f.name: self._on_media_info_ready(n)
                    caller.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "fire:", None, False)
        except Exception:
            with self._media_info_lock:
                self._media_info_busy = False

    def _on_media_info_ready(self, name):
        if not hasattr(self, "_file_list_table"):
            return
        for i, f in enumerate(self._files):
            if f.name == name:
                from AppKit import NSIndexSet
                table = self._file_list_table
                cols = NSIndexSet.indexSetWithIndexesInRange_((0, table.numberOfColumns()))
                table.reloadDataForRowIndexes_columnIndexes_(
                    NSIndexSet.indexSetWithIndex_(i), cols)
                break

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

    def _scan_folder(self):
        """Return (sorted video files, {name: inode}); empty if the folder is gone.
        A file that vanishes mid-scan is skipped."""
        if not (self.folder and self.folder.is_dir()):
            return [], {}
        sort = self._settings.get("file_sort_order", "name_asc")
        entries = []
        try:
            listing = list(self.folder.iterdir())
        except OSError:
            return [], {}
        for f in listing:
            if not is_video(f):
                continue
            try:
                entries.append((f, f.stat()))
            except OSError:
                continue
        cache = getattr(self, "_media_info", {})
        def info_for(_path, st):
            return cache.get((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns))
        entries = sort_file_entries(entries, sort, info_for)
        return [f for f, _ in entries], {f.name: st.st_ino for f, st in entries}

    def _refresh_files(self, external=False):
        """Reload the clip lists from disk. The selection stays on the same clip,
        following it through a rename. With external=True (a Finder change or the
        window regaining focus), nothing redraws unless the clip names changed.
        Returns True when the lists were rebuilt."""
        prev_names = [f.name for f in self._files]
        prev_idx   = self._selected_file_idx
        prev_name  = prev_names[prev_idx] if 0 <= prev_idx < len(prev_names) else None

        files, inodes = self._scan_folder()
        names   = [f.name for f in files]
        renames = match_renames(self._file_inodes, inodes) if self._file_inodes else {}
        self._file_inodes = inodes

        records = load_json(TAG_RECORDS_FILE, {})
        if renames:
            if move_records_for_renames(records, renames):
                save_tag_records(records)
            self._naming_selected = {renames.get(n, n) for n in self._naming_selected}

        folder_missing = bool(self.folder) and not self.folder.is_dir()
        if (external and names == prev_names and not renames
                and folder_missing == self._folder_missing):
            return False
        self._folder_missing = folder_missing

        self._files    = files
        self._rejected = rejected_names(records, set(names))
        new_idx = pick_selection(names, prev_name, renames, prev_idx)
        self._selected_file_idx = new_idx
        if hasattr(self, "_file_list_table"):
            from AppKit import NSIndexSet
            table = self._file_list_table
            self._quiet_select = True
            try:
                table.reloadData()
                if new_idx >= 0:
                    table.selectRowIndexes_byExtendingSelection_(
                        NSIndexSet.indexSetWithIndex_(new_idx), False)
                else:
                    table.deselectAll_(None)
            finally:
                self._quiet_select = False
        if hasattr(self, "_empty_state_overlay"):
            show_empty = not bool(self._files)
            self._empty_state_overlay.setHidden_(not show_empty)
            if show_empty and hasattr(self, "_empty_state_msg"):
                if folder_missing:
                    msg = "Folder not found"
                elif not self.folder:
                    msg = "No folder selected"
                else:
                    msg = "No video files found"
                self._empty_state_msg.setStringValue_(msg)
        self._refresh_naming_clips()
        if hasattr(self, "_media_info"):
            self._queue_media_info()

        if prev_name is not None:
            self._follow_selected_clip(prev_name, renames, new_idx, external)
        return True

    def _follow_selected_clip(self, prev_name, renames, new_idx, external):
        """Keep the Now Logging card in step with the selected clip after a reload."""
        now_name = self._files[new_idx].name if new_idx >= 0 else None
        if now_name == prev_name:
            return
        if now_name is not None and renames.get(prev_name) == now_name:
            # Same clip under a new name: keep any log in progress going
            if hasattr(self, "_now_filename"):
                self._now_filename.setStringValue_(now_name)
            self._thumb_for_path = str(self._files[new_idx])
            return
        cancelled = self.step is not None
        if cancelled:
            # The clip being logged is gone, so finishing would rename the wrong one
            self._search_mode = False
            self.handle_key("\x1b")
        if external and now_name is not None:
            self._on_file_selected(new_idx)
        elif now_name is None and hasattr(self, "_now_filename"):
            self._now_filename.setStringValue_("")
        if cancelled:   # after selecting, which resets the hint
            self._set_v2_hint("⚠  The clip you were logging was removed or moved out "
                              "of the folder, so the log was cancelled")
            rumps.alert(
                title="Log Cancelled",
                message=(f"{prev_name} was deleted or moved out of the folder "
                         "while you were logging it, so the log was cancelled.\n\n"
                         "Nothing was renamed."))

    def _on_folder_changed(self):
        """FSEvents or window focus: pick up changes made outside the app."""
        if getattr(self, "_quiet_select", False):
            return
        self._refresh_files(external=True)

    def _start_folder_watch(self):
        _watch_folder(self.folder, self._on_folder_changed)

    def _on_file_selected(self, row):
        self._selected_file_idx = row
        if getattr(self, "_quiet_select", False):
            return   # _refresh_files restoring the selection; it updates the card itself
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

    def _add_finder_color_dot(self, parent, x, y, color):
        """Draw a small dot showing the Finder color assigned to a shortcut."""
        if color not in FINDER_COLOR_HEX:
            return
        from AppKit import NSView, NSMakeRect
        dot = NSView.alloc().initWithFrame_(NSMakeRect(x, y, 9, 9))
        dot.setWantsLayer_(True)
        dot.layer().setCornerRadius_(4.5)
        dot.layer().setBackgroundColor_(_hex_color(FINDER_COLOR_HEX[color]).CGColor())
        parent.addSubview_(dot)

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

            pill = PillButton.alloc().initWithFrame_(NSMakeRect(x, y, col_w, PILL_H))
            pill.setClickHandler_(
                lambda v, e, b=bank, s=sc: self._on_shortcut_pill_click(b, s))
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
            self._add_finder_color_dot(
                pill, 8 + 22 - 6, (PILL_H + 20) / 2 - 6, sc.get("finder_color"))

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
        """Show one card at a time, fading the new one in.
        active_bank=None → restore current card visibility (no animation).
        active_bank='players'|'plays'|'ratings' → hide old, fade in new.
        Inactive cards must be hidden, not just transparent: they are stacked
        in the same spot and a view with alpha 0 still receives clicks."""
        from AppKit import NSAnimationContext

        if active_bank is None:
            # Returning to tag section from another nav item — restore alphas
            for bank, card in self._sc_cards.items():
                card.setHidden_(bank != self._sc_current_bank)
                card.setAlphaValue_(1.0 if bank == self._sc_current_bank else 0.0)
            return

        if active_bank == self._sc_current_bank:
            return

        old_bank = self._sc_current_bank
        self._sc_current_bank = active_bank

        # Reflow the incoming card for the current window width before showing it
        self._populate_shortcut_pills(active_bank)

        old_card = self._sc_cards[old_bank]
        old_card.setAlphaValue_(0.0)
        old_card.setHidden_(True)
        new_card = self._sc_cards[active_bank]
        new_card.setAlphaValue_(0.0)
        new_card.setHidden_(False)
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(0.25)
        new_card.animator().setAlphaValue_(1.0)
        NSAnimationContext.endGrouping()

    def _set_step_state(self, active=-1, completed=()):
        """active = index of current step (0,1,2 or -1 for none).
           completed = tuple of completed step indices."""
        self._step_state = (active, tuple(completed))
        self._paint_step_circles(active, completed)

        # Sync shortcut cards with active step
        if hasattr(self, "_sc_cards"):
            bank_for_step = (self._steps[active]
                             if 0 <= active < len(self._steps) else None)
            self._set_cards_for_step(bank_for_step)
            self._set_active_shortcut_card(bank_for_step)

    def _paint_step_circles(self, active=-1, completed=()):
        """Colors only: crimson for the active step, tan for completed ones."""
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
        sp_info      = sport_info(active_sport)
        sport_label  = f"▸  {sp_info['emoji']}  {sp_info['name']}  ▾"
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
        self._tutorial_url_btn = url_btn

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
            if sport_key == "__add__":
                self._start_add_sport()
                return
            if sport_key == "__edit__":
                self._edit_sports()
                return
            if self._sport_setup and sport_key != self._sport_setup["code"]:
                self._end_sport_setup()   # picking another sport leaves the setup; the new sport is kept
            if self.app:
                self.app.switch_sport(sport_key)
            self._update_sport_pill(sport_key)

        self._sport_picker_mt._callback = on_pick
        active = self.app.session.get("sport", "MBB") if self.app else "MBB"
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        sports = all_sports()
        for key, info in sports.items():
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                info["label"], "menuPicked:", "")
            mi.setTarget_(self._sport_picker_mt)
            mi.setRepresentedObject_(key)
            if key == active:
                mi.setState_(1)
            menu.addItem_(mi)
        menu.addItem_(NSMenuItem.separatorItem())
        extra = [("Add Sport…", "__add__")]
        if any(i["custom"] for i in sports.values()):
            extra.append(("Edit Sports…", "__edit__"))
        for title, rep_obj in extra:
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "menuPicked:", "")
            mi.setTarget_(self._sport_picker_mt)
            mi.setRepresentedObject_(rep_obj)
            menu.addItem_(mi)
        menu.popUpMenuPositioningItem_atLocation_inView_(None, NSPoint(0, 0), pill)

    # ── Add Sport: 1 basics, 2 steps & labels (Labels tab), 3 done ────────────

    def _sport_basics_form(self, title, info, err="", code_locked=False, copy_choice=True,
                           delete_btn=False):
        """Ask for a sport's name, code, emoji, site slug and starting steps.
        info holds current values. Returns a dict, {"delete": True} for the
        Delete button, or None on Cancel."""
        from AppKit import (NSAlert, NSTextField, NSView, NSMakeRect, NSFont,
                            NSPopUpButton, NSNotificationCenter, NSColor)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(err or
            "The code goes in file names and can't be changed later. "
            "The school site name is the part of the URL after /sports/, "
            "used to fetch the roster.")
        alert.addButtonWithTitle_("Next" if not code_locked else "Save")
        alert.addButtonWithTitle_("Cancel")
        if delete_btn:
            alert.addButtonWithTitle_("Delete Sport…")

        W, ROW, LBL_W = 360.0, 32.0, 96.0
        rows = ["Name", "Code", "Emoji", "School site"] + (["Start from"] if copy_choice else [])
        panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, W, ROW * len(rows)))
        fields = {}
        for i, cap in enumerate(rows):
            y = ROW * (len(rows) - 1 - i)
            lbl = NSTextField.labelWithString_(cap)
            lbl.setFont_(NSFont.systemFontOfSize_(12))
            lbl.setFrame_(NSMakeRect(0, y + 6, LBL_W - 8, 18))
            panel.addSubview_(lbl)
            if cap == "Start from":
                pop = NSPopUpButton.alloc().initWithFrame_pullsDown_(
                    NSMakeRect(LBL_W - 3, y + 1, W - LBL_W + 3, 26), False)
                fields[cap] = pop
            elif cap == "Emoji":
                # Click to open the emoji picker; a narrow box since it holds one emoji
                tf = EmojiField.alloc().initWithFrame_(NSMakeRect(LBL_W, y + 3, 44, 24))
                tf.setFont_(NSFont.systemFontOfSize_(15))
                tf.setAlignment_(1)   # center
                fields[cap] = tf
                hint = NSTextField.labelWithString_("Click to choose")
                hint.setFont_(NSFont.systemFontOfSize_(11))
                hint.setTextColor_(NSColor.secondaryLabelColor())
                hint.setFrame_(NSMakeRect(LBL_W + 52, y + 7, 160, 16))
                panel.addSubview_(hint)
            else:
                tf = NSTextField.alloc().initWithFrame_(NSMakeRect(LBL_W, y + 3, W - LBL_W, 24))
                tf.setFont_(NSFont.systemFontOfSize_(13))
                fields[cap] = tf
            panel.addSubview_(fields[cap])

        sports = all_sports()
        taken = set(sports)
        name_f, code_f = fields["Name"], fields["Code"]
        emoji_f, slug_f = fields["Emoji"], fields["School site"]
        name_f.setPlaceholderString_("e.g. Men's Rugby")
        name_f.setStringValue_(info.get("name", ""))
        code_f.setPlaceholderString_("e.g. MRUG")
        code_f.setStringValue_(info.get("code", ""))
        emoji_f.setStringValue_(info.get("emoji", DEFAULT_SPORT_EMOJI))
        slug_f.setPlaceholderString_("optional, e.g. mens-rugby")
        slug_f.setStringValue_(info.get("slug", ""))
        if code_locked:
            code_f.setEditable_(False)
            code_f.setSelectable_(True)
            code_f.setTextColor_(_hex_color("#8e8e93"))

        sources = []
        if copy_choice:
            pop = fields["Start from"]
            titles = ["Blank: Player, Play, Rating"]
            sources = [None]
            if code_locked:
                titles.insert(0, "Keep current steps")
                sources.insert(0, "__keep__")
            for k, inf in sports.items():
                if k != info.get("code"):
                    titles.append(f"Copy of {inf['emoji']}  {inf['name']}")
                    sources.append(k)
            pop.addItemsWithTitles_(titles)
            if info.get("copy_from") in sources:
                pop.selectItemAtIndex_(sources.index(info.get("copy_from")))

        # Suggest a code as the name is typed, until the code is typed in by hand
        state = {"code_edited": bool(info.get("code"))}
        observers = []
        if not code_locked:
            def name_changed():
                if not state["code_edited"]:
                    nm = name_f.stringValue().strip()
                    code_f.setStringValue_(suggest_sport_code(nm, taken) if nm else "")
            def code_changed():
                state["code_edited"] = bool(code_f.stringValue().strip())
            for tf, cb in ((name_f, name_changed), (code_f, code_changed)):
                obs = MainCaller.alloc().init()
                obs._cb = cb
                NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
                    obs, "fire:", "NSControlTextDidChangeNotification", tf)
                observers.append(obs)
        alert.setAccessoryView_(panel)
        alert.window().setInitialFirstResponder_(name_f)
        resp = alert.runModal()
        for obs in observers:
            NSNotificationCenter.defaultCenter().removeObserver_(obs)
        if delete_btn and resp == 1002:
            return {"delete": True}
        if resp != 1000:
            return None

        out = {
            "name":  name_f.stringValue().strip(),
            "code":  code_f.stringValue().strip().upper(),
            "emoji": emoji_f.stringValue().strip() or DEFAULT_SPORT_EMOJI,
            "slug":  slug_f.stringValue().strip().strip("/").lower(),
            "copy_from": (sources[fields["Start from"].indexOfSelectedItem()]
                          if copy_choice else None),
        }
        problem = ""
        if not out["name"]:
            problem = "Enter a name for the sport."
        elif not code_locked:
            problem = validate_sport_code(out["code"], taken)
        if not problem and out["slug"] and not re.fullmatch(r"[a-z0-9-]+", out["slug"]):
            problem = "The school site name uses only letters, digits and dashes."
        if problem:
            return self._sport_basics_form(title, out, err="⚠️  " + problem,
                                           code_locked=code_locked, copy_choice=copy_choice,
                                           delete_btn=delete_btn)
        return out

    def _start_add_sport(self):
        """Step 1: basics. Creates the sport, switches to it and opens step 2."""
        if not self.app:
            return
        basics = self._sport_basics_form("Add Sport — step 1 of 3", {})
        if basics is None:
            return
        prev = self._current_sport()
        session = self.app.session
        code = create_custom_sport(session, self.app._shortcuts_data, basics,
                                   copy_from=basics["copy_from"])
        self._save_session()
        save_json(SHORTCUTS_FILE, self.app._shortcuts_data)
        self._sport_setup = {"code": code, "prev": prev}
        self.app.switch_sport(code)
        self._update_sport_pill(code)
        self._on_nav_select("labels")
        self._show_sport_setup_bar()

    def _show_sport_setup_bar(self):
        bar = getattr(self, "_labels_setup_bar", None)
        if bar is None or not self._sport_setup:
            return
        info = sport_info(self._sport_setup["code"])
        self._labels_setup_lbl.setStringValue_(
            f"Setting up {info['emoji']}  {info['name']}  —  step 2 of 3: "
            "add steps and their labels")
        if bar.isHidden():
            bar.setHidden_(False)
            sv = self._labels_scrollview
            f = sv.frame()
            sv.setFrame_(((f.origin.x, f.origin.y + self._labels_setup_bar_h),
                          (f.size.width, f.size.height - self._labels_setup_bar_h)))

    def _end_sport_setup(self):
        self._sport_setup = None
        bar = getattr(self, "_labels_setup_bar", None)
        if bar is not None and not bar.isHidden():
            bar.setHidden_(True)
            sv = self._labels_scrollview
            f = sv.frame()
            sv.setFrame_(((f.origin.x, f.origin.y - self._labels_setup_bar_h),
                          (f.size.width, f.size.height + self._labels_setup_bar_h)))

    def _setup_back(self):
        """Back to step 1. The code is fixed by now; name, emoji, site and steps can change."""
        st = self._sport_setup
        if not st:
            return
        info = sport_info(st["code"])
        out = self._sport_basics_form(
            "Add Sport — step 1 of 3",
            {"name": info["name"], "code": st["code"], "emoji": info["emoji"],
             "slug": info["slug"], "copy_from": "__keep__"},
            code_locked=True)
        if out is None:
            return
        update_custom_sport(self.app.session, st["code"], out["name"], out["emoji"], out["slug"])
        self._save_session()
        if out["copy_from"] != "__keep__":
            if out["copy_from"] is None:
                import copy
                own = self._own_step_list()
                for s_ in own:
                    if s_["id"] != "players":
                        self.shortcuts.pop(s_["id"], None)
                own[:] = copy.deepcopy(BLANK_SPORT_STEPS)
                for s_ in own:
                    if s_["id"] != "players":
                        self.shortcuts[s_["id"]] = []
                self._save_session()
                self.app._save_shortcuts()
            else:
                self._copy_steps_from_sport(out["copy_from"], ask=True)
            self._apply_steps_change()
        self.app._build_menu()
        self._update_sport_pill()
        self._show_sport_setup_bar()

    def _setup_cancel(self):
        from AppKit import NSAlert
        st = self._sport_setup
        if not st:
            return
        info = sport_info(st["code"])
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"Discard {info['name']}?")
        alert.setInformativeText_("The new sport, its steps and its labels are removed. "
                                  "No video files are touched.")
        alert.addButtonWithTitle_("Discard")
        alert.addButtonWithTitle_("Keep Setting Up")
        if alert.runModal() != 1000:
            return
        prev = st["prev"] if st["prev"] in all_sports() and st["prev"] != st["code"] else "MBB"
        self._end_sport_setup()
        self._delete_sport_data(st["code"], switch_to=prev)

    def _setup_next(self):
        """Step 3: summary, then Finish (and an offer to fetch the roster)."""
        from AppKit import NSAlert
        st = self._sport_setup
        if not st:
            return
        code = st["code"]
        info = sport_info(code)
        steps = self._sport_step_list()
        empty = [s_["label"] for s_ in steps
                 if s_["id"] != "players" and not self.shortcuts.get(s_["id"])]
        if empty:
            a = NSAlert.alloc().init()
            a.setMessageText_("Some steps have no labels")
            a.setInformativeText_(
                f"{', '.join(empty)} {'has' if len(empty) == 1 else 'have'} no labels yet. "
                "You can still type text on those steps with ⌥ Option while logging.")
            a.addButtonWithTitle_("Keep Editing")
            a.addButtonWithTitle_("Continue Anyway")
            if a.runModal() == 1000:
                return

        lines = [f"Code: {code}",
                 "Steps: " + "  →  ".join(s_["label"] for s_ in steps)]
        for s_ in steps:
            if s_["id"] != "players":
                n = len(self.shortcuts.get(s_["id"], []))
                lines.append(f"{s_['label']}: {n} label{'s' if n != 1 else ''}")
        if not any(s_["id"] == "players" for s_ in steps):
            lines.append("Player step is off")
        base_url = (self._settings or {}).get("roster_base_url", "").strip()
        can_fetch = bool(info["slug"] and base_url
                         and any(s_["id"] == "players" for s_ in steps))
        lines.append(f"School site: /sports/{info['slug']}" if info["slug"]
                     else "School site: none (add players on the Team tab)")

        a = NSAlert.alloc().init()
        a.setMessageText_(f"{info['emoji']}  {info['name']} is ready — step 3 of 3")
        a.setInformativeText_("\n".join(lines))
        if can_fetch:
            a.addButtonWithTitle_("Finish and Fetch Roster")
        a.addButtonWithTitle_("Finish")
        a.addButtonWithTitle_("Back")
        resp = a.runModal()
        back = 1002 if can_fetch else 1001
        if resp == back:
            return
        self._end_sport_setup()
        if can_fetch and resp == 1000:
            cd = (self._settings or {}).get("roster_cache_days", 7)
            threading.Thread(target=self.app._load_roster_bg,
                             args=(code, False, cd), daemon=True).start()
            self._on_nav_select("players")

    # ── Edit Sports (user sports only) ────────────────────────────────────────

    def _edit_sports(self):
        from AppKit import NSAlert, NSPopUpButton, NSMakeRect
        customs = [i for i in all_sports().values() if i["custom"]]
        if not customs:
            return
        target = customs[0]["code"]
        if len(customs) > 1:
            a = NSAlert.alloc().init()
            a.setMessageText_("Edit Sports")
            a.setInformativeText_("Choose one of your sports. Built-in sports can't be edited.")
            a.addButtonWithTitle_("Edit")
            a.addButtonWithTitle_("Cancel")
            pop = NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, 260, 26), False)
            pop.addItemsWithTitles_([i["label"] for i in customs])
            cur = self._current_sport()
            for n, i in enumerate(customs):
                if i["code"] == cur:
                    pop.selectItemAtIndex_(n)
            a.setAccessoryView_(pop)
            if a.runModal() != 1000:
                return
            target = customs[pop.indexOfSelectedItem()]["code"]
        self._edit_one_sport(target)

    def _edit_one_sport(self, code):
        from AppKit import NSAlert
        info = sport_info(code)
        out = self._sport_basics_form(
            f"Edit {info['name']}",
            {"name": info["name"], "code": code, "emoji": info["emoji"], "slug": info["slug"]},
            err="The code can't be changed, because clips already use it. "
                "Edit steps and labels on the Labels tab.",
            code_locked=True, copy_choice=False, delete_btn=True)
        if out is None:
            return
        if out.get("delete"):
            a = NSAlert.alloc().init()
            a.setMessageText_(f"Delete {info['name']}?")
            a.setInformativeText_(
                "Its steps, labels, roster and naming presets are removed. "
                "Stats and video files are kept. This can't be undone.")
            a.addButtonWithTitle_("Cancel")
            a.addButtonWithTitle_("Delete Sport")
            if a.runModal() == 1001:
                if self._sport_setup and self._sport_setup["code"] == code:
                    self._end_sport_setup()
                self._delete_sport_data(code)
            return
        update_custom_sport(self.app.session, code, out["name"], out["emoji"], out["slug"])
        self._save_session()
        self.app._build_menu()
        self._update_sport_pill()

    def _delete_sport_data(self, code, switch_to=None):
        """Remove a user sport everywhere. Switches away first if it's the active sport."""
        if not self.app or code in SPORTS:
            return
        if self._current_sport() == code:
            nxt = switch_to if switch_to in all_sports() and switch_to != code else "MBB"
            self.app.switch_sport(nxt)
        rosters = load_json(ROSTERS_FILE, {})
        meta = load_json(ROSTERS_META_FILE, {})
        keyp = load_json(KEY_PRESETS_FILE, {})
        remove_custom_sport(self.app.session, self.app._shortcuts_data,
                            rosters, meta, keyp, code)
        save_json(ROSTERS_FILE, rosters)
        save_json(ROSTERS_META_FILE, meta)
        save_json(KEY_PRESETS_FILE, keyp)
        self._save_session()
        self.app._save_shortcuts()
        self.app._build_menu()
        self._update_sport_pill()

    def _update_sport_pill(self, sport_key=None):
        if sport_key is None and self.app:
            sport_key = self.app.session.get("sport", "MBB")
        if sport_key is None:
            sport_key = "MBB"
        info = sport_info(sport_key)
        label = f"▸  {info['emoji']}  {info['name']}  ▾"
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

        def _key_order(sc):
            k = sc.get("key", "")
            return (0, int(k)) if k.isdigit() else (1, k.lower())
        items = sorted(self.shortcuts.get("players", []), key=_key_order)
        sv    = self._players_scrollview
        # Derive width from window geometry — sv.frame() can lag on macOS snap/tile
        # events where windowDidResize_ fires before autoresizing has propagated.
        _W  = self.win.frame().size.width
        _cx = self.SIDEBAR_W if self._sidebar_visible else 0
        cw  = _W - _cx
        if cw < 1:
            cw = sv.frame().size.width
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
        btn = HoverButton.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
        btn.setBordered_(False)
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
        if img:
            btn.setImage_(img)
            btn.setContentTintColor_(NSColor.secondaryLabelColor())
        target = MenuTarget.alloc().init()
        target._callback = lambda _: action()
        btn.setTarget_(target)
        btn.setAction_("menuPicked:")
        add_hover_highlight(btn)
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
        name_field.setPlaceholderString_("Player name  (e.g.  JONES,  SMITH)")
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
            message="Paste your school's athletics website URL\n(e.g. https://yourschoolathletics.com)",
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
                parts = [f"{sport_info(c)['emoji']} {len(n)}" for c, n in results.items()]
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
        sp_info      = sport_info(active_sport)
        sport_lbl_str = f"▸  {sp_info['emoji']}  {sp_info['name']}  ▾"
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

        COPY_STEPS_W = 150.0
        copy_steps_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(cw - 32 - ADD_STEP_W - 8 - COPY_STEPS_W,
                       header_y + (HEADER_H - BTN_H) / 2, COPY_STEPS_W, BTN_H))
        copy_steps_btn.configureTitle_bg_press_action_(
            "Copy Steps From…", "#3a3a3c", "#2c2c2e", self._labels_copy_steps_from)
        copy_steps_btn.setAutoresizingMask_(1 | 8)
        section.addSubview_(copy_steps_btn)
        self._labels_copy_steps_btn = copy_steps_btn

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

        # ── Add Sport setup bar (step 2 of 3), shown only while setting up ────
        BAR_H = 56.0
        bar = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cw, BAR_H))
        bar.setWantsLayer_(True)
        bar.layer().setBackgroundColor_(_hex_color_alpha(COLOR_CRIMSON, 0.28).CGColor())
        bar.setAutoresizingMask_(2 | 32)
        bar.setHidden_(True)
        section.addSubview_(bar)
        self._labels_setup_bar   = bar
        self._labels_setup_bar_h = BAR_H
        NEXT_W, CANCEL_W, BACK_W, GAP = 92.0, 92.0, 80.0, 8.0
        lbl = NSTextField.labelWithString_("")
        lbl.setFont_(NSFont.boldSystemFontOfSize_(13))
        lbl.setTextColor_(NSColor.labelColor())
        lbl.setLineBreakMode_(4)   # truncate tail on narrow windows
        lbl.setFrame_(NSMakeRect(32, (BAR_H - 18) / 2,
                                 cw - 64 - NEXT_W - CANCEL_W - BACK_W - 3 * GAP - 12, 18))
        lbl.setAutoresizingMask_(2)
        bar.addSubview_(lbl)
        self._labels_setup_lbl = lbl
        x = cw - 32
        for title, bg, press, action, w in (
                ("Next  →", "#8c2232", "#6b1a26", self._setup_next, NEXT_W),
                ("Cancel", "#3a3a3c", "#2c2c2e", self._setup_cancel, CANCEL_W),
                ("←  Back", "#3a3a3c", "#2c2c2e", self._setup_back, BACK_W)):
            x -= w
            b = ActionButton.alloc().initWithFrame_(NSMakeRect(x, (BAR_H - BTN_H) / 2, w, BTN_H))
            b.configureTitle_bg_press_action_(title, bg, press, action)
            b.setAutoresizingMask_(1)
            bar.addSubview_(b)
            x -= GAP

        # ── Init state ────────────────────────────────────────────────────────
        custom = self._non_player_steps()
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

        # This sport's steps in order. Player can move or be turned off like any
        # step, but its name is fixed and its labels live on the Team tab.
        all_steps = [dict(st, _locked=(st["id"] == "players"))
                     for st in self._sport_step_list()]
        player_off = not any(st["id"] == "players" for st in all_steps)

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

        n        = len(all_steps) + (1 if player_off else 0)
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

                lock_lbl = NSTextField.labelWithString_("ROSTER · TEAM TAB")
                lock_lbl.setFont_(NSFont.systemFontOfSize_(10))
                lock_lbl.setTextColor_(NSColor.tertiaryLabelColor())
                lock_lbl.setAlignment_(2)  # right
                lock_lbl.setFrame_(NSMakeRect(FORM_W - ctrl_block_w - 130,
                                              (ROW_H - 14) / 2, 120, 14))
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

            # ↑ ↓ × controls (× on Player turns the step off for this sport)
            ctrl_x = FORM_W - ctrl_block_w
            n_all  = len(all_steps)
            for ci, (sym, action, enabled) in enumerate([
                ("↑", lambda sid=step_id: self._labels_move_step(sid, -1), i > 0),
                ("↓", lambda sid=step_id: self._labels_move_step(sid,  1), i < n_all - 1),
                ("×", lambda sid=step_id: self._labels_delete_step(sid),
                 n_all > 1 and not (step_id != "players" and
                                    sum(1 for st in all_steps
                                        if st["id"] != "players") <= 1)),
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

        if player_off:
            y -= ROW_H
            row = NSView.alloc().initWithFrame_(NSMakeRect(PAD_X, y, FORM_W, ROW_H))
            row.setWantsLayer_(True)
            row.layer().setCornerRadius_(10.0)
            row.layer().setBorderWidth_(0.5)
            row.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.10).CGColor())
            off_lbl = NSTextField.labelWithString_(
                "Player step is off for this sport, so clips are logged without a player.")
            off_lbl.setFont_(NSFont.systemFontOfSize_(12))
            off_lbl.setTextColor_(NSColor.secondaryLabelColor())
            off_lbl.setFrame_(NSMakeRect(14, (ROW_H - 16) / 2, FORM_W - 150, 16))
            row.addSubview_(off_lbl)
            on_btn = ActionButton.alloc().initWithFrame_(
                NSMakeRect(FORM_W - 124, (ROW_H - 28) / 2, 112, 28))
            on_btn.configureTitle_bg_press_action_(
                "Turn On Player", "#3a3a3c", "#2c2c2e", self._labels_turn_on_player)
            row.addSubview_(on_btn)
            steps_doc.addSubview_(row)
            self._labels_player_on_btn = on_btn

        # Update sub-header to reflect active step name
        custom  = self._non_player_steps()
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

        custom = self._non_player_steps()
        step_cfg  = next((s for s in custom if s["id"] == step_id), None)
        step_name = step_cfg["label"] if step_cfg else step_id

        def on_pick(target_sport):
            import copy
            target_label = sport_info(target_sport)["name"]
            session = self.app.session
            if not any(st["id"] == step_id for st in sport_steps(session, target_sport)):
                # Steps are per sport: offer to add this one rather than hide the labels
                from AppKit import NSAlert
                alert = NSAlert.alloc().init()
                alert.setMessageText_(f"{target_label} has no {step_name} step")
                alert.setInformativeText_(
                    f"Add a {step_name} step to {target_label} and copy the labels into it? "
                    "Its other steps are not changed.")
                alert.addButtonWithTitle_("Add Step and Copy")
                alert.addButtonWithTitle_("Cancel")
                if alert.runModal() != 1000:
                    return
                target_steps = own_sport_steps(session, target_sport)
                target_steps.insert(max(0, len(target_steps) - 1),
                                    {"id": step_id, "label": step_name})
                self._save_session()
            sc_data = self.app._shortcuts_data
            if target_sport not in sc_data:
                sc_data[target_sport] = default_shortcuts(target_sport)
            sc_data[target_sport][step_id] = copy.deepcopy(items)
            self.app._save_shortcuts()
            rumps.alert("Copied",
                        f"{len(items)} {step_name} shortcut{'s' if len(items) != 1 else ''} "
                        f"copied to {target_label}.")

        self._labels_copy_mt._callback = on_pick
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        for key, info in all_sports().items():
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
        if step_id == "players":
            return
        step = next((s for s in self._sport_step_list() if s["id"] == step_id), None)
        if step is None or step["label"] == name:
            return
        step = next(s for s in self._own_step_list() if s["id"] == step_id)
        step["label"] = name
        self._save_session()
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
        _W  = self.win.frame().size.width
        _cx = self.SIDEBAR_W if self._sidebar_visible else 0
        cw  = _W - _cx
        if cw < 1:
            cw = sv.frame().size.width
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

        custom  = self._non_player_steps()
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
            self._add_finder_color_dot(
                pill, 12 + BADGE - 6, (PILL_H + BADGE) / 2 - 6, sc.get("finder_color"))

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
        custom  = self._non_player_steps()
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
        from AppKit import NSAlert, NSTextField, NSView, NSMakeRect, NSFont, NSPopUpButton
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

        panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 94))
        key_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 66, 300, 24))
        key_field.setStringValue_(sc["key"])
        key_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(key_field)
        name_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 34, 300, 24))
        name_field.setStringValue_(sc["label"])
        name_field.setFont_(NSFont.systemFontOfSize_(13))
        panel.addSubview_(name_field)

        color_caption = NSTextField.labelWithString_("Finder color")
        color_caption.setFont_(NSFont.systemFontOfSize_(12))
        color_caption.setFrame_(NSMakeRect(0, 4, 90, 18))
        panel.addSubview_(color_caption)
        color_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(96, 0, 204, 26), False)
        color_popup.addItemsWithTitles_(["None"] + FINDER_COLORS)
        color_popup.selectItemWithTitle_(sc.get("finder_color") or "None")
        panel.addSubview_(color_popup)
        alert.setAccessoryView_(panel)

        if alert.runModal() == 1000:
            key   = key_field.stringValue().strip()[:1]
            label = _asc(name_field.stringValue().strip()).upper()
            if key and label:
                updated = {**sc, "key": key, "label": label}  # keeps children and number
                color = color_popup.titleOfSelectedItem()
                if color != "None":
                    updated["finder_color"] = color
                else:
                    updated.pop("finder_color", None)
                items[idx] = updated
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
            new_id = f"step_{uuid.uuid4().hex[:8]}"
            steps  = self._own_step_list()
            # Insert before the last step (treat last as "rating-like" finale)
            steps.insert(max(0, len(steps) - 1), {"id": new_id, "label": name})
            self._save_session()
            self._labels_active_step = new_id
            self._apply_steps_change()

    def _labels_delete_step(self, step_id):
        """Remove a step from this sport only. On Player it turns the step off."""
        from AppKit import NSAlert
        steps = self._sport_step_list()
        step  = next((s for s in steps if s["id"] == step_id), None)
        if step is None or len(steps) <= 1:
            return
        others = [s for s in steps if s["id"] != "players"]
        if step_id != "players" and len(others) <= 1:
            return   # keep at least one labeling step
        sport = sport_info(self._current_sport())["name"]

        alert = NSAlert.alloc().init()
        if step_id == "players":
            alert.setMessageText_("Turn off the Player step?")
            alert.setInformativeText_(
                f"Clips for {sport.strip()} will be logged without a player. "
                "The roster is kept, and you can turn the step back on anytime. "
                "Other sports are not changed.")
            alert.addButtonWithTitle_("Turn Off")
        else:
            alert.setMessageText_(f"Delete step \"{step['label']}\"?")
            alert.setInformativeText_(
                f"Its shortcuts for {sport.strip()} will also be removed. "
                "Other sports are not changed.")
            alert.addButtonWithTitle_("Delete")
        alert.addButtonWithTitle_("Cancel")

        if alert.runModal() == 1000:
            own = self._own_step_list()
            own[:] = [s for s in own if s["id"] != step_id]
            if step_id != "players":
                self.shortcuts.pop(step_id, None)
                if self.app:
                    self.app._save_shortcuts()
            self._save_session()
            remaining = [s for s in own if s["id"] != "players"]
            if self._labels_active_step == step_id:
                self._labels_active_step = remaining[0]["id"] if remaining else None
            self._apply_steps_change()

    def _labels_copy_steps_from(self):
        """Set this sport up like another: same steps, in order, with copies of their labels."""
        from AppKit import NSMenu, NSMenuItem, NSPoint
        if not self.app:
            return
        current = self._current_sport()
        if not hasattr(self, "_labels_copy_steps_mt"):
            self._labels_copy_steps_mt = MenuTarget.alloc().init()

        def on_pick(source):
            if self._copy_steps_from_sport(source, ask=True):
                self._apply_steps_change()

        self._labels_copy_steps_mt._callback = on_pick
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        for key, info in all_sports().items():
            if key == current:
                continue
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                info["label"], "menuPicked:", "")
            mi.setTarget_(self._labels_copy_steps_mt)
            mi.setRepresentedObject_(key)
            menu.addItem_(mi)
        btn = getattr(self, "_labels_copy_steps_btn", None)
        if btn is not None:
            menu.popUpMenuPositioningItem_atLocation_inView_(None, NSPoint(0, 0), btn)

    def _copy_steps_from_sport(self, source, ask=True):
        """Replace this sport's steps and their labels with copies of source's.
        The roster is never touched. Returns True when anything changed."""
        import copy
        from AppKit import NSAlert
        session = self.app.session
        has_labels = any(self.shortcuts.get(s["id"]) for s in self._non_player_steps())
        if ask and has_labels:
            src_name = sport_info(source)["name"]
            alert = NSAlert.alloc().init()
            alert.setMessageText_(f"Copy steps from {src_name}?")
            alert.setInformativeText_(
                f"This sport's steps and labels will be replaced with copies of {src_name}'s. "
                "The roster is kept, and other sports are not changed.")
            alert.addButtonWithTitle_("Replace")
            alert.addButtonWithTitle_("Cancel")
            if alert.runModal() != 1000:
                return False
        src_steps = copy.deepcopy(sport_steps(session, source))
        src_sc = (self.app._shortcuts_data.get(source)
                  or default_shortcuts(source))
        own = own_sport_steps(session, self._current_sport())
        for st in own:
            if st["id"] != "players":
                self.shortcuts.pop(st["id"], None)
        own[:] = src_steps
        for st in src_steps:
            if st["id"] != "players":
                self.shortcuts[st["id"]] = copy.deepcopy(src_sc.get(st["id"], []))
        self._save_session()
        self.app._save_shortcuts()
        return True

    def _labels_turn_on_player(self):
        own = self._own_step_list()
        if not any(s["id"] == "players" for s in own):
            own.insert(0, dict(PLAYER_STEP))
            self._save_session()
            self._apply_steps_change()

    def _labels_move_step(self, step_id, direction):
        steps = self._own_step_list()
        idx   = next((i for i, s in enumerate(steps) if s["id"] == step_id), None)
        if idx is None:
            return
        new_idx = idx + direction
        if not (0 <= new_idx < len(steps)):
            return
        steps[idx], steps[new_idx] = steps[new_idx], steps[idx]
        self._save_session()
        self._apply_steps_change()

    def _save_session(self):
        if self.app:
            save_json(CONFIG_FILE, self.app.session)

    def _apply_steps_change(self):
        """Rebuild all step-dependent UI after this sport's steps change, or the sport does."""
        if self.step is not None or self._tag_parts:
            self._search_mode = False
            self.handle_key("\x1b")    # cancel any log in progress first
        self._rebuild_steps()
        ids = [s["id"] for s in self._non_player_steps()]
        if getattr(self, "_labels_active_step", None) not in ids:
            self._labels_active_step = ids[0] if ids else None
        self._rebuild_labels_rows()
        self._refresh_labels_grid()
        self._rebuild_sc_cards()
        self._build_step_circles()
        self._set_step_state(active=-1)
        if hasattr(self, "_sc_cards"):
            sec = getattr(self, "current_section", "tag")
            for bank, card in self._sc_cards.items():
                card.setHidden_(sec != "tag" or bank != self._sc_current_bank)

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
        layout_w = self._naming_form_area_w(cw)
        FORM_W  = min(560.0, layout_w - 80.0)
        form_x  = (layout_w - FORM_W) / 2
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
        self._tutorial_folder_row = row_bg

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
        self._tutorial_convention_sv = conv_sv

        self._build_convention_ui(section, layout_w)
        self._build_naming_clips_panel(section, cw, ch)
        self._reposition_session_section(cw, ch)

    # ── Naming section — clip selection for Batch Rename ─────────────────────

    NAMING_CLIPS_W     = 280.0
    TRASH_BTN_COLORS   = ("#a3302a", "#7f2420")
    NAMING_CLIPS_MIN_W = 860.0   # below this content width the panel hides

    def _naming_form_area_w(self, cw):
        """Width left for the folder row and convention builder beside the clip panel."""
        if cw < self.NAMING_CLIPS_MIN_W:
            return cw
        return cw - self.NAMING_CLIPS_W - 24.0

    def _naming_panel_pos(self, panel_h):
        """Return layout positions for all elements in the naming clips panel."""
        PANEL_W  = self.NAMING_CLIPS_W
        THUMB_W  = PANEL_W - 28.0
        THUMB_H  = round(THUMB_W * 9.0 / 16.0)   # 16:9
        PAD      = 10.0
        BTN_H    = 26.0
        GAP      = 6.0
        TITLE_H  = 18.0
        STATUS_H = 34.0
        show_thumb = panel_h >= 360.0
        clear_y   = PAD
        trash_y   = clear_y + BTN_H + GAP
        preview_y = trash_y + BTN_H + GAP
        scroll_y  = preview_y + BTN_H + GAP
        title_y   = panel_h - PAD - TITLE_H
        status_y  = title_y - GAP - STATUS_H
        if show_thumb:
            thumb_y   = status_y - GAP - THUMB_H
            scroll_top = thumb_y - GAP
        else:
            thumb_y    = None
            scroll_top = status_y - GAP
        scroll_h = max(30.0, scroll_top - scroll_y)
        return dict(clear_y=clear_y, trash_y=trash_y, preview_y=preview_y, scroll_y=scroll_y,
                    scroll_h=scroll_h, title_y=title_y, status_y=status_y,
                    show_thumb=show_thumb, thumb_y=thumb_y, thumb_h=THUMB_H,
                    thumb_w=THUMB_W, title_h=TITLE_H, status_h=STATUS_H,
                    btn_h=BTN_H)

    def _build_naming_clips_panel(self, section, cw, ch):
        from AppKit import (
            NSView, NSScrollView, NSTableColumn, NSImageView, NSImage,
            NSTextField, NSFont, NSColor, NSMakeRect,
        )
        PANEL_W = self.NAMING_CLIPS_W
        panel_h = max(200.0, ch - 64.0 - 24.0)

        panel = NSView.alloc().initWithFrame_(
            NSMakeRect(cw - PANEL_W - 12.0, 12.0, PANEL_W, panel_h))
        panel.setWantsLayer_(True)
        panel.layer().setCornerRadius_(8.0)
        panel.layer().setBackgroundColor_(_hex_color("#252528").CGColor())
        panel.layer().setBorderWidth_(0.5)
        panel.layer().setBorderColor_(_hex_color_alpha("#ffffff", 0.08).CGColor())
        section.addSubview_(panel)
        self._naming_clips_panel = panel

        pos = self._naming_panel_pos(panel_h)

        title = NSTextField.labelWithString_("CLIPS")
        title.setFont_(NSFont.boldSystemFontOfSize_(13))
        title.setTextColor_(_hex_color(COLOR_TAN))
        title.setFrame_(NSMakeRect(14, pos['title_y'], PANEL_W - 28, pos['title_h']))
        panel.addSubview_(title)
        self._naming_clips_title = title

        status = NSTextField.wrappingLabelWithString_("")
        status.setFont_(NSFont.systemFontOfSize_(11))
        status.setTextColor_(NSColor.secondaryLabelColor())
        status.setFrame_(NSMakeRect(14, pos['status_y'], PANEL_W - 28, pos['status_h']))
        panel.addSubview_(status)
        self._naming_clips_status = status

        # ── Thumbnail container (shows frame of the clicked clip) ─────────────
        THUMB_W, THUMB_H = pos['thumb_w'], pos['thumb_h']
        thumb_cont = NSView.alloc().initWithFrame_(
            NSMakeRect(14, pos['thumb_y'] or 0, THUMB_W, THUMB_H))
        thumb_cont.setWantsLayer_(True)
        thumb_cont.layer().setCornerRadius_(6.0)
        thumb_cont.layer().setBackgroundColor_(_hex_color("#1a1a1c").CGColor())
        thumb_cont.layer().setBorderWidth_(0.5)
        thumb_cont.layer().setBorderColor_(
            _hex_color_alpha("#ffffff", 0.10).CGColor())
        thumb_cont.setHidden_(not pos['show_thumb'])
        panel.addSubview_(thumb_cont)
        self._naming_thumb_cont = thumb_cont

        icon_sz = 32
        thumb_icon = NSImageView.alloc().initWithFrame_(
            NSMakeRect((THUMB_W - icon_sz) / 2, (THUMB_H - icon_sz) / 2,
                       icon_sz, icon_sz))
        sym = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "play.rectangle.fill", None)
        if sym:
            thumb_icon.setImage_(sym)
        thumb_icon.setContentTintColor_(NSColor.tertiaryLabelColor())
        thumb_cont.addSubview_(thumb_icon)
        self._naming_thumb_icon = thumb_icon

        thumb_img = NSImageView.alloc().initWithFrame_(
            NSMakeRect(0, 0, THUMB_W, THUMB_H))
        thumb_img.setImageScaling_(0)   # NSImageScaleProportionallyDown
        thumb_img.setWantsLayer_(True)
        thumb_img.layer().setCornerRadius_(6.0)
        thumb_img.layer().setMasksToBounds_(True)
        thumb_img.setHidden_(True)
        thumb_cont.addSubview_(thumb_img)
        self._naming_thumb_img  = thumb_img
        self._naming_thumb_path = None   # staleness guard

        # ── Buttons ───────────────────────────────────────────────────────────
        BTN_H = pos['btn_h']
        preview_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(14, pos['preview_y'], PANEL_W - 28, BTN_H))
        preview_btn.configureTitle_bg_press_action_(
            "Quick Look", "#3a3a3c", "#2c2c2e", self._naming_quicklook)
        preview_btn.setHidden_(True)
        panel.addSubview_(preview_btn)
        self._naming_preview_btn = preview_btn

        clear_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(14, pos['clear_y'], PANEL_W - 28, BTN_H))
        clear_btn.configureTitle_bg_press_action_(
            "Clear Selection", "#3a3a3c", "#2c2c2e", self._naming_clear_selection)
        panel.addSubview_(clear_btn)
        self._naming_clear_btn = clear_btn

        trash_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(14, pos['trash_y'], PANEL_W - 28, BTN_H))
        trash_btn.configureTitle_bg_press_action_(
            "Move to Trash", *self.TRASH_BTN_COLORS, self._naming_trash)
        trash_btn.setHidden_(True)
        panel.addSubview_(trash_btn)
        self._naming_trash_btn = trash_btn

        # ── Clip list ─────────────────────────────────────────────────────────
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, pos['scroll_y'], PANEL_W, pos['scroll_h']))
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        scroll.setDrawsBackground_(False)
        panel.addSubview_(scroll)
        self._naming_clips_scroll = scroll

        table = NamingClipsTable.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_W, pos['scroll_h']))
        table.setBackgroundColor_(_hex_color("#252528"))
        table.setRowHeight_(26)
        table.setGridStyleMask_(0)
        table.setSelectionHighlightStyle_(1)
        table.setHeaderView_(None)
        table.setAllowsMultipleSelection_(True)
        table.setAllowsEmptySelection_(True)
        table.owner = self

        col = NSTableColumn.alloc().initWithIdentifier_("name")
        col.setWidth_(PANEL_W - 20)
        col.setEditable_(False)
        col.setDataCell_(VCenterTextCell.alloc().initTextCell_(""))
        table.addTableColumn_(col)
        scroll.setDocumentView_(table)

        self._naming_clips_delegate = NamingClipsDelegate.alloc().init()
        self._naming_clips_delegate.owner = self
        table.setDataSource_(self._naming_clips_delegate)
        table.setDelegate_(self._naming_clips_delegate)
        self._naming_clips_table = table
        self._apply_file_list_density()
        self._naming_focused_row = -1
        self._refresh_naming_clips()

    def _refresh_naming_clips(self):
        """Reload the clip list, keeping the selection for clips that still exist."""
        names = {f.name for f in self._files}
        self._naming_selected &= names
        if hasattr(self, "_naming_clips_table"):
            from AppKit import NSMutableIndexSet
            table    = self._naming_clips_table
            delegate = self._naming_clips_delegate
            delegate._suppressed = True
            table.reloadData()
            # Rows can shift after a rename, so rebuild the highlight from the names
            table.deselectAll_(None)
            rows = NSMutableIndexSet.alloc().init()
            for i, f in enumerate(self._files):
                if f.name in self._naming_selected:
                    rows.addIndex_(i)
            if self._naming_selected:
                table.selectRowIndexes_byExtendingSelection_(rows, False)
            delegate._suppressed = False
        self._update_naming_selection_ui()

    def _on_naming_selection_changed(self):
        table = self._naming_clips_table
        self._naming_selected = {
            f.name for i, f in enumerate(self._files) if table.isRowSelected_(i)}
        self._update_naming_selection_ui()

    def _naming_clear_selection(self):
        if hasattr(self, "_naming_clips_table"):
            self._naming_clips_table.deselectAll_(None)

    def _update_naming_selection_ui(self):
        count = len(self._naming_selected)
        if hasattr(self, "_naming_clips_status"):
            if count:
                text = (f"{count} of {len(self._files)} selected. "
                        "Batch Rename will only rename these.")
            else:
                text = ("None selected, so Batch Rename will rename every clip. "
                        "Click, ⇧-click or ⌘-click to choose clips.")
            self._naming_clips_status.setStringValue_(text)
            self._naming_clear_btn.setHidden_(count == 0)
        if hasattr(self, "_naming_trash_btn"):
            n_rej = len(self._rejected)
            if count:
                trash_title = f"Move {count} to Trash"
            elif n_rej:
                trash_title = f"Trash {n_rej} Rejected"
            else:
                trash_title = "Move to Trash"
            self._naming_trash_btn.configureTitle_bg_press_action_(
                trash_title, *self.TRASH_BTN_COLORS, self._naming_trash)
            self._naming_trash_btn.setHidden_(not (count or n_rej))
        if hasattr(self, "_batch_btn"):
            title = f"Batch Rename ({count})" if count else "Batch Rename"
            self._batch_btn.configureTitle_bg_press_action_(
                title, "#8c2232", "#6b1a26", self._on_batch_rename)

    def _reposition_naming_clips_panel_internals(self, panel_h):
        """Reframe all subviews inside the naming clips panel after a resize."""
        if not hasattr(self, "_naming_clips_title"):
            return
        from AppKit import NSMakeRect
        PANEL_W = self.NAMING_CLIPS_W
        pos = self._naming_panel_pos(panel_h)
        self._naming_clips_title.setFrame_(
            NSMakeRect(14, pos['title_y'], PANEL_W - 28, pos['title_h']))
        self._naming_clips_status.setFrame_(
            NSMakeRect(14, pos['status_y'], PANEL_W - 28, pos['status_h']))
        if hasattr(self, "_naming_thumb_cont"):
            show = pos['show_thumb']
            self._naming_thumb_cont.setHidden_(not show)
            if show and pos['thumb_y'] is not None:
                self._naming_thumb_cont.setFrame_(
                    NSMakeRect(14, pos['thumb_y'], pos['thumb_w'], pos['thumb_h']))
        if hasattr(self, "_naming_preview_btn"):
            self._naming_preview_btn.setFrame_(
                NSMakeRect(14, pos['preview_y'], PANEL_W - 28, pos['btn_h']))
        if hasattr(self, "_naming_clear_btn"):
            self._naming_clear_btn.setFrame_(
                NSMakeRect(14, pos['clear_y'], PANEL_W - 28, pos['btn_h']))
        if hasattr(self, "_naming_trash_btn"):
            self._naming_trash_btn.setFrame_(
                NSMakeRect(14, pos['trash_y'], PANEL_W - 28, pos['btn_h']))
        if hasattr(self, "_naming_clips_scroll"):
            self._naming_clips_scroll.setFrame_(
                NSMakeRect(0, pos['scroll_y'], PANEL_W, pos['scroll_h']))

    def _on_naming_row_clicked(self, row):
        """Load thumbnail for the clicked row and show the Quick Look button."""
        self._naming_focused_row = row
        if not (0 <= row < len(self._files)):
            return
        path = self._files[row]
        if hasattr(self, "_naming_preview_btn"):
            self._naming_preview_btn.setHidden_(False)
        if not hasattr(self, "_naming_thumb_cont"):
            return
        self._naming_thumb_path = str(path)
        if hasattr(self, "_naming_thumb_img"):
            self._naming_thumb_img.setHidden_(True)
        if hasattr(self, "_naming_thumb_icon"):
            self._naming_thumb_icon.setHidden_(False)
        import threading
        threading.Thread(target=self._load_naming_thumb, args=(path,), daemon=True).start()

    def _load_naming_thumb(self, path):
        """Background: generate a thumbnail for the naming panel preview."""
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
            done       = _threading.Event()
            result_box = [None]

            def _handler(cgimg, actual_time, error):
                result_box[0] = cgimg
                done.set()

            gen.generateCGImageAsynchronouslyForTime_completionHandler_(req_time, _handler)
            done.wait(timeout=10.0)
            cgimg = result_box[0]
            if not cgimg or getattr(self, "_naming_thumb_path", None) != str(path):
                return
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
                caller._cb = lambda d=data: self._render_naming_thumb_from_data(d)
                caller.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "fire:", None, False)
        except Exception:
            pass

    def _render_naming_thumb_from_data(self, data):
        try:
            from AppKit import NSImage
            img = NSImage.alloc().initWithData_(data)
            if img and hasattr(self, "_naming_thumb_img"):
                self._naming_thumb_img.setImage_(img)
                self._naming_thumb_img.setHidden_(False)
                if hasattr(self, "_naming_thumb_icon"):
                    self._naming_thumb_icon.setHidden_(True)
        except Exception:
            pass

    def _naming_quicklook(self):
        row = getattr(self, "_naming_focused_row", -1)
        if 0 <= row < len(self._files):
            close_quicklook()
            quicklook(str(self._files[row]))

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
            self._file_inodes = {}   # a different folder: nothing here was renamed
            self._refresh_files()
            self._start_folder_watch()

    # ── Naming section — layout helpers ──────────────────────────────────────

    def _reposition_session_section(self, cw, ch):
        """Folder row is pinned just below the header; convention_sv fills the rest."""
        from AppKit import NSMakeRect
        HEADER_H = 64.0
        FOLDER_H = 54.0
        GAP      = 12.0
        BOT_PAD  = 12.0

        folder_row_y = ch - HEADER_H - FOLDER_H - GAP
        layout_w = self._naming_form_area_w(cw)
        FORM_W = min(560.0, layout_w - 80.0)
        form_x = (layout_w - FORM_W) / 2
        self._conv_form_w = FORM_W
        self._conv_form_x = form_x

        if hasattr(self, "_naming_clips_panel"):
            panel_hidden = cw < self.NAMING_CLIPS_MIN_W
            self._naming_clips_panel.setHidden_(panel_hidden)
            if panel_hidden:
                self._naming_clear_selection()  # never filter by a selection the user can't see
            new_panel_h = max(200.0, ch - HEADER_H - GAP - BOT_PAD)
            self._naming_clips_panel.setFrame_(NSMakeRect(
                cw - self.NAMING_CLIPS_W - 12.0, BOT_PAD,
                self.NAMING_CLIPS_W, new_panel_h))
            self._reposition_naming_clips_panel_internals(new_panel_h)

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
            sv.setFrame_(NSMakeRect(0, conv_y, layout_w, conv_h))
            doc = sv.documentView()
            if doc:
                doc_h = doc.frame().size.height
                # Keep doc width in sync so _rebuild_convention_rows uses correct cw
                if doc.frame().size.width != layout_w:
                    doc.setFrame_(NSMakeRect(0, 0, layout_w, doc_h))
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
        sport_label = sport_info(sport_key)["label"].strip()
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
            sport_label = sport_info(sport_key)["label"].strip()
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
            btn = HoverButton.alloc().initWithFrame_(NSMakeRect(0, 0, pw, ROW_H))
            btn.setBordered_(False)
            btn.setTitle_("")
            btn.setTarget_(t)
            btn.setAction_("menuPicked:")
            add_hover_highlight(btn)
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
        sport_label = sport_info(sport_key)["label"].strip()
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
        rows_per_group = [5, 3, 2, 2, 2, 4, 1, 1]  # Log, Rename, Display, Stats, Roster, System, Undo, Onboarding
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
        sort_opts = list(SORT_LABELS.items())
        cur_sort  = self._settings.get("file_sort_order", "name_asc")
        if cur_sort not in SORT_LABELS:   # sorted by clicking an info column header
            sort_opts.append((cur_sort, sort_order_label(cur_sort)))
        make_dropdown("file_sort_order",
                      "File sort order",
                      "Order in which video files appear in the list. "
                      "Click a column header in the list to sort by it.",
                      sort_opts,
                      post_cb=lambda v: self._set_sort_order(v))
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
        make_dropdown("file_list_density",
                      "Clip list row density",
                      "Row height of the clip lists in Log Mode and Naming.",
                      [("compact",     "Compact"),
                       ("normal",      "Normal"),
                       ("comfortable", "Comfortable")],
                      post_cb=lambda v: self._apply_file_list_density())

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

        section_gap()

        # ── ONBOARDING ──────────────────────────────────────────────────────
        make_header("Onboarding")
        y  = _y[0] - ROW_H
        bg = _row_bg(y)
        _row_labels(bg, "Replay tutorial", "Walk through the first-time setup guide again.", 160)
        replay_btn = ActionButton.alloc().initWithFrame_(
            NSMakeRect(row_w - 160 - 16, (ROW_H - BTN_H) / 2, 160, BTN_H))
        replay_btn.configureTitle_bg_press_action_(
            "Replay Tutorial", "#3a3a3c", "#2c2c2e",
            lambda: (self._dismiss_tutorial(), self._start_tutorial()))
        bg.addSubview_(replay_btn)
        _y[0] = y - ROW_GAP

        # Scroll to top
        sv.contentView().scrollToPoint_((0, max(0.0, doc_h - SCROLL_H)))
        sv.reflectScrolledClipView_(sv.contentView())

    # ── Tutorial ──────────────────────────────────────────────────────────────

    TUTORIAL_STEPS = [
        {
            "tab":     None,
            "title":   "Welcome to EZ Logger",
            "body":    "Let's get you set up in about a minute. You can skip this at any time.",
            "ref":     None,
            "pad":     0,
        },
        {
            "tab":     "session",
            "title":   "Choose your footage folder",
            "body":    "Pick the folder where your video clips live. EZ Logger reads and renames files here.",
            "ref":     "_tutorial_folder_row",
            "pad":     8,
        },
        {
            "tab":     "session",
            "title":   "Set up your naming convention",
            "body":    "Build how you want your files named. Add fields for text, metadata, opponent and more. The preview at the bottom updates live.",
            "ref":     "_tutorial_convention_sv",
            "pad":     12,
        },
        {
            "tab":     "players",
            "title":   "Add your team roster",
            "body":    "Paste your school's athletics roster URL and tap Fetch, or add players manually with + Add Player.",
            "ref":     "_tutorial_url_btn",
            "pad":     12,
        },
        {
            "tab":     "tag",
            "title":   "You're all set",
            "body":    "Head to Log Mode to start tagging clips. Select a file, pick a player, then press Enter to log it.",
            "ref":     None,
            "pad":     0,
        },
    ]

    def _start_tutorial(self):
        from AppKit import NSView, NSMakeRect
        cv = self.win.contentView()
        bounds = cv.bounds()
        overlay = TutorialOverlay.alloc().initWithFrame_(bounds)
        overlay.setAutoresizingMask_(2 | 4 | 8 | 16)
        cv.addSubview_(overlay)
        self._tutorial_overlay = overlay
        self._tutorial_step = 0
        self._show_tutorial_step(0)

    def _show_tutorial_step(self, idx):
        from AppKit import NSMakeRect
        steps = self.TUTORIAL_STEPS
        if idx >= len(steps):
            self._dismiss_tutorial()
            return
        step = steps[idx]
        total = len(steps)

        # Switch to the step's tab
        if step["tab"] is not None:
            self._on_nav_select(step["tab"])

        # Compute spotlight rect in overlay (window content-view) coords
        spotlight = None
        ref_name = step["ref"]
        if ref_name and hasattr(self, ref_name):
            view = getattr(self, ref_name)
            # Convert view bounds to window content-view coords
            vb = view.bounds()
            origin = view.convertPoint_toView_((vb.origin.x, vb.origin.y), None)
            # None means convert to window base coords; content view IS the base
            pad = step["pad"]
            spotlight = NSMakeRect(
                origin.x - pad,
                origin.y - pad,
                vb.size.width + pad * 2,
                vb.size.height + pad * 2,
            )

        self._tutorial_overlay.setSpotlightRect_cardTitle_body_step_total_onNext_onSkip_(
            spotlight,
            step["title"],
            step["body"],
            idx + 1,
            total,
            lambda: self._show_tutorial_step(idx + 1),
            self._dismiss_tutorial,
        )

    def _dismiss_tutorial(self):
        overlay = getattr(self, "_tutorial_overlay", None)
        if overlay is not None:
            overlay.removeFromSuperview()
            self._tutorial_overlay = None
        _save_setting("seen_tutorial", True)
        if hasattr(self, "_settings"):
            self._settings["seen_tutorial"] = True

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
                 f"EZ Logger v{APP_VERSION} — a keyboard-driven tool for tagging sports video files. "
                 "Set up your session once, then use Log Mode to tag each clip — the label "
                 "appends directly to the filename."),
                ("subhead", "LOGGING FLOW"),
                ("para", "Player  →  [custom steps]  →  final step   (each sport sets its own steps)"),
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
                 "Configure your session before logging. Choose ⚙️ Setup Session from the menu "
                 "bar icon and answer each prompt. The current session is shown at the top "
                 "of that menu."),
                ("subhead", "FIELDS"),
                ("table", [
                    ("Sport",        "Enter the sport code, or use the Team tab sport pill"),
                    ("Opponent",     "Opposing team code (e.g. MIAMI, DUKE, YALE)"),
                    ("Videographer", "Your initials or operator code (e.g. AB)"),
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
                    ("4–N",   "Press shortcut keys or click buttons at each step, then ENTER to advance"),
                    ("Final", "ENTER on the last step tags the file and marks it ✓"),
                ]),
                ("para",
                 "At each step you can press multiple shortcut keys before advancing — "
                 "labels accumulate. Press ESC at any time to cancel."),
                ("subhead", "CLICKING BUTTONS"),
                ("para",
                 "Every button in the Log Mode cards does the same thing as pressing its key. "
                 "Clicking a player with a clip selected and no log in progress starts the log. "
                 "Anything clickable lifts when you point at it and pushes in when clicked."),
                ("subhead", "SEARCHING FOR PLAYERS"),
                ("para",
                 "Turn on Search in the top bar, then start typing a player's name on the Player "
                 "step. Click a name in the list, or use ↑ ↓ and press ENTER. Search only runs on "
                 "the Player step, so letter and number keys on every other step go straight to "
                 "that step's shortcuts."),
                ("subhead", "FIXING A LABEL"),
                ("para",
                 "To correct a clip, select it and log it again. The new labels and Finder color "
                 "replace the old ones. Clips labeled before version 1.0.2 keep their old labels "
                 "and add the new ones after them. Each log adds to Stats, and neither relabeling "
                 "nor Undo removes the earlier entry."),
                ("subhead", "CUSTOM INSERT  (⌥ OPTION)"),
                ("para",
                 "At any step, hold Option then type free-form text instead of a shortcut. "
                 "Spaces are preserved as typed. Press ENTER to confirm, Backspace to delete "
                 "the last character, or ⌥ Option again to cancel without confirming."),
                ("subhead", "UNDO  (⌘Z)"),
                ("para",
                 "Reverses the last logged rename and restores the clip's previous Finder color. "
                 "Works from the keyboard in Log Mode or from the menubar."),
            ]),
            ("Removing Clips", [
                ("para",
                 "Clips you don't want can be moved to the Trash without leaving the app. "
                 "Nothing is ever deleted for good: clips go to the macOS Trash, and ⌘Z "
                 "puts them back with their labels. Every move asks first."),
                ("subhead", "MARK REJECTS WHILE LOGGING  (X)"),
                ("para",
                 "In Log Mode, press X between logs to mark the clip as a reject. It's shown "
                 "struck through and the next clip is selected. Press X again to unmark it. "
                 "Logging a rejected clip clears the mark."),
                ("subhead", "TRASH THEM WHEN YOU'RE DONE"),
                ("para",
                 "On the Naming tab, the Clips list has a 'Trash N Rejected' button. Select clips "
                 "instead and it becomes 'Move N to Trash', acting on the selection only."),
                ("subhead", "ONE CLIP AT A TIME  (⌘⌫)"),
                ("para",
                 "⌘⌫ moves the selected clip in Log Mode, or the selected clips in the Naming "
                 "tab's Clips list, to the Trash. Drives without a Trash, like some network "
                 "shares, refuse rather than delete."),
            ]),
            ("Team & Roster", [
                ("para", "The Team tab manages the player list for the active sport."),
                ("subhead", "SPORT PICKER"),
                ("para",
                 "The pill button at the top shows the active sport "
                 "(e.g. ▸ 🏀 Men's Basketball ▾). Click it to switch sports — "
                 "the roster and session update automatically."),
                ("subhead", "ADDING YOUR OWN SPORT"),
                ("para",
                 "Choose 'Add Sport…' at the bottom of the sport picker. Step 1: give it a name, "
                 "a short code for file names (filled in for you), an emoji, and optionally the "
                 "school site name used in roster URLs (/sports/<name>/roster). Start blank or "
                 "copy another sport's steps and labels. Step 2: set up steps and labels on the "
                 "Labels tab, then click Next. Step 3: review and Finish, with an offer to fetch "
                 "the roster. Cancel during setup discards the new sport."),
                ("para",
                 "'Edit Sports…' renames your own sports, changes their emoji or site name, or "
                 "deletes them. Deleting removes the sport's steps, labels, roster and naming "
                 "presets, never video files or stats. Codes can't be changed, and built-in "
                 "sports can't be edited."),
                ("subhead", "LOADING A ROSTER"),
                ("para",
                 "Click 'Fetch All Rosters ↓' to automatically pull current rosters from "
                 "your school's athletics website for all sports. Each athlete becomes a shortcut entry "
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
                 "The Labels tab configures the logging steps and shortcut banks for the "
                 "sport shown in its header. Each sport has its own steps, so changes here "
                 "never affect other sports."),
                ("subhead", "CONFIGURING STEPS"),
                ("para",
                 "The step-order list shows every step in the logging sequence. "
                 "Player can move anywhere in the order, or be turned off with × for sports "
                 "logged without a player. Its names come from the Team tab."),
                ("bullets", [
                    "Click '+ Add Step' to add a new logging step",
                    "Click 'Copy Steps From…' to use another sport's steps and labels",
                    "Click a step's numbered badge to select it and manage its shortcuts",
                    "Edit the step name inline — the Log Mode card updates automatically",
                    "Use ↑ ↓ to reorder steps, × to delete",
                    "'Copy to →' offers to add the step to a sport that doesn't have it",
                ]),
                ("para",
                 "Stats follow the steps: the player comes from the Player step, the rating "
                 "from the last step, and the play from the steps in between. Press = to log "
                 "another player on the same clip; labels picked before Player apply to "
                 "every player."),
                ("subhead", "MANAGING SHORTCUTS"),
                ("bullets", [
                    "Click the pencil icon to edit a key or label",
                    "Click the trash icon to delete a shortcut",
                    "Click '+ Add Shortcut' to create a new entry",
                ]),
                ("para",
                 "Shortcut keys are single characters. The same key can be reused across "
                 "different steps — context (which step you're on) determines which label applies."),
                ("subhead", "FINDER COLORS"),
                ("para",
                 "Click the pencil icon on a shortcut and choose a Finder color to label clips "
                 "with that color when the shortcut is used, such as red for GOOD. The word "
                 "stays in the filename as well. A dot on the shortcut shows its color. "
                 "Relabeling a clip replaces its color, and Undo restores the previous one."),
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
                 "Click '⚡ Import Schedule' to auto-generate one preset per opponent on your "
                 "team's schedule. The active preset must have an Opponent field. Existing presets "
                 "are not overwritten. Set your school's website in the Team section."),
            ]),
            ("Batch Rename", [
                ("para",
                 "Batch Rename standardizes video filenames in the selected folder using "
                 "the active naming preset. Run it before logging to establish the base filename."),
                ("subhead", "RENAMING ONLY SOME CLIPS"),
                ("para",
                 "To rename part of a folder, such as one period, select clips in the Clips "
                 "list on the Naming tab using click, ⇧-click or ⌘-click. The button then shows "
                 "how many are selected, like 'Batch Rename (12)', and only those clips are "
                 "renamed. With nothing selected, every clip in the folder is renamed. "
                 "If the Clips list isn't showing, make the window wider."),
                ("subhead", "DEFAULT FORMAT"),
                ("para", "SPORT_OPPONENT_YYYYMMDD_HHMMSS_VID_PHASE.ext"),
                ("para", "Example:   MBB_MIAMI_20260117_143022_AB_2H.mp4"),
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
                 "When enabled, the Player step switches to search mode: start typing a "
                 "player's name to filter the list — no need to memorize shortcut keys. "
                 "Click a name or press ENTER to confirm the highlighted match. "
                 "Toggle at any time; takes effect immediately on the next log."),
                ("subhead", "SEARCH PLAYERS BY JERSEY NUMBER"),
                ("para",
                 "When enabled, typing digits on the Player step searches by jersey number "
                 "instead of using number shortcut keys. Other steps are not affected."),
                ("subhead", "ROSTER DOMAIN"),
                ("para",
                 "Click '🔗 domain.com' in the Team header to set the base URL for roster "
                 "and schedule scraping (e.g. yourschoolathletics.com). Saved to Settings automatically."),
            ]),
            ("Keyboard Reference", [
                ("subhead", "LOG MODE"),
                ("table", [
                    ("ENTER",          "Begin logging · advance step · confirm custom insert"),
                    ("SPACE",          "QuickLook preview of the selected file"),
                    ("ESC",            "Close player search, or cancel the current log"),
                    ("[key]",          "Apply shortcut — stays on current step to allow stacking"),
                    ("⌥ Option",       "Enter custom-insert mode (spaces preserved as typed)"),
                    ("⌥ Option again", "Cancel custom-insert without confirming"),
                    ("Backspace",      "Remove the last label · delete a character in custom-insert mode"),
                    ("↑ / ↓",          "Move through player search results"),
                    ("TAB",            "Advance to the next file (only when not mid-tag)"),
                    ("X",              "Mark or unmark the clip as a reject (only when not mid-tag)"),
                    ("⌘⌫",            "Move the clip to the Trash (only when not mid-tag)"),
                    ("⌘Z",            "Undo the last logged file rename or Move to Trash"),
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
            btn = HoverButton.alloc().initWithFrame_(
                NSMakeRect(8, toc_y, TOC_W - 16, 30))
            btn.setBordered_(False)
            btn.setAttributedTitle_(self._make_toc_attr(title, NSColor.secondaryLabelColor()))
            btn.setAlignment_(0)
            btn.setWantsLayer_(True)
            btn.layer().setCornerRadius_(8.0)
            btn.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
            btn.setAutoresizingMask_(8)  # flexible bottom — stays anchored to top as panel resizes
            t = MenuTarget.alloc().init()
            t._callback = lambda _, i=idx: self._help_scroll_to(i)
            btn.setTarget_(t)
            btn.setAction_("menuPicked:")
            add_hover_highlight(btn)
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
        # First-run tutorial — show after a short delay so the window renders first
        if not self._settings.get("seen_tutorial", False):
            import rumps as _rumps
            _rumps.Timer(self._auto_start_tutorial, 0.6).start()

    def _auto_start_tutorial(self, timer):
        timer.stop()
        self._start_tutorial()


# ── Menubar App ───────────────────────────────────────────────────────────────

class BasketballRenamerApp(rumps.App):
    def __init__(self):
        super().__init__("🪵", quit_button=None)
        self.session          = load_json(CONFIG_FILE, DEFAULT_SESSION)
        set_custom_sports(self.session.get("custom_sports", []))
        raw                   = load_json(SHORTCUTS_FILE, {})
        self._shortcuts_data  = self._migrate_shortcuts(raw)
        sport                 = self.session.get("sport", "MBB")
        self.shortcuts        = dict(self._shortcuts_data.get(sport) or default_shortcuts(sport))
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
        rumps.Timer(self._start_sparkle, 1.0).start()

    def _start_sparkle(self, _timer):
        _timer.stop()
        _init_sparkle()
        if _sparkle_controller is None:
            # Running from source or Sparkle unavailable — fall back to notification
            threading.Thread(target=self._run_update_check, daemon=True).start()

    def _run_update_check(self):
        def _notify(version, url):
            rumps.notification(
                title="EZ Logger Update Available",
                subtitle=f"Version {version} is ready",
                message="Visit github.com/EZ-LOGGER/ez-logger/releases to download.",
                sound=False,
            )
        _check_for_updates_bg(_notify)

    def _check_for_updates_menu(self, _):
        if _sparkle_controller is not None:
            _sparkle_controller.checkForUpdates_(None)
        else:
            import webbrowser
            webbrowser.open("https://github.com/EZ-LOGGER/ez-logger/releases")

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
        sport_label = sport_info(s.get("sport", ""))["label"]
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

        self.menu.add(rumps.MenuItem("Check for Updates…", callback=self._check_for_updates_menu))
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    # ── Session setup ─────────────────────────────────────────────────────────

    def setup_session(self, _):
        s = dict(self.session)
        fields = [
            ("sport",        "Sport Code",           f"Options: {', '.join(all_sports())}"),
            ("opponent",     "Opponent",              "e.g. MIAMI"),
            ("videographer", "Videographer Initials", "e.g. AB"),
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
        new_sc = dict(self._shortcuts_data.get(sport_key) or default_shortcuts(sport_key))

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
            rumps.alert("No School Website Set",
                        "Open the Team section and click the 🔗 button to enter "
                        "your school's athletics website, then try again.")
            return
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
                            f"{sport_info(sport_key)['label']}\n\n"
                            f"{len(names)} players loaded:\n" +
                            "\n".join(f"[{sc['key']}]  {sc['label']}" for sc in shortcuts[:15]) +
                            ("\n…" if len(shortcuts) > 15 else ""))
            self._refresh_tag_window_players()
        else:
            if not silent:
                rumps.alert("❌ Roster Load Failed",
                            "Could not fetch a roster from your school's website.\n"
                            "Check the URL in the Team section (🔗) and your internet connection.\n"
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
            if hasattr(win, "_apply_steps_change"):
                # Each sport has its own steps: rebuild circles, cards and Labels rows
                win._apply_steps_change()
        caller = MainCaller.alloc().init()
        caller._cb = refresh
        caller.performSelectorOnMainThread_withObject_waitUntilDone_(
            b"fire:", None, False)

    # ── Batch rename ──────────────────────────────────────────────────────────

    def batch_rename(self, _, only_names=None):
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
        files = select_batch_files(files, only_names)
        if not files:
            rumps.alert("No Files", "The selected clips are no longer in this folder.")
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
        base_stems = _col.Counter(batch_base_stem(n, deduped) for _, n, deduped in plan)
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
            # A batch rename gives clips a fresh name, so earlier tag records no longer apply
            records = load_json(TAG_RECORDS_FILE, {})
            for r in snapshot["renames"]:
                old_record = records.pop(r["old"], None)
                records.pop(r["new"], None)
                if old_record:
                    r["record_before"] = old_record
                    if old_record.get("reject"):
                        records[r["new"]] = {"reject": True}   # a reject stays a reject
            save_tag_records(records)
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

        if op_type == "trash":
            self._undo_trash(stack, op)
            return

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
                records = load_json(TAG_RECORDS_FILE, {})
                records.pop(r["new"], None)
                if "record_before" in r:
                    records[r["old"]] = r["record_before"]
                save_tag_records(records)
                if "tags_before" in r:
                    set_finder_tags(dst, r["tags_before"])
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

    # ── Move to Trash ─────────────────────────────────────────────────────────

    def trash_clips(self, paths, folder, confirm=True):
        """Move clips to the Trash after confirming. Returns how many were moved.
        Every move goes through SafeRenamer.safe_trash and can be undone."""
        paths = [Path(p) for p in paths]
        if not paths:
            return 0
        ok, err = SafeRenamer.validate_folder(folder)
        if not ok:
            rumps.alert("Can't Move to Trash", err)
            return 0
        if confirm and not _confirm_trash_alert([p.name for p in paths]):
            return 0

        folder_path = Path(folder)
        records = load_json(TAG_RECORDS_FILE, {})
        items, errors = [], []
        for p in paths:
            ok, result = SafeRenamer.safe_trash(p, folder_path, self.session)
            if ok:
                item = {"name": p.name, "trash_path": result}
                rec = records.pop(p.name, None)
                if rec:
                    item["record_before"] = rec
                items.append(item)
            else:
                errors.append(f"  {p.name}: {result}")

        if items:
            save_tag_records(records)
            _max_stack = load_json(SETTINGS_FILE, DEFAULT_SETTINGS).get("undo_stack_size", 50)
            self._push_undo({
                "type": "trash",
                "folder": str(folder_path),
                "timestamp": datetime.now().isoformat(),
                "items": items,
                "renames": [],
            }, max_stack=_max_stack)
        if errors:
            head = (f"Moved {len(items)} clip(s) to the Trash.\n" if items else
                    "No clips were moved to the Trash.\n")
            rumps.alert("Some Clips Weren't Moved",
                        head + f"{len(errors)} clip(s) stayed in the folder:\n"
                        + "\n".join(errors))
        self._refresh_tag_window_files()
        return len(items)

    def _undo_trash(self, stack, op):
        folder_path = Path(op.get("folder", ""))
        items = [i for i in op.get("items", [])
                 if i.get("trash_path") and os.path.exists(i["trash_path"])]
        if not items:
            stack.pop()
            save_json(UNDO_FILE, stack)
            self._refresh_undo_item()
            rumps.alert("Nothing to Undo",
                        "Those clips are no longer in the Trash.")
            return
        n = len(items)
        if not rumps.alert(title="Undo Move to Trash",
                           message=f"Put {n} clip(s) back into:\n{folder_path}\n\nContinue?",
                           ok="Put Back", cancel="Cancel"):
            return

        restored, errors = 0, []
        records = load_json(TAG_RECORDS_FILE, {})
        for i in items:
            ok, err = SafeRenamer.safe_restore(
                Path(i["trash_path"]), folder_path / i["name"], folder_path, self.session)
            if ok:
                restored += 1
                if "record_before" in i:
                    records[i["name"]] = i["record_before"]
            else:
                errors.append(f"  {i['name']}: {err}")
        save_tag_records(records)

        stack.pop()
        save_json(UNDO_FILE, stack)
        self._refresh_undo_item()
        parts = [f"Put back {restored} clip(s)."]
        if errors:
            parts.append(f"{len(errors)} clip(s) are still in the Trash:\n" + "\n".join(errors))
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
            if undo_op_available(op):
                top = op
                break

        if top is None:
            self._undo_item._menuitem.setEnabled_(False)
            self._undo_item.title = "    ↩  Undo Rename"
        elif top.get("type") == "trash":
            n = len(top.get("items", []))
            self._undo_item._menuitem.setEnabled_(True)
            self._undo_item.title = f"    ↩  Undo Move to Trash ({n})"
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
