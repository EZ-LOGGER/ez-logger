"""
py2app setup file — builds EZ Logger into a proper Mac .app
Run via build.sh
"""
from setuptools import setup
import re

# Pull version from the single source of truth in renamer.py
with open("renamer.py") as f:
    _ver_match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    APP_VERSION = _ver_match.group(1) if _ver_match else "1.0.0"

APP      = ["renamer.py"]
APP_NAME = "EZ Logger"

SPARKLE_FW = "Sparkle/Sparkle.framework"

OPTIONS = {
    "iconfile": "icon.icns",
    "plist": {
        "CFBundleName":               APP_NAME,
        "CFBundleDisplayName":        APP_NAME,
        "CFBundleIdentifier":         "com.bball.renamer",
        "CFBundleVersion":            APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "NSHighResolutionCapable":    True,
        "LSUIElement":                False,
        "NSAppleEventsUsageDescription":
            "EZ Logger needs Automation access to rename files in Finder.",
        "NSDesktopFolderUsageDescription":
            "EZ Logger needs access to your footage folder.",
        "NSDocumentsFolderUsageDescription":
            "EZ Logger needs access to your footage folder.",
        "NSDownloadsFolderUsageDescription":
            "EZ Logger needs access to your footage folder.",
        # Sparkle auto-update
        "SUFeedURL":      "https://raw.githubusercontent.com/EZ-LOGGER/ez-logger/main/appcast.xml",
        "SUPublicEDKey":  "JRZIA1vLikS4u1DczE/MLelmm5EJm6zyeLOXd+2EVak=",
        "SUEnableAutomaticChecks": True,
    },
    "frameworks": [SPARKLE_FW],
    "packages": ["rumps", "AppKit", "Foundation", "objc", "FSEvents", "CoreFoundation"],
    "includes": ["AppKit", "Foundation", "objc", "rumps", "FSEvents", "CoreFoundation"],
    "excludes": ["tkinter", "matplotlib", "numpy", "PIL"],
    "semi_standalone": False,
    "site_packages":   True,
}

setup(
    app=APP,
    name=APP_NAME,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
    data_files=[(".", ["icon.icns"])],
)
