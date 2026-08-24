#!/usr/bin/env python3
"""Fetch a redistributable static ffmpeg for the current platform.

Drops the binary into bin/ where find_ffmpeg() and the PyInstaller spec
both expect it.

Licensing matters here. Most popular prebuilt ffmpeg binaries, including
the evermeet and osxexperts macOS builds, are compiled with
--enable-nonfree, which makes them illegal to redistribute. The sources
below are plain GPL v3 builds, so they may be shipped as long as the
licence travels with them and the source is offered. This script refuses
to continue if it is ever handed a nonfree binary.
"""

import io
import os
import platform
import stat
import subprocess
import sys
import urllib.request
import zipfile

MARTIN_RIEDL = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/ffmpeg.zip"
GYAN = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "bin")


def source_for_platform():
    """Return (url, name of the member inside the zip, output filename)."""
    if sys.platform == "darwin":
        arch = "arm64" if platform.machine() == "arm64" else "amd64"
        return MARTIN_RIEDL.format(arch=arch), "ffmpeg", "ffmpeg"
    if sys.platform == "win32":
        return GYAN, "bin/ffmpeg.exe", "ffmpeg.exe"
    raise SystemExit(f"No configured ffmpeg source for {sys.platform}")


def download(url):
    print(f"Downloading {url}")
    # Both hosts reject the stock urllib user agent with a 403
    req = urllib.request.Request(
        url, headers={"User-Agent": "MediaDownloader-build/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    print(f"  {len(data) / 1048576:.1f} MB")
    return data


def extract(data, member_suffix, out_path):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if n.endswith(member_suffix)]
        if not names:
            raise SystemExit(f"{member_suffix} not found in archive")
        # Shortest path wins, to avoid picking up a nested duplicate
        name = min(names, key=len)
        print(f"  extracting {name}")
        with zf.open(name) as src, open(out_path, "wb") as dst:
            dst.write(src.read())

    os.chmod(out_path, os.stat(out_path).st_mode | stat.S_IEXEC | stat.S_IXGRP
             | stat.S_IXOTH)


def verify(path):
    """Refuse anything we are not allowed to redistribute."""
    if sys.platform == "win32":
        with open(path, "rb") as fh:
            blob = fh.read()
        config = b"--enable-nonfree" in blob
        version = "not checked on this host"
    else:
        out = subprocess.run([path, "-version"], capture_output=True,
                             text=True, timeout=60).stdout
        config = "--enable-nonfree" in out
        version = out.splitlines()[0]

        if "libmp3lame" not in out:
            raise SystemExit("Build lacks libmp3lame, MP3 export would fail")

    if config:
        raise SystemExit(
            "This build is --enable-nonfree and cannot legally be "
            "redistributed. Pick a different source.")

    print(f"  {version}")
    print("  licence check passed, no nonfree flag")


def write_licence():
    """Ship the licence and the written offer of source alongside it."""
    text = """ffmpeg is bundled with this application.

It is licensed under the GNU General Public Licence version 3, and is
used unmodified as a separate executable. This application invokes it as
a subprocess and does not link against it.

  Full licence:  https://www.gnu.org/licenses/gpl-3.0.html
  Source code:   https://ffmpeg.org/download.html

macOS builds come from https://ffmpeg.martin-riedl.de
Windows builds come from https://www.gyan.dev/ffmpeg/builds/

Both are plain GPL v3 builds. Neither is built with --enable-nonfree.
The exact build configuration is printed by running: ffmpeg -version
"""
    path = os.path.join(BIN, "FFMPEG-LICENCE.txt")
    with open(path, "w") as fh:
        fh.write(text)
    print(f"  wrote {os.path.relpath(path)}")


def main():
    os.makedirs(BIN, exist_ok=True)
    url, member, out_name = source_for_platform()
    out_path = os.path.join(BIN, out_name)

    extract(download(url), member, out_path)
    verify(out_path)
    write_licence()

    size = os.path.getsize(out_path) / 1048576
    print(f"\nffmpeg ready at {out_path} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
