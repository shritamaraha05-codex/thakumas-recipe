# 11 Privacy and consent (TRU-3)

1. **Audio is processed, not kept.** Browser audio goes to Gnani via our server and is discarded after transcription. Only the transcript is stored, after the user confirms it. No audio files in the repo, in fixtures or in logs.
2. **Consent before recording another person.** A modal asks the recorder to confirm the cook agrees; it creates a `consent` row (`transcript`). Sharing publicly needs `share_public`; cloned voice needs `voice_clone` plus a spoken verification phrase read by the cook. Consent can be revoked; revocation hides share/clone features for that person's recipes.
3. **Names stripped before LLM calls.** Replace person names with placeholders; send transcript text only. Check each free provider's data-use terms.
4. **Synthetic or consented data only.** Follow the programme rule: no real phone numbers, account numbers, Aadhaar, PAN or recorded calls in the project or demo. Demo with ourselves or a relative who agreed in writing.
5. **Delete means delete.** Deleting a person removes consents, hand profiles and weighings; recipes drop the link. Provide a "delete everything" button.
6. **No minors' voices** in recordings or the demo.
7. **Advice limits.** Kitchen rescue and any nutrition/allergen output is labelled an estimate or suggestion, not medical or food-safety advice.
8. **Secrets.** `.env` is never committed; the Kaggle tunnel token is rotated per run.
9. **Cloned voice (SHR-4)**: off by default; if built, add an audible "AI voice" disclosure to every clip and never use it for anyone who has not consented.
