# Contributing to SOMA

Thanks for your interest in SOMA! This project is research-oriented and values **interpretability**, **reproducibility**, and **small, auditable changes**.

## Quick Start (dev setup)

```
# from repo root
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

python -m pip install -U pip
pip install -r requirements.txt
```

## Smoke test:

```
Copy code
# Minimal run (Grid v0)
python -m scripts.run --ticks 30 --seed 123 --env grid-v0
# Replay notes from the last run folder
python -m scripts.replay --kind note
# Optional caregiver loop:
python -m scripts.caregiver ls runs/<run_id_from_above>
```

## Grid v1.5 (richer affordances):
```
python -m scripts.run --env grid-v1 --ticks 60 --seed 123 --size 9 --n-objects 16 --view-radius 1
```

## Project Structure (high level)

- `soma/core/` — event log, store, tick loop, state snapshot
- `soma/cogs/` — modular “cogs” (reflex, memory, curiosity, motivation, planner, perception, state tracker, channel, caregiver)
- `soma/sandbox/` — environments (`grid-v0`, `grid-v1`)
- `scripts/` — CLI entry points (`run`, `replay`, `eval`, `caregiver`)
- `runs/` — per-run artifacts (`meta.json`, `events.jsonl`, SQLite, reports)

## How to Contribute
1. **Discuss**: open an Issue describing the change or experiment.
2. **Branch**: fork and create a feature branch from main.
3. **Implement**: keep diffs small and interpretable; prefer adding cogs or parameters over tight coupling.
4. **Test locally**:
    - Run `scripts.run` on both `grid-v0` and `grid-v1` for at least 30–60 ticks.
    - Inspect `runs/<id>/report.md` and `scripts.replay --kind note` output.
    - If you add a cog, ensure it writes **self-notes**.
5. **PR checklist**:
    - Code is typed (PEP 484) and minimally documented (docstrings).
    - No print-spamming; use the event log or self-notes.
    - Runs complete deterministically with `--seed` set.
    - README/docs updated if flags or behavior changed.
    - Added/updated small tests where applicable (see `tests/`).

## Coding Guidelines
- **Interpretability first**: every cog that makes a decision emits a self-note with the inputs/outputs it used.
- **Separation of concerns**: cogs communicate via the event bus/state snapshot, not ad-hoc imports.
- **No external rewards**: behaviors consume drive pressures only.
- **Style**: follow standard Python style; prefer clear names over cleverness.
- **Types**: annotate public functions; keep dataclasses for structured payloads.

## Tests
A lightweight smoke suite is sufficient; if you use `pytest`:

```
pip install pytest
pytest -q
```

## Reporting Bugs / Proposing Features
- Use GitHub Issues. Include:
    - OS + Python version
    - Exact command(s) run
    - Traceback (if any) and `runs/<id>/meta.json`
    - What you expected vs. observed

## License & CLA
By contributing, you agree your contributions are licensed under the **MIT License** (see `LICENSE`). No CLA required.