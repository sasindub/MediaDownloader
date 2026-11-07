#!/usr/bin/env python3
"""
Media Downloader
A local desktop app for downloading videos from YouTube, Instagram, Facebook
and around 1000 other sites, using yt-dlp.

Intended for downloading content you own, content licensed for reuse,
or content you have permission to download.

Requirements:
    pip install yt-dlp
    ffmpeg must be installed and on PATH (needed to merge high resolution
    video with separate audio streams)

Run:
    python media_downloader.py
"""

import os
import re
import sys
import json
import queue
import shutil
import time
import ssl
import zipfile
import threading
import subprocess
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import (
    BOTH, BOTTOM, DANGER, DISABLED, END, LEFT, NORMAL, PRIMARY, RIGHT,
    SECONDARY, SUCCESS, W, X, Y, YES,
)

APP_NAME = "Media Downloader"
APP_VERSION = "1.3.1"

# ----------------------------------------------------------------------
# Dependency check
# ----------------------------------------------------------------------

def resource_dir():
    """Folder holding bundled resources, whether frozen or run from source."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def user_data_dir():
    """Per user writable folder, in the conventional place for each OS."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = (os.environ.get("XDG_CONFIG_HOME")
                or os.path.expanduser("~/.config"))
    return os.path.join(base, "MediaDownloader")


# yt-dlp ships a self contained zipapp: one file, pure Python, importable
# straight off sys.path. Shipping it as data rather than freezing it into
# the executable is what makes the app updatable. A frozen module could
# never be replaced at runtime, which is why the old update button could
# not work once packaged.
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
BUNDLED_YTDLP = os.path.join(resource_dir(), "ytdlp", "yt-dlp")
UPDATED_YTDLP = os.path.join(user_data_dir(), "yt-dlp")


def ssl_context():
    """Build an SSL context that works inside a packaged app.

    A frozen app has no system OpenSSL certificate directory, so the
    default context can fail to verify anything. certifi ships with
    yt-dlp and is bundled, so it is used when present.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:      # noqa: BLE001 - fall back to the default context
        return None


def download_ytdlp(log=print):
    """Fetch the latest yt-dlp zipapp into the user data folder.

    Downloads to a temporary file and only moves it into place once it
    has been confirmed to be a readable zipapp, so an interrupted
    download can never leave the app broken. Returns the new version, or
    None if what is already installed is current.
    """
    os.makedirs(user_data_dir(), exist_ok=True)
    tmp = UPDATED_YTDLP + ".part"

    try:
        req = urllib.request.Request(
            YTDLP_URL, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=120,
                                    context=ssl_context()) as resp, \
                open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh)

        new_version = zipapp_version(tmp)
        if not new_version:
            raise ValueError("the downloaded file was not a usable yt-dlp")

        current = YTDLP_VERSION or (yt_dlp.version.__version__
                                    if yt_dlp else None)
        if current and version_key(new_version) <= version_key(current):
            os.remove(tmp)
            log(f"Already up to date, yt-dlp {current}.")
            return None

        os.replace(tmp, UPDATED_YTDLP)
        log(f"Updated to yt-dlp {new_version}. Restart the app to use it.")
        return new_version

    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def zipapp_version(path):
    """Read yt-dlp's version out of a zipapp without importing it.

    Returns None if the file is missing or not a usable zipapp, which is
    how a truncated or corrupt download gets rejected.
    """
    try:
        with zipfile.ZipFile(path) as zf:
            blob = zf.read("yt_dlp/version.py").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    found = re.search(r"__version__\s*=\s*[\'\"]([^\'\"]+)", blob)
    return found.group(1) if found else None


def version_key(version):
    """Sort key for yt-dlp's date style versions, e.g. 2026.08.19."""
    parts = []
    for chunk in re.split(r"[.\-]", version or ""):
        parts.append((0, int(chunk)) if chunk.isdigit() else (1, 0, chunk))
    return parts


def activate_ytdlp():
    """Put the newest available yt-dlp on sys.path before it is imported.

    Prefers whichever of the downloaded and bundled copies is newer, so
    that updating the app itself is never a downgrade.
    """
    # Bundled is considered first, so the downloaded copy is only used
    # when it is strictly newer. Ties go to the bundled file, which is not
    # user writable.
    best = None
    for path in (BUNDLED_YTDLP, UPDATED_YTDLP):
        version = zipapp_version(path)
        if not version:
            continue
        key = version_key(version)
        if best is None or key > best[0]:
            best = (key, version, path)

    if best is None:
        return None, None

    _, version, path = best
    sys.path.insert(0, path)
    return version, path


YTDLP_VERSION, YTDLP_PATH = activate_ytdlp()

YTDLP_IMPORT_ERROR = None

try:
    import yt_dlp
except Exception as exc:            # noqa: BLE001 - shown to the user verbatim
    yt_dlp = None
    YTDLP_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def find_ffmpeg():
    """Return path to ffmpeg.

    The bundled copy is preferred so a broken or ancient system install
    cannot break a packaged app. Explicit Homebrew paths are checked last
    because an app launched from Finder inherits a minimal PATH that does
    not include /opt/homebrew/bin.
    """
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = os.path.join(resource_dir(), "bin", name)
        if os.path.isfile(candidate):
            return candidate

    found = shutil.which("ffmpeg")
    if found:
        return found

    for path in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg",
                 "/usr/bin/ffmpeg"):
        if os.path.isfile(path):
            return path

    return None


def settings_path():
    return os.path.join(user_data_dir(), "settings.json")


def load_settings():
    try:
        with open(settings_path()) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        with open(settings_path(), "w") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass


# ----------------------------------------------------------------------
# Quality presets
# ----------------------------------------------------------------------

# Maps the label shown in the UI to a max height. None means no limit.
QUALITY_PRESETS = {
    "Best available": None,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "Audio only (MP3)": "audio",
    "Smallest file": "worst",
}

AUDIO_ONLY = "Audio only (MP3)"


def build_format(quality, apple_safe):
    """Build a yt-dlp format string.

    apple_safe restricts the pick to H.264 video and AAC audio, the only
    combination QuickTime, Photos and iOS play natively. YouTube serves
    H.264 up to 1080p only, so 4K requires turning this off and accepting
    AV1 or VP9, which need VLC or IINA to play.
    """
    preset = QUALITY_PRESETS[quality]

    if preset == "audio":
        return "bestaudio/best"
    if preset == "worst":
        return "worst[vcodec^=avc1]/worst" if apple_safe else "worst"

    height = f"[height<={preset}]" if preset else ""

    if apple_safe:
        # Fall back progressively: exact codecs, then mp4 containers,
        # then anything, so a site that does not offer H.264 still works.
        chain = [
            f"bestvideo{height}[vcodec^=avc1]+bestaudio[acodec^=mp4a]",
            f"bestvideo{height}[ext=mp4]+bestaudio[ext=m4a]",
            f"best{height}[ext=mp4]",
            f"best{height}",
            "best",
        ]
    else:
        chain = [f"bestvideo{height}+bestaudio", f"best{height}", "best"]

    # dict.fromkeys drops the duplicate tail when height is empty
    return "/".join(dict.fromkeys(chain))


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# ----------------------------------------------------------------------
# Text shown in the welcome and help windows
# ----------------------------------------------------------------------

_GATEKEEPER_MAC = """OPENING THE APP ON macOS

This app is not signed with an Apple Developer certificate, so macOS
will warn you the first time you open it. This is expected. You only
need to do this once.

On macOS 15 Sequoia and newer
  1. Drag Media Downloader into your Applications folder.
  2. Double click it. macOS says it "could not verify" the app.
     Click Done.
  3. Open System Settings, go to Privacy and Security, and scroll
     down to the Security section.
  4. Next to "Media Downloader was blocked", click Open Anyway.
  5. Confirm with Touch ID or your password, then click Open Anyway
     once more.

On macOS 14 Sonoma and older
  1. Drag Media Downloader into your Applications folder.
  2. Right click the app and choose Open.
  3. Click Open in the dialog that appears.

After this first time, the app opens normally by double clicking.
"""

_GATEKEEPER_WIN = """OPENING THE APP ON WINDOWS

This app is not signed with a code signing certificate, so Windows
SmartScreen will warn you the first time you run it. This is expected.

  1. Run the installer or the exe.
  2. If you see "Windows protected your PC", click More info.
  3. Click Run anyway.

Your antivirus may also flag it. This is a common false positive for
apps built with PyInstaller, because the packaging method resembles
what some malware uses. The source code is available if you want to
check it or build it yourself.
"""

_GATEKEEPER = _GATEKEEPER_WIN if sys.platform == "win32" else _GATEKEEPER_MAC

WELCOME_TEXT = f"""{APP_NAME} {APP_VERSION}

Download videos from YouTube, Instagram, Facebook, TikTok and around a
thousand other sites. Everything runs on your own machine. Nothing is
uploaded anywhere.

QUICK START
  1. Copy a video link in your browser.
  2. Click Paste.
  3. Pick a quality, then click Download.

Files are saved to your Downloads folder unless you change it, and are
named Title [videoID] so nothing overwrites anything else.

ABOUT VIDEO QUALITY
"QuickTime compatible" is on by default. It downloads H.264 video with
AAC audio, which plays in QuickTime, Photos, iMovie and on iPhone.
YouTube only offers H.264 up to 1080p, so this caps YouTube downloads
at 1080p.

Turn it off to get 4K. Those files use the AV1 or VP9 codec, which
QuickTime cannot play. You will need VLC or IINA for them, and they
will not import into Photos or iMovie.

KEEPING IT WORKING
YouTube changes its site often and breaks downloaders. If downloads
suddenly stop working, click Update yt-dlp, then restart the app. That
fixes it nearly every time.

PLEASE USE IT RESPONSIBLY
Downloading may breach the terms of service of these sites. Intended
for content you own, content licensed for reuse, and content you have
permission to download. Redistributing other people's copyrighted work
is a separate matter and is on you.

Click Help at any time to see this again.
"""

HELP_TEXT = f"""{APP_NAME} {APP_VERSION}

{_GATEKEEPER}

CHOOSING A QUALITY

  Best available    Highest quality that fits your codec choice
  1080p to 360p     Caps the resolution, smaller files
  Audio only (MP3)  Extracts audio at 192 kbps
  Smallest file     Lowest quality, fastest download

QUICKTIME COMPATIBLE, AND WHY 4K IS DIFFERENT

Leave this ticked and you get H.264 video with AAC audio. That plays
everywhere on a Mac or iPhone, including QuickTime, Photos, iMovie and
Final Cut.

YouTube stopped encoding H.264 above 1080p. Their 1440p and 4K versions
exist only as AV1 and VP9. So to download 4K you must untick the box,
and the file you get will not open in QuickTime, will not import into
Photos or iMovie, and will not AirDrop usefully to an iPhone. Play those
with VLC or IINA, both free.

On Macs with an M1 or M2 chip there is no hardware decoder for AV1, so
4K playback uses the processor heavily and drains battery. M3 and newer
handle it in hardware.

SUBTITLES
Downloads English, Sinhala and Tamil subtitles when the site has them,
including automatically generated ones. They are saved as separate .srt
files next to the video.

PLAYLISTS
Off by default, so pasting a link from inside a playlist gets you just
that one video. Tick Whole playlist to download all of it.

WHEN SOMETHING GOES WRONG

  Downloads suddenly stopped working
    Click Update yt-dlp and restart. This is the usual cause, because
    sites change and break the extractor.

  "Sign in to confirm you're not a bot"
    YouTube's bot check. Usually clears by itself after a while.

  Private or login required
    Public posts only. Private accounts, stories and anything behind a
    login wall cannot be downloaded.

  Video unavailable or region blocked
    Nothing to be done from here.

  Only low resolution downloads, or no sound
    ffmpeg is missing. It ships inside this app, so if you see this,
    please report it.

WHERE FILES GO
Whatever folder is shown in Save to. Click Open folder to see them.
"""



# ----------------------------------------------------------------------
# Download worker
# ----------------------------------------------------------------------

class DownloadWorker(threading.Thread):
    """Runs a single yt-dlp download on a background thread."""

    def __init__(self, url, folder, quality, subtitles, playlist, msg_queue,
                 apple_safe=True):
        super().__init__(daemon=True)
        self.url = url
        self.folder = folder
        self.quality = quality
        self.subtitles = subtitles
        self.playlist = playlist
        self.apple_safe = apple_safe
        self.q = msg_queue
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    # -- yt-dlp callbacks ---------------------------------------------

    def _progress_hook(self, d):
        if self.cancelled:
            raise yt_dlp.utils.DownloadError("Cancelled by user")

        status = d.get("status")

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            pct = (done / total * 100) if total else 0
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0

            self.q.put({
                "type": "progress",
                "percent": pct,
                "speed": self._fmt_speed(speed),
                "eta": self._fmt_eta(eta),
                "size": self._fmt_size(total),
            })

        elif status == "finished":
            self.q.put({
                "type": "log",
                "text": "Download finished, processing with ffmpeg...",
            })

    def _postprocessor_hook(self, d):
        if d.get("status") == "started":
            name = d.get("postprocessor", "")
            self.q.put({"type": "log", "text": f"Post processing: {name}"})

    # -- formatting helpers -------------------------------------------

    @staticmethod
    def _fmt_size(b):
        if not b:
            return "unknown"
        for unit in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    @staticmethod
    def _fmt_speed(s):
        if not s:
            return "..."
        for unit in ("B/s", "KB/s", "MB/s"):
            if s < 1024:
                return f"{s:.1f} {unit}"
            s /= 1024
        return f"{s:.1f} GB/s"

    @staticmethod
    def _fmt_eta(e):
        if not e:
            return "..."
        m, s = divmod(int(e), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m}m"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    # -- main ----------------------------------------------------------

    def build_options(self):
        outtmpl = os.path.join(self.folder, "%(title).200B [%(id)s].%(ext)s")

        opts = {
            "outtmpl": outtmpl,
            "format": build_format(self.quality, self.apple_safe),
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "noplaylist": not self.playlist,
            "ignoreerrors": self.playlist,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "restrictfilenames": False,
            "windowsfilenames": True,
            "concurrent_fragment_downloads": 4,
            "retries": 5,
            "fragment_retries": 5,
            "extractor_retries": 3,
        }

        ffmpeg = find_ffmpeg()
        if ffmpeg:
            opts["ffmpeg_location"] = ffmpeg

        if self.quality == AUDIO_ONLY:
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            opts["merge_output_format"] = "mp4"

        if self.subtitles:
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitleslangs"] = ["en", "si", "ta"]
            opts["subtitlesformat"] = "srt/vtt/best"

        return opts

    # Sites like TikTok intermittently serve a page with no video data in
    # it, as a soft bot check. Asking again a moment later usually works,
    # so these are retried rather than shown to the user as a failure.
    TRANSIENT = (
        "unable to extract",
        "unexpected response",
        "failed to parse json",
        "unable to download webpage",
        "read timed out",
    )

    @classmethod
    def _is_transient(cls, exc):
        low = ANSI_RE.sub("", str(exc)).lower()
        return any(marker in low for marker in cls.TRANSIENT)

    # Seconds to wait before each retry. A site that is throttling can
    # stay unhappy for a minute or more, and the old 2, 4, 6, 8 schedule
    # gave up after twenty seconds, well inside that window.
    BACKOFF = (4, 10, 25, 45)

    def _sleep_unless_cancelled(self, seconds):
        """Wait, but stay responsive to the Cancel button."""
        for _ in range(int(seconds * 2)):
            if self.cancelled:
                return
            time.sleep(0.5)

    def _retry(self, action):
        """Run action, retrying the intermittent bot check responses.

        Both metadata extraction and the download itself hit the site, and
        either can come back with a page that has no video data in it, so
        both go through here.
        """
        attempts = len(self.BACKOFF) + 1
        for attempt in range(1, attempts + 1):
            if self.cancelled:
                raise yt_dlp.utils.DownloadError("Cancelled by user")
            try:
                return action()
            except Exception as exc:
                if attempt >= attempts or not self._is_transient(exc):
                    raise
                wait = self.BACKOFF[attempt - 1]
                self.q.put({
                    "type": "log",
                    "text": f"The site is not responding properly. Waiting "
                            f"{wait} seconds, then trying again "
                            f"({attempt} of {attempts - 1})...",
                })
                self._sleep_unless_cancelled(wait)

    def run(self):
        try:
            self.q.put({"type": "log", "text": "Fetching video information..."})

            with yt_dlp.YoutubeDL(self.build_options()) as ydl:
                info = self._retry(
                    lambda: ydl.extract_info(self.url, download=False))

                if info is None:
                    raise Exception("Could not read that URL")

                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    count = len(entries)
                    self.q.put({
                        "type": "title",
                        "text": f"Playlist: {info.get('title', 'Untitled')} "
                                f"({count} items)",
                    })
                else:
                    self.q.put({
                        "type": "title",
                        "text": info.get("title", "Untitled"),
                    })

                self.q.put({"type": "log", "text": "Starting download..."})
                self._retry(lambda: ydl.download([self.url]))

            if not self.cancelled:
                self.q.put({"type": "done", "folder": self.folder})

        except Exception as exc:
            if self.cancelled:
                self.q.put({"type": "cancelled"})
            else:
                self.q.put({"type": "error", "text": self._friendly_error(exc)})

    @staticmethod
    def _friendly_error(exc):
        raw = ANSI_RE.sub("", str(exc))
        low = raw.lower()

        if "sign in to confirm" in low or "not a bot" in low:
            return ("YouTube is asking for sign in verification. This usually "
                    "clears on its own. If it keeps happening, use the cookies "
                    "option described in the README.")
        if "private" in low or "login required" in low:
            return ("This content is private or needs a login. Public posts "
                    "only, unless you supply cookies.")
        if "unavailable" in low or "removed" in low:
            return "This video is unavailable, removed, or region blocked."
        if "ffmpeg" in low:
            return ("ffmpeg is missing. Install it and make sure it is on your "
                    "PATH, then restart the app.")
        if "unsupported url" in low:
            return "That URL is not recognised. Check it and try again."
        if "age" in low and "restrict" in low:
            return "This video is age restricted and needs account cookies."
        if ("unexpected response" in low or "unable to extract" in low
                or "rehydration" in low):
            return ("The site kept refusing to return the video data. This "
                    "is usually temporary throttling rather than a problem "
                    "with the video or this app. Wait a few minutes and try "
                    "again, and avoid downloading many videos back to back. "
                    "If it persists for hours, click Update yt-dlp.")

        return raw[:400]


# ----------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------


def system_is_dark():
    """Best effort read of the operating system appearance."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=5)
            return "dark" in out.stdout.lower()
        if sys.platform == "win32":
            import winreg
            path = (r"Software\\Microsoft\\Windows\\CurrentVersion"
                    r"\\Themes\\Personalize")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except Exception:          # noqa: BLE001 - appearance is cosmetic
        pass
    return False


def asset(name):
    """Absolute path to a bundled image, or None when it is missing."""
    path = os.path.join(resource_dir(), "assets", name)
    return path if os.path.isfile(path) else None


class DownloaderApp(tb.Window):

    PAD = 16

    def __init__(self):
        self.settings = load_settings()
        dark = self.settings.get("dark_mode")
        if dark is None:
            dark = system_is_dark()

        super().__init__(
            title=f"{APP_NAME} {APP_VERSION}",
            themename="bootstrap-dark" if dark else "bootstrap-light",
            size=(880, 760),
            minsize=(780, 680),
        )

        self._images = {}      # Tk discards images that are not referenced
        self._set_window_icon()

        self.msg_queue = queue.Queue()
        self.worker = None
        self.finished_folder = None

        self.folder = tk.StringVar(
            value=self.settings.get(
                "folder", os.path.join(os.path.expanduser("~"), "Downloads")))
        quality = self.settings.get("quality", "Best available")
        if quality not in QUALITY_PRESETS:
            quality = "Best available"
        self.quality = tk.StringVar(value=quality)
        self.subtitles = tk.BooleanVar(value=False)
        self.playlist = tk.BooleanVar(value=False)
        self.apple_safe = tk.BooleanVar(
            value=self.settings.get("apple_safe", True))
        self.dark_mode = tk.BooleanVar(value=bool(dark))

        self._build_ui()
        self._check_dependencies()
        self._prefill_from_clipboard()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)

        if not self.settings.get("seen_welcome"):
            self.after(500, self._show_welcome)

    # -- window chrome -------------------------------------------------

    def _set_window_icon(self):
        path = asset("icon_128.png")
        if not path:
            return
        try:
            self._images["app"] = tk.PhotoImage(file=path)
            self.iconphoto(True, self._images["app"])
        except tk.TclError:
            pass

    def _image(self, name, key):
        path = asset(name)
        if not path:
            return None
        try:
            self._images[key] = tk.PhotoImage(file=path)
            return self._images[key]
        except tk.TclError:
            return None

    # -- layout --------------------------------------------------------

    def _build_ui(self):
        outer = tb.Frame(self, padding=(self.PAD, 12, self.PAD, self.PAD))
        outer.pack(fill=BOTH, expand=YES)

        self._build_header(outer)
        self._build_link_card(outer)
        self._build_options_card(outer)
        self._build_actions(outer)
        self._build_status_card(outer)
        self._build_log(outer)
        self._build_statusbar()

    def _build_header(self, parent):
        header = tb.Frame(parent)
        header.pack(fill=X, pady=(0, 14))

        logo = self._image("icon_64.png", "logo")
        if logo:
            tb.Label(header, image=logo).pack(side=LEFT, padx=(0, 12))

        titles = tb.Frame(header)
        titles.pack(side=LEFT, anchor=W)
        tb.Label(titles, text=APP_NAME,
                 font=("-size 19 -weight bold")).pack(anchor=W)
        tb.Label(titles,
                 text="YouTube, TikTok, Instagram, Facebook and more",
                 bootstyle=SECONDARY).pack(anchor=W)

        tb.Button(header, text="Help", bootstyle="secondary-link",
                  command=self._show_help).pack(side=RIGHT)
        tb.Checkbutton(header, text="Dark", variable=self.dark_mode,
                       bootstyle="round-toggle",
                       command=self._toggle_theme).pack(side=RIGHT,
                                                        padx=(0, 14))

    def _build_link_card(self, parent):
        card = tb.Labelframe(parent, text="  1.  Paste a video link  ",
                             padding=14)
        card.pack(fill=X, pady=(0, 12))

        row = tb.Frame(card)
        row.pack(fill=X)

        self.url_entry = tb.Entry(row, font=("-size 12"))
        self.url_entry.pack(side=LEFT, fill=X, expand=YES, ipady=5)
        self.url_entry.bind("<Return>", lambda e: self.start_download())
        self.url_entry.bind("<KeyRelease>", lambda e: self._sync_download_btn())

        tb.Button(row, text="Paste", bootstyle="primary-outline", width=9,
                  command=self.paste_url).pack(side=LEFT, padx=(10, 0))
        tb.Button(row, text="Clear", bootstyle="secondary-outline", width=9,
                  command=self.clear_url).pack(side=LEFT, padx=(8, 0))

    def _build_options_card(self, parent):
        card = tb.Labelframe(parent, text="  2.  Choose how to save it  ",
                             padding=14)
        card.pack(fill=X, pady=(0, 12))

        row1 = tb.Frame(card)
        row1.pack(fill=X)
        tb.Label(row1, text="Quality", width=9).pack(side=LEFT)
        tb.Combobox(row1, textvariable=self.quality, state="readonly",
                    width=22, values=list(QUALITY_PRESETS)).pack(side=LEFT)

        tb.Checkbutton(row1, text="Subtitles", variable=self.subtitles,
                       bootstyle="round-toggle").pack(side=LEFT, padx=(24, 0))
        tb.Checkbutton(row1, text="Whole playlist", variable=self.playlist,
                       bootstyle="round-toggle").pack(side=LEFT, padx=(20, 0))

        row2 = tb.Frame(card)
        row2.pack(fill=X, pady=(12, 0))
        tb.Label(row2, text="", width=9).pack(side=LEFT)
        tb.Checkbutton(row2, text="Plays everywhere (H.264, needed for "
                                  "QuickTime, Photos and iPhone)",
                       variable=self.apple_safe, bootstyle="round-toggle",
                       command=self._compat_note).pack(side=LEFT)

        row3 = tb.Frame(card)
        row3.pack(fill=X, pady=(12, 0))
        tb.Label(row3, text="Save to", width=9).pack(side=LEFT)
        tb.Entry(row3, textvariable=self.folder).pack(
            side=LEFT, fill=X, expand=YES, ipady=3)
        tb.Button(row3, text="Browse", bootstyle="secondary-outline", width=9,
                  command=self.choose_folder).pack(side=LEFT, padx=(10, 0))

    def _build_actions(self, parent):
        row = tb.Frame(parent)
        row.pack(fill=X, pady=(0, 14))

        self.download_btn = tb.Button(
            row, text="Download", bootstyle=PRIMARY, width=18,
            command=self.start_download, state=DISABLED)
        self.download_btn.pack(side=LEFT, ipady=6)

        self.cancel_btn = tb.Button(
            row, text="Cancel", bootstyle="danger-outline", width=11,
            state=DISABLED, command=self.cancel_download)
        self.cancel_btn.pack(side=LEFT, padx=(10, 0), ipady=6)

        self.open_btn = tb.Button(
            row, text="Open folder", bootstyle="secondary-outline", width=13,
            command=self.open_folder)
        self.open_btn.pack(side=RIGHT, ipady=6)

    def _build_status_card(self, parent):
        card = tb.Labelframe(parent, text="  Progress  ", padding=14)
        card.pack(fill=X, pady=(0, 12))

        self.title_label = tb.Label(card, text="Ready when you are",
                                    font=("-size 12 -weight bold"),
                                    wraplength=760)
        self.title_label.pack(anchor=W)

        self.progress = tb.Progressbar(card, maximum=100, bootstyle=PRIMARY)
        self.progress.pack(fill=X, pady=(8, 6))

        self.stats_label = tb.Label(
            card, text="Paste a link above, then click Download.",
            bootstyle=SECONDARY)
        self.stats_label.pack(anchor=W)

    def _build_log(self, parent):
        card = tb.Labelframe(parent, text="  Activity  ", padding=10)
        card.pack(fill=BOTH, expand=YES)

        try:
            bg = self.style.colors.inputbg
            fg = self.style.colors.inputfg
        except Exception:      # noqa: BLE001 - only affects colours
            bg, fg = "#1e1e1e", "#d4d4d4"

        wrap = tb.Frame(card)
        wrap.pack(fill=BOTH, expand=YES)

        self.log = tk.Text(wrap, height=7, wrap="word", relief="flat",
                           font=("TkFixedFont", 11), state="disabled",
                           background=bg, foreground=fg,
                           highlightthickness=0, padx=10, pady=8)
        self.log.pack(side=LEFT, fill=BOTH, expand=YES)

        bar = tb.Scrollbar(wrap, command=self.log.yview, bootstyle="round")
        bar.pack(side=RIGHT, fill=Y)
        self.log.config(yscrollcommand=bar.set)

    def _build_statusbar(self):
        bar = tb.Frame(self, padding=(self.PAD, 6))
        bar.pack(fill=X, side=BOTTOM)

        self.env_label = tb.Label(bar, text="", bootstyle=SECONDARY)
        self.env_label.pack(side=LEFT)

        tb.Button(bar, text="Update yt-dlp", bootstyle="secondary-link",
                  command=self.update_ytdlp).pack(side=RIGHT)

    # -- small helpers -------------------------------------------------

    def _toggle_theme(self):
        theme = "bootstrap-dark" if self.dark_mode.get() else "bootstrap-light"
        self.style.theme_use(theme)
        try:
            self.log.config(background=self.style.colors.inputbg,
                            foreground=self.style.colors.inputfg)
        except Exception:      # noqa: BLE001
            pass

    def _sync_download_btn(self):
        busy = bool(self.worker and self.worker.is_alive())
        has_url = bool(self.url_entry.get().strip())
        self.download_btn.config(
            state=NORMAL if has_url and not busy and yt_dlp else DISABLED)

    def clear_url(self):
        self.url_entry.delete(0, END)
        self._sync_download_btn()

    def _prefill_from_clipboard(self):
        """Fill the box when a link is already on the clipboard."""
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            return
        if text.startswith(("http://", "https://")) and len(text) < 500:
            self.url_entry.insert(0, text)
            self._sync_download_btn()
            self.log_msg("Found a link on your clipboard and filled it in.")

    def log_msg(self, text):
        self.log.config(state="normal")
        self.log.insert(END, text + "\n")
        self.log.see(END)
        self.log.config(state="disabled")

    def _check_dependencies(self):
        if yt_dlp is None:
            self.log_msg("ERROR: could not load yt-dlp.")
            if YTDLP_IMPORT_ERROR:
                self.log_msg(f"  {YTDLP_IMPORT_ERROR}")
            self.log_msg("Click Update yt-dlp to download a fresh copy.")
            self.env_label.config(text="yt-dlp missing", bootstyle=DANGER)
            return

        if YTDLP_PATH == UPDATED_YTDLP:
            source = "updated"
        elif YTDLP_PATH == BUNDLED_YTDLP:
            source = "bundled"
        else:
            source = "system"

        parts = [f"yt-dlp {yt_dlp.version.__version__} ({source})"]
        if find_ffmpeg():
            parts.append("ffmpeg ready")
        else:
            parts.append("ffmpeg missing")
            self.log_msg("WARNING: ffmpeg was not found. High resolution "
                         "merging and MP3 export will fail.")
        self.env_label.config(text="   •   ".join(parts))
        self.log_msg("Ready. Paste a video link above to begin.")

    def _compat_note(self):
        if self.apple_safe.get():
            self.log_msg("Compatibility mode on. H.264 and AAC only, which "
                         "caps YouTube at 1080p.")
        else:
            self.log_msg("Compatibility mode off. 4K is available, but those "
                         "files are AV1 or VP9 and need VLC or IINA.")

    # -- welcome and help ----------------------------------------------

    def _text_window(self, title, body, height=28):
        win = tb.Toplevel(title=title, transient=self, resizable=(False, True))
        frame = tb.Frame(win, padding=14)
        frame.pack(fill=BOTH, expand=YES)

        txt = tk.Text(frame, wrap="word", width=74, height=height,
                      relief="flat", padx=12, pady=10,
                      highlightthickness=0, font=("TkDefaultFont", 12))
        try:
            txt.config(background=self.style.colors.inputbg,
                       foreground=self.style.colors.inputfg)
        except Exception:      # noqa: BLE001
            pass
        txt.pack(side=LEFT, fill=BOTH, expand=YES)

        bar = tb.Scrollbar(frame, command=txt.yview, bootstyle="round")
        bar.pack(side=RIGHT, fill=Y)
        txt.config(yscrollcommand=bar.set)

        txt.insert("1.0", body)
        txt.config(state="disabled")

        tb.Button(win, text="Close", bootstyle=PRIMARY, width=12,
                  command=win.destroy).pack(pady=(0, 14))
        return win

    def _show_welcome(self):
        self._text_window(f"Welcome to {APP_NAME}", WELCOME_TEXT, height=24)
        self.settings["seen_welcome"] = True
        save_settings(self.settings)

    def _show_help(self):
        self._text_window(f"{APP_NAME} Help", HELP_TEXT)

    def _on_close(self):
        self.settings.update({
            "folder": self.folder.get(),
            "quality": self.quality.get(),
            "apple_safe": self.apple_safe.get(),
            "dark_mode": self.dark_mode.get(),
            "seen_welcome": True,
        })
        save_settings(self.settings)
        self.destroy()

    # -- clipboard and folders -----------------------------------------

    def paste_url(self):
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            return
        self.url_entry.delete(0, END)
        self.url_entry.insert(0, text)
        self._sync_download_btn()

    def choose_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.folder.get())
        if chosen:
            self.folder.set(chosen)

    def open_folder(self):
        path = self.finished_folder or self.folder.get()
        if not os.path.isdir(path):
            messagebox.showerror(APP_NAME, "That folder does not exist.")
            return
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def update_ytdlp(self):
        self.log_msg("Checking for a yt-dlp update...")

        def work():
            def log(text):
                self.msg_queue.put({"type": "log", "text": text})
            try:
                download_ytdlp(log)
            except Exception as exc:      # noqa: BLE001 - shown to the user
                log(f"Update failed: {exc}. Check your connection and "
                    f"try again.")

        threading.Thread(target=work, daemon=True).start()

    # -- actions -------------------------------------------------------

    def start_download(self):
        if self.worker and self.worker.is_alive():
            return

        url = self.url_entry.get().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        folder = self.folder.get()
        if not os.path.isdir(folder):
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError:
                messagebox.showerror(APP_NAME, "Cannot use that folder.")
                return

        self.progress.config(bootstyle=PRIMARY)
        self.progress["value"] = 0
        self.stats_label.config(text="Contacting the site...")
        self.title_label.config(text="Starting")
        self.cancel_btn.config(state=NORMAL)
        self.log_msg("-" * 56)

        self.worker = DownloadWorker(
            url, folder, self.quality.get(), self.subtitles.get(),
            self.playlist.get(), self.msg_queue,
            apple_safe=self.apple_safe.get())
        self.worker.start()
        self._sync_download_btn()

    def cancel_download(self):
        if self.worker and self.worker.is_alive():
            self.worker.cancel()
            self.log_msg("Cancelling...")
            self.cancel_btn.config(state=DISABLED)

    def _finish(self, title, stats, style):
        self.title_label.config(text=title)
        self.stats_label.config(text=stats)
        self.progress.config(bootstyle=style)
        self.cancel_btn.config(state=DISABLED)
        self._sync_download_btn()

    # -- queue pump ----------------------------------------------------

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                kind = msg["type"]

                if kind == "progress":
                    self.progress["value"] = msg["percent"]
                    self.stats_label.config(
                        text=f"{msg['percent']:.1f}%      {msg['speed']}"
                             f"      {msg['eta']} left      {msg['size']}")

                elif kind == "title":
                    self.title_label.config(text=msg["text"])
                    self.log_msg(msg["text"])

                elif kind == "log":
                    self.log_msg(msg["text"])

                elif kind == "done":
                    self.progress["value"] = 100
                    self.finished_folder = msg["folder"]
                    self._finish("Finished",
                                 f"Saved to {msg['folder']}", SUCCESS)
                    self.log_msg(f"Saved to: {msg['folder']}")

                elif kind == "cancelled":
                    self.progress["value"] = 0
                    self._finish("Cancelled", "Nothing was saved.", SECONDARY)
                    self.log_msg("Download cancelled.")

                elif kind == "error":
                    self._finish("Could not download that one",
                                 "See the Activity log below.", DANGER)
                    self.log_msg(f"ERROR: {msg['text']}")
                    messagebox.showerror(APP_NAME, msg["text"])

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)


# ----------------------------------------------------------------------

def main():
    # Lets a user repair a broken yt-dlp without the GUI, and lets a
    # packaged build be tested without clicking anything.
    if "--update-ytdlp" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        print(f"current yt-dlp: {YTDLP_VERSION or 'none'}")
        print(f"loaded from   : {YTDLP_PATH or 'not loaded'}")
        try:
            download_ytdlp()
        except Exception as exc:          # noqa: BLE001
            print(f"Update failed: {exc}")
            return 1
        return 0

    app = DownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    sys.exit(main())
