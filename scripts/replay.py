from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import sqlite3
import json
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _latest_run_dir(runs_dir: Path) -> Path:
    candidates = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not candidates:
        raise typer.BadParameter(f"No runs found in {runs_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


@app.command()
def replay(
    runs_dir: Path = typer.Option(Path("runs"), help="Directory containing runs"),
    run_path: Optional[Path] = typer.Option(None, help="Specific run directory to replay"),
    kind: List[str] = typer.Option([], help="Filter by event type(s), e.g. --kind tick --kind note"),
    limit: int = typer.Option(200, help="Max events to display"),
):
    """Replay events from a SOMA run (reads events.sqlite)."""
    run_dir = run_path or _latest_run_dir(runs_dir)
    db = run_dir / "events.sqlite"
    if not db.exists():
        raise typer.BadParameter(f"No events.sqlite in {run_dir}")

    conn = sqlite3.connect(str(db))
    try:
        cur = conn.cursor()
        if kind:
            placeholders = ",".join(["?"] * len(kind))
            q = f"SELECT tick, type, data FROM events WHERE type IN ({placeholders}) ORDER BY tick, id LIMIT ?"
            params = (*kind, limit)
        else:
            q = "SELECT tick, type, data FROM events ORDER BY tick, id LIMIT ?"
            params = (limit,)
        rows = cur.execute(q, params).fetchall()

        table = Table(title=f"Replay — {run_dir.name}")
        table.add_column("Tick", justify="right")
        table.add_column("Type")
        table.add_column("Summary")

        for tick, etype, data_json in rows:
            try:
                data = json.loads(data_json)
                summary = data.get("note") or data.get("payload") or data.get("type")
                summary = str(summary)[:80]
            except Exception:
                summary = data_json[:80]
            table.add_row(str(tick), etype, summary)

        console.print(table)
    finally:
        conn.close()


if __name__ == "__main__":
    app()