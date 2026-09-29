"""Общие утилиты пайпа: HTTP без системного прокси, ffmpeg/ffprobe, формат narration.json.

narration.json — единственный источник таймингов диктора:
{
  "duration": 112,                      # длина ролика, сек
  "voice": {"provider": "gpt-audio", "voice": "ash", "style": "..."},
  "lines": [{"start": 0.5, "text": "..."}, ...]
}
Окно фразы = до старта следующей минус зазор; у последней до конца ролика.
"""

import json
import os
import subprocess
import urllib.request

GAP = 0.35        # зазор перед следующей фразой, сек
TAIL = 0.6        # запас в конце ролика после последней фразы, сек


def http(url, body=None, headers=None, timeout=300):
    """POST/GET мимо HTTPS_PROXY: на ноутбуке он рвёт соединения (правило репо Hub)."""
    data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(req, timeout=timeout)


def run(args):
    subprocess.run(args, check=True)


def ffmpeg(*args):
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args])


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


def load_narration(path):
    with open(path) as f:
        n = json.load(f)
    lines = n["lines"]
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["start"] - GAP if i + 1 < len(lines) else n["duration"] - TAIL
        ln["window"] = round(nxt - ln["start"], 3)
    return n


def env_key(*names):
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    raise SystemExit(f"нужен ключ в env: {' или '.join(names)}")


def clip_name(i):
    return f"line_{i:02d}.wav"


# ---- NeuralDeep API (api.neuraldeep.ru): всё, что пайп берёт у хаба ----

def nd_base():
    return os.environ.get("ND_API_BASE", "https://api.neuraldeep.ru").rstrip("/")


def nd_auth():
    return {"Authorization": f"Bearer {env_key('ND_API_KEY')}"}


def _retry(call, attempts=4):
    """429 и 5xx хаба повторяем с паузой: разовый 503 шлюза не должен ронять весь пайп."""
    import time
    import urllib.error
    for i in range(attempts):
        try:
            return call()
        except urllib.error.HTTPError as e:
            if i == attempts - 1 or not (e.code == 429 or e.code >= 500):
                raise
            wait = float(e.headers.get("Retry-After") or 0) or 3 * (i + 1)
            print(f"  HTTP {e.code}, повтор через {wait:.0f} с")
            time.sleep(min(wait, 60))


def nd_json(path, body=None, timeout=300):
    hdr = {**nd_auth(), "Content-Type": "application/json"}

    def call():
        with http(f"{nd_base()}{path}", body, hdr, timeout) as r:
            return json.load(r)
    return _retry(call)


def nd_chat(messages, model=None, timeout=600, **kw):
    """Чат хаба. Для JSON и коротких структурных ответов только -noreason алиасы:
    базовые qwen думают всегда и на коротком ответе отдают пустой content."""
    body = {"model": model or os.environ.get("ND_CHAT_MODEL", "qwen3.8-27b-noreason"),
            "messages": messages, **kw}
    return nd_json("/v1/chat/completions", body, timeout)["choices"][0]["message"]["content"] or ""


def multipart(fields, files):
    """fields: {name: str}; files: {name: (filename, bytes, mime)} → (body, content_type)."""
    import uuid
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (fn, data, mime) in files.items():
        out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\n"
                   f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n")
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"


def nd_multipart(path, fields, files, timeout=300):
    body, ctype = multipart(fields, files)

    def call():
        with http(f"{nd_base()}{path}", body, {**nd_auth(), "Content-Type": ctype}, timeout) as r:
            return json.load(r)
    return _retry(call)


def extract_json(text):
    """Модель иногда оборачивает JSON в ```json ... ``` или пишет слово перед ним."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0]
    i = min([p for p in (s.find("{"), s.find("[")) if p >= 0], default=0)
    return json.loads(s[i:])
