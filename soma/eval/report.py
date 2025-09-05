from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json


def _fmt_pct(x: float) -> str:
    return f"{100.0 * x:.2f}%"


def build_markdown(metrics: Dict[str, Any]) -> str:
    m = metrics
    meta = m.get("meta", {})
    sym = m.get("symbols", {})
    mem = m.get("memory", {})
    nov = m.get("novelty", {})
    care = m.get("caregiver", {})
    counts = m.get("counts", {})

    # Symbols table
    sym_table = "Token | Count\n---|---\n"
    for k, v in sorted((sym.get("counts") or {}).items(), key=lambda kv: (-kv[1], kv[0])):
        sym_table += f"{k} | {v}\n"
    if sym_table.strip().endswith("---|---"):
        sym_table += "- | -\n"

    md = [
        f"# SOMA Run Report — {meta.get('run_id','(unknown)')}",
        "\n## Meta\n",
        "```json\n" + json.dumps(meta, indent=2) + "\n```\n",
        "## Summary\n",
        f"- Ticks: {counts.get('ticks',0)}",
        f"- Novelty mean: {nov.get('mean',0.0):.3f} | p95: {nov.get('p95',0.0):.3f} | high-novelty rate: {_fmt_pct(nov.get('high_rate',0.0))}",
        f"- Memory reuse helpful ratio: {_fmt_pct(mem.get('helpful_ratio',0.0))} ({mem.get('helpful_recall',0)} / {mem.get('any_recall',0)})",
        f"- Symbol kinds: {sym.get('kinds',0)} | Simpson diversity: {sym.get('simpson',0.0):.3f}",
        f"- Self-model references: {len(m.get('timeseries',{}).get('drive',[]))} ({_fmt_pct(1.0) if (len(m.get('timeseries',{}).get('drive',[]))>0) else _fmt_pct(0.0)})",
        f"- Symbolic continuity: repeat {int(sym.get('continuity',0.0)*max(1, (metrics.get('counts',{}).get('symbol_rows',0))))}/{metrics.get('counts',{}).get('symbol_rows',0)} ({_fmt_pct(sym.get('continuity',0.0))})",
        f"- Caregiver tags present: {'yes' if care.get('has_tags') else 'no'} | rows with caregiver gloss: {care.get('rows_with_gloss',0)} / {metrics.get('counts',{}).get('symbol_rows',0)} ({_fmt_pct((care.get('rows_with_gloss',0) / max(1, metrics.get('counts',{}).get('symbol_rows',0))))})",
        "\n## Symbols\n\n" + sym_table,
    ]

    # Add a short per-tick preview (first 20 rows)
    rows = m.get("rows", [])
    if rows:
        preview = rows[:20]
        md.append("## Preview (first 20 ticks)\n")
        md.append("Tick | Drive | Behavior | Act | Bored | Novelty | TopSim | Cover | Sym\n---|---|---|---|---|---|---|---|---")
        for r in preview:
            md.append(
                f"{r['tick']} | {r['drive']} | {r['behavior']} | {r['action']} | "
                f"{r['boredom']:.2f} | {r['novelty']:.2f} | {r['top_sim']:.2f} | {r['coverage']:.2f} | {r['symbols']}"
            )

    return "\n".join(md) + "\n"


def build_html(metrics: Dict[str, Any]) -> str:
    """Very small self-contained HTML report (no external deps)."""
    m = metrics
    md = build_markdown(metrics)
    # simple <pre> wrapper; markdown not rendered but easy to view in browser
    return f"""
<!doctype html>
<html lang=\"en\"><head>
<meta charset=\"utf-8\" />
<title>SOMA Report — {m.get('meta',{}).get('run_id','')}</title>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<style>
body{{font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 1.5rem;}}
pre{{white-space: pre-wrap; background:#fafafa; padding:1rem; border:1px solid #eee; border-radius:8px;}}
code{{font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;}}
</style>
</head><body>
<h1>SOMA Run Report — {m.get('meta',{}).get('run_id','')}</h1>
<pre>{md}</pre>
</body></html>
"""