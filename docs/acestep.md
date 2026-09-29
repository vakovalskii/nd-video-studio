# ACE-Step 1.5 XL on your own GPU

An open music generation model, MIT license, repository
https://github.com/ace-step/ACE-Step-1.5. XL = a 4B-parameter DiT (~9 GB bf16).
Needs ≥12 GB VRAM with offload and quantization, ≥20 GB without them.

## Reference setup

A single RTX A4500 20 GB, container `acestep-xl`: DiT **XL turbo 4B** + LM **1.7B**, no offload.
Below, `<gpu-box>` is the ssh alias of your GPU server.

Measured: XL with LM takes ~16.6 GB, leaving ~3 GB for other tenants of the card. A 60 s track
with `thinking` takes 78 s; two 60 s variants without it take 11 s. Don't request more than two
variants at once (the studio button is capped), otherwise a 20 GB card runs out of memory.

The previous `acestep-turbo` (2B + LM 0.6B, ~7.5 GB) is a fallback option for smaller cards.

- sources: `/srv/acestep/ACE-Step-1.5` (commit `ca1e85f`, 2026-08-29)
- image: `acestep:bench` (their `Dockerfile`, CUDA 12.8)
- weights: `/srv/acestep/checkpoints` (mounted at `/app/checkpoints`)

## Running

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
docker logs -f acestep-xl          # wait for the models to load
```

From the laptop:

```bash
ssh -N -L 8001:127.0.0.1:8001 <gpu-box> &
python3 scripts/music_acestep.py "Instrumental minimal electronic, 110 BPM, pulsing analog synth arpeggio, soft sub bass, no vocals" music.mp3 --duration 120 --bpm 110 --model acestep-v15-xl-turbo
```

Stop: `docker stop acestep-xl` (the container stays, `docker start acestep-xl` brings it back).

## Shared box rules

Experiments on a shared GPU box go only in a separate container with `--memory` and its own
`--gpus device=N`; don't touch the neighbors' live engines.
