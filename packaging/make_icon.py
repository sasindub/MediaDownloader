#!/usr/bin/env python3
"""Build the app icon and the platform badges from source artwork.

Run this only when the artwork changes. The generated files are
committed, so a build does not need Pillow or these system fonts.

    python packaging/make_icon.py
"""

import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS = os.path.join(ROOT, "assets")
LOGO_SOURCE = os.path.join(ASSETS, "logo_source.webp")
SIZE = 1024

FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]


def load_font(px):
    for path in FONTS:
        if os.path.isfile(path):
            return ImageFont.truetype(path, px)
    return ImageFont.load_default()


# ----------------------------------------------------------------------
# App icon, built from the supplied artwork
# ----------------------------------------------------------------------

def build_app_icon():
    """Trim the artwork to its content and centre it on a square canvas."""
    art = Image.open(LOGO_SOURCE).convert("RGBA")

    box = art.getbbox()
    if box:
        art = art.crop(box)

    # Leave a margin so the icon does not collide with the edges of a
    # dock tile or a taskbar button.
    inner = int(SIZE * 0.88)
    scale = min(inner / art.width, inner / art.height)
    art = art.resize((max(1, round(art.width * scale)),
                      max(1, round(art.height * scale))), Image.LANCZOS)

    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(art, ((SIZE - art.width) // 2, (SIZE - art.height) // 2), art)
    return canvas


# ----------------------------------------------------------------------
# Platform badges shown in the window header
# ----------------------------------------------------------------------

BADGE = 96          # drawn large, then scaled down for a clean edge


def badge(colour):
    img = Image.new("RGBA", (BADGE, BADGE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, BADGE - 1, BADGE - 1],
                        radius=int(BADGE * 0.28), fill=colour)
    return img, d


def youtube():
    img, d = badge((255, 0, 0, 255))
    c = BADGE / 2
    w = BADGE * 0.17
    d.polygon([(c - w, c - w * 1.25), (c - w, c + w * 1.25),
               (c + w * 1.45, c)], fill="white")
    return img


def facebook():
    img, d = badge((24, 119, 242, 255))
    f = load_font(int(BADGE * 0.78))
    d.text((BADGE * 0.5, BADGE * 0.52), "f", font=f, fill="white",
           anchor="mm")
    return img


def instagram():
    """Rounded square with the familiar warm gradient and camera outline."""
    grad = Image.new("RGB", (BADGE, BADGE))
    gd = ImageDraw.Draw(grad)
    top, mid, bottom = (254, 218, 117), (214, 41, 118), (129, 52, 175)
    for y in range(BADGE):
        t = y / (BADGE - 1)
        if t < 0.5:
            a, b, k = top, mid, t / 0.5
        else:
            a, b, k = mid, bottom, (t - 0.5) / 0.5
        gd.line([(0, y), (BADGE, y)],
                fill=tuple(round(a[i] + (b[i] - a[i]) * k) for i in range(3)))

    mask = Image.new("L", (BADGE, BADGE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, BADGE - 1, BADGE - 1], radius=int(BADGE * 0.28), fill=255)
    img = Image.new("RGBA", (BADGE, BADGE), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    pad, line = BADGE * 0.22, max(2, int(BADGE * 0.062))
    d.rounded_rectangle([pad, pad, BADGE - pad, BADGE - pad],
                        radius=int(BADGE * 0.20), outline="white", width=line)
    r = BADGE * 0.155
    c = BADGE / 2
    d.ellipse([c - r, c - r, c + r, c + r], outline="white", width=line)
    dot = BADGE * 0.045
    dx = BADGE - pad * 1.42
    d.ellipse([dx - dot, pad * 1.30 - dot, dx + dot, pad * 1.30 + dot],
              fill="white")
    return img


def tiktok():
    """Black badge with a music note, offset in cyan and pink."""
    img, d = badge((0, 0, 0, 255))

    def note(dx, dy, colour):
        x, y = BADGE * 0.38 + dx, BADGE * 0.26 + dy
        stem = max(2, int(BADGE * 0.085))
        d.rounded_rectangle([x, y, x + stem, y + BADGE * 0.38],
                            radius=stem / 2, fill=colour)
        head = BADGE * 0.115
        d.ellipse([x - head * 1.25, y + BADGE * 0.30,
                   x + head * 0.95, y + BADGE * 0.30 + head * 2],
                  fill=colour)
        d.polygon([(x + stem, y),
                   (x + stem + BADGE * 0.20, y + BADGE * 0.05),
                   (x + stem, y + BADGE * 0.15)], fill=colour)

    note(-BADGE * 0.045, BADGE * 0.035, (37, 244, 238, 255))   # cyan
    note(BADGE * 0.045, -BADGE * 0.02, (254, 44, 85, 255))     # pink
    note(0, 0, (255, 255, 255, 255))
    return img


PLATFORMS = {
    "youtube": youtube,
    "tiktok": tiktok,
    "instagram": instagram,
    "facebook": facebook,
}


def main():
    os.makedirs(ASSETS, exist_ok=True)

    icon = build_app_icon()
    png = os.path.join(ASSETS, "icon.png")
    icon.save(png)
    print("wrote", png)

    # Tk can only subsample by whole numbers, so window sizes are made here.
    for px in (64, 128):
        out = os.path.join(ASSETS, f"icon_{px}.png")
        icon.resize((px, px), Image.LANCZOS).save(out)
        print("wrote", out)

    # Windows icons have no alpha in some shells, so flatten onto white.
    flat = Image.new("RGBA", icon.size, (255, 255, 255, 255))
    flat.alpha_composite(icon)
    ico = os.path.join(ASSETS, "icon.ico")
    flat.convert("RGB").save(
        ico, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("wrote", ico)

    for name, builder in PLATFORMS.items():
        out = os.path.join(ASSETS, f"platform_{name}.png")
        builder().resize((22, 22), Image.LANCZOS).save(out)
        print("wrote", out)

    if sys.platform == "darwin":
        iconset = os.path.join(ASSETS, "AppIcon.iconset")
        shutil.rmtree(iconset, ignore_errors=True)
        os.makedirs(iconset)
        for base in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                px = base * scale
                name = f"icon_{base}x{base}{'@2x' if scale == 2 else ''}.png"
                icon.resize((px, px), Image.LANCZOS).save(
                    os.path.join(iconset, name))
        icns = os.path.join(ASSETS, "AppIcon.icns")
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns],
                       check=True)
        shutil.rmtree(iconset, ignore_errors=True)
        print("wrote", icns)


if __name__ == "__main__":
    main()
