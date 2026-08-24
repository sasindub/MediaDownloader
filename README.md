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

# Development

## Branches

Three kinds of branch, nothing more.

| Branch | What it is | Who merges into it |
|---|---|---|
| `main` | Released code. Every commit here is a version people downloaded. Never commit to it directly. | `release/*` and `hotfix/*` only |
| `dev` | Day to day work. The next version, in progress. | `feature/*` branches |
| `release/1.2` | A version being prepared. Only bug fixes and the version bump go in. | nothing, it is the end of the line |

Short lived branches you create as needed:

| Branch | Cut from | Merges back into |
|---|---|---|
| `feature/batch-queue` | `dev` | `dev` |
| `hotfix/1.1.1` | `main` | `main` **and** `dev` |

Rule of thumb: **work on `dev`, release from `main`.**

## Versions

Plain [semantic versioning](https://semver.org), `MAJOR.MINOR.PATCH`.

| Part | Bump it when | Example |
|---|---|---|
| PATCH | A bug fix, nothing new | `1.1.0` to `1.1.1` |
| MINOR | A new feature, old things still work | `1.1.0` to `1.2.0` |
| MAJOR | Something people relied on has changed or gone | `1.9.0` to `2.0.0` |

Tags are the version with a `v` in front: `v1.1.0`. **The tag is what
triggers a build**, so nothing ships until you push one.

The version lives in three files and all three must match:

```
media_downloader.py           APP_VERSION
packaging/MediaDownloader.spec  version, CFBundleShortVersionString, CFBundleVersion
packaging/installer.iss       AppVersion
```

## Day to day work

```bash
git checkout dev
git pull

git checkout -b feature/drag-and-drop
# ... write code, commit as you go ...

git checkout dev
git merge feature/drag-and-drop
git push origin dev
git branch -d feature/drag-and-drop
```

Nothing is built or published by any of this. `dev` is safe to break.

## Making a release

Say `dev` has the features you want and you are shipping 1.2.0.

**1. Cut a release branch.**

```bash
git checkout dev
git checkout -b release/1.2
```

**2. Bump the version** in the three files listed above, then commit.

```bash
git commit -am "Bump version to 1.2.0"
```

**3. Test it.** Build locally, install it, download a video. Fix anything
broken directly on the release branch.

```bash
bash packaging/build_macos.sh
```

**4. Merge into `main` and tag.**

```bash
git checkout main
git merge --no-ff release/1.2
git tag v1.2.0
git push origin main --tags
```

Pushing the tag starts the build. Ten minutes later a **draft release**
appears on GitHub with all three installers attached.

**5. Merge back into `dev`**, so the version bump and any fixes are not
lost.

```bash
git checkout dev
git merge --no-ff release/1.2
git push origin dev
git branch -d release/1.2
```

**6. Publish the release** on GitHub once you have tested the installers,
and upload them to your site.

## Fixing something urgent in a release

Skip `dev` entirely. Branch from `main`, fix, and release a PATCH.

```bash
git checkout main
git checkout -b hotfix/1.1.1
# fix it, bump the version to 1.1.1, commit
git checkout main
git merge --no-ff hotfix/1.1.1
git tag v1.1.1
git push origin main --tags
git checkout dev && git merge --no-ff hotfix/1.1.1 && git push origin dev
```

## How the installers get built

`.github/workflows/build.yml` runs on every `v*` tag. It builds on three
runners, because PyInstaller cannot cross compile:

| Runner | Produces |
|---|---|
| `macos-14` | `MediaDownloader-macOS-arm64.dmg` for Apple Silicon |
| `macos-13` | `MediaDownloader-macOS-x86_64.dmg` for Intel Macs |
| `windows-latest` | `MediaDownloader-Windows-Setup.exe` |

Watch a build with:

```bash
gh run watch
```

### Building locally

Only builds for the machine you are sitting at.

```bash
pip install -r requirements.txt pyinstaller
bash packaging/build_macos.sh          # macOS
powershell packaging/build_windows.ps1 # Windows, needs Inno Setup
```

A local macOS build inherits the deployment target of the Python that
built it. Homebrew's Python targets the current macOS only, so those
builds will not run on older systems. **Use local builds for testing and
CI builds for shipping.**

### ffmpeg

`packaging/fetch_ffmpeg.py` downloads a static ffmpeg into `bin/` at build
time, so it is never committed. It refuses any build compiled with
`--enable-nonfree`, because those cannot legally be redistributed. macOS
binaries come from ffmpeg.martin-riedl.de, Windows from gyan.dev. Both are
plain GPL v3 builds, and `bin/FFMPEG-LICENCE.txt` carries the source offer
that the licence requires.

### Signing

Builds are unsigned, so both operating systems warn on first launch.
macOS builds are ad hoc signed, which is free and required on Apple
Silicon, otherwise macOS calls the app damaged rather than merely
unverified. [INSTALL.md](INSTALL.md) tells users how to get past the
warning.

To sign properly later, add an Apple Developer certificate and a Windows
code signing certificate as GitHub secrets and extend the workflow. No
restructuring needed.

See [INSTALL.md](INSTALL.md) for the end user instructions.
