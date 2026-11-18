# Decision log

Decisions made through logic gates (see `CLAUDE.md`). Newest first.

| Date | Decision | Why | Where it lives |
|------|----------|-----|----------------|
| 2026-11-18 | Favicon: rising bar chart on deep teal | Reads as "data and growth" and stays clear at 16px | `site_assets/`, linked from `page_shell` in `generate_site.py` |
| 2026-11-18 | Put the redesigned city page live for all 50 cities; other pages follow next | Preview approved; fixes the dated look where readers land most | `city_page.py`, `docs/assets/city.css` |
| 2026-11-18 | City page layout: one section per metric (explanation, headline number, score bar, write-up together) | Each metric used to appear in three disconnected places | `city_page.py` |
| 2026-11-18 | Look and feel: clean and editorial (serif headings, calm colors, white space) | Matches the plain, careful tone of the write-ups | `city_page.py` (`CITY_CSS`) |
| 2026-11-18 | New plain-English write-ups go live now; tighten wording later with the redesign | Fixes wrong Cost of Living / Days on Market text on the live site today | `city_econ_pipeline.py` |
| 2026-11-17 | Spell out each metric's verdict ("a strength: more affordable than most") in the AI's data | The AI kept reading Cost of Living backwards when left to work out the direction | `city_econ_pipeline.py` (`VERDICT_WORDS`) |
| 2026-11-17 | Test new write-ups on the working branch before going live | See the result before the public does | GitHub Actions runs #61, #62 |
| 2026-11-17 | Metric explanation wording approved as drafted | Short, plain, matches how scores are calculated | `generate_site.py` (`METRIC_EXPLAINERS`) |
| 2026-11-17 | Show one plain sentence under each metric name, always visible | Nobody has to click to understand a metric | `generate_site.py` |
| 2026-11-17 | Fix the write-ups before the redesign | Wrong Days on Market text was live | `city_econ_pipeline.py` |
| 2026-11-11 | Run the city briefs through OpenRouter (`meta-llama/llama-3.3-70b-instruct`) instead of Together AI | Together AI dropped the model from its pay-per-use plan, and every run after Oct 19 failed | `city_econ_pipeline.py`, `OPENROUTER_API_KEY` secret |
