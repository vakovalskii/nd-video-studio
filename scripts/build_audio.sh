#!/usr/bin/env bash
# Звук проекта из того, что уже сгенерировано: raw-фразы → подгонка → обработка → сведение.
#   scripts/build_audio.sh projects/jev-vs-llm [preset] [доп. флаги voice_fx, например --wet 0.25]
# Источники (платные, поэтому лежат в git): audio/raw/line_NN.wav и audio/music.mp3.
# Нет music.mp3 — сводится только голос.
set -euo pipefail
P="${1:?путь к проекту}"; PRESET="${2:-trailer}"; shift $(( $# >= 2 ? 2 : 1 ))
S="$(cd "$(dirname "$0")" && pwd)"
python3 "$S/fit_narration.py" "$P/narration.json" "$P/audio/raw" "$P/audio/fit"
python3 "$S/voice_fx.py" "$P/audio/fit" "$P/audio/fx" --preset "$PRESET" "$@"
python3 "$S/mix.py" "$P/narration.json" "$P/audio/fx" "$P/audio/music.mp3" "$P/audio/mix.wav"
