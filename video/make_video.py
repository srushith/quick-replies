"""Assemble the final walkthrough: recording + narration clips + end card -> 1080p MP4.

    .venv\\Scripts\\python.exe video\\make_video.py

Finds the sync flash (magenta frames) at the start of video/build/rec.mkv, trims to it,
places each narration clip at its scene start (timeline.json), appends an end card and
writes dist/QuickReplies-walkthrough.mp4.
"""
import array
import json
import os
import subprocess
import sys
import wave

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(ROOT, "dist", "QuickReplies-walkthrough.mp4")
FPS = 30
RATE = 24000
W, H = 1920, 1080


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode:
        err = r.stderr.decode(errors="replace") if isinstance(r.stderr, bytes) else r.stderr
        sys.exit(f"{cmd[0]} failed: {err[-600:]}")
    return r


def sync_offset(rec):
    """Seconds into rec.mkv where the magenta sync frames end (= timeline t0)."""
    raw = run(["ffmpeg", "-v", "error", "-t", "8", "-i", rec, "-vf", f"fps={FPS},scale=8:4",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
    size = 8 * 4 * 3
    last_magenta = None
    for i in range(len(raw) // size):
        frame = raw[i * size:(i + 1) * size]
        px = [frame[j:j + 3] for j in range(0, size, 3)]
        mag = sum(1 for p in px if p[0] > 190 and p[1] < 90 and p[2] > 190)
        if mag >= len(px) * 0.8:
            last_magenta = i
        elif last_magenta is not None:
            return (last_magenta + 1) / FPS
    sys.exit("Sync flash not found at the start of the recording.")


def read_pcm(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
        return a


def compose_audio(timeline, clips, total, path):
    starts = {s["id"]: s["start"] for s in timeline["scenes"]}
    mix = array.array("h", bytes(2 * int(total * RATE)))
    for c in clips:
        pcm = read_pcm(c["wav"])
        off = int((starts[c["id"]] + timeline["lead"]) * RATE)
        n = min(len(pcm), len(mix) - off)
        mix[off:off + n] = pcm[:n]
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(mix.tobytes())


def font(names, size):
    for n in names:
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def end_card(path):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, bottom = (0x14, 0x17, 0x2e), (0x3b, 0x27, 0x6e)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    src = None
    for name in ("icon512.png", "icon256.png", "icon128.png"):
        p = os.path.join(ROOT, "assets", name)
        if os.path.exists(p):
            src = Image.open(p).convert("RGBA")
            break
    size = 240
    icon = src.resize((size, size), Image.LANCZOS)
    glow = Image.new("RGBA", (size + 160, size + 160), (0, 0, 0, 0))
    glow.paste(Image.new("RGBA", (size, size), (167, 139, 250, 110)), (80, 80), icon)
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    ix, iy = (W - size) // 2, 230
    img.paste(glow, (ix - 80, iy - 80), glow)
    img.paste(icon, (ix, iy), icon)
    title = font(["seguisb.ttf", "segoeuib.ttf", "segoeui.ttf"], 84)
    sub = font(["segoeui.ttf"], 40)
    mono = font(["CascadiaMono.ttf", "consola.ttf"], 34)

    def centered(text, y, f, fill):
        x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f)
        d.text(((W - (x1 - x0)) // 2, y), text, font=f, fill=fill)

    centered("Quick Replies for Windows", 530, title, (232, 238, 248))
    centered("Your replies, one shortcut away. In any app.", 650, sub, (180, 192, 211))
    keys = "Ctrl + Shift + Space"
    x0, y0, x1, y1 = d.textbbox((0, 0), keys, font=mono)
    kw, kx, ky = x1 - x0, (W - (x1 - x0)) // 2, 760
    d.rounded_rectangle([kx - 28, ky - 16, kx + kw + 28, ky + (y1 - y0) + 26], radius=14,
                        fill=(11, 15, 25), outline=(34, 211, 238), width=3)
    d.text((kx, ky), keys, font=mono, fill=(34, 211, 238))
    centered("Get it on the Microsoft Store", 880, sub, (167, 139, 250))
    img.save(path)


def main():
    rec = os.path.join(BUILD, "rec.mkv")
    timeline = json.load(open(os.path.join(BUILD, "timeline.json")))
    clips = json.load(open(os.path.join(BUILD, "clips.json")))
    t0 = sync_offset(rec)
    rec_len = timeline["end"]
    outro = next(s for s in timeline["scenes"] if s["id"] == "outro")
    outro_clip = next(c for c in clips if c["id"] == "outro")
    narration_end = outro["start"] + timeline["lead"] + outro_clip["seconds"]
    card_len = max(3.5, narration_end + 1.2 - rec_len)
    total = rec_len + card_len
    print(f"sync at {t0:.2f}s, recording {rec_len:.1f}s + end card {card_len:.1f}s = {total:.1f}s")

    audio = os.path.join(BUILD, "narration_mix.wav")
    card = os.path.join(BUILD, "end_card.png")
    compose_audio(timeline, clips, total, audio)
    end_card(card)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fade_out = total - 0.6
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-ss", f"{t0:.3f}", "-t", f"{rec_len:.3f}", "-i", rec,
         "-loop", "1", "-framerate", str(FPS), "-t", f"{card_len:.3f}", "-i", card,
         "-i", audio,
         "-filter_complex",
         f"[0:v]scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1,format=yuv420p,"
         f"fade=t=in:st=0:d=0.4[a];"
         f"[1:v]scale={W}:{H},fps={FPS},setsar=1,format=yuv420p,fade=t=in:st=0:d=0.5[b];"
         f"[a][b]concat=n=2:v=1:a=0,fade=t=out:st={fade_out:.3f}:d=0.6[v];"
         f"[2:a]afade=t=out:st={fade_out:.3f}:d=0.6[aout]",
         "-map", "[v]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
