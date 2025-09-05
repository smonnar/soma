from __future__ import annotations

from pathlib import Path
from typing import List
import json
import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _load_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


@app.command()
def ls(run_dir: Path = typer.Argument(..., help="Run directory, e.g. runs/m10care_2025...")):
    """List outstanding queries."""
    run_dir = Path(run_dir)
    queries = _load_jsonl(run_dir / "caregiver_queries.jsonl")
    answers = _load_jsonl(run_dir / "caregiver_answers.jsonl")
    answered = {a.get("qid") for a in answers}
    pending = [q for q in queries if q.get("qid") not in answered]
    if not pending:
        typer.echo("No pending queries.")
        raise typer.Exit(code=0)
    for q in pending:
        typer.echo(
            f"qid={q['qid']}  tick={q['tick']}  tokens={q.get('tokens')}  ctx={q.get('context')}"
        )


def _parse_tags(items: List[str]) -> dict:
    tags = {}
    for it in items or []:
        if "=" not in it:
            raise typer.BadParameter(f"--tag must look like TOKEN=GLOSS, got: {it}")
        k, v = it.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            raise typer.BadParameter(f"--tag must look like TOKEN=GLOSS, got: {it}")
        tags[k] = v
    return tags


@app.command()
def answer(
    run_dir: Path = typer.Argument(..., help="Run directory"),
    qid: str = typer.Option(..., help="Query id to answer (from ls)"),
    tag: List[str] = typer.Option(
        None,
        help="Mapping TOKEN=GLOSS (repeatable). "
             "Ex: --tag N!=sudden-color-change --tag ?=object-behaved-different",
    ),
    note: str = typer.Option("", help="Optional note for this answer"),
):
    """Answer a query with token->gloss tags."""
    run_dir = Path(run_dir)
    tags = _parse_tags(tag)
    path_a = run_dir / "caregiver_answers.jsonl"
    obj = {
        "qid": qid,
        "tick": int(qid.split(":")[-1]) if ":" in qid else -1,
        "tags": tags,
        "note": note,
    }
    with path_a.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")
    typer.echo(f"Wrote answer for {qid}: {tags}")


if __name__ == "__main__":
    app()