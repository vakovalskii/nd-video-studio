#!/usr/bin/env python3
"""Mixdown: narrator lines at narration.json timings + ducked music → one wav.

Voice is normalized in voice_fx (−16 LUFS), music sits around −27 LUFS and ducks
under the voice via a sidechain compressor. loudnorm resamples to 192 kHz internally and
eats the tail, so it's always followed by aresample and a final apad to length.

  python3 scripts/mix.py projects/x/narration.json projects/x/audio/fx music.mp3 projects/x/audio/mix.wav
  python3 scripts/mix.py ... none projects/x/audio/mix.wav      # no music, voice only
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import clip_name, duration, ffmpeg, load_narration  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("narration")
    ap.add_argument("voice_dir")
    ap.add_argument("music")
    ap.add_argument("out")
    ap.add_argument("--music-lufs", type=float, default=-27)
    ap.add_argument("--music-offset", type=float, default=0, help="track start offset, seconds")
    ap.add_argument("--duck-ratio", type=float, default=6)
    a = ap.parse_args()

    n = load_narration(a.narration)
    T = n["duration"]
    no_music = a.music == "none" or not os.path.exists(a.music)
    if no_music:
        print(f"no music ({a.music}), mixing voice only")
    # without music, silence takes its place: same graph, ducking just has nothing to duck
    args = ["-f", "lavfi", "-t", str(T), "-i", "anullsrc=r=48000:cl=stereo"] if no_music else ["-i", a.music]
    for i in range(len(n["lines"])):
        args += ["-i", os.path.join(a.voice_dir, clip_name(i))]
    f = []
    for i, ln in enumerate(n["lines"]):
        ms = int(ln["start"] * 1000)
        f.append(f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},apad=whole_dur={T}[v{i}]")
    k = len(n["lines"])
    f.append("".join(f"[v{i}]" for i in range(k)) + f"amix=inputs={k}:normalize=0:duration=longest,atrim=0:{T}[vo]")
    f.append("[vo]asplit=2[voa][sc]")
    if no_music:
        f.append(f"[0:a]apad=whole_dur={T}[mu]")
    else:
        f.append(f"[0:a]loudnorm=I={a.music_lufs}:TP=-6:LRA=11,aresample=48000,atrim={a.music_offset}:{a.music_offset + T},"
                 f"asetpts=N/SR/TB,afade=t=in:st=0:d=1.5,afade=t=out:st={T - 4}:d=4,apad=whole_dur={T}[mu]")
    f.append(f"[mu][sc]sidechaincompress=threshold=0.03:ratio={a.duck_ratio}:attack=30:release=500[duck]")
    f.append(f"[duck][voa]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.9,apad=whole_dur={T},atrim=0:{T}[out]")
    ffmpeg(*args, "-filter_complex", ";".join(f), "-map", "[out]", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", a.out)
    print(f"{a.out}: {duration(a.out):.2f}s (expected {T}s)")


if __name__ == "__main__":
    main()
