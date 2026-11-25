"""Builds the final results: agent vs manual (MTTR / diagnosis time) and RCA accuracy.
  python -m eval.summarize           -> eval/results/results.md, results.csv, mttr_chart.png
  python -m eval.summarize --max-diagnose 600
"""
import argparse
import csv
import statistics as st

from .common import ROOT, load_jsonl
from .rca_accuracy import compute

OUT = ROOT / "eval" / "results"


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "mean": round(st.mean(vals), 1), "min": round(min(vals), 1), "max": round(max(vals), 1)}


def collect(max_diagnose):
    dep = load_jsonl("deployments.jsonl")
    mon = load_jsonl("monitoring_incidents.jsonl")
    ci = load_jsonl("incidents.jsonl")
    man = load_jsonl("manual_baseline.jsonl")
    agent = {
        "Faulty release (crash): detect + rollback": [round((d["detect_seconds"] or 0) + d["recover_seconds"], 1) for d in dep
                                                       if d.get("bug") == "crash" and d.get("outcome") == "rolled_back" and d.get("recover_seconds") is not None],
        "Service down: detect + restart": [m["mttr_seconds"] for m in mon if m.get("anomaly") == "service_down" and m.get("outcome") == "recovered"],
        "Memory leak: detect + recover": [m["mttr_seconds"] for m in mon if m.get("anomaly") == "memory_leak" and m.get("outcome") == "recovered"],
        "CI failure: time to root cause": [c["seconds_to_diagnose"] for c in ci if str(c.get("source")) == "llm"
                                           and c.get("seconds_to_diagnose") is not None and c["seconds_to_diagnose"] <= max_diagnose],
    }
    key = {"Faulty release (crash): detect + rollback": "crash", "Service down: detect + restart": "service_down",
           "CI failure: time to root cause": "ci_failure"}
    manual = {name: [m["seconds"] for m in man if m["scenario"] == k] for name, k in key.items()}
    return agent, manual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-diagnose", type=int, default=600, help="ignore CI diagnoses slower than this (agent started late)")
    a = ap.parse_args()
    agent, manual = collect(a.max_diagnose)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in agent:
        sa, sm = stats(agent[name]), stats(manual.get(name, []))
        imp = round((sm["mean"] - sa["mean"]) / sm["mean"] * 100) if sa and sm and sm["mean"] else None
        rows.append({"scenario": name, "agent_n": sa["n"] if sa else 0, "agent_mean_s": sa["mean"] if sa else "", "agent_min_s": sa["min"] if sa else "",
                     "agent_max_s": sa["max"] if sa else "", "manual_n": sm["n"] if sm else 0, "manual_mean_s": sm["mean"] if sm else "",
                     "improvement_pct": imp if imp is not None else ""})
    with open(OUT / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    rca = compute()
    md = ["# Evaluation results", "", "## Recovery / diagnosis time (seconds)", "",
          "| Scenario | Agent runs | Agent mean | Agent min-max | Manual runs | Manual mean | Improvement |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        rng = f"{r['agent_min_s']}-{r['agent_max_s']}" if r["agent_n"] else "-"
        md.append(f"| {r['scenario']} | {r['agent_n']} | {r['agent_mean_s'] or '-'} | {rng} | {r['manual_n']} | {r['manual_mean_s'] or '-'} | "
                  f"{str(r['improvement_pct']) + '%' if r['improvement_pct'] != '' else '-'} |")
    md += ["", "## Root cause analysis accuracy (Pipeline Agent)", ""]
    if rca["accuracy"] is None:
        md.append("No analysed injected bugs yet.")
    else:
        md += [f"Accuracy: **{rca['accuracy']:.0f}%** ({sum(x['correct'] for x in rca['rows'])} correct of {rca['analysed']} analysed; {rca['total']} bugs injected)", "",
               "| Bug | Test found | File found | Correct | Analysed by |", "|---|---|---|---|---|"]
        md += [f"| {x['bug']} | {x['test_ok']} | {x['file_ok']} | {x['correct']} | {x['by']} |" for x in rca["rows"]]
    md += ["", "Notes: manual times come from a person who is actively watching; the sample is small (few runs per scenario)."]
    (OUT / "results.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        both = [r for r in rows if r["agent_n"] and r["manual_n"]]
        if both:
            import numpy as np
            x = np.arange(len(both)); fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(x - 0.2, [r["manual_mean_s"] for r in both], 0.4, label="Manual", color="#C8434F")
            ax.bar(x + 0.2, [r["agent_mean_s"] for r in both], 0.4, label="Agent", color="#2E8B57")
            ax.set_xticks(x); ax.set_xticklabels([r["scenario"].split(":")[0] for r in both], fontsize=8); ax.set_ylabel("Seconds (mean)")
            ax.set_title("Manual vs agent-assisted"); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "mttr_chart.png", dpi=170)
            print(f"\nChart saved: {OUT / 'mttr_chart.png'}")
        else:
            print("\n(Chart needs at least one scenario with both agent and manual runs.)")
    except ImportError:
        print("\n(Install matplotlib for the chart: python -m pip install matplotlib)")
    print(f"Files saved in {OUT}")


if __name__ == "__main__":
    main()
