"""Reads the agents' audit logs (data/*.jsonl) and turns them into tables for the dashboard."""
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("AGENTIC_DATA", ROOT / "data"))


def load_jsonl(name):
    p = DATA / name
    rows = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def ci_table():
    cols = ["time", "test", "file", "line", "root_cause", "fix", "confidence", "analysed_by", "seconds_to_diagnose", "run"]
    rows = []
    for r in load_jsonl("incidents.jsonl"):
        a = r.get("analysis") or {}
        rows.append({"time": r.get("time"), "test": a.get("failing_test"), "file": a.get("file"), "line": a.get("line"),
                     "root_cause": a.get("root_cause"), "fix": a.get("suggested_fix"), "confidence": a.get("confidence"),
                     "analysed_by": r.get("source"), "seconds_to_diagnose": r.get("seconds_to_diagnose"), "run": r.get("run_url")})
    return pd.DataFrame(rows, columns=cols)


def deploy_table():
    cols = ["time", "tag", "bug", "outcome", "detect_seconds", "recover_seconds", "diagnosis", "analysed_by"]
    rows = []
    for r in load_jsonl("deployments.jsonl"):
        rows.append({**{c: r.get(c) for c in cols}, "diagnosis": (r.get("diagnosis") or {}).get("diagnosis")})
    return pd.DataFrame(rows, columns=cols)


def monitor_table():
    cols = ["time", "anomaly", "action", "outcome", "mttr_seconds", "explanation", "analysed_by"]
    rows = []
    for r in load_jsonl("monitoring_incidents.jsonl"):
        rows.append({**{c: r.get(c) for c in cols}, "explanation": (r.get("explanation") or {}).get("explanation")})
    return pd.DataFrame(rows, columns=cols)


def timeline():
    rows = []
    for _, r in ci_table().iterrows():
        rows.append({"time": r["time"], "agent": "Pipeline", "event": f"CI failure: {r['test']}", "detail": r["root_cause"]})
    for _, r in deploy_table().iterrows():
        rows.append({"time": r["time"], "agent": "Deployment", "event": f"release {r['tag']} (bug={r['bug']}) -> {r['outcome']}", "detail": r["diagnosis"]})
    for _, r in monitor_table().iterrows():
        rows.append({"time": r["time"], "agent": "Monitoring", "event": f"{r['anomaly']} -> {r['action']} -> {r['outcome']}", "detail": r["explanation"]})
    df = pd.DataFrame(rows, columns=["time", "agent", "event", "detail"])
    return df.sort_values("time", ascending=False) if len(df) else df
