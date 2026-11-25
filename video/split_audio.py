"""Split the narration into one clip per line (scene).

    python video/split_audio.py

Uses the per-line files in video/audio/ if they're named after the segments
(intro.wav, hotkey.mp3, ...). Otherwise takes the single recording in that folder and
cuts it at the pauses: of all detected pauses, it picks the ones that best match where
each line should end given its length in characters. Writes video/build/clips/*.wav
(24 kHz mono, silence trimmed) and video/build/clips.json.
"""
import json
import os
import re
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from narration import SEGMENTS  # noqa: E402

AUDIO = os.path.join(HERE, "audio")
OUT = os.path.join(HERE, "build", "clips")
EXTS = (".wav", ".mp3", ".m4a", ".ogg", ".flac")


def ffmpeg(*args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


def to_clip(src, dst, start=None, end=None):
    args = []
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    if end is not None:
        args += ["-to", f"{end:.3f}"]
    r = ffmpeg(*args, "-i", src, "-ac", "1", "-ar", "24000", "-sample_fmt", "s16",
               "-af", "silenceremove=start_periods=1:start_threshold=-45dB,"
                      "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
               dst)
    if r.returncode:
        sys.exit(f"ffmpeg failed on {src}: {r.stderr[-400:]}")


def silences(path):
    r = ffmpeg("-i", path, "-af", "silencedetect=noise=-40dB:d=0.25", "-f", "null", "-")
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    total = float(re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr).group(3)) + \
        60 * float(re.search(r"Duration: (\d+):(\d+)", r.stderr).group(2))
    return list(zip(starts, ends)), total


def best_cuts(gaps, total, n_cuts, weights):
    """Choose n_cuts gaps (in order) closest to the expected line boundaries."""
    cum, acc = [], 0
    for wgt in weights[:-1]:
        acc += wgt
        cum.append(total * acc / sum(weights))
    INF = float("inf")
    # dp[i][j] = best cost using gap j as cut i
    dp = [[INF] * len(gaps) for _ in range(n_cuts)]
    back = [[-1] * len(gaps) for _ in range(n_cuts)]
    for j, (s, e) in enumerate(gaps):
        dp[0][j] = (((s + e) / 2) - cum[0]) ** 2 - (e - s)
    for i in range(1, n_cuts):
        for j, (s, e) in enumerate(gaps):
            cost = (((s + e) / 2) - cum[i]) ** 2 - (e - s)
            for k in range(j):
                if dp[i - 1][k] + cost < dp[i][j]:
                    dp[i][j], back[i][j] = dp[i - 1][k] + cost, k
    j = min(range(len(gaps)), key=lambda x: dp[-1][x])
    picks = []
    for i in range(n_cuts - 1, -1, -1):
        picks.append(gaps[j])
        j = back[i][j]
    return picks[::-1], cum


def main():
    os.makedirs(OUT, exist_ok=True)
    files = [f for f in os.listdir(AUDIO) if f.lower().endswith(EXTS)]
    by_id = {os.path.splitext(f)[0].lower(): f for f in files}
    clips = []
    if all(seg_id in by_id for seg_id, _ in SEGMENTS):
        for seg_id, _ in SEGMENTS:
            dst = os.path.join(OUT, f"{seg_id}.wav")
            to_clip(os.path.join(AUDIO, by_id[seg_id]), dst)
            clips.append((seg_id, dst))
    elif len(files) == 1:
        src = os.path.join(AUDIO, files[0])
        gaps, total = silences(src)
        if len(gaps) < len(SEGMENTS) - 1:
            sys.exit(f"Only {len(gaps)} pauses found; need {len(SEGMENTS) - 1}.")
        cuts, expected = best_cuts(gaps, total, len(SEGMENTS) - 1,
                                   [len(text) for _, text in SEGMENTS])
        bounds = [0.0] + [(s + e) / 2 for s, e in cuts] + [total]
        for i, (seg_id, _) in enumerate(SEGMENTS):
            note = f"  (expected cut {expected[i]:.1f}s)" if i < len(cuts) else ""
            print(f"{seg_id:9s} {bounds[i]:6.2f} -> {bounds[i + 1]:6.2f}{note}")
            dst = os.path.join(OUT, f"{seg_id}.wav")
            to_clip(src, dst, bounds[i], bounds[i + 1])
            clips.append((seg_id, dst))
    else:
        sys.exit("Put either one file per line (intro.wav, hotkey.wav, ...) or a single "
                 "recording in video/audio/.")
    manifest = [{"id": i, "wav": p, "seconds": round(duration(p), 3)} for i, p in clips]
    with open(os.path.join(HERE, "build", "clips.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    for m in manifest:
        print(f"{m['id']:9s} clip {m['seconds']:.2f}s")


if __name__ == "__main__":
    main()
