# CLAUDE.md

Instructions for Claude when working in this repository.

## Logic gates (how to ask for decisions)

When a path forward needs my decision, don't write one long answer with a big decision at the end.

- Break the decision into small **gates**, one at a time.
- Each gate gives **three clear options**, labeled A, B and C, readable in about one minute.
- Mark the recommended option.
- Keep each option to one or two lines: what it means and what it leads to.
- When there are several gates, show the path first (numbered list, current gate marked).
- After I pick, lock it in with one line, then move to the next gate.
- I may tweak an option ("A, but ..."); restate it and move on.
- When the gates are done, record the decisions in the project's decision log.

## Decision log

The decision log is `DECISIONS.md` in the repo root. Add new decisions to the
top of its table: date, decision, why, and where it lives (file or setting).
Keep it out of `docs/`, because that folder is the published website.

## Taking actions

- Don't make code changes until the gates for that change are answered.
- Explain things in plain, simple steps. Don't assume I know how to do everything.
- Clearly separate steps I have to do myself (accounts, secrets, settings) from
  steps Claude does in the code.
