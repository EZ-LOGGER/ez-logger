"""
py2app setup file — builds EZ Logger into a proper Mac .app
Run via build.sh
"""
from setuptools import setup

APP     = ["renamer.py"]
APP_NAME = "EZ Logger"

OPTIONS = {
    "iconfile": "icon.icns",
    "plist": {
        "CFBundleName":               APP_NAME,
        "CFBundleDisplayName":        APP_NAME,
        "CFBundleIdentifier":         "com.bball.renamer",
        "CFBundleVersion":            "3.0.0",
        "CFBundleShortVersionString": "3.0",
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
    },
    "packages": ["rumps", "AppKit", "Foundation", "objc"],
    "includes": ["AppKit", "Foundation", "objc", "rumps"],
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
