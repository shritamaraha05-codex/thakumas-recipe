# 07 Gnani integration

Facts below come from docs.gnani.ai (read 1-3 Nov 2026). **Nothing has been run against the live API.** Index of all pages: https://docs.gnani.ai/llms.txt

## Speech-to-text (REST)
- `POST https://api.vachana.ai/stt/v3`, `multipart/form-data`, header `X-API-Key-ID: <key>` (optional `X-API-Request-ID`).
- Fields: `audio_file` (required), `language_code` (required; except `format=transliterate` on v3.0), `model` (`prisma-v3.0`, or omit for Prisma v2.5), `format` (`verbatim` default | `transcribe` (ITN: digits, currency, dates) | `codemix` v3.0 only | `transliterate` v3.0 only), `keyterms` (v3.0; JSON array or comma list, up to 200), `topic` (v3.0, <=1600 chars), `previous_text` (v3.0, last 600 chars kept), `speaker_names` (v3.0), `bias_list`+`bias_score` (v2.5 only; single letters-only words).
- Languages: `bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN`. Prisma v3.0 also accepts `indic-auto` or a comma list of 1-4 languages (hints, not locks) and returns `detected_language_code`.
- Limits: audio **<=30 s**; formats WAV, MP3, OGG, FLAC, AAC, M4A (**WebM is not listed**, so convert in the browser); audio <0.1 s returns an empty transcript; clips under ~1 s are the least reliable. Empty transcript is not an error.
- The browser preserves raw ADTS AAC rather than requiring Web Audio decode (which is unavailable in some desktop browsers). AAC clips over 30 seconds are split sequentially at AAC frame boundaries into <=25 s requests; WAV retains the documented low-energy PCM splitting. Backend validates each request's format and duration and passes the actual MIME type to Gnani. No audio is persisted.
- Response: `{success, request_id, transcript, model, detected_language_code?, truncated?, processing_time, end_to_end_latency}`; v2.5 adds `output.literal`.
- Errors: validation 422 `{detail:[...]}`; envelope `{success:false,error:{type,message}}` for 400/500 (`INVALID_LANGUAGE_CODE, MODEL_UNSUPPORTED_LANGUAGE, INVALID_MODEL, INVALID_FORMAT, INVALID_CONTEXT, EMPTY_AUDIO, UNSUPPORTED_AUDIO_FORMAT, AUDIO_CONVERSION_ERROR, MAX_AUDIO_DURATION_EXCEEDED, TRANSCRIPTION_FAILED`); 504 `UPSTREAM_TIMEOUT` (5 s bound on the transcription step); gateway errors `{detail:{error_code,message,status_code}}` for 401 `MISSING_API_KEY/INVALID_API_KEY`, 402 credit, 403 `SCOPE_NOT_ALLOWED`, 429 `RATE_LIMITED`. **Some accounts allow only one active request at a time** (429 while another runs): hold a global lock.
- Word-level timestamps are **not** in the REST response (another participant reported the same for v3.0). We do not need them.
- Python SDK exists (`pip install gnani-vachana`, `GnaniSTTClient`, `GnaniTTSClient`); we use plain `requests` so the code is transparent and mockable.

## Text-to-speech (REST)
- `POST https://api.vachana.ai/api/v1/tts/inference`, JSON, header `X-API-Key-ID`.
- Body: `text`, `model` (`timbre-v2.5` | `timbre-v3.0`), `voice` (voices are per model), `language` (`auto, hi-IN, en-IN, ta-IN, te-IN, kn-IN, ml-IN, mr-IN, pa-IN, bn-IN, gu-IN, hi-en`), `speed` (0.85-1.15 or `slow|medium|fast`), `audio_config{sample_rate 8000..48000, num_channels, sample_width, encoding, container wav|raw|mp3|ogg|mulaw|alaw, bitrate}`.
- Returns **binary audio** in the requested container (200), or 400/403/429/500/503 JSON errors. The [current official REST guide](https://docs.gnani.ai/api/TTS/tts-inference) confirms `POST /api/v1/tts/inference`, `X-API-Key-ID`, and WAV audio via `audio_config`.
- Timbre v3.0: 13 voices, each speaks all 10 languages: Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash, Devansh, Yashraj, Chetana, Vasudha, Riyaa, Tarika, Harshad; supports inline audio tags (`<pauses>`, `<whispers>`, `<slow>`, ...). v2.5 has 42 voices with a preferred language each (e.g. Nalini, Kaveri, Deepak, Poorvi for Hinglish) and strips audio tags. Default for us: `timbre-v3.0` + `Shivani`; **listen to several voices for Bengali and pick by ear** (record in `08`'s decision log).
- Pass numbers, dates and IDs as spoken words: raw digits are mispronounced (see their Text Normalization Guide). Implement `gnani/tts_text.py` (COK-3).

## Cook Mode integration status
- `/api/speak` is implemented as an authenticated backend proxy using `GNANI_TTS_MODEL`, `GNANI_VOICE`, `GNANI_TTS_URL` and `GNANI_TTS_TIMEOUT`; the API key is never sent to the browser. WAV responses are cached in a bounded process-local cache. Gnani calls share one request lock with STT because some accounts permit only one concurrent call.
- `GNANI_MOCK=1` and upstream failures return an error that tells the frontend to use browser speech. Bengali selection sends the original Bengali step to Timbre (`bn-IN`); English selection sends the generated English translation (`en-IN`) when the translation provider is configured.
- Live audio output has not been smoke-tested in this workspace because no real Gnani request was made.

## Pages to read before implementing the related task
STT WebSocket (`/api/STT/stt-websocket.md`) for COK-2; TTS SSE and WebSocket; Voice Clone Embeddings + Voice Cloned TTS (SHR-4); Available Voices; Text Normalization Guide; Limits; Error Reference; Changelog.

## Chunking rules (CAP-1)
1. Browser finishes recording the actual microphone stream, then decodes, mixes to mono, resamples to 16 kHz, and encodes PCM16 WAV.
2. Clips <=30 s go in one REST request. Longer recordings are held whole while processing, then divided into <=25 s windows. Cut at the lowest-energy 100 ms frame inside the last 3 s of each window so words are less likely to be split.
3. Send longer-clip segments **sequentially**; for v3.0 pass the previous segment's transcript as `previous_text`. Never upload a recording twice or send parallel STT calls.
4. Merge transcripts with a single space; mark chunk boundaries as `|` only in debug logs.
5. Retry once on 429/5xx with 1 s then 3 s backoff; surface `UPSTREAM_BUSY` after that.

## Language and format choices (decide by experiment, record in the eval report)
Compare for Bengali and Benglish narrations: `language_code` = `bn-IN` vs `bn-IN,en-IN` vs `indic-auto`; `format` = default vs `codemix` vs `transcribe`. Use `keyterms` = unit and ingredient words in Bengali script and Roman. Choose the setting that gives the best parse F1, not the prettiest transcript.

## Credit budget (PLT-2)
Credit cost per call is **unknown**. Task M2 makes 5 test calls per endpoint and reads the dashboard to derive credits per audio-second (STT) and per character (TTS). Then set `DAILY_BUDGET` in config, log every call in `api_usage`, cache TTS by hash, and refuse non-essential calls when the budget is low. Never loop calls in tests; `GNANI_MOCK=1`.

## Mock mode
`GNANI_MOCK=1`: STT returns the clearly labelled synthetic transcript in `backend/app/fixtures/mock_transcript_bn.txt` for the first chunk (and an empty transcript for later chunks); tests may override it with `X-Mock-Transcript`. The response has `mock: true`, so the frontend warns that it was not derived from the selected audio. No request is sent to Gnani. All CI tests run in mock mode.
