#!/usr/bin/env python3
"""Beat map of a track: beats, downbeats, hits → beats.json for the composition.

Idea from rocketmandrey/vibecoder-anthem: cuts, camera hits and karaoke lines go not
on a "clean" BPM grid but on the track's real beats. Generated music drifts in tempo
(Suno there went from 0.639 to 0.662 s per beat after 2:00), and a fixed grid drifts
off the audio by the end. ACE-Step holds the requested BPM better, but the start and downbeats
still have to be taken from the audio.

  uv run --no-project --with librosa python3 scripts/beat_map.py projects/x/audio/music.mp3 projects/x/beats.json [--bpm 174]

beats.json: {"bpm", "beats": [t...], "downbeats": [t...], "hits": [[t, strength]...]}
hit strength = how many times the loudness spike exceeds the median (like hits.txt in anthem).
"""

import argparse
import json

import librosa
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--bpm", type=float, help="tempo hint (ACE-Step knows it exactly from the request)")
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--min-hit", type=float, default=4.5, help="hit threshold, in medians")
    a = ap.parse_args()

    y, sr = librosa.load(a.audio, sr=22050, mono=True)
    env = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    kw = {"start_bpm": a.bpm, "tightness": 400} if a.bpm else {}
    tempo, frames = librosa.beat.beat_track(onset_envelope=env, sr=sr, units="frames", **kw)
    beats = librosa.frames_to_time(frames, sr=sr)

    # downbeat: of the four possible offsets, pick the one with the most onset energy on "one"
    low = librosa.onset.onset_strength(y=y, sr=sr, fmax=150)  # the kick lives down low
    strength = low[np.clip(frames, 0, len(low) - 1)]
    n = a.beats_per_bar
    phase = int(np.argmax([strength[k::n].sum() for k in range(n)]))
    downbeats = beats[phase::n]

    # hits: envelope peaks, normalized to the median
    med = float(np.median(env[env > 0])) or 1.0
    peaks = librosa.util.peak_pick(env, pre_max=6, post_max=6, pre_avg=20, post_avg=20, delta=med, wait=8)
    hits = [[round(float(librosa.frames_to_time(p, sr=sr)), 3), round(float(env[p] / med), 1)]
            for p in peaks if env[p] / med >= a.min_hit]

    bpm = float(np.atleast_1d(tempo)[0])
    out = {"bpm": round(bpm, 2), "beats": [round(float(t), 3) for t in beats],
           "downbeats": [round(float(t), 3) for t in downbeats], "hits": hits}
    json.dump(out, open(a.out, "w"))
    iv = np.diff(beats)
    print(f"{a.audio}: {bpm:.1f} BPM, {len(beats)} beats, {len(downbeats)} bars, {len(hits)} hits; "
          f"beat {iv.mean():.3f}±{iv.std():.3f} s (drift {iv[-8:].mean() - iv[:8].mean():+.3f} s) → {a.out}")


if __name__ == "__main__":
    main()
