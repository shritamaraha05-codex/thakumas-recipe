# Thakuma's Recipe (ঠাকুমার রান্না)

Narrate a recipe the way grandmothers do ("ek muthi chal, ek chimti nun, jol ta jemon lage"). The app turns it into steps, converts vague units into **ranges** (not fake-precise grams), lets you **calibrate** with your own weighing, and reads steps back hands-free.

## Run
    pip install -r requirements.txt
    cp .env.example .env      # add GNANI_API_KEY
    uvicorn app:app --reload  # open http://127.0.0.1:8000
    python tests/test_core.py # parser tests, no API needed

Without a key, typing/pasting and "Use a sample" still work; voice is disabled.

## How Gnani is used
- **Prisma** (`/stt/v3`): browser audio is converted to 16 kHz WAV and split into 25 s chunks (REST limit is 30 s). Sent one at a time. Tip: set the language in the dropdown for better results than auto-detect.
- **Timbre** (`/api/v1/tts/inference`): reads each step aloud. Falls back to the browser voice if the call fails. Voice and model are set in `.env`.
- Voice commands in cook mode (next, back, repeat, stop) are a 3.5 s Prisma clip matched against Bengali, Hindi and English words.

## Honest limits
- The unit table in `core.py` (`D`) holds **starting estimates, not measurements**. Calibration replaces them: one weighing gives +-15%, several give your observed spread +-5%.
- Parsing is rule-based: lexicon + spelling tolerance. New words go into the tables at the top of `core.py`.
- The Gnani calls were written from the docs and **not run against the live API**. Test one real Bengali recording first.
- Timbre reads text as written; digits may be mispronounced, so only the step text is spoken, and grams are shown on screen.
