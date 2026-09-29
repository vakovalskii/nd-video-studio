#!/usr/bin/env bash
# Project audio from what's already generated: raw lines → fitting → processing → mixdown.
#   scripts/build_audio.sh projects/jev-vs-llm [preset] [extra voice_fx flags, e.g. --wet 0.25]
# Sources (paid, so they're kept in git): audio/raw/line_NN.wav and audio/music.mp3.
# No music.mp3: only the voice is mixed.
set -euo pipefail
P="${1:?project path}"; PRESET="${2:-trailer}"; shift $(( $# >= 2 ? 2 : 1 ))
S="$(cd "$(dirname "$0")" && pwd)"
python3 "$S/fit_narration.py" "$P/narration.json" "$P/audio/raw" "$P/audio/fit"
python3 "$S/voice_fx.py" "$P/audio/fit" "$P/audio/fx" --preset "$PRESET" "$@"
python3 "$S/mix.py" "$P/narration.json" "$P/audio/fx" "$P/audio/music.mp3" "$P/audio/mix.wav"
