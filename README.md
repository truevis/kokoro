# Kokoro-FastAPI on Windows (no Docker)

Native Windows install (no Docker): installs **uv**, **eSpeak NG**, and **Git** via winget (only if missing), clones [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) into `Kokoro-FastAPI\`, creates a `.venv`, and starts the API. `app.py` is a Streamlit page that starts that API and turns text into speech.

## Install and run

```powershell
git clone https://github.com/truevis/kokoro.git
cd kokoro
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

To use another directory name, clone as usual and run `install.ps1` from the repo root. Optional: set `$env:KOKORO_DIR` before install to choose where `Kokoro-FastAPI` is cloned (default: `.\Kokoro-FastAPI` next to this repo).

`install.ps1` picks **GPU** (`start-gpu.ps1`) when `nvidia-smi` works, otherwise **CPU** (`start-cpu.ps1`). First start downloads model weights.

Start again later (from the clone):

```powershell
cd .\Kokoro-FastAPI
.\start-gpu.ps1    # or .\start-cpu.ps1
.\stop.ps1         # stop uvicorn when not in the start terminal
```

From the repo root you can also run `.\stop.ps1`.

Open a **new** PowerShell after install if `uv` is not found (winget updates PATH).

| What | URL |
|------|-----|
| This app | http://localhost:8501 |
| Web player | http://localhost:8880/web/ |
| API docs | http://localhost:8880/docs |
| Health | http://localhost:8880/health |
| TTS (OpenAI-compatible) | `POST http://localhost:8880/v1/audio/speech` |

## App

From the repo root, with [Streamlit](https://docs.streamlit.io) installed:

```powershell
streamlit run app.py
```

Open http://localhost:8501. The page calls the API at http://localhost:8880.

The sidebar shows whether the API is running and a **Start API** / **Stop API** button. Start launches `Kokoro-FastAPI\start-gpu.ps1` when `nvidia-smi` works, otherwise `start-cpu.ps1`. Stop runs `stop.ps1` and ends that launcher. Status refreshes every few seconds. The first start downloads weights and can take several minutes.

The main form is voice, language, speed (`0.25`–`4`), volume (`0`–`2`), format (`mp3`, `wav`, or `flac`), and the text. Each voice keeps its id and adds a short description: language and gender (`af_heart — American English, female`). A name ending in `_inno` is marked tuned, `_tuned` is a tune you saved, and `v0` is an older pack. **Create audio** plays the clip under the button and offers **Download**.

**Read phone numbers** is on by default. A separated number such as `555-123-4567` is spoken digit by digit. A number with no separators is spoken digit by digit when the sentence calls it a phone, mobile, cell, fax, or dial number: `My phone number is 8275409.` is "eight two seven, five four zero nine." A 7-digit figure with no phone wording is still read as a quantity ("eight million…"). The same rule is `phone_normalization` on `POST /v1/audio/speech`.

The page footer links to [aifab.xyz](https://aifab.xyz).

Root `http://localhost:8880/` returns 404 — use `/web/` or `/docs`. Default: no API key (`API_KEYS` unset). Keep port **8880** off the public internet.

## Stopping the server

In the terminal running `start-gpu.ps1` / `start-cpu.ps1`: **Ctrl+C** and wait until uvicorn exits (frees GPU memory).

If it is running elsewhere (or you closed that terminal):

```powershell
cd .\Kokoro-FastAPI
.\stop.ps1
```

`install.ps1` copies `stop.ps1` from this repo into `Kokoro-FastAPI\`. It ends whichever process is listening on port **8880** and confirms `/health` no longer responds.

Check: `Invoke-WebRequest http://localhost:8880/health` should fail once stopped.

## Quick test (PowerShell)

```powershell
$body = '{"model":"kokoro","input":"Kokoro is running.","voice":"af_heart","response_format":"mp3","stream":false}'
Invoke-RestMethod -Uri http://localhost:8880/v1/audio/speech `
  -Method Post -Body $body -ContentType application/json `
  -OutFile .\test\kokoro-test.mp3
```

Set `"stream": false` for a single file response (the API default is streaming).

## Generate speech with Python

Requires the server running. Use the project venv or any Python 3.10+ with `httpx` or `requests`.

```powershell
cd .\Kokoro-FastAPI
uv pip install httpx
```

### Minimal example

```python
from pathlib import Path

import httpx

BASE = "http://localhost:8880"
payload = {
    "model": "kokoro",
    "input": "Hello from Python.",
    "voice": "af_heart",
    "response_format": "mp3",
    "stream": False,
}
r = httpx.post(f"{BASE}/v1/audio/speech", json=payload, timeout=120.0)
r.raise_for_status()
Path("speech.mp3").write_bytes(r.content)
```

### All `POST /v1/audio/speech` body fields

| Field | Default | Notes |
|-------|---------|--------|
| `input` | *(required)* | Text to speak (large limit; see upstream settings). |
| `model` | `kokoro` | Also `tts-1`, `tts-1-hd` (mapped to Kokoro weights). |
| `voice` | `af_heart` | Kokoro name (`af_bella`, `am_adam`, …) or OpenAI alias (`alloy`, `nova`, …). Mix voices: `af_bella(2)+af_sky`. |
| `response_format` | `mp3` | `mp3`, `wav`, `flac`, `opus`, `aac`, `pcm`. |
| `stream` | `true` | Set **`false`** to get one complete file in the response body. |
| `speed` | `1.0` | `0.25`–`4.0`. |
| `volume_multiplier` | `1.0` | `0.0`–`10.0`. |
| `lang_code` | *(auto)* | Optional: `a`, `b`, `e`, `f`, `h`, `i`, `j`, `p`, `z`. Else inferred from voice. |
| `allow_voice_tags` | `false` | `true` enables `[voice:name]` and `[pause:0.5s]` in `input`. |
| `ssml` | `false` | SSML → tags; requires `allow_voice_tags: true`. |
| `return_download_link` | `false` | If `true`, response headers include `X-Download-Path` (temp file on server). |
| `download_format` | `null` | Must match `response_format` when set. |
| `return_timing` | `false` | With `return_download_link`, adds timing sidecar (`X-Timing-Path`). |
| `voice_aliases` | `null` | e.g. `{"narrator": "af_bella", "guest": {"voice": "am_adam", "rate": 0.9}}`. |
| `normalization_options` | defaults | Sub-keys: `normalize`, `unit_normalization`, `url_normalization`, `email_normalization`, `phone_normalization` (digit-by-digit for separated numbers, and for a bare number named as a phone, mobile, cell, fax, or dial number), `caps_normalization`, `remove_emoji`, etc. |

If `API_KEYS` is set in `Kokoro-FastAPI\.env`, send `Authorization: Bearer <key>`.

### Full-option example

```python
from pathlib import Path

import httpx

payload = {
    "model": "kokoro",
    "input": "Visit https://example.com or call 555-0100.",
    "voice": "nova",
    "response_format": "wav",
    "stream": False,
    "speed": 1.05,
    "volume_multiplier": 1.0,
    "lang_code": "a",
    "allow_voice_tags": False,
    "normalization_options": {
        "normalize": True,
        "url_normalization": True,
        "phone_normalization": True,
        "remove_emoji": False,
    },
    "voice_aliases": {"host": "af_heart"},
}

with httpx.Client(base_url="http://localhost:8880", timeout=120.0) as client:
    r = client.post("/v1/audio/speech", json=payload)
    r.raise_for_status()
    Path("speech.wav").write_bytes(r.content)
```

### List voices and models

```python
import httpx

base = "http://localhost:8880"
print(httpx.get(f"{base}/v1/models").json())
print(httpx.get(f"{base}/v1/audio/voices").json())
```

### OpenAI Python client (optional)

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8880/v1", api_key="not-needed")
with client.audio.speech.with_streaming_response.create(
    model="kokoro",
    voice="alloy",
    input="Hello.",
    response_format="mp3",
) as response:
    response.stream_to_file("speech.mp3")
```

### Extra dev endpoints (same server)

| Endpoint | Purpose |
|----------|---------|
| `POST /dev/dialogue` | Multi-speaker JSON `turns` → one audio file. |
| `POST /dev/captioned_speech` | Audio + word timestamps (JSON). |
| `GET /v1/download/{filename}` | Fetch file named in `X-Download-Path`. |

See http://localhost:8880/docs for schemas and try-it-out.

## Troubleshooting

- **No venv / no torch:** ensure `Kokoro-FastAPI\.venv` exists (`uv venv` in that folder) before `start-gpu.ps1`.
- **CPU torch on NVIDIA GPU:** reinstall CUDA wheel, e.g. `uv pip install --reinstall "torch==2.8.0+cu128" --index https://download.pytorch.org/whl/cu128` (RTX 40-series often use cu128; see upstream `pyproject.toml` extras).

Upstream details: https://github.com/remsky/Kokoro-FastAPI

## License

[WTFPL](LICENSE) for the scripts and docs in this repo. [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) is a separate project under its own license and is downloaded at install time, not included here.
