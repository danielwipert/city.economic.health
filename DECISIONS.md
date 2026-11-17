# Decision log

Decisions made through logic gates (see `CLAUDE.md`). Newest first.

| Date | Decision | Why | Where it lives |
|------|----------|-----|----------------|
| 2026-11-11 | Run the city briefs through OpenRouter (`meta-llama/llama-3.3-70b-instruct`) instead of Together AI | Together AI dropped the model from its pay-per-use plan, and every run after Oct 19 failed | `city_econ_pipeline.py`, `OPENROUTER_API_KEY` secret |
