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

ytdlp_path = os.path.join(ROOT, "bin", "yt-dlp")

if not os.path.isfile(ytdlp_path):
    raise SystemExit(
        f"{ytdlp_path} is missing. Run packaging/fetch_ytdlp.py first.")

# Landing them in bin/ matches what find_ffmpeg() looks for at runtime.
binaries = [(ffmpeg_path, "bin")]
datas = [
    (os.path.join(ROOT, "bin", "FFMPEG-LICENCE.txt"), "bin"),
    # Shipped as data, not frozen, so update_ytdlp() can replace it later.
    (ytdlp_path, "ytdlp"),
]

a = Analysis(
    [os.path.join(ROOT, "media_downloader.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    # yt_dlp is analysed so that everything it imports (ssl, http.cookiejar,
    # xml, email and friends) is collected. The package itself is stripped
    # from the archive below, leaving the dependencies behind for the
    # zipapp to use.
    hiddenimports=["yt_dlp"],
    hookspath=[],
    runtime_hooks=[],
    # Trimming these keeps the bundle from ballooning. yt-dlp imports them
    # only for features this app does not expose.
    excludes=["numpy", "pytest", "setuptools", "pip", "PIL", "matplotlib"],
    noarchive=False,
)

# Drop the frozen yt_dlp modules. A frozen copy would be found first and
# would shadow the zipapp, which is what made the old update button
# pointless once packaged. Their dependencies stay collected.
a.pure = TOC([entry for entry in a.pure
              if not (entry[0] == "yt_dlp" or entry[0].startswith("yt_dlp."))])

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
        version="1.2.0",
        info_plist={
            "CFBundleShortVersionString": "1.2.0",
            "CFBundleVersion": "1.2.0",
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
