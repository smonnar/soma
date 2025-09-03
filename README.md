# SOMA — Self-Organizing Mechanomorphic Agent

Milestone M0: minimal runnable scaffold with a deterministic tick loop and JSONL event stream.

## Quickstart
```bash
# from repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
python scripts/run.py --ticks 25 --seed 123