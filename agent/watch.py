"""Polls GitHub and runs the Pipeline Agent on every NEW failed CI run.
Polling means no webhook / tunnel is needed on your laptop.
Usage: python -m agent.watch          (only new failures)
       python -m agent.watch --all    (also analyse existing failed runs)
"""
import argparse
import json
import os
import time

from . import config, github_client
from .pipeline_agent import analyze_run

STATE_FILE = os.path.join(config.DATA_DIR, "processed.json")


def _load():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return None


def _save(ids):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    seen = _load()
    first = seen is None
    seen = seen or set()
    print(f"Watching {config.GITHUB_REPO} every {config.POLL_SECONDS}s ... (Ctrl+C to stop)")
    while True:
        try:
            runs = github_client.list_runs(10)
            for run in runs:
                if run["status"] != "completed" or run["id"] in seen:
                    continue
                seen.add(run["id"])
                if run["conclusion"] == "failure" and (args.all or not first):
                    print(f"\nNew failed run detected: #{run['run_number']}")
                    analyze_run(run)
            first = False
            _save(seen)
        except Exception as e:
            print(f"[watch] error: {e}")
        time.sleep(config.POLL_SECONDS)


if __name__ == "__main__":
    main()
