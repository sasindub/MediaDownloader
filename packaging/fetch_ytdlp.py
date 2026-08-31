#!/usr/bin/env python3
"""Download the yt-dlp zipapp for bundling into the app.

yt-dlp publishes a self contained zipapp: one file, pure Python, no
compiled extensions. Shipping that as a data file rather than freezing
the package into the executable is what lets the app update yt-dlp
later, which matters because sites break extractors constantly.

Writes bin/yt-dlp, which the spec file copies into the bundle.
"""

import os
import re
import sys
import shutil
import zipfile
import urllib.request

URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "bin", "yt-dlp")


def version_of(path):
    """Read the version out of the zipapp, which also proves it is valid."""
    with zipfile.ZipFile(path) as zf:
        blob = zf.read("yt_dlp/version.py").decode("utf-8", "replace")
    found = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", blob)
    return found.group(1) if found else None


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".part"

    print(f"Downloading {URL}")
    req = urllib.request.Request(URL, headers={"User-Agent": "MediaDownloader-build"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as fh:
        shutil.copyfileobj(resp, fh)

    try:
        version = version_of(tmp)
    except (zipfile.BadZipFile, KeyError) as exc:
        os.remove(tmp)
        raise SystemExit(f"Downloaded file is not a usable yt-dlp zipapp: {exc}")

    if not version:
        os.remove(tmp)
        raise SystemExit("Could not read a version out of the zipapp.")

    os.replace(tmp, OUT)
    size = os.path.getsize(OUT) // 1024
    print(f"yt-dlp {version} -> {OUT}  ({size} KB)")


if __name__ == "__main__":
    sys.exit(main())
