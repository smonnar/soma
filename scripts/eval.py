from __future__ import annotations

from pathlib import Path
import csv
import json
import typer
from rich.console import Console
from rich.table import Table

# Local imports
from soma.eval.metrics import compute_metrics, load_meta
from soma.eval.report import build_markdown, build_html

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def run(run_dir: Path = typer.Argument(..., help="Path to a single run directory (e.g., runs/m10care_...)")):
    """Compute metrics and write report.md + report.html (+ ticks.csv)."""
    run_dir = Path(run_dir)
    if not run_dir.exists():
        raise typer.BadParameter(f"Run directory not found: {run_dir}")

    m = compute_metrics(run_dir)

    # Write artifacts
    (run_dir / "report.md").write_text(build_markdown(m), encoding="utf-8")
    (run_dir / "report.html").write_text(build_html(m), encoding="utf-8")

    # CSV of per-tick rows
    rows = m.get("rows", [])
    if rows:
        csv_path = run_dir / "ticks.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "tick",
                    "drive",
                    "behavior",
                    "action",
                    "novelty",
                    "boredom",
                    "top_sim",
                    "coverage",
                    "symbols",
                ],
            )
            w.writeheader()
            for r in rows:
                w.writerow(r)

    # Console summary
    meta = load_meta(run_dir)
    table = Table(title=f"SOMA Eval — {meta.get('run_id', run_dir.name)}")
    table.add_column("Metric")
    table.add_column("Value")

    nov = m.get("novelty", {})
    mem = m.get("memory", {})
    sym = m.get("symbols", {})
    care = m.get("caregiver", {})
    counts = m.get("counts", {})

    table.add_row("Ticks", str(counts.get("ticks", 0)))
    table.add_row("Novelty mean / p95 / high-rate",
                  f"{nov.get('mean',0.0):.3f} / {nov.get('p95',0.0):.3f} / {100.0*nov.get('high_rate',0.0):.1f}%")
    if counts.get("ticks", 0) > 0:
        table.add_row("Memory helpful ratio",
                      f"{100.0*mem.get('helpful_ratio',0.0):.1f}%  ({mem.get('helpful_recall',0)} / {mem.get('any_recall',0)})")
    table.add_row("Symbol kinds / Simpson / continuity",
                  f"{sym.get('kinds',0)} / {sym.get('simpson',0.0):.3f} / {100.0*sym.get('continuity',0.0):.1f}%")
    table.add_row("Caregiver: tags / rows w/ gloss",
                  f"{care.get('tag_count',0)} / {care.get('rows_with_gloss',0)}")

    console.print(table)
    console.print(f"Wrote: {run_dir / 'report.md'}  and  {run_dir / 'report.html'}" )


if __name__ == "__main__":
    app()