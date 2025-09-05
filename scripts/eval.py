from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple
import json
import statistics as stats
import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _read_jsonl(path: Path) -> List[Dict]:
    out: List[Dict] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    i = max(0, int(round(0.95 * (len(arr) - 1))))
    return float(arr[i])


def _simpson_diversity(counts: Dict[str, int]) -> float:
    N = sum(counts.values())
    if N <= 1:
        return 0.0
    s = 0.0
    for c in counts.values():
        p = c / N
        s += p * p
    return float(1.0 - s)


@app.command()
def eval_run(run_dir: Path = typer.Argument(..., help="Path to runs/<id>")) -> None:
    run_dir = Path(run_dir)
    events = _read_jsonl(run_dir / "events.jsonl")
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8")) if (run_dir / "meta.json").exists() else {}
    tags_path = run_dir / "caregiver_tags.json"
    caregiver_tags = json.loads(tags_path.read_text(encoding="utf-8")) if tags_path.exists() else {}

    # ------ metrics ------
    novs: List[float] = []
    top_sims: List[float] = []
    sym_counts: Dict[str, int] = {}
    sym_sequence: List[List[str]] = []
    self_model_refs = 0
    rows_with_cg_gloss = 0

    for ev in events:
        if ev.get("type") != "tick":
            continue
        cur = ev.get("curiosity", {})
        nov = float(cur.get("novelty", 0.0))
        novs.append(nov)
        rec = ev.get("recall", [])
        if rec:
            top_sims.append(float(rec[0].get("score", 0.0)))
        ch = ev.get("channel", {})
        toks = ch.get("tokens", []) or []
        if toks:
            for t in toks:
                sym_counts[t] = sym_counts.get(t, 0) + 1
        sym_sequence.append(list(toks))
        if ev.get("state"):
            self_model_refs += 1
        if ch.get("caregiver_gloss"):
            rows_with_cg_gloss += 1

    novelty_mean = float(stats.mean(novs)) if novs else 0.0
    novelty_p95 = _p95(novs)
    high_novelty_rate = float(sum(1 for x in novs if x >= 1.0) / len(novs)) if novs else 0.0

    # memory reuse helpful: proportion of recalled ticks with top_sim >= 0.5
    reuse_total = len(top_sims)
    reuse_helpful = sum(1 for s in top_sims if s >= 0.5)
    reuse_ratio = float(reuse_helpful / reuse_total) if reuse_total else 0.0

    # symbolic continuity: fraction of consecutive emissions sharing at least one token
    cont_hits = 0
    cont_pairs = 0
    prev = None
    for toks in sym_sequence:
        if prev is not None:
            if prev or toks:
                cont_pairs += 1
                if set(prev) & set(toks):
                    cont_hits += 1
        prev = toks
    symbolic_continuity = float(cont_hits / cont_pairs) if cont_pairs else 0.0

    simpson = _simpson_diversity(sym_counts)

    report = []
    report.append(f"# SOMA Run Report — {run_dir.name}\n")
    report.append("## Meta\n")
    report.append("```json\n" + json.dumps(meta, indent=2) + "\n````\n")
    report.append("## Summary\n")
    report.append(f"- Ticks: {len(novs)}")
    report.append(f"- Novelty mean: {novelty_mean:.3f} | p95: {novelty_p95:.3f} | high-novelty rate: {high_novelty_rate*100:.2f}%")
    report.append(f"- Memory reuse helpful ratio: {reuse_ratio*100:.2f}% ({reuse_helpful} / {reuse_total})")
    report.append(f"- Symbol kinds: {len(sym_counts)} | Simpson diversity: {simpson:.3f}")
    report.append(f"- Self-model references: {self_model_refs} ({(self_model_refs/len(novs))*100:.2f}% of ticks)")
    report.append(f"- Symbolic continuity: {cont_hits}/{cont_pairs} ({symbolic_continuity*100:.2f}%)")
    report.append(f"- Caregiver tags present: {'yes' if caregiver_tags else 'no'} | rows with caregiver gloss: {rows_with_cg_gloss}")

    if sym_counts:
        report.append("\n## Symbols\n\nToken | Count\n---|---")
        for t, c in sorted(sym_counts.items(), key=lambda kv: kv[1], reverse=True):
            report.append(f"{t} | {c}")

    # write
    out_md = run_dir / "report.md"
    out_md.write_text("\n".join(report) + "\n", encoding="utf-8")
    typer.echo(f"Wrote {out_md}")


if __name__ == "__main__":
    app()