"""Generate the ChgNet Studio application icon.

Design: an iOS style rounded square in a teal->blue gradient with a white
atom/graph motif (a central node wired to orbiting nodes) -- a nod to the
CHGNet graph neural network potential and 3D structure visualisation.
Rendered at high resolution and downsampled to a multi-size .ico.

Usage:
    python assets/make_icon.py
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER = 1024
ICO_SIZES = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]

# cool teal -> indigo gradient (top -> bottom)
TOP = (96, 226, 214)
BOTTOM = (48, 120, 230)
GLOW = (206, 250, 246)


def _gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        t = t ** 0.92
        r = round(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
        g = round(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
        b = round(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=radius, fill=255)
    return mask


def _draw_motif(size: int) -> Image.Image:
    """White graph/atom motif on a transparent layer."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size / 2.0

    ring_r = size * 0.315          # orbit radius
    node_r = size * 0.052
    core_r = size * 0.098
    wire_w = max(2, round(size * 0.020))

    angles = (-90, -18, 54, 126, 198)   # 5 satellites
    d = ImageDraw.Draw(layer)

    # wires from the core to every satellite
    for angle in angles:
        rad = math.radians(angle)
        x = cx + ring_r * math.cos(rad)
        y = cy + ring_r * math.sin(rad)
        d.line([(cx, cy), (x, y)], fill=(255, 255, 255, 200), width=wire_w)

    # satellite nodes
    for angle in angles:
        rad = math.radians(angle)
        x = cx + ring_r * math.cos(rad)
        y = cy + ring_r * math.sin(rad)
        d.ellipse([x - node_r, y - node_r, x + node_r, y + node_r],
                  fill=(255, 255, 255, 250))

    # nucleus
    d.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r],
              fill=(255, 255, 255, 255))
    return layer


def build_master() -> Image.Image:
    size = MASTER
    radius = round(size * 0.225)

    icon = _gradient(size).convert("RGBA")

    # soft highlight at the top for depth
    glow = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glow).ellipse(
        [-size * 0.35, -size * 0.75, size * 1.35, size * 0.45], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.10))
    icon = Image.composite(Image.new("RGBA", (size, size), GLOW + (255,)),
                           icon, glow)

    icon = Image.alpha_composite(icon, _draw_motif(size))

    # subtle inner light border
    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        [1, 1, size - 2, size - 2], radius=radius - 1,
        outline=(255, 255, 255, 46), width=max(2, round(size * 0.006)))
    icon = Image.alpha_composite(icon, border)

    icon.putalpha(_rounded_mask(size, radius))
    return icon


def main():
    master = build_master()
    master.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "app.png"))
    master.resize((256, 256), Image.LANCZOS).save(
        os.path.join(HERE, "app.ico"), format="ICO", sizes=ICO_SIZES)
    print("wrote assets/app.ico and assets/app.png")


if __name__ == "__main__":
    main()
