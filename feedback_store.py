import json, time, os
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
FEEDBACK_LOG = DATA_DIR / "feedback.jsonl"
STATS_FILE = DATA_DIR / "feedback_stats.json"

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows

def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def record_feedback(event: Dict[str, Any]) -> None:
    """Append a feedback event to JSONL and update stats."""
    event = dict(event)
    event.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    update_stats_with_event(event)

def load_stats() -> Dict[str, Any]:
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"tip_stats": {}, "global": {"n": 0}}

def update_stats_with_event(event: Dict[str, Any]) -> None:
    stats = load_stats()
    tip_stats = stats.setdefault("tip_stats", {})
    reward = float(event.get("reward", 0.0))
    checks = event.get("checks", [])
    seen = set()
    for rec in checks:
        tip = rec.get("Tip_norm") or rec.get("Tip") or rec.get("tip")
        if not tip or tip in seen:
            continue
        seen.add(tip)
        s = tip_stats.setdefault(tip, {"n": 0, "mean_reward": 0.0})
        n = s["n"] + 1
        mean = s["mean_reward"] + (reward - s["mean_reward"]) / n
        s["n"], s["mean_reward"] = n, mean
    stats["global"]["n"] = stats.get("global", {}).get("n", 0) + 1
    _write_json(STATS_FILE, stats)

def get_tip_weights(alpha: float = 1.0) -> Dict[str, float]:
    """Return a weight per Tip_norm where positive reward => boost priority."""
    stats = load_stats()
    weights = {}
    for tip, s in stats.get("tip_stats", {}).items():
        n = s.get("n", 0)
        mean = s.get("mean_reward", 0.0)
        shrink = min(1.0, n / 10.0)  # after 10+ samples, near full weight
        weights[tip] = alpha * shrink * mean
    return weights

def apply_weights_to_checklist(df: pd.DataFrame, alpha: float = 1.0) -> pd.DataFrame:
    """Adjust ordering using learned weights; higher weight => earlier in list."""
    df = df.copy()
    weights = get_tip_weights(alpha=alpha)
    tip_col = None
    for c in ["Tip_norm", "tip_norm", "Tip"]:
        if c in df.columns:
            tip_col = c
            break
    if tip_col is None:
        return df
    df["__weight__"] = df[tip_col].map(weights).fillna(0.0)
    if "Prioriteit" in df.columns:
        try:
            pr = pd.to_numeric(df["Prioriteit"], errors="coerce").fillna(9999)
        except Exception:
            pr = 9999
        df["__sortkey__"] = pr - df["__weight__"]
        df = df.sort_values(["__sortkey__"], ascending=[True])
    else:
        df = df.sort_values(["__weight__"], ascending=[False])
    return df.drop(columns=[c for c in ["__weight__", "__sortkey__"] if c in df.columns])