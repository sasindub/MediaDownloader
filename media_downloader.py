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
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Media Downloader"
APP_VERSION = "1.0"

# ----------------------------------------------------------------------
# Dependency check
# ----------------------------------------------------------------------

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


def find_ffmpeg():
    """Return path to ffmpeg, checking PATH first then the app folder."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = os.path.join(here, "bin", name)
        if os.path.isfile(candidate):
            return candidate
    return None


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

    def run(self):
        try:
            self.q.put({"type": "log", "text": "Fetching video information..."})

            with yt_dlp.YoutubeDL(self.build_options()) as ydl:
                info = ydl.extract_info(self.url, download=False)

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
                ydl.download([self.url])

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

        return raw[:400]


# ----------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------

class DownloaderApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("720x600")
        self.minsize(640, 560)

        self.msg_queue = queue.Queue()
        self.worker = None
        self.folder = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Downloads")
        )
        self.quality = tk.StringVar(value="Best available")
        self.subtitles = tk.BooleanVar(value=False)
        self.playlist = tk.BooleanVar(value=False)
        self.apple_safe = tk.BooleanVar(value=True)

        self._build_ui()
        self._check_dependencies()
        self.after(100, self._poll_queue)

    # -- layout --------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 14, "pady": 6}

        header = ttk.Frame(self)
        header.pack(fill="x", **pad)
        ttk.Label(header, text=APP_NAME,
                  font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(header,
                  text="YouTube, Instagram, Facebook, TikTok and more",
                  foreground="#666").pack(anchor="w")

        # URL
        url_frame = ttk.LabelFrame(self, text="Video URL")
        url_frame.pack(fill="x", **pad)
        row = ttk.Frame(url_frame)
        row.pack(fill="x", padx=10, pady=10)

        self.url_entry = ttk.Entry(row, font=("Segoe UI", 10))
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda e: self.start_download())

        ttk.Button(row, text="Paste", width=8,
                   command=self.paste_url).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Clear", width=8,
                   command=lambda: self.url_entry.delete(0, "end")
                   ).pack(side="left", padx=(6, 0))

        # Options
        opt = ttk.LabelFrame(self, text="Options")
        opt.pack(fill="x", **pad)

        r1 = ttk.Frame(opt)
        r1.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(r1, text="Quality:", width=10).pack(side="left")
        ttk.Combobox(r1, textvariable=self.quality, width=22, state="readonly",
                     values=list(QUALITY_PRESETS.keys())).pack(side="left")

        ttk.Checkbutton(r1, text="Download subtitles",
                        variable=self.subtitles).pack(side="left", padx=(20, 0))
        ttk.Checkbutton(r1, text="Whole playlist",
                        variable=self.playlist).pack(side="left", padx=(14, 0))

        r1b = ttk.Frame(opt)
        r1b.pack(fill="x", padx=10, pady=(4, 4))
        ttk.Label(r1b, text="", width=10).pack(side="left")
        ttk.Checkbutton(r1b, text="QuickTime compatible (H.264 + AAC)",
                        variable=self.apple_safe,
                        command=self._compat_note).pack(side="left")
        ttk.Label(r1b, text="caps YouTube at 1080p",
                  foreground="#666").pack(side="left", padx=(8, 0))

        r2 = ttk.Frame(opt)
        r2.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Label(r2, text="Save to:", width=10).pack(side="left")
        ttk.Entry(r2, textvariable=self.folder).pack(
            side="left", fill="x", expand=True)
        ttk.Button(r2, text="Browse", width=8,
                   command=self.choose_folder).pack(side="left", padx=(8, 0))

        # Buttons
        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        self.download_btn = ttk.Button(btns, text="Download",
                                       command=self.start_download)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="Cancel", state="disabled",
                                     command=self.cancel_download)
        self.cancel_btn.pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Open folder",
                   command=self.open_folder).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Update yt-dlp",
                   command=self.update_ytdlp).pack(side="right")

        # Progress
        prog = ttk.LabelFrame(self, text="Progress")
        prog.pack(fill="x", **pad)

        self.title_label = ttk.Label(prog, text="Ready",
                                     font=("Segoe UI", 10, "bold"),
                                     wraplength=640)
        self.title_label.pack(anchor="w", padx=10, pady=(10, 4))

        self.progress = ttk.Progressbar(prog, maximum=100)
        self.progress.pack(fill="x", padx=10)

        self.stats_label = ttk.Label(prog, text="", foreground="#666")
        self.stats_label.pack(anchor="w", padx=10, pady=(4, 10))

        # Log
        log_frame = ttk.LabelFrame(self, text="Activity")
        log_frame.pack(fill="both", expand=True, padx=14, pady=(6, 14))

        self.log = tk.Text(log_frame, height=8, wrap="word",
                           font=("Consolas", 9), state="disabled",
                           background="#1e1e1e", foreground="#d4d4d4",
                           relief="flat")
        self.log.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        sb = ttk.Scrollbar(log_frame, command=self.log.yview)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 8))
        self.log.config(yscrollcommand=sb.set)

    # -- helpers -------------------------------------------------------

    def log_msg(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _check_dependencies(self):
        if yt_dlp is None:
            self.log_msg("ERROR: yt-dlp is not installed.")
            self.log_msg("Run:  pip install yt-dlp")
            self.download_btn.config(state="disabled")
            return

        self.log_msg(f"yt-dlp {yt_dlp.version.__version__} loaded.")

        if find_ffmpeg():
            self.log_msg("ffmpeg found.")
        else:
            self.log_msg("WARNING: ffmpeg not found on PATH.")
            self.log_msg("High resolution merging and MP3 export will fail.")

        self.log_msg("Ready. Paste a URL to begin.")

    def _compat_note(self):
        if self.apple_safe.get():
            self.log_msg("QuickTime mode on. H.264 and AAC only, 1080p max on "
                         "YouTube.")
        else:
            self.log_msg("QuickTime mode off. Higher resolutions may arrive as "
                         "AV1 or VP9, which QuickTime cannot play. Use VLC or "
                         "IINA for those.")

    def paste_url(self):
        try:
            text = self.clipboard_get().strip()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
        except tk.TclError:
            pass

    def choose_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.folder.get())
        if chosen:
            self.folder.set(chosen)

    def open_folder(self):
        path = self.folder.get()
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
        self.log_msg("Updating yt-dlp, please wait...")

        def work():
            try:
                out = subprocess.run(
                    [sys.executable, "-m", "pip", "install",
                     "--upgrade", "yt-dlp"],
                    capture_output=True, text=True, timeout=180)
                ok = out.returncode == 0
                self.msg_queue.put({
                    "type": "log",
                    "text": ("yt-dlp updated. Restart the app to load the new "
                             "version." if ok else "Update failed. Run "
                             "'pip install -U yt-dlp' manually."),
                })
            except Exception as exc:
                self.msg_queue.put({"type": "log",
                                    "text": f"Update error: {exc}"})

        threading.Thread(target=work, daemon=True).start()

    # -- actions -------------------------------------------------------

    def start_download(self):
        if self.worker and self.worker.is_alive():
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(APP_NAME, "Please enter a URL.")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        folder = self.folder.get()
        if not os.path.isdir(folder):
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                messagebox.showerror(APP_NAME, "Cannot use that folder.")
                return

        self.progress["value"] = 0
        self.stats_label.config(text="")
        self.title_label.config(text="Connecting...")
        self.download_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.log_msg("-" * 50)

        self.worker = DownloadWorker(
            url, folder, self.quality.get(),
            self.subtitles.get(), self.playlist.get(), self.msg_queue,
            apple_safe=self.apple_safe.get())
        self.worker.start()

    def cancel_download(self):
        if self.worker and self.worker.is_alive():
            self.worker.cancel()
            self.log_msg("Cancelling...")
            self.cancel_btn.config(state="disabled")

    def _reset_buttons(self):
        self.download_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")

    # -- queue pump ----------------------------------------------------

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                kind = msg["type"]

                if kind == "progress":
                    self.progress["value"] = msg["percent"]
                    self.stats_label.config(
                        text=f"{msg['percent']:.1f}%   "
                             f"{msg['speed']}   "
                             f"ETA {msg['eta']}   "
                             f"Size {msg['size']}")

                elif kind == "title":
                    self.title_label.config(text=msg["text"])
                    self.log_msg(msg["text"])

                elif kind == "log":
                    self.log_msg(msg["text"])

                elif kind == "done":
                    self.progress["value"] = 100
                    self.title_label.config(text="Completed")
                    self.log_msg(f"Saved to: {msg['folder']}")
                    self._reset_buttons()

                elif kind == "cancelled":
                    self.title_label.config(text="Cancelled")
                    self.progress["value"] = 0
                    self.log_msg("Download cancelled.")
                    self._reset_buttons()

                elif kind == "error":
                    self.title_label.config(text="Failed")
                    self.log_msg(f"ERROR: {msg['text']}")
                    self._reset_buttons()
                    messagebox.showerror(APP_NAME, msg["text"])

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)


# ----------------------------------------------------------------------

def main():
    app = DownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
