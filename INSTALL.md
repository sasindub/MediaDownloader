# Installing Media Downloader

Pick the file that matches your computer.

| Download | For |
|---|---|
| `MediaDownloader-macOS-arm64.dmg` | Macs with an M1, M2, M3 or M4 chip |
| `MediaDownloader-macOS-x86_64.dmg` | Intel Macs |
| `MediaDownloader-Windows-Setup.exe` | Windows 10 and 11, 64 bit |

Not sure which Mac you have? Click the Apple menu, choose About This Mac,
and look at the Chip line. Anything starting with Apple is the first one.

Everything needed is inside the download. You do not need to install
Python, ffmpeg, or anything else.

---

## macOS

**1.** Open the DMG and drag **Media Downloader** into Applications.

**2.** The first time you open it, macOS blocks it. This is expected.

The app is not signed with an Apple Developer certificate, which costs
99 US dollars a year. macOS treats any unsigned app this way. It is not
a sign that anything is wrong with the app.

### macOS 15 Sequoia and newer

1. Double click the app. macOS says it could not verify it. Click **Done**.
2. Open **System Settings** → **Privacy & Security**.
3. Scroll down to **Security**. You will see a line saying Media
   Downloader was blocked. Click **Open Anyway**.
4. Confirm with Touch ID or your password, then click **Open Anyway** again.

> Apple removed the old right click → Open shortcut in Sequoia. The
> Privacy & Security route above is now the only way.

### macOS 14 Sonoma and older

1. **Right click** the app and choose **Open**.
2. Click **Open** in the dialog.

After the first time, it opens normally by double clicking.

---

## Windows

**1.** Run `MediaDownloader-Windows-Setup.exe`.

**2.** SmartScreen will warn you. Click **More info**, then **Run anyway**.

Same reason as on macOS: the app is not signed with a code signing
certificate, which costs a few hundred dollars a year.

**3.** Follow the installer. It installs for the current user, so it does
not ask for an administrator password.

### If antivirus flags it

Some antivirus products flag PyInstaller applications as suspicious. This
is a known false positive across nearly every app built this way, because
the packaging method resembles techniques malware also uses. The source
code is public if you or your IT team want to check it, or build it
yourself.

---

## Using it

1. Copy a video link in your browser.
2. Click **Paste**.
3. Choose a quality and click **Download**.

Files go to your Downloads folder unless you change it.

### About 4K

**QuickTime compatible** is ticked by default. It downloads H.264 video
with AAC audio, which plays everywhere on a Mac or PC, imports into
iMovie and Photos, and AirDrops to an iPhone.

YouTube stopped producing H.264 above 1080p, so this caps YouTube
downloads at 1080p. Untick the box to get 4K, but those files use the
AV1 or VP9 codec:

- QuickTime Player will not open them. Use [VLC](https://www.videolan.org/)
  or [IINA](https://iina.io/), both free.
- They will not import into Photos, iMovie or Final Cut.
- On M1 and M2 Macs there is no hardware AV1 decoder, so playback uses a
  lot of processor and battery. M3 and newer are fine.

### If downloads suddenly stop working

Click **Update yt-dlp** in the app, then restart it. YouTube changes its
site regularly and breaks downloaders. This fixes it nearly every time.

---

## What is included

ffmpeg is bundled inside the app under the GNU General Public Licence
version 3, used unmodified as a separate program. Source is available at
<https://ffmpeg.org/download.html>. See `FFMPEG-LICENCE.txt` in the
install folder.

## Please use it responsibly

Downloading may breach the terms of service of these sites. Intended for
content you own, content licensed for reuse, and content you have
permission to download.
