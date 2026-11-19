"""Streamlit UI for the local Kokoro-FastAPI server."""

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "Kokoro-FastAPI"
PID_FILE = ROOT / ".kokoro-api.pid"
LOG_FILE = ROOT / ".kokoro-api.log"
BASE_URL = "http://127.0.0.1:8880"
FORMATS = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "flac": "audio/flac",
}
LANGUAGES = {
    "Auto": None,
    "American English": "a",
    "British English": "b",
    "Spanish": "e",
    "French": "f",
    "Hindi": "h",
    "Italian": "i",
    "Japanese": "j",
    "Brazilian Portuguese": "p",
    "Chinese": "z",
}
ACCENT_NAMES = {code: name for name, code in LANGUAGES.items() if code}
GENDERS = {"f": "female", "m": "male"}
CREATE_FLAGS = (
    subprocess.CREATE_NEW_PROCESS_GROUP
    | subprocess.CREATE_NO_WINDOW
    | subprocess.CREATE_BREAKAWAY_FROM_JOB
)


def for_display(text: str) -> str:
    return text.replace("$", "＄")


def api_is_running() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1.0) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def process_is_running(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    return result.stdout.strip().startswith('"')


def launcher_pid() -> int | None:
    if not PID_FILE.is_file():
        return None
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        PID_FILE.unlink(missing_ok=True)
        return None
    if not process_is_running(pid):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def last_log_line() -> str:
    if not LOG_FILE.is_file():
        return ""
    text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:180]


def start_script() -> Path:
    name = "start-gpu.ps1" if shutil.which("nvidia-smi") else "start-cpu.ps1"
    return API_DIR / name


def launch_server(script: Path) -> subprocess.Popen:
    log = open(LOG_FILE, "wb")
    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    try:
        try:
            return subprocess.Popen(
                args,
                cwd=str(API_DIR),
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_FLAGS,
            )
        except OSError:
            return subprocess.Popen(
                args,
                cwd=str(API_DIR),
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            )
    finally:
        log.close()


def start_api() -> None:
    script = start_script()
    if not script.is_file():
        raise FileNotFoundError("Kokoro-FastAPI is not installed. Run install.ps1 first.")
    process = launch_server(script)
    PID_FILE.write_text(str(process.pid), encoding="utf-8")


def stop_api() -> None:
    pid = launcher_pid()
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "stop.ps1"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    if pid:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    PID_FILE.unlink(missing_ok=True)


def remember_start_failure(starting: bool, running: bool) -> str:
    was_starting = st.session_state.get("api_starting", False)
    if was_starting and not starting and not running:
        st.session_state["start_error"] = (
            last_log_line() or "The API process exited before it was ready."
        )
    elif starting or running:
        st.session_state["start_error"] = ""
    st.session_state["api_starting"] = starting
    return st.session_state.get("start_error", "")


def render_service_status(running: bool, starting: bool, start_error: str) -> None:
    if running:
        st.text("API running at http://localhost:8880")
        return
    if starting:
        detail = last_log_line()
        st.text(f"Starting API… {detail}".strip())
        return
    st.text("API stopped. The first start can take several minutes.")
    if start_error:
        st.error(for_display(start_error))


@st.fragment(run_every=2)
def render_service_controls() -> None:
    running = api_is_running()
    starting = launcher_pid() is not None and not running
    status = st.empty()
    clicked = st.button(
        "Stop API" if running or starting else "Start API",
        width="stretch",
        key="api_power",
    )
    if clicked:
        try:
            if running or starting:
                stop_api()
                st.session_state["api_starting"] = False
                st.session_state["start_error"] = ""
            else:
                st.session_state["start_error"] = ""
                start_api()
        except (OSError, subprocess.SubprocessError) as exc:
            st.session_state["start_error"] = str(exc)
        running = api_is_running()
        starting = launcher_pid() is not None and not running
    start_error = remember_start_failure(starting, running)
    with status.container():
        render_service_status(running, starting, start_error)


def voices_on_disk() -> list[str]:
    folder = API_DIR / "api" / "src" / "voices" / "v1_0"
    names = sorted(path.stem for path in folder.glob("*.pt")) if folder.is_dir() else []
    return names or ["af_heart"]


def fetch_voices() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/v1/audio/voices", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    voices = payload.get("voices", [])
    if not voices:
        return None
    if isinstance(voices[0], dict):
        names = [item.get("id") or item.get("name") for item in voices]
        return sorted(name for name in names if name)
    return sorted(str(name) for name in voices)


@st.cache_data(ttl=15, show_spinner=False)
def available_voices() -> list[str]:
    return fetch_voices() or voices_on_disk()


def voice_index(voices: list[str]) -> int:
    if "af_heart" in voices:
        return voices.index("af_heart")
    return 0


def voice_label(voice: str) -> str:
    accent = ACCENT_NAMES.get(voice[:1], "")
    gender = ""
    if len(voice) > 2 and voice[2] == "_":
        gender = GENDERS.get(voice[1], "")
    detail = ", ".join(part for part in (accent, gender) if part)
    name = voice.split("_", 1)[1] if "_" in voice else ""
    if name.endswith("_inno"):
        detail = f"{detail}, tuned" if detail else "tuned"
    elif name.endswith("_tuned"):
        detail = f"{detail}, saved tune" if detail else "saved tune"
    elif name.startswith("v0"):
        detail = f"{detail}, v0" if detail else "v0"
    if not detail:
        return voice
    return f"{voice} — {detail}"


def http_error_message(exc: urllib.error.HTTPError) -> str:
    raw = exc.read().decode("utf-8", errors="replace")
    try:
        detail = json.loads(raw).get("detail", raw)
    except json.JSONDecodeError:
        return raw or str(exc.reason)
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)


def reading_options() -> dict[str, bool]:
    st.caption("How text is read")
    left, right = st.columns(2)
    return {
        "unit_normalization": left.checkbox(
            "Spell out units",
            help="10KB is spoken as 10 kilobytes.",
        ),
        "url_normalization": right.checkbox("Read URLs", value=True),
        "email_normalization": left.checkbox("Read email addresses", value=True),
        "phone_normalization": right.checkbox("Read phone numbers", value=True),
        "caps_normalization": left.checkbox("Read all-caps words as words", value=True),
        "replace_remaining_symbols": right.checkbox("Replace leftover symbols", value=True),
        "remove_emoji": left.checkbox("Strip emoji"),
    }


def voice_markup_options() -> tuple[bool, bool]:
    tag_col, ssml_col = st.columns(2)
    allow_voice_tags = tag_col.checkbox(
        "Voice tags",
        help="[voice:af_bella] switches speaker. [pause:0.5s] inserts a pause.",
    )
    ssml = ssml_col.checkbox(
        "SSML input",
        help="The text is SSML. Voice tags are sent as on, because the translation uses them.",
    )
    return allow_voice_tags or ssml, ssml


def create_speech(
    text: str,
    voice: str,
    speed: float,
    volume: float,
    audio_format: str,
    lang_code: str | None,
    reading: dict[str, bool],
    allow_voice_tags: bool,
    ssml: bool,
) -> bytes:
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": audio_format,
        "stream": False,
        "speed": speed,
        "volume_multiplier": volume,
        "normalization_options": reading,
        "allow_voice_tags": allow_voice_tags,
        "ssml": ssml,
    }
    if lang_code:
        payload["lang_code"] = lang_code
    request = urllib.request.Request(
        f"{BASE_URL}/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def render_speech_form() -> None:
    voices = available_voices()
    with st.form("speech"):
        voice_col, lang_col = st.columns(2)
        voice = voice_col.selectbox(
            "Voice",
            voices,
            index=voice_index(voices),
            format_func=voice_label,
        )
        language_names = list(LANGUAGES)
        language = lang_col.selectbox(
            "Language",
            language_names,
            index=language_names.index("American English"),
        )
        speed_col, volume_col, format_col = st.columns(3)
        speed = speed_col.slider("Speed", min_value=0.25, max_value=4.0, value=1.0, step=0.05)
        volume = volume_col.slider("Volume", min_value=0.0, max_value=2.0, value=1.0, step=0.05)
        audio_format = format_col.selectbox("Format", list(FORMATS))
        reading = reading_options()
        allow_voice_tags, ssml = voice_markup_options()
        text = st.text_area("Text", height=140, placeholder="Text to turn into audio")
        submitted = st.form_submit_button("Create audio", width="stretch")
    if not submitted:
        return
    if not text.strip():
        st.warning("Enter some text first.")
        return
    if not api_is_running():
        st.error("The API is not running. Start it above, then try again.")
        return
    try:
        with st.spinner("Creating audio…"):
            audio = create_speech(
                text.strip(),
                voice,
                speed,
                volume,
                audio_format,
                LANGUAGES[language],
                reading,
                allow_voice_tags,
                ssml,
            )
    except urllib.error.HTTPError as exc:
        st.error(for_display(http_error_message(exc)))
        return
    except (OSError, urllib.error.URLError) as exc:
        st.error(for_display(f"Could not reach the API. {exc}"))
        return
    st.session_state["audio_bytes"] = audio
    st.session_state["audio_format"] = audio_format


def show_audio() -> None:
    audio = st.session_state.get("audio_bytes")
    audio_format = st.session_state.get("audio_format")
    if not audio or audio_format not in FORMATS:
        return
    st.audio(audio, format=FORMATS[audio_format])
    st.download_button(
        "Download",
        data=audio,
        file_name=f"speech.{audio_format}",
        mime=FORMATS[audio_format],
        key="download_audio",
    )


def render_footer() -> None:
    st.caption("Sponsored by [aifab.xyz](https://aifab.xyz)")


def main() -> None:
    st.set_page_config(page_title="Kokoro", layout="centered")
    with st.sidebar:
        render_service_controls()
    st.title("Kokoro")
    render_speech_form()
    show_audio()
    render_footer()


main()
