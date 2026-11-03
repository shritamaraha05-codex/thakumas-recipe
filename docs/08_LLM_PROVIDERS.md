# 08 LLM providers, fallback chain and the Kaggle-Evon experiment

## Interface (`backend/app/llm/base.py`)
```python
class LLMProvider(Protocol):
    name: str
    def chat_json(self, system: str, user: str, schema: dict, timeout: float) -> dict: ...
    def chat_text(self, system: str, user: str, timeout: float) -> str: ...
    def health(self) -> dict: ...
```
All providers are OpenAI-compatible HTTP (`POST {base}/chat/completions`, bearer token). One generic class, different base URLs.

## Chain (`LLM_CHAIN`, default `gemini,ollama,evon_kaggle,rules`)
1. Check `llm_cache` (key = sha256 of prompt version + system + user + schema; provider-independent so replay works for any provider).
2. Try providers in order. Per provider: timeout 12 s, one retry on 429/5xx. Circuit breaker: 3 consecutive failures -> skip for 60 s.
3. Validate with pydantic; on invalid JSON retry once with "Return valid JSON only"; then next provider.
4. If all fail, return rules-only result with `meta.llm_provider=null`.
5. `LLM_REPLAY_ONLY=1` serves cache only; UI shows "replayed" badge. Use it for the demo and label it honestly.
The UI shows a "Running on <provider>" badge only when that provider actually answered.

## Providers
- **Gemini**: base `https://generativelanguage.googleapis.com/v1beta/openai/`, bearer `GEMINI_API_KEY` (verify in Google AI docs; model names change, so keep `GEMINI_MODEL` in `.env` and check current ones). Free-tier limits and data-use terms must be checked: assume prompts may be used for improvement, so send only transcript text with names stripped.
- **Ollama (local)**: `http://localhost:11434/v1`. Laptop GPU is small (6 GB VRAM): pick a small instruct model, test it on `parse_cases.yaml` for Bengali quality, and record the result below.
- **Evon on Kaggle (experimental)**: `EVON_BASE_URL` = tunnel URL + `/v1`, bearer `EVON_API_KEY`. See below.

## What the LLM is used for (all optional, all validated)
UND-2 extraction; CAP-3 interview follow-up questions; COK-4 kitchen rescue (labelled advice); UND-5 later. The LLM never produces grams.

## Evon on Kaggle: facts and plan
Facts: Evon v3.3 is a ~31.7B-parameter hybrid Mamba MoE (about 3B active), BF16 weights (~63 GB), Apache-2.0, 131k context. The model card says to pass `enable_thinking=False` to disable reasoning traces. Kaggle free: 2x T4 (32 GB combined) or one P100 (16 GB), roughly 30 GPU-hours/week, sessions 9-12 h, 20 GB disk. The plain `from_pretrained` in the original notebook will run out of memory.
No Evon GGUF/AWQ build was found. Converting it ourselves needs more disk than Kaggle gives.

**Timebox: 2 hours, Day 1, owner Mrinmoy (task M10).** Stop and use Gemini/Ollama if any gate fails.
Gates: (1) internet on and `!df -h` shows enough free space on a non-working directory; (2) model downloads with `HF_HOME=/tmp/hf`; (3) 4-bit load succeeds across both T4s; (4) one Bengali JSON-extraction prompt returns valid JSON in < 60 s; (5) tunnel reachable from the laptop.

Untested starting cells:
```python
# 1. install
!pip install -q -U transformers accelerate bitsandbytes fastapi uvicorn nest_asyncio
# optional if the architecture needs them (may fail to build on T4): mamba-ssm causal-conv1d
# 2. load in 4-bit across both GPUs (T4 has no bf16: use float16)
import os; os.environ["HF_HOME"] = "/tmp/hf"
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
MID = "gnani/gnani-evon-v3.3-30B-A3B"   # model card examples also show gnani/gnani-evon-v3.3: use whichever resolves
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
tok = AutoTokenizer.from_pretrained(MID, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(MID, quantization_config=bnb, device_map="auto",
        max_memory={0: "14GiB", 1: "14GiB", "cpu": "20GiB"}, trust_remote_code=True)
# 3. OpenAI-compatible server with bearer auth
import threading, uuid, uvicorn, nest_asyncio; nest_asyncio.apply()
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
TOKEN = "CHANGE_ME_LONG_RANDOM"; LOCK = threading.Lock(); app = FastAPI()
class Msg(BaseModel): role: str; content: str
class Req(BaseModel): model: str | None = None; messages: list[Msg]; max_tokens: int = 512; temperature: float = 0.0
@app.post("/v1/chat/completions")
def chat(r: Req, authorization: str = Header(None)):
    if authorization != f"Bearer {TOKEN}": raise HTTPException(401)
    with LOCK:
        ids = tok.apply_chat_template([m.model_dump() for m in r.messages], add_generation_prompt=True,
              return_tensors="pt", return_dict=True, enable_thinking=False).to(model.device)
        out = model.generate(**ids, max_new_tokens=r.max_tokens, do_sample=r.temperature > 0, temperature=r.temperature or None)
    text = tok.decode(out[0][ids["input_ids"].shape[-1]:], skip_special_tokens=True)
    return {"id": str(uuid.uuid4()), "object": "chat.completion", "model": "evon",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning"), daemon=True).start()
# 4. public tunnel (no account): prints the URL to put in EVON_BASE_URL
import subprocess, re
subprocess.run("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared && chmod +x cloudflared", shell=True)
p = subprocess.Popen(["./cloudflared", "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"], stderr=subprocess.PIPE, text=True)
for line in p.stderr:
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
    if m: print("EVON_BASE_URL =", m.group(0) + "/v1"); break
```
Operational rules: run as "Save & Run All" so closing the tab does not stop it (uses quota); the URL changes every run; keep the token secret; send only transcript text; check Kaggle's terms about public tunnels first; the app must work when it is down.

## Decision log (fill in)
| Date | Provider | Tried | Result | Decision | Who |
|---|---|---|---|---|---|
| | evon_kaggle | gates 1-5 | | | |
| | gemini | 10 Bengali parse cases | | | |
| | ollama (model: ) | 10 Bengali parse cases | | | |
