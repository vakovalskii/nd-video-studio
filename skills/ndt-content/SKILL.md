---
name: ndt-content
description: Контент целиком на моделях NeuralDeep (api.neuraldeep.ru), без внешних API: ресёрч, сценарий, голос, картинки, сверка речи, пословные субтитры, ревью кадров, музыка на своём GPU. Триггеры: «сделай ролик на наших моделях», «только на NDT», «контент через хаб», «без OpenRouter», «ролик из брифа».
---

# ndt-content: ролик от брифа до MP4 на моделях хаба

Один ключ `ND_API_KEY` (свой `sk-` хаба) на всё. Сборка кадров, звук и рендер те же, что в
навыке [`nd-video`](../nd-video/SKILL.md): его разделы «Приёмы HyperFrames», «Голос: грабли»,
«Музыка: грабли» действуют и здесь. Этот навык меняет источники: вместо OpenRouter (gpt-audio,
Lyria) и Gemini только хаб и свой GPU.

## Что откуда

| шаг | модель хаба | ручка | скрипт |
|---|---|---|---|
| ресёрч | Search API (web, tg) | `/v1/search/web`, `/v1/search/tg` | `nd_research.py` |
| сценарий | `qwen3.8-27b-noreason` (или `kimi-k2.6`, `gemma-4-31b-noreason`) | `/v1/chat/completions` | `nd_script.py` |
| голос | `qwen3-tts` (8 голосов, стиль текстом), русский через ESpeech + RUAccent | `/v1/audio/speech` | `tts_hub.py` |
| тайминги | по реальной длине озвучки | — | `nd_retime.py`, `fit_narration.py` |
| сверка речи + слова | `whisper-1` | `/v1/audio/transcriptions` | `nd_align.py` |
| картинки | FLUX, снятие фона, апскейл | `/v1/images/*` | `nd_images.py` |
| ревью кадров | `qwen3.6-35b-a3b-noreason` (vision) | `/v1/chat/completions` | `nd_review.py` |
| музыка | своя ACE-Step 1.5 на своём GPU (на хабе музыки нет) | REST бокса | `music_acestep.py`, [docs/acestep.md](../../docs/acestep.md) |
| обработка голоса, сведение | локально, ffmpeg | — | `voice_fx.py`, `mix.py` |

Для JSON и коротких структурных ответов только `-noreason` алиасы: базовые qwen думают всегда
и на коротком ответе отдают пустой `content`.

## Порядок

Всё из папки проекта, `S=../../scripts`, ключ в env (не печатать, не коммитить).

```bash
mkdir -p projects/<slug> && cd projects/<slug>
$EDITOR brief.md                                   # о чём, для кого, тон, длина

python3 $S/nd_research.py sources.md "<запрос 1>" "<запрос 2>" [--tg "<запрос>"]
python3 $S/nd_script.py brief.md narration.json --sources sources.md --lang en --seconds 60
#   → сцены (heading-вопрос, key_idea) и фразы; прочитать глазами, поправить факты руками

python3 $S/tts_hub.py narration.json audio/raw --voice ryan    # ru: язык берётся из narration.json
python3 $S/nd_retime.py narration.json audio/raw               # старты по живой озвучке
python3 $S/fit_narration.py narration.json audio/raw audio/fit
python3 $S/nd_align.py narration.json audio/fit words.json     # BAD → переозвучить: tts_hub.py --only N

python3 $S/nd_images.py assets "bg:<промпт>" "hero:<промпт>" --remove-bg hero

# композиция index.html по narration.json (scenes → заголовки, lines → субтитры,
# words.json → подсветка слова в момент звучания), приёмы — навык nd-video
npx hyperframes check && npx hyperframes snapshot --at <t1>,<t2>,...
python3 $S/nd_review.py snapshots/contact-sheet-*.jpg --brief "horizontal 16:9 explainer"

bash $S/build_audio.sh . trailer                  # fx + дакинг музыки → audio/mix.wav
npx hyperframes render --output renders/<slug>.mp4
```

`npx`, `curl`, `gh` — без системного прокси:
`env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy -u ALL_PROXY <cmd>`.

## Порядок важен: сначала голос, потом HTML

Темп TTS по тексту не угадать: `ryan` говорит ~1.7 слова/с, а черновик сценария считает
2.1. Поэтому старты из `nd_script.py` — черновик, `nd_retime.py` ставит настоящие по длине
клипов. Композицию верстать после retime, иначе анимация разъедется с голосом. Если HTML уже
свёрстан под старты (как ролик Jev), retime не запускать: там `fit_narration.py` ужимает
фразы под окна, а длинные сокращать текстом.

## Грабли, пойманные на демо

- **TTS глотает и путает слова**, на слух легко пропустить: «reuse» прозвучало как «ray use».
  `nd_align.py` сверяет распознанное с текстом и падает с кодом 2 и списком `--only N`.
  Лечится переформулировкой фразы, не перезапуском с тем же текстом.
- **Разовый 503 шлюза** бывает на любой ручке. `ndv_common._retry` повторяет 429 и 5xx
  с паузой (`Retry-After`, если есть).
- **Картинка квадратная 1312×1312** по умолчанию. Размер задаётся `--options '{...}'`,
  а в кадр её проще класть через `object-fit: cover`.
- **Ревью vision-моделью** читает сетку контакт-листа неточно (путает метки времени), но
  проблемы видит: мелкий текст, наложения, пустые кадры. Это вторая пара глаз, не замена
  своему взгляду на кадры.
- **Квоты**: поиск (web дороже tg), картинки (`/v1/images/quota`), TTS в символах, всё
  по тарифу ключа. Отказ по квоте = 429 с `Retry-After`.

## Музыка

На хабе музыкальной модели нет. Своя ACE-Step 1.5 XL (MIT) ставится на свой GPU-бокс
(`<gpu-box>` — его ssh-алиас), порядок и ограничения карты — [docs/acestep.md](../../docs/acestep.md).
Поиграться руками: `ssh -N -L 18001:127.0.0.1:8001 <gpu-box> &` и
`python3 scripts/music_studio.py` → http://127.0.0.1:8765 (пресеты, до 2 вариантов, история,
кнопка «в проект» кладёт трек в `projects/<slug>/audio/music.mp3`, прежний сохраняет рядом).
Эталон: XL turbo 4B + LM 1.7B на одной A4500 20 ГБ, два варианта по 60 с за 11 с.
Пока бокс не поднят, ролик собирается без музыки: `mix.py` с пустым треком или
`build_audio.sh` без `audio/music.mp3`.

## Синхрон с музыкой

Из [vibecoder-anthem](https://github.com/rocketmandrey/vibecoder-anthem) (клип «ЖГИ ТОКЕНЫ»):
склейки, удары камеры и караоке ставятся на **реальные доли трека**, а не на сетку по BPM.

```bash
uv run --no-project --with librosa python3 $S/beat_map.py audio/music.mp3 beats.json --bpm 174
```

`beats.json` вставить в страницу как `window.BEATS = {...}`, рядом `tools/beat-sync.js`:
`beat.snap(t)` / `beat.nextBar(t)` двигают черновое время на долю или сильную долю,
`beat.hits(from, to, min)` отдаёт удары для тряски и вспышек, `beat.warpFrom(anchors)`
переносит готовую анимацию на новую версию трека: якоря `[новое, старое]` на одних и тех же
событиях, между ними линейно. Пословные тайминги диктора или вокала — `nd_align.py`.

- Темп детектор путает вдвое: трек Jev от Lyria просили на 110, а вышло 73.8 (то есть 147.6/2).
  Подсказка `--bpm` помогает, но смотреть на цифру всё равно.
- ACE-Step держит заданный темп: DnB на 174 дал 172.3 BPM, разброс доли ±5 мс, дрейфа нет.
- Проверять синхрон контакт-листом по ударам: `snapshot --at` на временах из `hits`.

## Честность

- Сценарий пишется только по `sources.md`; оценки помечаются в тексте («likely», «est.»).
- В посте о ролике писать ровно то, что использовано. Если хоть один шаг шёл мимо хаба
  (например, музыка с Lyria), не писать «полностью на моделях neuraldeep.ru».

## Пример

Демо на 31 с про KV cache прошло весь пайп на хабе (ресёрч → сценарий →
`ryan` → retime → whisper-сверка с одной пойманной ошибкой TTS → картинка → ревью).
