#!/usr/bin/env python3
"""Draw the app icon and export it for macOS and Windows.

Run this only when the icon changes. The generated files are committed
so that building does not need Pillow.

    python packaging/make_icon.py
"""

import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS = os.path.join(ROOT, "assets")
SIZE = 1024

# Deep indigo to violet, which reads clearly at small sizes in both the
# macOS dock and the Windows taskbar.
TOP = (79, 70, 229)
BOTTOM = (147, 51, 234)
WHITE = (255, 255, 255, 255)


def rounded_gradient(size, radius):
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel((0, y), tuple(
            round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)))
    grad = grad.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def draw_mark(img):
    """A play triangle sitting above a download arrow and a base line."""
    d = ImageDraw.Draw(img)
    c = SIZE // 2

    # Play triangle, the "media" half of the idea.
    tri = SIZE * 0.150
    top = SIZE * 0.190
    d.polygon([(c - tri * 0.80, top),
               (c - tri * 0.80, top + tri * 1.75),
               (c + tri * 0.92, top + tri * 0.875)], fill=WHITE)

    # Arrow shaft and head, the "download" half, clear of the triangle.
    shaft_w = SIZE * 0.080
    shaft_top = SIZE * 0.530
    shaft_bottom = SIZE * 0.660
    d.rounded_rectangle([c - shaft_w / 2, shaft_top,
                         c + shaft_w / 2, shaft_bottom],
                        radius=shaft_w / 2, fill=WHITE)

    head = SIZE * 0.150
    tip = SIZE * 0.790
    d.polygon([(c - head, shaft_bottom - SIZE * 0.012),
               (c + head, shaft_bottom - SIZE * 0.012),
               (c, tip)], fill=WHITE)

    # Base line, the tray the file lands in.
    bar_w = SIZE * 0.40
    bar_y = SIZE * 0.858
    bar_h = SIZE * 0.055
    d.rounded_rectangle([c - bar_w / 2, bar_y,
                         c + bar_w / 2, bar_y + bar_h],
                        radius=bar_h / 2, fill=WHITE)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    icon = rounded_gradient(SIZE, radius=int(SIZE * 0.225))
    draw_mark(icon)

    png = os.path.join(ASSETS, "icon.png")
    icon.save(png)
    print("wrote", png)

    # Small sizes for use inside the window itself. Tk can only subsample
    # by whole numbers, so scaling is done here instead.
    for px in (64, 128):
        small = os.path.join(ASSETS, f"icon_{px}.png")
        icon.resize((px, px), Image.LANCZOS).save(small)
        print("wrote", small)

    ico = os.path.join(ASSETS, "icon.ico")
    icon.save(ico, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("wrote", ico)

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
