---
name: ndt-content
description: Content made entirely on NeuralDeep models (api.neuraldeep.ru), no external APIs: research, script, voice, images, speech verification, word-level subtitles, frame review, music on your own GPU. Triggers: "make a video on our models", "NDT only", "content through the hub", "without OpenRouter", "video from a brief".
---

# ndt-content: from brief to MP4 on hub models

One key, `ND_API_KEY` (your own hub `sk-`), for everything. Frame building, sound and rendering
are the same as in the [`nd-video`](../nd-video/SKILL.md) skill: its "HyperFrames techniques",
"Voice: pitfalls" and "Music: pitfalls" sections apply here too. This skill changes the sources:
instead of OpenRouter (gpt-audio, Lyria) and Gemini, only the hub and your own GPU.

## What comes from where

| step | hub model | endpoint | script |
|---|---|---|---|
| research | Search API (web, tg) | `/v1/search/web`, `/v1/search/tg` | `nd_research.py` |
| script | `qwen3.8-27b-noreason` (or `kimi-k2.6`, `gemma-4-31b-noreason`) | `/v1/chat/completions` | `nd_script.py` |
| voice | `qwen3-tts` (8 voices, style as text), Russian via ESpeech + RUAccent | `/v1/audio/speech` | `tts_hub.py` |
| timing | from the real voiceover length | — | `nd_retime.py`, `fit_narration.py` |
| speech check + words | `whisper-1` | `/v1/audio/transcriptions` | `nd_align.py` |
| images | FLUX, background removal, upscale | `/v1/images/*` | `nd_images.py` |
| frame review | `qwen3.6-35b-a3b-noreason` (vision) | `/v1/chat/completions` | `nd_review.py` |
| music | self-hosted ACE-Step 1.5 on your own GPU (the hub has no music model) | box REST | `music_acestep.py`, [docs/acestep.md](../../docs/acestep.md) |
| voice processing, mixing | local, ffmpeg | — | `voice_fx.py`, `mix.py` |

For JSON and short structured answers use only the `-noreason` aliases: base qwen models always
think and return an empty `content` on short answers.

Check that everything above is up before a run: `python3 scripts/nd_probe.py` pings every chat
model from `/v1/models` and walks TTS → whisper, FLUX → vision, quota and search
(`--no-images` saves image quota).

## Workflow

Run everything from the project folder, `S=../../scripts`, key in env (never print or commit it).

```bash
mkdir -p projects/<slug> && cd projects/<slug>
$EDITOR brief.md                                   # topic, audience, tone, length

python3 $S/nd_research.py sources.md "<query 1>" "<query 2>" [--tg "<query>"]
python3 $S/nd_script.py brief.md narration.json --sources sources.md --lang en --seconds 60
#   → scenes (question heading, key_idea) and lines; read them, fix facts by hand

python3 $S/tts_hub.py narration.json audio/raw --voice ryan    # ru: language comes from narration.json
python3 $S/nd_retime.py narration.json audio/raw               # starts from the real voiceover
python3 $S/fit_narration.py narration.json audio/raw audio/fit
python3 $S/nd_align.py narration.json audio/fit words.json     # BAD → re-voice: tts_hub.py --only N

python3 $S/nd_images.py assets "bg:<prompt>" "hero:<prompt>" --remove-bg hero

# compose index.html from narration.json (scenes → headings, lines → subtitles,
# words.json → highlight each word as it is spoken), techniques in the nd-video skill
npx hyperframes check && npx hyperframes snapshot --at <t1>,<t2>,...
python3 $S/nd_review.py snapshots/contact-sheet-*.jpg --brief "horizontal 16:9 explainer"

bash $S/build_audio.sh . trailer                  # fx + music ducking → audio/mix.wav
npx hyperframes render --output renders/<slug>.mp4
```

`npx`, `curl`, `gh` run without the system proxy:
`env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY <cmd>`.

## Order matters: voice first, then HTML

TTS pace can't be guessed from text: `ryan` speaks ~1.7 words/s while the script draft assumes
2.1. So the starts from `nd_script.py` are a draft; `nd_retime.py` sets the real ones from clip
lengths. Lay out the composition after retime, otherwise the animation drifts from the voice. If
the HTML is already laid out to fixed starts (like the Jev video), skip retime: there
`fit_narration.py` squeezes lines into their windows, and long ones get shortened in the text.

## Pitfalls caught on the demo

- **TTS swallows and mixes up words**, easy to miss by ear: "reuse" came out as "ray use".
  `nd_align.py` compares the transcript with the text and exits with code 2 and an `--only N` list.
  Fix it by rephrasing the line, not by rerunning the same text.
- **A one-off gateway 503** can hit any endpoint. `ndv_common._retry` retries 429 and 5xx
  with a pause (`Retry-After` if present).
- **Images are square 1312×1312** by default. Set the size with `--options '{...}'`,
  or simply place the image with `object-fit: cover`.
- **Vision review** reads the contact-sheet grid imprecisely (mixes up timestamps), but it does
  catch problems: small text, overlaps, empty frames. It is a second pair of eyes, not a
  replacement for looking at the frames yourself.
- **Quotas**: search (web costs more than tg), images (`/v1/images/quota`), TTS in characters,
  all per the key's plan. A quota refusal is a 429 with `Retry-After`.

## Music

The hub has no music model. Self-hosted ACE-Step 1.5 XL (MIT) runs on your own GPU box
(`<gpu-box>` is its ssh alias); setup and card limits are in [docs/acestep.md](../../docs/acestep.md).
To play by hand: `ssh -N -L 18001:127.0.0.1:8001 <gpu-box> &` and
`python3 scripts/music_studio.py` → http://127.0.0.1:8765 (presets, up to 2 variants, history;
the "to project" button puts the track into `projects/<slug>/audio/music.mp3` and keeps the
previous one next to it). Reference: XL turbo 4B + LM 1.7B on a single A4500 20 GB, two 60 s
variants in 11 s. While the box is down, build the video without music: `mix.py` with an empty
track or `build_audio.sh` without `audio/music.mp3`.

## Syncing to music

From [vibecoder-anthem](https://github.com/rocketmandrey/vibecoder-anthem) (the "ЖГИ ТОКЕНЫ"
clip): cuts, camera hits and karaoke land on the **track's real beats**, not on a BPM grid.

```bash
uv run --no-project --with librosa python3 $S/beat_map.py audio/music.mp3 beats.json --bpm 174
```

Paste `beats.json` into the page as `window.BEATS = {...}`, next to `tools/beat-sync.js`:
`beat.snap(t)` / `beat.nextBar(t)` move a rough time onto a beat or downbeat,
`beat.hits(from, to, min)` returns hits for shakes and flashes, `beat.warpFrom(anchors)` moves a
finished animation onto a new version of the track: `[new, old]` anchors on the same events,
linear in between. Word-level timings for narration or vocals come from `nd_align.py`.

- The tempo detector gets octave errors: the Jev track from Lyria was requested at 110 and came
  out as 73.8 (i.e. 147.6/2). The `--bpm` hint helps, but always check the number.
- ACE-Step holds the requested tempo: DnB at 174 gave 172.3 BPM, beat jitter ±5 ms, no drift.
- Verify sync with a contact sheet on the hits: `snapshot --at` at the times from `hits`.

## Honesty

- The script is written only from `sources.md`; estimates are marked in the text ("likely", "est.").
- In the post about the video, state exactly what was used. If even one step bypassed the hub
  (e.g. music from Lyria), don't write "made entirely on neuraldeep.ru models".

## Example

A 31 s demo about KV cache went through the whole pipeline on the hub (research → script →
`ryan` → retime → whisper check with one caught TTS error → image → review).
