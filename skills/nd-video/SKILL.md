---
name: nd-video
description: Explainer videos with HyperFrames (HTML → MP4) plus narrator, music and mixing on NeuralDeep infrastructure. Triggers: "make a video", "explainer", "explain visually", "add voiceover", "add music", "re-render", "change the voice / reverb".
---

# nd-video: from idea to MP4

The pipeline was built on the LLM vs Jev video (112 s, [`media/jev-vs-llm.mp4`](../../media/jev-vs-llm.mp4)).
Everything that worked there is here. Projects (`projects/`) are local and not tracked in git.
The HyperFrames composition contract is in `vendor/hyperframes/skills/hyperframes-core/SKILL.md`;
read it before writing the first line of HTML.

## Workflow

1. **Brief and storyboard.** One idea per scene. Each scene gets a question-style heading, 2–4
   narrator lines and a "key idea" at the end. Without subtitles and a route map viewers don't
   understand what they are looking at (the main feedback on the first cut).
2. **Composition** `projects/<slug>/index.html`: `npx hyperframes init <slug> --example blank`.
   Proven techniques are below, under "Techniques".
3. **Check**: `npx hyperframes check` and `npx hyperframes snapshot --at t1,t2,...`, then look at
   the contact sheet yourself. `check` flags overlaps where the camera intentionally goes under
   overlays (subtitles, magnifier); those are false positives, trust the frames.
4. **Narration text** in `projects/<slug>/narration.json` (`start` + `text`, windows are computed).
5. **Voice** → `audio/raw/line_NN.wav`:
   - `scripts/tts_gpt_audio.py`: OpenAI gpt-audio via OpenRouter, best delivery. Voice `ash`.
   - `scripts/tts_hub.py`: the hub TTS (Qwen3-TTS, 8 presets). A bit weak for trailer delivery.
   - `scripts/tts_elevenlabs.py`: ElevenLabs `eleven_multilingual_v2`. The best Russian of the three;
     `voices` lists the account's voices, `speak` voices narration.json (neighbouring lines go as context).
6. **Music** → `audio/music.mp3`:
   - `scripts/music_lyria.py`: Lyria 3 Pro, $0.08 per track.
   - `scripts/music_acestep.py`: self-hosted ACE-Step 1.5 (MIT), see `docs/acestep.md`.
7. **Sound**: `scripts/build_audio.sh projects/<slug> trailer` = fit lines into windows
   (`fit_narration.py`) → voice processing (`voice_fx.py`) → mix with ducking (`mix.py`).
   The composition has a single `<audio id="soundtrack" src="audio/mix.wav">` for the full length.
8. **Render**: `npx hyperframes render --output renders/<name>.mp4`; 112 s renders in ~1.5 min.
9. **Compress for sharing**: `ffmpeg -i in.mp4 -c:v libx264 -preset slow -crf 30 -tune animation
   -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart out.mp4`. For the Jev video this took
   51 MB down to 8.7 MB with no visible loss, small text included.

Outbound commands (`gh`, `curl`, `npx`) run without the system proxy:
`env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY <command>`.

## Keys and where to run

| what | key | where from |
|---|---|---|
| gpt-audio, Lyria | `OPENROUTER_API_KEY` | not from a Russian IP: OpenRouter returns 403. Use a server outside Russia or `OPENROUTER_API_BASE` pointing at your egress |
| hub TTS | `ND_API_KEY` (your own `sk-`) | anywhere |
| ACE-Step | `ACESTEP_API_KEY` (if set) | ssh tunnel to the box, the API listens on 127.0.0.1 |

Never print secrets or commit them (`.env` is in `.gitignore`).

## Voice: pitfalls

- gpt-audio answers like an assistant ("Understood, here is…") and reads tags such as `<line>`
  aloud. Fix: a "you are a TTS engine" system prompt, bare text in the user turn, then transcribe
  the result, compare it with the text and retry (`tts_gpt_audio.py` does this).
- OpenRouter audio output works only with `stream: true`; the format is `pcm16`, 24 kHz mono.
- A line longer than its window: `fit_narration.py` speeds it up to ×1.12, beyond that it is
  audible. `TOO LONG` = shorten the text and re-voice only that line: `--only N`.
- Processing presets (`voice_fx.py`): `natural` (no processing), `trailer` (final Jev mix: bass
  +5 at 110 Hz, presence +2.5 at 3 kHz, 4:1 compression, 1.4 s / 18% reverb), `deep` (pitch
  −2 semitones), `titan` (−4), `cathedral` (3.2 s / 45% reverb), `radio` (350–3400 Hz band).
  Small EQ tweaks after loudnorm are barely audible (the first A/B sounded "like clones"), so the
  presets are spread far apart. Fine-tune with flags: `--pitch -1 --bass 7 --wet 0.25 --room 2`.
  Compare by ear: `voice_fx.py fit ab --compare 0`.

- ElevenLabs free tier: pcm output and library voices (native Russian speakers) are paid only
  (403 / 402), so the script takes mp3 and the premade voices work (Brian `nPczCjzI2devNBz1zQrb`
  was picked for Russian). 10 000 characters a month; a 90 s video is ~1 300. Reachable from RU IPs.
- Hub TTS for Russian: `language` Russian goes to ESpeech, which answers 500 on words it doesn't
  know (terms, transliterated names); `Auto` goes to Qwen3-TTS, whose presets are not native
  Russian speakers and drift in timbre and emotion between lines.

## Music: pitfalls

- Lyria rejects prompts that mention AI/video/product as `PROHIBITED_CONTENT` (no charge).
  Describe only the music: genre, BPM, instruments, mood, "No vocals".
- A Lyria track is ~170 s; `mix.py` trims it to the video length, 1.5 s fade-in, 4 s fade-out;
  `--music-offset` shifts the start.
- Loudness: voice −16 LUFS, music −27 LUFS with sidechain ducking under the voice.
- `loudnorm` resamples to 192 kHz and eats the tail: follow it with `aresample` and `apad` to length.

## HyperFrames techniques proven on the video

- **Camera over a "world"**: a single `#world` (e.g. 3400×1800) holding two architecture
  "crystals"; the camera is `gsap.to("#world", {x, y, scale})` via `camState(x, y, s, sx, sy)`,
  which puts a world point at a screen point. Wide shot ~0.43, block ~1.15, detail ~2.7. Read
  finer details through a **magnifier**: a round overlay with a separate full-size SVG.
- **Counters** without `onUpdate` (callbacks are muted on seek): `@property --n { syntax: "<integer>";
  inherits: true }` + `counter-reset: n var(--n)` in `::before`, tween `"--n"` with `snap`.
  `inherits` must be `true`, otherwise the pseudo-element sees 0.
- Repeated tweens on the same element: `fromTo(..., {immediateRender: false})`, otherwise a late
  `fromTo` resets the earlier state on frame zero.
- Don't tween `letterSpacing` or other layout properties (lint `gsap_non_transform_motion`),
  don't tween `visibility`/`autoAlpha` on `.clip`.
- Seeded randomness only (`mulberry32`), no `Date.now`/`Math.random`.
- Put a dark gradient and a backing plate behind the header, otherwise zoomed text lands on blocks.
- Copyright: a corner badge + a faint centered watermark (7% white), removed in the finale.

## Factual honesty

When breaking down someone else's model, mark on screen what a source confirms and what is an
estimate ("likely", "est.", "illustrative"). In the Jev video MoE, ~10B active parameters and
expert specialization are marked this way.
