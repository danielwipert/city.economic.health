# Decision Log

Decisions made for this project, newest first. See the "Logic gates" section
in `CLAUDE.md` for how decisions are made.

| Date | Decision | Why | Where it lives |
| :--- | :------- | :-- | :------------- |
| 2026-11-02 | Test the switch with a full GitHub Actions run from the branch; no local test first. Merge to `master` only after it passes. | Avoids local setup. Nothing is published to the live site until the merge. | GitHub Actions tab ("Run workflow" on the branch) |
| 2026-11-02 | No backup model; rely on OpenRouter's automatic switching between hosts of the same model | Keeps one consistent writing style. The run only fails if every host is down. | OpenRouter default behaviour (no code) |
| 2026-11-02 | Call OpenRouter with the `openai` Python library (pinned `openai==3.31.0`), replacing `together` | Standard approach in OpenRouter's docs; the existing code barely changes. | `requirements.txt`, `city_econ_pipeline.py` |
| 2026-11-02 | Write briefs with paid Llama 3.3 70B Instruct (`meta-llama/llama-3.3-70b-instruct`) on OpenRouter | Same model and style as before; about $0.03/week. Free version risks rate limits; smaller models weaken the format. | `MODEL_ID` in `city_econ_pipeline.py` |
| 2026-11-02 | Move all AI model usage from Together AI to OpenRouter (details to be settled through logic gates) | Together removed the Llama 3.3 70B model from its serverless service around Oct 22, which broke the weekly run on Oct 26 and Nov 2. One router for all models keeps things simple. | `city_econ_pipeline.py`, `requirements.txt`, `.github/workflows/economic-data-weekly.yml`, `README.md`; secret `OPENROUTER_API_KEY` |
| 2026-11-02 | Use logic gates for all decisions, and record them in this log | Small A/B/C decisions are faster to read, easier to get right, and leave a clear record. | `CLAUDE.md` |
