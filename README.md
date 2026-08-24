# Media Downloader

A local desktop app for downloading videos from YouTube, Instagram, Facebook,
TikTok and around 1000 other sites. Runs entirely on your machine. No server,
no hosting cost, no bandwidth bill.

## Setup

### 1. Install Python
Python 3.9 or newer. On Windows, tick **Add Python to PATH** during install.

### 2. Install yt-dlp
```bash
pip install yt-dlp
```

### 3. Install ffmpeg
Required for merging high resolution video with separate audio, and for MP3 export.

**Windows**
```bash
winget install ffmpeg
```
Or download from gyan.dev, extract, and add the `bin` folder to PATH.

**macOS**
```bash
brew install ffmpeg
```

**Linux**
```bash
sudo apt install ffmpeg
```

Verify it worked:
```bash
ffmpeg -version
```

### 4. Run
```bash
python media_downloader.py
```

If tkinter is missing on Linux: `sudo apt install python3-tk`

## Features

| Feature | Notes |
|---|---|
| Quality presets | Best, 1080p, 720p, 480p, 360p, smallest |
| Audio only | Exports MP3 at 192kbps |
| Subtitles | English, Sinhala, Tamil, including auto generated |
| Playlists | Optional, off by default |
| Live progress | Percentage, speed, ETA, file size |
| Cancel | Stops mid download cleanly |
| Auto update | Updates yt-dlp from inside the app |

Files are saved as `Title [videoID].mp4` so nothing overwrites anything else.

## Important: keep yt-dlp updated

YouTube changes its player regularly and breaks extractors, sometimes weekly.
When downloads suddenly stop working, this is almost always the cause. Hit
**Update yt-dlp** in the app, or run:

```bash
pip install -U yt-dlp
```

This is the single most common reason these tools appear broken.

## Common problems

**"Sign in to confirm you're not a bot"**
YouTube's bot detection. Rare on a home connection, common on a VPS. If it
persists, export your browser cookies with a Netscape format cookie extension,
save as `cookies.txt` next to the app, and add to `build_options`:
```python
opts["cookiefile"] = "cookies.txt"
```

**Instagram or Facebook fails**
Public posts and reels work without login. Private accounts, stories and
anything behind a login wall need cookies as above. Be aware that using account
cookies for automated access can get the account flagged.

**Only 360p downloads**
ffmpeg is missing. Higher resolutions ship video and audio as separate streams
that must be merged.

**Slow speeds**
YouTube throttles some formats. Increase `concurrent_fragment_downloads` in
`build_options` from 4 to 8.

## Packaging as a standalone app

To produce a single file others can run without installing Python.

```bash
pip install pyinstaller
```

**Windows**
```bash
pyinstaller --onefile --windowed --name MediaDownloader media_downloader.py
```

**macOS**
```bash
pyinstaller --onefile --windowed --name MediaDownloader --osx-bundle-identifier com.tioss.mediadownloader media_downloader.py
```

Output lands in `dist/`.

To bundle ffmpeg so users do not need to install it, put the binary in a `bin`
folder beside the script and add:
```bash
--add-binary "bin/ffmpeg.exe;bin"     # Windows, use : instead of ; on macOS
```
The app already checks `bin/ffmpeg` before falling back to PATH.

**Signing.** Unsigned builds trigger security warnings. Windows certificates run
a few hundred dollars a year. Apple's developer program is 99 dollars a year and
notarization is mandatory on modern macOS or the app will not open at all. For
personal or portfolio use, ship unsigned and tell people to right click and
choose Open on first launch.

**Distribution.** Neither the Microsoft Store nor the Mac App Store accepts
downloader apps. GitHub Releases is the practical channel.

## Legal note

Downloading is a ToS violation on all three platforms. Fine for content you own,
Creative Commons material, or content you have permission for. Redistributing
copyrighted material is a different matter entirely. Keep this local and personal.

## Ideas for extending it

- Batch queue reading URLs from a text file
- Drag and drop URL support
- Local Whisper transcription for Sinhala subtitle generation
- Auto clipping long videos into short form vertical cuts
- Thumbnail preview before download

The last three are considerably more interesting than the downloader itself.

Sasindu Bandara
Follow for more

---

## Building the installers

Installers are built by GitHub Actions. Push a tag and all three are
produced automatically and attached to a draft release:

```bash
git tag v1.1
git push origin v1.1
```

The matrix in `.github/workflows/build.yml` covers macOS Apple Silicon
(`macos-14`), macOS Intel (`macos-13`) and Windows (`windows-latest`).
PyInstaller cannot cross compile, so each target needs its own runner.

### Building locally

Only builds for the machine you are on.

```bash
pip install -r requirements.txt pyinstaller
bash packaging/build_macos.sh          # macOS
powershell packaging/build_windows.ps1 # Windows, needs Inno Setup
```

`packaging/fetch_ffmpeg.py` downloads a static ffmpeg into `bin/` and
refuses any build compiled with `--enable-nonfree`, since those cannot
legally be redistributed. macOS binaries come from ffmpeg.martin-riedl.de
and Windows from gyan.dev; both are plain GPL v3 builds.

Note that a local macOS build inherits the deployment target of the
Python that built it. Homebrew's Python targets the current macOS only,
so builds made with it will not run on older systems. The CI runners use
python.org builds, which do not have this problem.

See [INSTALL.md](INSTALL.md) for the end user instructions.
