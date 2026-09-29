#!/usr/bin/env python3
"""Карта бита трека: доли, сильные доли, удары → beats.json для композиции.

Идея из rocketmandrey/vibecoder-anthem: склейки, удары камеры и строчки караоке ставятся не
на «ровную» сетку по BPM, а на реальные доли трека. У генеративной музыки темп плывёт
(Suno там уезжал с 0.639 до 0.662 с на долю после 2:00), и фиксированная сетка к концу
ролика съезжает от звука. ACE-Step держит заданный BPM ровнее, но начало и сильные доли
всё равно надо снимать с аудио.

  uv run --no-project --with librosa python3 scripts/beat_map.py projects/x/audio/music.mp3 projects/x/beats.json [--bpm 174]

beats.json: {"bpm", "beats": [t...], "downbeats": [t...], "hits": [[t, сила]...]}
сила удара = во сколько раз всплеск громкости выше медианного (как hits.txt в anthem).
"""

import argparse
import json

import librosa
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--bpm", type=float, help="подсказка темпа (ACE-Step знает его точно из запроса)")
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--min-hit", type=float, default=4.5, help="порог удара, в медианах")
    a = ap.parse_args()

    y, sr = librosa.load(a.audio, sr=22050, mono=True)
    env = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    kw = {"start_bpm": a.bpm, "tightness": 400} if a.bpm else {}
    tempo, frames = librosa.beat.beat_track(onset_envelope=env, sr=sr, units="frames", **kw)
    beats = librosa.frames_to_time(frames, sr=sr)

    # сильная доля: из четырёх возможных сдвигов берём тот, где сумма атак на «раз» больше
    low = librosa.onset.onset_strength(y=y, sr=sr, fmax=150)  # бочка живёт внизу
    strength = low[np.clip(frames, 0, len(low) - 1)]
    n = a.beats_per_bar
    phase = int(np.argmax([strength[k::n].sum() for k in range(n)]))
    downbeats = beats[phase::n]

    # удары: пики огибающей, нормированные на медиану
    med = float(np.median(env[env > 0])) or 1.0
    peaks = librosa.util.peak_pick(env, pre_max=6, post_max=6, pre_avg=20, post_avg=20, delta=med, wait=8)
    hits = [[round(float(librosa.frames_to_time(p, sr=sr)), 3), round(float(env[p] / med), 1)]
            for p in peaks if env[p] / med >= a.min_hit]

    bpm = float(np.atleast_1d(tempo)[0])
    out = {"bpm": round(bpm, 2), "beats": [round(float(t), 3) for t in beats],
           "downbeats": [round(float(t), 3) for t in downbeats], "hits": hits}
    json.dump(out, open(a.out, "w"))
    iv = np.diff(beats)
    print(f"{a.audio}: {bpm:.1f} BPM, {len(beats)} долей, {len(downbeats)} тактов, {len(hits)} ударов; "
          f"доля {iv.mean():.3f}±{iv.std():.3f} с (дрейф {iv[-8:].mean() - iv[:8].mean():+.3f} с) → {a.out}")


if __name__ == "__main__":
    main()
