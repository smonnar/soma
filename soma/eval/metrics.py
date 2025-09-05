from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
from statistics import mean
from collections import Counter

Number = float

# ---------- Loading ----------

def load_meta(run_dir: Path) -> Dict[str, Any]:
    meta_path = Path(run_dir) / "meta.json"
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_events(run_dir: Path) -> List[Dict[str, Any]]:
    ev_path = Path(run_dir) / "events.jsonl"
    out: List[Dict[str, Any]] = []
    if not ev_path.exists():
        return out
    with ev_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # tolerate partial/corrupt lines
                continue
    return out


# ---------- Helpers ----------

def p95(xs: List[Number]) -> Number:
    if not xs:
        return 0.0
    s = sorted(xs)
    if not s:
        return 0.0
    # Clamp index to valid range
    idx = max(0, min(len(s) - 1, int(round(0.95 * (len(s) - 1)))))
    return float(s[idx])


def top_sim(e: Dict[str, Any]) -> Number:
    rec = e.get("recall", []) or []
    if not isinstance(rec, list) or not rec:
        return 0.0
    try:
        m = max(float(item.get("score", 0.0)) for item in rec if isinstance(item, dict))
    except Exception:
        m = 0.0
    return m


def novelty_of(e: Dict[str, Any]) -> Number:
    try:
        return float(e.get("curiosity", {}).get("novelty", 0.0))
    except Exception:
        return 0.0


def boredom_of(e: Dict[str, Any]) -> Number:
    try:
        return float(e.get("staleness", {}).get("boredom", 0.0))
    except Exception:
        return 0.0


def drive_of(e: Dict[str, Any]) -> str:
    return str(e.get("motivation", {}).get("dominant", ""))


def behavior_of(e: Dict[str, Any]) -> str:
    return str(e.get("planner", {}).get("behavior", ""))


def action_of(e: Dict[str, Any]) -> str:
    return str(e.get("action_final", ""))


def coverage_of(e: Dict[str, Any]) -> Number:
    try:
        return float(e.get("state", {}).get("coverage", 0.0))
    except Exception:
        return 0.0


def channel_tokens(e: Dict[str, Any]) -> List[str]:
    toks = e.get("channel", {}).get("tokens", [])
    if isinstance(toks, list):
        return [str(t) for t in toks]
    return []


def channel_pairs(e: Dict[str, Any]) -> List[Tuple[str, str]]:
    pairs = e.get("channel", {}).get("caregiver_gloss", [])
    if isinstance(pairs, list):
        out: List[Tuple[str, str]] = []
        for p in pairs:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                out.append((str(p[0]), str(p[1])))
        return out
    return []


# ---------- Metric computation ----------

def compute_metrics(run_dir: Path) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    meta = load_meta(run_dir)
    events = load_events(run_dir)
    ticks = [e for e in events if e.get("type") == "tick"]
    notes = [e for e in events if e.get("type") == "note"]

    # Series
    nov = [novelty_of(e) for e in ticks]
    brd = [boredom_of(e) for e in ticks]
    drv = [drive_of(e) for e in ticks]
    beh = [behavior_of(e) for e in ticks]
    act = [action_of(e) for e in ticks]
    top = [top_sim(e) for e in ticks]
    cov = [coverage_of(e) for e in ticks]
    tok_lists = [channel_tokens(e) for e in ticks]

    # Novelty stats
    novelty_mean = float(mean(nov)) if nov else 0.0
    novelty_p95 = p95(nov)
    high_novelty_rate = (sum(1 for x in nov if x >= 0.8) / len(nov)) if nov else 0.0

    # Memory reuse helpfulness (top recall >= 0.5 among ticks with any recall)
    any_recall = [x for x in top if x > 0.0]
    helpful = sum(1 for x in top if x >= 0.5)
    memory_reuse_ratio = (helpful / len(any_recall)) if any_recall else 0.0

    # Symbols
    flat_tokens: List[str] = []
    for toks in tok_lists:
        flat_tokens.extend(toks)
    token_counts = Counter(flat_tokens)
    symbol_kinds = len(token_counts)
    symbol_rows = sum(1 for toks in tok_lists if toks)
    def simpson_diversity(counts: Counter) -> float:
        N = sum(counts.values())
        if N <= 1:
            return 0.0
        return 1.0 - sum((c / N) ** 2 for c in counts.values())
    simpson = simpson_diversity(token_counts)

    # Symbolic continuity (within run): proportion of emissions that repeat a previously seen emission
    emissions = [" ".join(toks) for toks in tok_lists if toks]
    if emissions:
        seen: set[str] = set()
        repeats = 0
        for s in emissions:
            if s in seen:
                repeats += 1
            else:
                seen.add(s)
        continuity = repeats / len(emissions)
    else:
        continuity = 0.0

    # Caregiver tags
    try:
        caregiver_tags = json.loads((run_dir / "caregiver_tags.json").read_text(encoding="utf-8"))
    except Exception:
        caregiver_tags = {}
    rows_with_caregiver = sum(1 for e in ticks if channel_pairs(e))

    # Self-model references in notes (notes that include drive/novelty/boredom keys)
    def is_self_model(n: Dict[str, Any]) -> bool:
        p = n.get("payload", {}) if isinstance(n, dict) else {}
        if not isinstance(p, dict):
            return False
        keys = set(p.keys())
        return bool(keys & {"dominant", "drives", "novelty", "boredom", "coverage"})
    self_model_refs = sum(1 for n in notes if is_self_model(n))

    # Pack per-tick table (for CSV/HTML table)
    rows: List[Dict[str, Any]] = []
    for i, e in enumerate(ticks):
        t = int(e.get("tick", i))
        rows.append(
            {
                "tick": t,
                "drive": drive_of(e),
                "behavior": behavior_of(e),
                "action": action_of(e),
                "novelty": round(nov[i], 6) if i < len(nov) else 0.0,
                "boredom": round(brd[i], 6) if i < len(brd) else 0.0,
                "top_sim": round(top[i], 6) if i < len(top) else 0.0,
                "coverage": round(cov[i], 6) if i < len(cov) else 0.0,
                "symbols": " ".join(tok_lists[i]) if i < len(tok_lists) and tok_lists[i] else "-",
            }
        )

    return {
        "meta": meta,
        "counts": {
            "ticks": len(ticks),
            "notes": len(notes),
            "symbol_rows": symbol_rows,
        },
        "novelty": {
            "mean": novelty_mean,
            "p95": float(novelty_p95),
            "high_rate": float(high_novelty_rate),
        },
        "memory": {
            "any_recall": len(any_recall),
            "helpful_recall": helpful,
            "helpful_ratio": float(memory_reuse_ratio),
        },
        "symbols": {
            "kinds": symbol_kinds,
            "counts": dict(token_counts),
            "simpson": float(simpson),
            "continuity": float(continuity),
        },
        "caregiver": {
            "has_tags": bool(caregiver_tags),
            "tag_count": len(caregiver_tags),
            "rows_with_gloss": rows_with_caregiver,
        },
        "timeseries": {
            "novelty": nov,
            "boredom": brd,
            "drive": drv,
            "behavior": beh,
            "action": act,
            "top_sim": top,
            "coverage": cov,
            "symbols": [" ".join(toks) if toks else "-" for toks in tok_lists],
        },
        "rows": rows,
    }