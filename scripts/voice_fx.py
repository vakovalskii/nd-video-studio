#!/usr/bin/env python3
"""Narrator voice processing: EQ, compression, convolution reverb.

Reverb is afir with a synthetic impulse (pink noise with exponential decay),
deterministic by seed, so renders are reproducible. Presets were tuned on the video
Jev vs LLM (gpt-audio ash voice); "trailer" is what made the final cut.

  python3 scripts/voice_fx.py projects/x/audio/fit projects/x/audio/fx --preset trailer
  python3 scripts/voice_fx.py projects/x/audio/fit /tmp/ab --compare 0       # A/B of all presets
  python3 scripts/voice_fx.py ... --preset trailer --bass 7 --wet 0.25     # manual tweaking
"""

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import ffmpeg  # noqa: E402

PRESETS = {
    # bass: dB shelf at 110 Hz; presence: dB at 3 kHz; comp: ratio (0 = no compressor);
    # room: reverb tail seconds; wet: reverb share; pitch: semitones (negative = lower);
    # band: "lo-hi" Hz bandpass (radio). loudnorm at the end evens out loudness,
    # so small EQ differences are barely audible: presets are made clearly different.
    "natural":   dict(bass=0, presence=0,   comp=0, room=0.0, wet=0.0,  pitch=0,  band=""),
    "trailer":   dict(bass=5, presence=2.5, comp=4, room=1.4, wet=0.18, pitch=0,  band=""),
    "deep":      dict(bass=6, presence=2,   comp=4, room=1.4, wet=0.15, pitch=-2, band=""),
    "titan":     dict(bass=7, presence=3,   comp=5, room=1.8, wet=0.20, pitch=-4, band=""),
    "cathedral": dict(bass=3, presence=1.5, comp=3, room=3.2, wet=0.45, pitch=0,  band=""),
    "radio":     dict(bass=0, presence=4,   comp=8, room=0.0, wet=0.0,  pitch=0,  band="350-3400"),
}


def make_ir(path, room, seed=7):
    ffmpeg("-f", "lavfi", "-i", f"anoisesrc=d={room}:c=pink:r=48000:a=0.5:seed={seed}",
           "-af", f"afade=t=out:st=0:d={room}:curve=exp,lowpass=f=5500,highpass=f=200", "-ac", "2", path)


def process(src, dst, p, ir):
    chain = ["aresample=48000", "highpass=f=60"]
    if p["pitch"]:
        r = 2 ** (p["pitch"] / 12)            # lower pitch, same duration
        chain += [f"asetrate={48000 * r:.0f}", "aresample=48000", f"atempo={1 / r:.5f}"]
    if p["band"]:
        lo, hi = p["band"].split("-")
        chain += [f"highpass=f={lo}", f"lowpass=f={hi}"]
    if p["bass"]:
        chain.append(f"bass=g={p['bass']}:f=110:w=0.7")
    if p["presence"]:
        chain.append(f"equalizer=f=3000:t=q:w=1.2:g={p['presence']}")
    if p["comp"]:
        chain.append(f"acompressor=threshold=0.1:ratio={p['comp']}:attack=5:release=90:makeup=3")
    chain.append("aformat=channel_layouts=stereo")
    chain = ",".join(chain)
    tail = "loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000"
    if p["wet"] > 0 and ir:
        fc = (f"[0:a]{chain},asplit=2[dry][w];[w][1:a]afir=dry=0:wet=10:length=1[wet];"
              f"[dry][wet]amix=inputs=2:weights='1 {p['wet']}':normalize=0,{tail}[o]")
        ffmpeg("-i", src, "-i", ir, "-filter_complex", fc, "-map", "[o]", dst)
    else:
        ffmpeg("-i", src, "-af", f"{chain},{tail}", dst)


def params(a, name):
    p = dict(PRESETS[name])
    for k in ("bass", "presence", "comp", "room", "wet", "pitch"):
        if getattr(a, k) is not None:
            p[k] = getattr(a, k)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--preset", default="trailer", choices=PRESETS)
    ap.add_argument("--compare", type=int, nargs="*", help="line numbers for an A/B file of all presets")
    for k in ("bass", "presence", "comp", "room", "wet", "pitch"):
        ap.add_argument(f"--{k}", type=float)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    if a.compare is not None:
        parts = []
        for name in PRESETS:
            p = params(a, name)
            ir = os.path.join(a.out_dir, f"ir_{name}.wav") if p["wet"] else None
            if ir:
                make_ir(ir, p["room"])
            for i in a.compare:
                out = os.path.join(a.out_dir, f"ab_{name}_{i:02d}.wav")
                process(os.path.join(a.in_dir, f"line_{i:02d}.wav"), out, p, ir)
                parts.append(out)
        # concatenate with pauses in preset order
        inputs = sum((["-i", x] for x in parts), [])
        fc = "".join(f"[{k}:a]apad=pad_dur=1.0[a{k}];" for k in range(len(parts)))
        fc += "".join(f"[a{k}]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[o]"
        ffmpeg(*inputs, "-filter_complex", fc, "-map", "[o]", os.path.join(a.out_dir, "AB-" + "-".join(PRESETS) + ".wav"))
        print("A/B:", os.path.join(a.out_dir, "AB-" + "-".join(PRESETS) + ".wav"), "order:", ", ".join(PRESETS))
        return

    p = params(a, a.preset)
    ir = os.path.join(a.out_dir, "ir.wav") if p["wet"] else None
    if ir:
        make_ir(ir, p["room"])
    for src in sorted(glob.glob(os.path.join(a.in_dir, "line_*.wav"))):
        process(src, os.path.join(a.out_dir, os.path.basename(src)), p, ir)
    print(f"{a.preset} {p} → {a.out_dir}")


if __name__ == "__main__":
    main()
