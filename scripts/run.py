from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import typer

from soma.core.tick import run_loop

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def run(
    ticks: int = typer.Option(50, help="Number of cognitive ticks to run"),
    seed: int = typer.Option(42, help="Deterministic seed"),
    runs_dir: Path = typer.Option(Path("runs"), help="Directory to store run artifacts"),
    env: str = typer.Option("grid-v0", help="Environment to run (e.g., grid-v0)"),
    size: int = typer.Option(9, help="Grid size (must be odd)"),
    n_objects: int = typer.Option(12, help="Number of objects to place"),
    view_radius: int = typer.Option(1, help="Agent view radius"),
):
    """Run the SOMA core loop (M3)."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = runs_dir / f"m3_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=False)
    run_loop(
        ticks=ticks,
        seed=seed,
        run_dir=out_dir,
        run_id=f"m3_{run_id}",
        env_name=env,
        size=size,
        n_objects=n_objects,
        view_radius=view_radius,
    )
    typer.echo(f"Done. See {out_dir}")


if __name__ == "__main__":
    app()