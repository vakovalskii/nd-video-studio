# nd-video-studio

Ролики-объяснялки на HTML: композиция на [HyperFrames](https://github.com/heygen-com/hyperframes)
(Apache 2.0) → MP4, плюс диктор, музыка и сведение на инфраструктуре NeuralDeep.
Пайп целиком описан в навыке [`skills/nd-video/SKILL.md`](skills/nd-video/SKILL.md) —
его подхватывают Claude Code (`.claude/skills`) и Codex/Cursor (`.agents/skills`).

## Что внутри

| путь | что |
|---|---|
| `skills/ndt-content/` | навык: ролик из брифа целиком на моделях хаба (ресёрч, сценарий, голос, картинки, сверка, ревью) |
| `scripts/nd_research.py` | ресёрч через Search API хаба → `sources.md` |
| `scripts/nd_script.py` | сценарий моделью хаба: бриф + источники → `narration.json` со сценами |
| `scripts/nd_retime.py` | старты фраз по живой озвучке, до вёрстки HTML |
| `scripts/nd_align.py` | `whisper-1`: сверка озвучки с текстом и пословные тайминги `words.json` |
| `scripts/nd_images.py` | картинки FLUX хаба, снятие фона, апскейл |
| `scripts/nd_review.py` | ревью contact-sheet vision-моделью хаба |
| `scripts/music_studio.py` + `tools/music-studio.html` | локальная студия музыки поверх своего ACE-Step: пресеты, варианты, история, «в проект» |
| `scripts/beat_map.py` + `tools/beat-sync.js` | карта бита трека (доли, сильные доли, удары) и привязка анимации к ней, тайм-варп |
| `scripts/tts_gpt_audio.py` | диктор через OpenAI gpt-audio (OpenRouter), с проверкой дословности |
| `scripts/tts_hub.py` | диктор через TTS хаба (`/v1/audio/speech`) |
| `scripts/music_lyria.py` | музыка через Google Lyria 3 (OpenRouter) |
| `scripts/music_acestep.py` | музыка через свой ACE-Step 1.5 ([docs/acestep.md](docs/acestep.md)) |
| `scripts/fit_narration.py` | синхронизация: фразы под окна таймлайна, срез тишины, atempo |
| `scripts/voice_fx.py` | EQ, компрессия, реверб свёрткой; пресеты и A/B |
| `scripts/mix.py` | сведение голоса и музыки с дакингом в один wav |
| `scripts/build_audio.sh` | fit → fx → mix одной командой |
| `scripts/sync_hyperframes.sh` | обновить вендоренные навыки HyperFrames |
| `vendor/hyperframes/` | взятые навыки и доки HyperFrames + их LICENSE ([NOTICE](vendor/hyperframes/NOTICE.nd-video-studio)) |

## Быстрый старт

```bash
mkdir -p projects/my-video && cd projects/my-video    # projects/ локальные, в git не попадают
env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY npx -y hyperframes@0.8.81 init . --example blank
# narration.json → голос (tts_hub.py) → build_audio.sh → render; по шагам в skills/ndt-content/SKILL.md
bash ../../scripts/build_audio.sh . trailer
env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY npx -y hyperframes@0.8.81 render --output renders/my-video.mp4
```

Нужны Node 22+, FFmpeg, Python 3.10+ (только стандартная библиотека).

## Ключи

`OPENROUTER_API_KEY` (gpt-audio, Lyria; с RU-IP OpenRouter отдаёт 403), `ND_API_KEY` (TTS хаба),
`ACESTEP_API_KEY` (если сервер ACE-Step закрыт ключом). Держать в `.env`, он в `.gitignore`.
