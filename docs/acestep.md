# ACE-Step 1.5 XL на своём GPU

Открытая модель генерации музыки, лицензия MIT, репозиторий
https://github.com/ace-step/ACE-Step-1.5. XL = DiT на 4B параметров (~9 ГБ bf16).
Нужно ≥12 ГБ VRAM с offload и квантованием, ≥20 ГБ без них.

## Эталонная установка

Одна RTX A4500 20 ГБ, контейнер `acestep-xl`: DiT **XL turbo 4B** + LM **1.7B**, без offload.
Ниже `<gpu-box>` — ssh-алиас своего GPU-сервера.

Замер: XL с LM занимает ~16.6 ГБ, на соседей карты остаётся ~3 ГБ. 60 с трека с
`thinking` за 78 с, два варианта по 60 с без него за 11 с. Больше двух вариантов за раз не
давать (в студии кнопка ограничена), иначе на 20 ГБ карте не хватит памяти.

Прежний `acestep-turbo` (2B + LM 0.6B, ~7.5 ГБ) остановлен и оставлен как запасной.

- исходники: `/srv/acestep/ACE-Step-1.5` (коммит `ca1e85f`, 29.08.26)
- образ: `acestep:bench` (их `Dockerfile`, CUDA 12.8)
- веса: `/srv/acestep/checkpoints` (монтируется в `/app/checkpoints`)

## Запуск

```bash
ssh <gpu-box>
docker run -d --name acestep-xl --gpus '"device=1"' --memory 32g --cpus 8 \
  -p 127.0.0.1:8001:8001 \
  -v /srv/acestep/checkpoints:/app/checkpoints -v /srv/acestep/out:/app/output \
  -e ACESTEP_MODE=api \
  -e ACESTEP_CONFIG_PATH=acestep-v15-xl-turbo \
  -e ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-1.7B \
  -e ACESTEP_OFFLOAD_TO_CPU=false -e ACESTEP_LLM_BACKEND=pt \
  acestep:bench
docker logs -f acestep-xl          # ждать загрузки моделей
```

С ноутбука:

```bash
ssh -N -L 8001:127.0.0.1:8001 <gpu-box> &
python3 scripts/music_acestep.py "Instrumental minimal electronic, 110 BPM, pulsing analog synth arpeggio, soft sub bass, no vocals" music.mp3 --duration 120 --bpm 110 --model acestep-v15-xl-turbo
```

Погасить: `docker stop acestep-xl` (контейнер остаётся, `docker start acestep-xl` поднимет снова).

## Правила парка

Эксперименты на общем GPU-боксе — только отдельным контейнером с `--memory` и своим
`--gpus device=N`, живые движки соседей не трогать.
