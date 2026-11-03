import os, json, threading
from pathlib import Path
import requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from core import parse, command

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent
KEY = os.getenv("GNANI_API_KEY", "")
STT_MODEL = os.getenv("GNANI_STT_MODEL", "prisma-v3.0")
TTS_MODEL = os.getenv("GNANI_TTS_MODEL", "timbre-v3.0")
VOICE = os.getenv("GNANI_VOICE", "Shivani")
TOPIC = "Home cooking narration in Bengali or Hinglish with vague measures like muthi, chimti, kap, chamoch"
KEYTERMS = ["মুঠো", "চিমটি", "চামচ", "কাপ", "muthi", "chimti", "chamoch", "tarpor"]
LOCK = threading.Lock()  # some accounts allow one active request at a time
app = FastAPI(title="Thakuma's Recipe")


def _fail(resp):
    try:
        j = resp.json()
        msg = j.get("error") or j.get("detail") or j
    except Exception:
        msg = resp.text[:200]
    raise HTTPException(502, f"Gnani API {resp.status_code}: {msg}")


def _need_key():
    if not KEY:
        raise HTTPException(503, "Set GNANI_API_KEY in .env to use voice. Typing and pasting still work.")


def stt(audio: bytes, lang: str) -> str:
    _need_key()
    if STT_MODEL == "prisma-v3.0":
        data = {"model": STT_MODEL, "language_code": lang, "topic": TOPIC, "keyterms": json.dumps(KEYTERMS, ensure_ascii=False)}
    else:  # Prisma v2.5 takes exactly one language
        data = {"language_code": "bn-IN" if lang == "indic-auto" or "," in lang else lang}
    with LOCK:
        r = requests.post("https://api.vachana.ai/stt/v3", headers={"X-API-Key-ID": KEY},
                          files={"audio_file": ("clip.wav", audio, "audio/wav")}, data=data, timeout=60)
    if r.status_code != 200:
        _fail(r)
    return r.json().get("transcript", "")


@app.get("/api/config")
def config():
    return {"gnani": bool(KEY), "voice": VOICE}


@app.post("/api/transcribe")
def transcribe(audio: UploadFile = File(...), language: str = Form("indic-auto")):
    return {"transcript": stt(audio.file.read(), language)}


@app.post("/api/command")
def cmd(audio: UploadFile = File(...), language: str = Form("indic-auto")):
    t = stt(audio.file.read(), language)
    return {"transcript": t, "command": command(t)}


class ParseIn(BaseModel):
    text: str
    calibration: dict = {}


@app.post("/api/parse")
def parse_ep(b: ParseIn):
    return {"steps": parse(b.text, b.calibration)}


class SpeakIn(BaseModel):
    text: str
    language: str = "auto"


@app.post("/api/speak")
def speak(b: SpeakIn):
    _need_key()
    body = {"text": b.text, "voice": VOICE, "model": TTS_MODEL, "language": b.language, "speed": 0.95,
            "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "wav"}}
    with LOCK:
        r = requests.post("https://api.vachana.ai/api/v1/tts/inference", headers={"X-API-Key-ID": KEY, "Content-Type": "application/json"}, json=body, timeout=60)
    if r.status_code != 200:
        _fail(r)
    return Response(r.content, media_type="audio/wav")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
