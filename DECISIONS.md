# Decision Log

Decisions made for this project, newest first. See the "Logic gates" section
in `CLAUDE.md` for how decisions are made.

| Date | Decision | Why | Where it lives |
| :--- | :------- | :-- | :------------- |
| 2026-11-02 | Move all AI model usage from Together AI to OpenRouter (details to be settled through logic gates) | Together removed the Llama 3.3 70B model from its serverless service around Oct 22, which broke the weekly run on Oct 26 and Nov 2. One router for all models keeps things simple. | `city_econ_pipeline.py`, `requirements.txt`, `.github/workflows/economic-data-weekly.yml`, `README.md` (changes pending) |
| 2026-11-02 | Use logic gates for all decisions, and record them in this log | Small A/B/C decisions are faster to read, easier to get right, and leave a clear record. | `CLAUDE.md` |
