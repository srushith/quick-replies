"""Generate the MSIX logo set from assets/icon128.png.

    python packaging/make_assets.py <out_dir>

Writes scale-100/200 and targetsize-* variants; makepri (in build-msix.ps1) indexes them
so Windows picks the sharpest one. The source is 128 px, so the 256/300 px variants are
upscaled; drop a larger assets/icon512.png in to get sharper ones.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def source():
    for name in ("icon512.png", "icon256.png", "icon128.png"):
        p = os.path.join(ROOT, "assets", name)
        if os.path.exists(p):
            return Image.open(p).convert("RGBA")
    raise SystemExit("no source icon in assets/")


def square(src, size, pad=0.0):
    """Icon centered on a transparent size*size canvas with fractional padding."""
    inner = max(1, round(size * (1 - 2 * pad)))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon = src.resize((inner, inner), Image.LANCZOS)
    canvas.paste(icon, ((size - inner) // 2, (size - inner) // 2), icon)
    return canvas


def wide(src, w, h):
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    inner = round(h * 0.6)
    icon = src.resize((inner, inner), Image.LANCZOS)
    canvas.paste(icon, ((w - inner) // 2, (h - inner) // 2), icon)
    return canvas


def main(out):
    os.makedirs(out, exist_ok=True)
    src = source()
    files = {}
    for scale in (100, 200):
        f = scale / 100
        files[f"StoreLogo.scale-{scale}.png"] = square(src, round(50 * f))
        files[f"Square150x150Logo.scale-{scale}.png"] = square(src, round(150 * f), pad=0.18)
        files[f"Square44x44Logo.scale-{scale}.png"] = square(src, round(44 * f))
        files[f"Wide310x150Logo.scale-{scale}.png"] = wide(src, round(310 * f), round(150 * f))
    for t in (16, 24, 32, 48, 256):
        img = square(src, t)
        files[f"Square44x44Logo.targetsize-{t}.png"] = img
        files[f"Square44x44Logo.targetsize-{t}_altform-unplated.png"] = img
    for name, img in files.items():
        img.save(os.path.join(out, name))
    print(f"wrote {len(files)} logo files to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "msix", "Assets"))
