# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Media Downloader.

Builds a windowed app with ffmpeg bundled inside, so users do not have to
install anything. Run packaging/fetch_ffmpeg.py first to populate bin/.

  macOS   -> dist/Media Downloader.app
  Windows -> dist/MediaDownloader.exe   (single file)
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
IS_MAC = sys.platform == "darwin"

ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
ffmpeg_path = os.path.join(ROOT, "bin", ffmpeg_name)

if not os.path.isfile(ffmpeg_path):
    raise SystemExit(
        f"{ffmpeg_path} is missing. Run packaging/fetch_ffmpeg.py first.")

# Landing them in bin/ matches what find_ffmpeg() looks for at runtime.
binaries = [(ffmpeg_path, "bin")]
datas = [(os.path.join(ROOT, "bin", "FFMPEG-LICENCE.txt"), "bin")]

a = Analysis(
    [os.path.join(ROOT, "media_downloader.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=["yt_dlp"],
    hookspath=[],
    runtime_hooks=[],
    # Trimming these keeps the bundle from ballooning. yt-dlp imports them
    # only for features this app does not expose.
    excludes=["numpy", "pytest", "setuptools", "pip", "PIL", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

if IS_MAC:
    # onedir, because a .app bundle needs a real directory layout
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="Media Downloader",
        debug=False,
        strip=False,
        upx=False,
        console=False,
        target_arch=None,       # native arch of the build machine
        codesign_identity=None, # ad hoc signed afterwards by the build script
        entitlements_file=None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
                   name="Media Downloader")
    app = BUNDLE(
        coll,
        name="Media Downloader.app",
        icon=None,
        bundle_identifier="com.sasindubandara.mediadownloader",
        version="1.1",
        info_plist={
            "CFBundleShortVersionString": "1.1",
            "CFBundleVersion": "1.1",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "Sasindu Bandara",
            # No network entitlement questions: this is not sandboxed.
        },
    )
else:
    # onefile, so Windows users get a single exe the installer can drop in
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="MediaDownloader",
        debug=False,
        strip=False,
        upx=False,
        console=False,
        icon=None,
    )
